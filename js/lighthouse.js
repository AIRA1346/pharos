/**
 * Pharos — 등대(Lighthouse): 랜딩 → 항해 서약 → 분야 → 조건 → 결과 카드, 잠금·리롤(모의 광고).
 *
 * 잠금 상태는 localStorage(pharos_lighthouse_state_v1)에 남고, 목표 데이터는
 * data/lighthouse-quests.json 을 지연 로딩한다.
 */

import * as engine from './engine.js';
import { t, getLang } from './i18n.js';
import { $, LS, esc, iconHtml, locale, num, readStore, recordById, state, writeStore } from './state.js';
import { showDetail } from './detail.js';
import { syncUrl, toast } from './app.js';

const LH_TIERS = [1, 2, 3];

const LH_DIFFICULTIES = ['all', 'chill', 'normal', 'hardcore'];

const LH_CATEGORIES = ['game', 'anime', 'movie', 'manga', 'all'];

const LH_MEDIA = ['anime', 'movie', 'manga'];

/** 서약·분야 화면의 단계 표식 — 조건 단계(1~3)와 숫자를 섞지 않으려고 문자열로 둔다. */
export const LH_PLEDGE = 'pledge';

export const LH_CATEGORY = 'category';

const lhText = (row, field) =>
  String((getLang() === 'en' ? row?.[`${field}_en`] : row?.[`${field}_ko`]) ?? '');

const lhCategoryMeta = (id) => (state.lh.data?.categories || []).find((row) => row.id === id) || null;

/** 분야의 진행 흐름 — 게임만 플랫폼·가격을 묻고, 나머지는 분량/시간부터 시작한다. */
function lhFlow() {
  return state.lh.filters.category === 'game' ? ['platform', 'time', 'difficulty'] : ['time', 'difficulty'];
}

const lhStepTotal = () => lhFlow().length;

/** 단계 문구는 분야마다 다르다 — 분야를 고르기 전(전체 랜덤 포함)에는 중립 문구를 쓴다. */
function lhTierMeta(tier) {
  const key = LH_MEDIA.includes(state.lh.filters.category) || state.lh.filters.category === 'game'
    ? state.lh.filters.category
    : 'all';
  const rows = state.lh.data?.tiers?.[key] || state.lh.data?.tiers?.all || [];
  return rows.find((row) => row.tier === Number(tier)) || null;
}

/** 추첨 단위는 작품이 아니라 퀘스트 — 분야별 데이터를 같은 모양으로 편다. */
function lhEntries(category = 'all') {
  const data = state.lh.data;
  if (!data) return [];
  const out = [];
  if (category === 'all' || category === 'game') {
    for (const game of data.games || []) {
      out.push({
        id: game.game_id,
        category: 'game',
        free_to_play: !!game.free_to_play,
        platforms: game.platforms || [],
        quests: game.quests || [],
      });
    }
  }
  for (const key of LH_MEDIA) {
    if (category !== 'all' && category !== key) continue;
    for (const row of data.media?.[key] || []) {
      out.push({ id: row.item_id, category: key, free_to_play: null, platforms: [], quests: row.quests || [] });
    }
  }
  return out;
}

const lhEntryById = (id) => lhEntries('all').find((entry) => entry.id === id) || null;

/** 목표는 (작품, 단계, 난이도)로 특정된다 — 같은 작품이 같은 단계에 다른 난이도의 목표를 가질 수 있다. */
const lhQuestOf = (entry, tier, difficulty) =>
  (entry?.quests || []).find((quest) => quest.tier === Number(tier) && quest.difficulty === difficulty) || null;

function lhLoadState() {
  const raw = readStore(LS.lighthouse, null);
  if (!raw || typeof raw !== 'object') return;
  const filters = raw.filters || {};
  if (LH_CATEGORIES.includes(filters.category)) state.lh.filters.category = filters.category;
  if (filters.price === 'free' || filters.price === 'all') state.lh.filters.price = filters.price;
  if (['pc', 'mobile', 'all'].includes(filters.platform)) state.lh.filters.platform = filters.platform;
  if (LH_TIERS.includes(Number(filters.tier))) state.lh.filters.tier = Number(filters.tier);
  if (LH_DIFFICULTIES.includes(filters.difficulty)) state.lh.filters.difficulty = filters.difficulty;
  if (Array.isArray(raw.history)) {
    state.lh.history = raw.history
      .filter((row) => row && typeof (row.item_id || row.game_id) === 'string')
      .map((row) => ({
        item_id: row.item_id || row.game_id,
        category: LH_CATEGORIES.includes(row.category) && row.category !== 'all' ? row.category : 'game',
        tier: Number(row.tier) || null,
        difficulty: LH_DIFFICULTIES.includes(row.difficulty) ? row.difficulty : null,
        title_ko: row.title_ko || '',
        title_en: row.title_en || '',
        completed_at: row.completed_at || null,
      }))
      .slice(-100);
  }
  if (Number.isFinite(Number(raw.skips))) state.lh.skips = Math.max(0, Number(raw.skips));
  const last = typeof raw.last_item_id === 'string' ? raw.last_item_id : raw.last_game_id;
  if (typeof last === 'string') state.lh.lastItemId = last;
  const current = raw.current;
  const currentId = typeof current?.item_id === 'string'
    ? current.item_id
    : typeof current?.game_id === 'string'
      ? current.game_id
      : null;
  if (currentId && LH_TIERS.includes(Number(current.tier))) {
    state.lh.current = {
      item_id: currentId,
      category: LH_CATEGORIES.includes(current.category) && current.category !== 'all' ? current.category : 'game',
      tier: Number(current.tier),
      difficulty: LH_DIFFICULTIES.includes(current.difficulty) ? current.difficulty : null,
      issued_at: current.issued_at || null,
      filters: {
        category: LH_CATEGORIES.includes(current.filters?.category) ? current.filters.category : null,
        price: current.filters?.price === 'free' ? 'free' : 'all',
        platform: ['pc', 'mobile'].includes(current.filters?.platform) ? current.filters.platform : 'all',
        tier: LH_TIERS.includes(Number(current.filters?.tier)) ? Number(current.filters.tier) : Number(current.tier),
        difficulty: LH_DIFFICULTIES.includes(current.filters?.difficulty) ? current.filters.difficulty : 'all',
      },
    };
    state.lh.filters = { ...state.lh.filters, ...state.lh.current.filters };
  }
}

function lhSaveState() {
  writeStore(LS.lighthouse, {
    version: 3,
    filters: state.lh.filters,
    current: state.lh.current,
    history: state.lh.history,
    skips: state.lh.skips,
    last_item_id: state.lh.lastItemId,
  });
}

export async function loadLighthouse() {
  try {
    const res = await fetch('./data/lighthouse-quests.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    if (!Array.isArray(data.games) || !data.games.length) throw new Error('empty');
    state.lh.data = data;
    lhLoadState();
    lhPruneCurrent();
  } catch (err) {
    state.lh.data = null;
    state.lh.loadError = err?.message || String(err);
  }
}

/** 저장된 목표가 데이터에서 사라졌으면 잠금을 풀어 준다(데이터 개편 대비). */
function lhPruneCurrent() {
  const current = state.lh.current;
  if (!current) return;
  const entry = lhEntryById(current.item_id);
  if (!entry || !lhQuestOf(entry, current.tier, current.difficulty)) {
    state.lh.current = null;
    lhSaveState();
  }
}

/** 위저드 단계 — 진행 중인 목표가 있으면 언제나 4(결과 카드).
 *  0 랜딩 · 'pledge' 항해 서약 · 'category' 분야 선택 · 1~3 조건(분야별 2~3단계) · 4 결과 */
function lhStep() {
  if (state.lh.current) return 4;
  if (state.lh.step === LH_PLEDGE) return LH_PLEDGE;
  if (state.lh.step === LH_CATEGORY) return LH_CATEGORY;
  const step = Number(state.lh.step);
  if (!Number.isInteger(step) || step < 0 || step > lhStepTotal()) return 0;
  if (step >= 1 && !state.lh.filters.category) return LH_CATEGORY;
  return step;
}

/** 현재 조건(분야·플랫폼·가격·단계·난이도)에 맞는 후보 목표. 추첨 단위는 작품이 아니라 퀘스트다. */
function lhPoolQuests() {
  const { category, price, platform, tier, difficulty } = state.lh.filters;
  const pool = [];
  for (const entry of lhEntries(category || 'all')) {
    if (category === 'game') {
      if (price === 'free' && !entry.free_to_play) continue;
      if (platform !== 'all' && !(entry.platforms || []).includes(platform)) continue;
    }
    for (const quest of entry.quests) {
      if (quest.tier !== Number(tier)) continue;
      if (difficulty !== 'all' && quest.difficulty !== difficulty) continue;
      pool.push({ entry, quest });
    }
  }
  return pool;
}

export function lhSetStep(step) {
  if (state.lh.current) return;
  if (step === LH_PLEDGE) {
    state.lh.step = LH_PLEDGE;
    // 서약은 매번 새로 — 체크는 저장하지 않고, 화면에 들어올 때 늘 비어 있다.
    state.lh.pledgeAccepted = false;
  } else if (step === LH_CATEGORY) {
    state.lh.step = LH_CATEGORY;
  } else {
    state.lh.step = Math.max(0, Math.min(lhStepTotal(), Number(step) || 0));
  }
  renderLighthouse();
  document.querySelector('.lh-pledge-title, .lh-cat-title, .lh-q')?.focus?.({ preventScroll: true });
}

export function lhPick(group, value) {
  if (state.lh.current) return;
  if (group === 'category') {
    // 분야 카드를 고르면 바로 첫 조건 화면으로 — 흐름이 분야마다 다르기 때문이다.
    if (!LH_CATEGORIES.includes(value)) return;
    state.lh.filters.category = value;
    state.lh.step = 1;
  } else if (group === 'tier') {
    const tier = Number(value);
    if (LH_TIERS.includes(tier)) state.lh.filters.tier = tier;
  } else if (group === 'platform' && ['all', 'pc', 'mobile'].includes(value)) {
    state.lh.filters.platform = value;
  } else if (group === 'price' && ['all', 'free'].includes(value)) {
    state.lh.filters.price = value;
  } else if (group === 'difficulty' && LH_DIFFICULTIES.includes(value)) {
    state.lh.filters.difficulty = value;
  } else {
    return;
  }
  lhSaveState();
  syncUrl('replace');
  renderLighthouse();
}

export function lhDraw() {
  if (!state.lh.data) {
    toast(t('lh.toast.noData'));
    return;
  }
  if (state.lh.current) return;
  let pool = lhPoolQuests();
  if (!pool.length) {
    toast(t('lh.toast.noMatch'));
    return;
  }
  if (pool.length > 1 && state.lh.lastItemId) {
    const fresh = pool.filter((row) => row.entry.id !== state.lh.lastItemId);
    if (fresh.length) pool = fresh;
  }
  const { entry, quest } = pool[Math.floor(Math.random() * pool.length)];
  state.lh.current = {
    item_id: entry.id,
    category: entry.category,
    tier: quest.tier,
    difficulty: quest.difficulty,
    issued_at: new Date().toISOString(),
    filters: { ...state.lh.filters },
  };
  state.lh.lastItemId = entry.id;
  state.lh.step = lhStepTotal() + 1;
  lhSaveState();
  syncUrl('replace');
  renderLighthouse();
  toast(t('lh.toast.drawn'), lhText(quest, 'title'));
}

export function lhComplete() {
  const current = state.lh.current;
  if (!current) return;
  const entry = lhEntryById(current.item_id);
  const quest = lhQuestOf(entry, current.tier, current.difficulty);
  if (!entry || !quest) {
    state.lh.current = null;
    lhSaveState();
    renderLighthouse();
    return;
  }
  state.lh.history.push({
    item_id: entry.id,
    category: entry.category,
    tier: current.tier,
    difficulty: quest.difficulty,
    title_ko: quest.title_ko,
    title_en: quest.title_en,
    completed_at: new Date().toISOString(),
  });
  state.lh.history = state.lh.history.slice(-100);
  state.lh.current = null;
  state.lh.step = 0;
  lhSaveState();
  renderLighthouse();
  toast(t('lh.toast.completed', { name: recordById(entry.id)?.name || entry.id }), lhText(quest, 'title'));
}

export function lhSkipComplete() {
  if (!state.lh.current) return;
  state.lh.skips += 1;
  state.lh.current = null;
  state.lh.step = 0;
  lhSaveState();
  lhCloseAd();
  renderLighthouse();
  toast(t('lh.toast.skipped'));
}

let lhAdTimer = null;

export function lhOpenAd() {
  if (!state.lh.current) return;
  const backdrop = $('lhAdBackdrop');
  if (!backdrop) return;
  backdrop.hidden = false;
  document.body.style.overflow = 'hidden';
  const btn = $('lhAdSkip');
  const count = $('lhAdCount');
  let left = 5;
  if (count) count.textContent = String(left);
  if (btn) {
    btn.disabled = true;
    btn.textContent = t('lh.ad.wait', { n: left });
  }
  clearInterval(lhAdTimer);
  lhAdTimer = setInterval(() => {
    left -= 1;
    if (count) count.textContent = String(Math.max(0, left));
    if (left > 0) {
      if (btn) btn.textContent = t('lh.ad.wait', { n: left });
      return;
    }
    clearInterval(lhAdTimer);
    lhAdTimer = null;
    if (btn) {
      btn.disabled = false;
      btn.textContent = t('lh.ad.ready');
    }
    if (count) count.textContent = '0';
  }, 1000);
  $('lhAdModal')?.focus({ preventScroll: true });
}

export function lhCloseAd() {
  clearInterval(lhAdTimer);
  lhAdTimer = null;
  const backdrop = $('lhAdBackdrop');
  if (backdrop) backdrop.hidden = true;
  document.body.style.overflow = '';
}

function lhChoiceButton({ group, value, label, sub, hint, active }) {
  return `<button type="button" class="lh-choice${active ? ' is-on' : ''}" role="radio" aria-checked="${active ? 'true' : 'false'}" data-lh-pick="${group}" data-lh-value="${esc(value)}">
      <span class="lh-choice-label">${esc(label)}</span>
      ${sub ? `<span class="lh-choice-sub">${esc(sub)}</span>` : ''}
      ${hint ? `<span class="lh-choice-hint">${esc(hint)}</span>` : ''}
    </button>`;
}

/** 결과 카드의 분야 배지 — 🎮 게임 / 📺 애니 / 🎬 영화 / 📖 만화 */
function lhCategoryBadge(category) {
  const meta = lhCategoryMeta(category);
  return `<span class="lh-cat-badge lh-cat-badge--${esc(category)}">${esc(lhText(meta, 'badge') || category)}</span>`;
}

/** 미디어 작품의 상태 칩 — 완결작인지 연재·방영 중인지 (게임은 무료/유료 칩을 쓴다). */
function lhMediaStatusChip(rec) {
  const status = rec?.maintenance_status;
  if (status === 'feature_complete') return t('lh.badge.complete');
  if (status === 'active') return t('lh.badge.ongoing');
  return t('lh.badge.unknown');
}

function lhQuestHtml(entry, quest) {
  if (!quest) return '';
  const meta = lhTierMeta(quest.tier);
  return `
    <div class="lh-quest" data-lh-tier-view="${quest.tier}" data-lh-difficulty-view="${esc(quest.difficulty)}">
      <p class="lh-quest-kicker"><span class="lh-tier-badge">${esc(lhText(meta, 'label'))}</span><span>${esc(lhText(meta, 'window'))}</span><span class="lh-diff lh-diff--${esc(quest.difficulty)}">${esc(t(`lh.diff.${quest.difficulty}`))}</span><span>${esc(t('lh.questKicker'))}</span></p>
      <h2 class="lh-quest-title">${esc(lhText(quest, 'title'))}</h2>
      <p class="lh-quest-desc">${esc(lhText(quest, 'desc'))}</p>
      <p class="lh-quest-tip"><b>${esc(t('lh.tipLabel'))}</b> ${esc(lhText(quest, 'tip'))}</p>
      <p class="lh-quest-time"><span aria-hidden="true">⏱</span> ${esc(t('lh.estLabel'))} <b>${esc(lhText(quest, 'est_time'))}</b></p>
    </div>`;
}

function lhStepper(step) {
  const total = lhStepTotal();
  return `
    <div class="lh-stepper">
      <span class="lh-progress" aria-label="${step} / ${total}">
        <span class="lh-progress-text">${step} / ${total}</span>
        <span class="lh-dots" aria-hidden="true">${Array.from({ length: total }, (_v, i) => `<i class="${i + 1 <= step ? 'is-on' : ''}"></i>`).join('')}</span>
      </span>
    </div>`;
}

function lhCatalogBanner() {
  return `
      <a class="lh-catalog-banner" href="?lang=${esc(state.lang)}&domain=catalog" data-action="catalog">
        <span class="lh-catalog-main">
          <span class="lh-catalog-kicker">${esc(t('lh.catalog.kicker'))}</span>
          <strong class="lh-catalog-link">${esc(t('lh.catalog.link', { n: num(state.core.index.counts.items) }))}<span class="lh-catalog-arrow" aria-hidden="true">→</span></strong>
        </span>
        <span class="lh-catalog-sub">${esc(t('lh.catalog.sub'))}</span>
      </a>`;
}

function lhHistoryHtml() {
  const history = state.lh.history || [];
  if (!history.length) return '';
  const rows = [...history].reverse().slice(0, 8);
  return `
    <section class="lh-history" id="lhHistory">
      <div class="section-head">
        <h2>${esc(t('lh.historyTitle'))}</h2>
        <span class="section-hint">${esc(t('lh.historyCount', { n: history.length, s: state.lh.skips }))}</span>
      </div>
      <div class="lh-history-list">
        ${rows
          .map((row) => {
            const rec = recordById(row.item_id);
            const date = row.completed_at ? new Date(row.completed_at) : null;
            const dateText = date && !Number.isNaN(date.getTime())
              ? date.toLocaleDateString(locale(), { month: 'short', day: 'numeric' })
              : '';
            const title = getLang() === 'en' ? row.title_en : row.title_ko;
            const diff = LH_DIFFICULTIES.includes(row.difficulty) ? t(`lh.diff.${row.difficulty}`) : '';
            return `<span class="lh-badge" title="${esc(title || '')}">${rec ? iconHtml(rec, 'small') : ''}<span class="lh-badge-text">${esc(rec?.name || row.item_id)}<b>${esc(title || '')}</b></span>${diff ? `<span class="lh-badge-diff">${esc(diff)}</span>` : ''}<span class="lh-badge-date">${esc(dateText)}</span></span>`;
          })
          .join('')}
      </div>
    </section>`;
}

function lhLandingHtml() {
  return `
    <section class="lh lh--landing">
      <div class="lh-landing">
        <picture class="lh-symbol">
          <source srcset="./assets/brand/pharos-lighthouse.webp" type="image/webp" />
          <img src="./assets/brand/pharos-lighthouse.png" alt="" width="406" height="560" aria-hidden="true" decoding="async" fetchpriority="high" />
        </picture>
        <p class="lh-landing-kicker">${esc(t('lh.kicker'))}</p>
        <h1 class="lh-landing-title">
          <span>${esc(t('lh.landing.l1'))}</span>
          <span class="hl">${esc(t('lh.landing.l2'))}</span>
        </h1>
        <button type="button" class="primary-btn lh-start" data-lh-goto="pledge">${esc(t('lh.start'))}</button>
      </div>
      ${lhHistoryHtml()}
      ${lhCatalogBanner()}
    </section>`;
}

/** 약정일 — 서약서 서명줄에 찍을 오늘 날짜(로컬 시간). */
function lhPledgeDate() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}.${pad(now.getMonth() + 1)}.${pad(now.getDate())}`;
}

/** 항해 서약(Pledge) — 목표 탐색 직후, 분야·조건을 고르기 전에 서는 각서 화면. */
function lhPledgeHtml() {
  const clauses = ['lh.pledge.body1', 'lh.pledge.body2', 'lh.pledge.body3'];
  return `
    <section class="lh lh--pledge${state.lh.pledgeAccepted ? ' is-sworn' : ''}" aria-labelledby="lhPledgeTitle">
      <div class="lh-pledge">
        <div class="lh-pledge-head">
          <picture class="lh-pledge-rune">
            <source srcset="./assets/brand/pharos-rune-96.webp" type="image/webp" />
            <img src="./assets/brand/pharos-rune-96.png" alt="" width="56" height="56" aria-hidden="true" decoding="async" />
          </picture>
          <p class="lh-pledge-kicker">${esc(t('lh.pledge.kicker'))}</p>
          <h1 class="lh-pledge-title" id="lhPledgeTitle" tabindex="-1">${esc(t('lh.pledge.title'))}</h1>
        </div>
        <div class="lh-pledge-rule" aria-hidden="true"><span></span></div>
        <ol class="lh-pledge-clauses">
          ${clauses
            .map(
              (key, i) => `<li><span class="lh-pledge-no" aria-hidden="true">${String(i + 1).padStart(2, '0')}</span><p>${esc(t(key))}</p></li>`,
            )
            .join('')}
        </ol>
        <label class="lh-pledge-check">
          <input type="checkbox" data-lh-oath-check${state.lh.pledgeAccepted ? ' checked' : ''} />
          <span class="lh-pledge-box" aria-hidden="true"></span>
          <span class="lh-pledge-check-text">${esc(t('lh.pledge.check'))}</span>
        </label>
        <div class="lh-pledge-actions">
          <button type="button" class="primary-btn lh-pledge-go" data-lh-oath${state.lh.pledgeAccepted ? '' : ' disabled'}>${esc(t('lh.pledge.accept'))}</button>
          <button type="button" class="text-btn lh-pledge-back" data-lh-goto="0">${esc(t('lh.pledge.back'))}</button>
        </div>
        <p class="lh-pledge-hint">${esc(t('lh.pledge.hint'))}</p>
        <p class="lh-pledge-sign" aria-hidden="true">PHAROS · LIGHTHOUSE · ${esc(lhPledgeDate())}</p>
      </div>
    </section>`;
}

/** 분야 선택 — 🎮 게임 · 📺 애니 · 🎬 영화 · 📖 만화 · 🎲 상관없이(전체 랜덤). */
function lhCategoryHtml() {
  const cats = state.lh.data?.categories || [];
  const active = state.lh.filters.category;
  return `
    <section class="lh lh--wizard lh--category">
      <div class="lh-panel">
        <h1 class="lh-q lh-cat-title" tabindex="-1">${esc(t('lh.q.category'))}</h1>
        <p class="lh-cat-lede">${esc(t('lh.category.lede'))}</p>
        <div class="lh-cats" role="radiogroup" aria-label="${esc(t('lh.q.category'))}">
          ${cats
            .map(
              (row) => `<button type="button" class="lh-cat${active === row.id ? ' is-on' : ''}" role="radio" aria-checked="${active === row.id ? 'true' : 'false'}" data-lh-cat="${esc(row.id)}">
              <span class="lh-cat-label">${esc(lhText(row, 'label'))}</span>
              <span class="lh-cat-sub">${esc(lhText(row, 'sub'))}</span>
              <span class="lh-cat-hint">${esc(lhText(row, 'hint'))}</span>
            </button>`,
            )
            .join('')}
        </div>
      </div>
      <div class="lh-wizard-nav">
        <button type="button" class="text-btn" data-lh-goto="0">${esc(t('lh.home'))}</button>
      </div>
    </section>`;
}

function lhPlatformPanelHtml() {
  const { platform, price } = state.lh.filters;
  return `
    <h1 class="lh-q" tabindex="-1">${esc(t('lh.q.platform'))}</h1>
    <div class="lh-choices" role="radiogroup" aria-label="${esc(t('lh.q.platform'))}">
      ${lhChoiceButton({ group: 'platform', value: 'all', label: t('lh.opt.all'), sub: t('lh.opt.allSub'), active: platform === 'all' })}
      ${lhChoiceButton({ group: 'platform', value: 'pc', label: 'PC', sub: t('lh.opt.pcSub'), active: platform === 'pc' })}
      ${lhChoiceButton({ group: 'platform', value: 'mobile', label: t('lh.opt.mobile'), sub: t('lh.opt.mobileSub'), active: platform === 'mobile' })}
    </div>
    <h2 class="lh-q lh-q--sub">${esc(t('lh.q.price'))}</h2>
    <div class="lh-choices lh-choices--seg" role="radiogroup" aria-label="${esc(t('lh.q.price'))}">
      ${lhChoiceButton({ group: 'price', value: 'all', label: t('lh.opt.all'), sub: t('lh.opt.priceAllSub'), active: price === 'all' })}
      ${lhChoiceButton({ group: 'price', value: 'free', label: t('lh.price.free'), sub: t('lh.opt.priceFreeSub'), active: price === 'free' })}
    </div>`;
}

function lhTierPanelHtml() {
  const { tier, category } = state.lh.filters;
  const qKey = category === 'game' ? 'lh.q.time' : category === 'manga' ? 'lh.q.read' : category === 'anime' || category === 'movie' ? 'lh.q.watch' : 'lh.q.amount';
  return `
    <h1 class="lh-q" tabindex="-1">${esc(t(qKey))}</h1>
    <div class="lh-choices lh-choices--tiers" role="radiogroup" aria-label="${esc(t(qKey))}">
      ${LH_TIERS.map((n) => {
        const meta = lhTierMeta(n);
        return lhChoiceButton({
          group: 'tier',
          value: String(n),
          label: lhText(meta, 'label'),
          sub: lhText(meta, 'window'),
          hint: lhText(meta, 'hint'),
          active: tier === n,
        });
      }).join('')}
    </div>`;
}

function lhDifficultyPanelHtml() {
  const { difficulty, category } = state.lh.filters;
  const isGame = category === 'game';
  const pool = lhPoolQuests();
  const count = pool.length;
  const qKey = isGame ? 'lh.q.difficulty' : 'lh.q.mood';
  const subs = isGame
    ? ['lh.opt.diffAllSub', 'lh.opt.diffChillSub', 'lh.opt.diffNormalSub', 'lh.opt.diffHardSub']
    : ['lh.opt.moodAllSub', 'lh.opt.moodChillSub', 'lh.opt.moodNormalSub', 'lh.opt.moodHardSub'];
  const values = ['all', 'chill', 'normal', 'hardcore'];
  return `
    <p class="lh-summary">${esc(lhSummaryText())}</p>
    <h1 class="lh-q" tabindex="-1">${esc(t(qKey))}</h1>
    <div class="lh-choices lh-choices--diff" role="radiogroup" aria-label="${esc(t(qKey))}">
      ${values
        .map((value, i) =>
          lhChoiceButton({
            group: 'difficulty',
            value,
            label: value === 'all' ? t('lh.diff.all') : t(`lh.diff.${value}`),
            sub: t(subs[i]),
            active: difficulty === value,
          }),
        )
        .join('')}
    </div>
    <p class="lh-count${count ? '' : ' is-empty'}" aria-live="polite">${esc(count ? t('lh.count', { n: count }) : t('lh.countZero'))}</p>
    <button type="button" class="primary-btn lh-draw" data-lh-draw${count ? '' : ' disabled'}>${esc(t('lh.draw'))}</button>
    ${count ? '' : `<p class="lh-hint">${esc(t(isGame ? 'lh.countZeroHint' : 'lh.countZeroHintMedia'))}</p>`}`;
}

function lhSummaryText() {
  const { category, platform, price, tier } = state.lh.filters;
  const parts = [];
  if (category === 'game') {
    parts.push(platform === 'all' ? t('lh.opt.all') : platform === 'pc' ? 'PC' : t('lh.opt.mobile'));
    parts.push(price === 'free' ? t('lh.price.free') : t('lh.opt.priceAll'));
  } else {
    const meta = lhCategoryMeta(category);
    if (meta) parts.push(lhText(meta, 'label'));
  }
  const tierMeta = lhTierMeta(tier);
  if (tierMeta) parts.push(lhText(tierMeta, 'label'));
  return parts.filter(Boolean).join(' · ');
}

/** 조건 화면 — 분야에 따라 1(플랫폼·가격 또는 시간) → 2(시간 또는 난이도) → 3(난이도). */
function lhWizardStepHtml(index) {
  const flow = lhFlow();
  const kind = flow[index - 1];
  const total = flow.length;
  const panel = kind === 'platform' ? lhPlatformPanelHtml() : kind === 'time' ? lhTierPanelHtml() : lhDifficultyPanelHtml();
  const back = index === 1
    ? `<button type="button" class="text-btn" data-lh-goto="category">${esc(t('lh.backCategory'))}</button>`
    : `<button type="button" class="text-btn" data-lh-goto="${index - 1}">${esc(t('lh.prev'))}</button>`;
  const next = index < total
    ? `<button type="button" class="primary-btn" data-lh-goto="${index + 1}">${esc(t('lh.next'))}</button>`
    : '';
  return `
    <section class="lh lh--wizard lh--step${index} lh--flow-${esc(kind)}">
      ${lhStepper(index)}
      <div class="lh-panel">${panel}</div>
      <div class="lh-wizard-nav">${back}${next}</div>
    </section>`;
}

function lhResultHtml() {
  const current = state.lh.current;
  if (!state.lh.data) {
    return `<section class="lh lh--wizard"><div class="lh-empty"><span class="lh-empty-glyph" aria-hidden="true">🚨</span><h1>${esc(t('lh.toast.noData'))}</h1></div></section>`;
  }
  if (!current) return '';
  const entry = lhEntryById(current.item_id);
  const rec = recordById(current.item_id);
  if (!entry || !rec) return '';
  const quest = lhQuestOf(entry, current.tier, current.difficulty);
  if (!quest) return '';
  const isGame = entry.category === 'game';
  const verdict = engine.VERDICT_META[rec.verdict] || engine.VERDICT_META.conditional;
  const scoreText = typeof rec.score === 'number' ? rec.score.toFixed(1) : '—';
  const statusChip = isGame
    ? (entry.free_to_play ? t('lh.badge.free') : t('lh.badge.paid'))
    : lhMediaStatusChip(rec);
  const platformChip = isGame
    ? `<span class="lh-chip">${esc(entry.platforms.map((p) => (p === 'pc' ? 'PC' : t('lh.opt.mobile'))).join(' · '))}</span>`
    : '';
  const catLabel = state.cat.categoryLabel(rec.category);
  return `
    <section class="lh lh--result">
      <p class="lh-result-kicker">${esc(t('lh.inprogress'))}</p>
      <article class="lh-card" data-lh-game="${esc(entry.id)}" data-lh-item="${esc(entry.id)}" data-lh-category-view="${esc(entry.category)}" data-lh-difficulty="${esc(quest.difficulty)}">
        <div class="lh-card-top">
          ${iconHtml(rec, 'detail')}
          <div class="lh-card-id">
            <div class="lh-card-chips">
              ${lhCategoryBadge(entry.category)}
              <span class="lh-chip">${esc(statusChip)}</span>
              ${platformChip}
              <span class="verdict verdict--${verdict.tone}"><span class="v-emoji" aria-hidden="true">${verdict.emoji}</span>${esc(verdict.label)}</span>
              <span class="lh-score">${esc(t('lh.score', { score: scoreText }))}</span>
            </div>
            <h1 class="lh-game-name">${esc(rec.name)}</h1>
            <p class="lh-game-meta">${esc(catLabel)}${rec.developer ? ` · ${esc(rec.developer)}` : ''}</p>
          </div>
        </div>
        ${lhQuestHtml(entry, quest)}
        <div class="lh-actions">
          <button type="button" class="primary-btn" data-lh-complete>${esc(t('lh.complete'))}</button>
          <button type="button" class="ghost-btn" data-lh-ad>${esc(t('lh.adSkip'))}</button>
          <button type="button" class="text-btn" data-lh-detail="${esc(entry.id)}">${esc(isGame ? t('lh.detail') : t('lh.detailMedia'))} →</button>
        </div>
        <p class="lh-locked">${esc(t('lh.lockedNote'))}</p>
      </article>
    </section>`;
}

export function renderLighthouse() {
  const wrap = $('view');
  if (!wrap) return;
  const step = lhStep();
  if (!state.lh.data) {
    wrap.innerHTML = `<section class="lh lh--wizard"><div class="lh-empty"><span class="lh-empty-glyph" aria-hidden="true">🚨</span><h1>${esc(t('lh.toast.noData'))}</h1><p>${esc(t('lh.emptyBody'))}</p></div></section>`;
    return;
  }
  if (step === 0) wrap.innerHTML = lhLandingHtml();
  else if (step === LH_PLEDGE) wrap.innerHTML = lhPledgeHtml();
  else if (step === LH_CATEGORY) wrap.innerHTML = lhCategoryHtml();
  else if (step >= 1 && step <= lhStepTotal()) wrap.innerHTML = lhWizardStepHtml(step);
  else wrap.innerHTML = lhResultHtml();
}

export async function openLighthouseDetail(id) {
  const rec = recordById(id);
  if (!rec) return;
  state.lastFocus = document.activeElement;
  state.route = { ...state.route, item: id };
  syncUrl('replace');
  await showDetail(id, rec.arenas[0]);
}

/* ------------------------------------------------------------- 보관함·공유 */
