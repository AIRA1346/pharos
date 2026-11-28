/**
 * Pharos 웹 v2 — 엔트리·초기화·라우팅·공통 바인딩.
 * 계산은 전부 engine.js(= x-pharos.client 계약)로 넘긴다.
 *
 * 화면 모듈
 *   - state.js      공유 상태·localStorage·테마·언어
 *   - catalog.js    상단·홈·도메인·대분류·비교군·카드·비교
 *   - detail.js     상세 모달(사전·판정·근거)
 *   - lighthouse.js 등대 서약·위저드·잠금·리롤
 *
 * 데이터
 *   - data/catalog.json          도메인·대분류·비교군 정의(어디에 무엇이 있는가)
 *   - data/search-index.json     통합 검색·홈 리포트용 경량 인덱스(모두의 요약)
 *   - data/{domain}/{arena}.json 비교군 항목 전체 — 목록·상세·비교에서만 지연 로딩
 */

import * as engine from './engine.js';
import { loadCore, createCatalogView, createArenaStore, searchRecords } from './data.js';
import { t, labeled, initLang, applyStaticI18n } from './i18n.js';
import { $, LS, PRESETS, applyDocumentLang, contract, esc, indexRecords, initTheme, loadPrefs, num, pct, presetHintOf, presetLabelOf, recordById, savePrefs, state, switchLang, toggleTheme, writeStore } from './state.js';
import { bookmarkRowHtml, computeViews, presetLabel, renderArena, renderArenaResults, renderBreadcrumb, renderCategory, renderCompare, renderCompareBar, renderDatasetChip, renderDomain, renderDomainTabs, renderHome, renderHomeSearch, setHomeDomain, toggleCompare } from './catalog.js';
import { calcRuleText, closeDetail, openDetail, showDetail } from './detail.js';
import { LH_CATEGORY, LH_PLEDGE, lhCloseAd, lhComplete, lhDraw, lhOpenAd, lhPick, lhSetStep, lhSkipComplete, loadLighthouse, openLighthouseDetail, renderLighthouse } from './lighthouse.js';

document.getElementById('bootNote')?.remove();

async function init() {
  state.lang = initLang();
  initTheme();
  applyStaticI18n();
  applyDocumentLang();
  bindEvents();
  try {
    const core = await loadCore(state.lang);
    state.core = core;
    state.cat = createCatalogView(core.catalog);
    state.store = createArenaStore(core.catalog, core.en);
  } catch (err) {
    renderFatal(err);
    return;
  }
  loadPrefs();
  await loadLighthouse();
  buildMethodBody();
  renderDatasetChip();
  await applyUrl();

  window.Pharos = {
    engine,
    state,
    api: {
      navigate: (patch) => navigate(patch),
      openItem: (id) => openDetail(id),
      closeItem: () => closeDetail(),
      setPreset: (id) => applyPreset(id),
      toggleBookmark,
      toggleCompare,
      search: (q) => searchRecords(state.core.index, state.cat, q),
      loadArena: (id) => state.store.load(id),
      currentUrl: () => location.href,
    },
  };
}

/* v31 — 통합 미디어 URL 호환. ?domain=media 와 구 비교군 주소를 새 영화·애니·만화 도메인으로 옮긴다. */
const LEGACY_MEDIA_ARENA = { 'feature-films': 'movie', 'anime-tv': 'anime', 'manga-volumes': 'manga' };

const LEGACY_MEDIA_CATEGORY = { movie: 'movie', anime: 'anime', manga: 'manga' };

function legacyMediaTarget(params) {
  const oldArena = params.get('arena');
  const oldCategory = params.get('category');
  if (oldArena && LEGACY_MEDIA_ARENA[oldArena]) return LEGACY_MEDIA_ARENA[oldArena];
  if (oldCategory && LEGACY_MEDIA_CATEGORY[oldCategory]) return LEGACY_MEDIA_CATEGORY[oldCategory];
  return 'movie';
}

function parseUrl() {
  const params = new URLSearchParams(location.search);
  const route = { view: 'home', domain: null, category: null, arena: null, item: null, compare: [] };
  const tab = params.get('tab');
  const domainParam = params.get('domain');
  const legacyMedia = domainParam === 'media';
  const domain = legacyMedia ? legacyMediaTarget(params) : domainParam;
  const wantsLighthouse = domain === 'lighthouse' || tab === 'lighthouse';
  // `?domain=catalog` · `?domain=all` 은 카탈로그 홈(전체 탐색)으로 — 실제 도메인이 아니라 화면 이름이다.
  const wantsCatalog = domain === 'catalog' || domain === 'all' || tab === 'catalog';
  if (wantsLighthouse) {
    route.view = 'lighthouse';
    const category = params.get('lh_cat');
    if (['game', 'anime', 'movie', 'manga', 'all'].includes(category)) state.lh.filters.category = category;
    const tier = Number(params.get('lh_tier'));
    if ([1, 2, 3].includes(tier)) state.lh.filters.tier = tier;
    const price = params.get('lh_price');
    if (price === 'free' || price === 'all') state.lh.filters.price = price;
    const platform = params.get('lh_platform');
    if (platform === 'pc' || platform === 'mobile' || platform === 'all') state.lh.filters.platform = platform;
    const difficulty = params.get('lh_diff');
    if (['chill', 'normal', 'hardcore', 'all'].includes(difficulty)) state.lh.filters.difficulty = difficulty;
  } else if (wantsCatalog) {
    route.view = 'home';
  } else if (domain && state.cat.domain(domain)) {
    route.view = 'browse';
    route.domain = domain;
    const category = legacyMedia ? null : params.get('category');
    if (category && state.cat.category(category) && state.cat.category(category).domain === domain) {
      route.category = category;
    }
    const arena = legacyMedia ? null : params.get('arena');
    if (arena && state.cat.arena(arena) && state.cat.arena(arena).domain === domain) {
      route.arena = arena;
      route.category = state.cat.arena(arena).category;
    }
  } else if (!domain) {
    const arena = params.get('arena');
    const def = arena ? state.cat.arena(arena) : null;
    if (def) {
      route.view = 'browse';
      route.domain = def.domain;
      route.category = def.category;
      route.arena = def.id;
    } else if (arena && LEGACY_MEDIA_ARENA[arena]) {
      // 구 미디어 비교군 주소 — 해당 도메인의 장르별 비교군 목록으로 보낸다.
      route.view = 'browse';
      route.domain = LEGACY_MEDIA_ARENA[arena];
    }
  }
  const compare = params.get('compare');
  if (compare && route.arena) {
    const ids = compare.split(',').map((id) => id.trim()).filter(Boolean);
    const allowed = new Set(indexRecords().filter((rec) => rec.arenas.includes(route.arena)).map((rec) => rec.id));
    route.compare = ids.filter((id) => allowed.has(id)).slice(0, 3);
    if (route.compare.length >= 2) route.view = 'compare';
  }
  const item = params.get('item');
  if (item) {
    const rec = recordById(item);
    if (rec) {
      route.item = item;
      if (route.view !== 'lighthouse' && !route.arena && rec.arenas.length) {
        const arena = state.cat.arena(rec.arenas[0]);
        if (arena) {
          route.view = 'browse';
          route.domain = arena.domain;
          route.category = arena.category;
          route.arena = arena.id;
        }
      }
    }
  }

  // 기본 랜딩은 등대 — 주소에 화면·도메인·항목이 없을 때만(?lang·?preset 같은 설정 파라미터는 무시).
  if (!domain && !tab && !route.domain && !route.item) route.view = 'lighthouse';

  const preset = params.get('preset');
  if (preset && PRESETS.some((p) => p.id === preset)) state.preset = preset;
  const weights = params.get('w');
  if (weights && !preset) {
    const parts = weights.split(',').map((v) => Number(v));
    const keys = Object.keys(state.weights);
    if (parts.length === keys.length && parts.every((v) => Number.isFinite(v) && v >= 0 && v <= 100)) {
      keys.forEach((key, i) => {
        state.weights[key] = parts[i];
      });
      state.preset = detectPreset() || 'custom';
    }
  } else if (preset) {
    const chosen = PRESETS.find((p) => p.id === preset);
    state.weights = { ...engine.defaultWeights(contract()), ...chosen.weights };
    if (Array.isArray(chosen.filters)) {
      const known = new Set((contract().hard_filters || []).map((f) => f.key));
      const base = contract().default_enabled_filters || [];
      state.enabledFilters = [...new Set([...base, ...chosen.filters])].filter((key) => known.has(key));
    }
  }
  const filters = params.get('filters');
  if (filters !== null) {
    const known = new Set((contract().hard_filters || []).map((f) => f.key));
    state.enabledFilters = filters.split(',').map((s) => s.trim()).filter((key) => known.has(key));
  }
  const strict = params.get('strict');
  if (strict === '0') state.strict = false;
  if (strict === '1') state.strict = true;
  const strictMonetizationParam = contract().monetization_impact?.strict_toggle?.param || 'strictmon';
  const strictMonetization = params.get(strictMonetizationParam);
  if (strictMonetization === '1') state.strictMonetization = true;
  if (strictMonetization === '0') state.strictMonetization = false;
  return route;
}

async function applyUrl() {
  state.route = parseUrl();
  await render({ replace: true });
}

function urlForRoute() {
  const params = new URLSearchParams();
  const route = state.route;
  params.set('lang', state.lang);
  if (route.view === 'lighthouse') {
    params.set('domain', 'lighthouse');
    const { tier, price, platform, difficulty, category } = state.lh.filters;
    if (category) params.set('lh_cat', category);
    if (tier !== 1) params.set('lh_tier', String(tier));
    if (price !== 'all') params.set('lh_price', price);
    if (platform !== 'all') params.set('lh_platform', platform);
    if (difficulty !== 'all') params.set('lh_diff', difficulty);
  } else if (route.view === 'home' && !route.domain) {
    params.set('domain', 'catalog');
  } else if (route.domain) {
    params.set('domain', route.domain);
    if (route.category && !route.arena) params.set('category', route.category);
    if (route.arena) {
      params.set('arena', route.arena);
      if (route.compare.length >= 2) params.set('compare', route.compare.join(','));
    }
  }
  if (route.item) params.set('item', route.item);
  const presetWeights = PRESETS.find((p) => p.id === state.preset)?.weights;
  if (state.preset && state.preset !== 'balanced' && state.preset !== 'custom') params.set('preset', state.preset);
  if (state.preset === 'custom' || (state.preset === 'balanced' && !isPresetWeights(PRESETS[0].weights))) {
    params.set('w', Object.keys(state.weights).map((key) => state.weights[key]).join(','));
  } else if (presetWeights && !isPresetWeights(presetWeights)) {
    params.set('w', Object.keys(state.weights).map((key) => state.weights[key]).join(','));
  }
  const defaults = (contract().default_enabled_filters || []).join(',');
  const current = [...state.enabledFilters].sort().join(',');
  if (current !== [...defaults.split(',')].filter(Boolean).sort().join(',')) {
    params.set('filters', state.enabledFilters.join(','));
  }
  if (!state.strict) params.set('strict', '0');
  if (state.strictMonetization) params.set(contract().monetization_impact?.strict_toggle?.param || 'strictmon', '1');
  const qs = params.toString();
  return `${location.pathname}${qs ? `?${qs}` : ''}`;
}

export function syncUrl(mode = 'push') {
  const next = urlForRoute();
  const now = `${location.pathname}${location.search}`;
  if (next === now) return;
  try {
    if (mode === 'replace') history.replaceState({ pharos: true }, '', next);
    else history.pushState({ pharos: true }, '', next);
  } catch {
    /* file:// 등에서 실패해도 화면은 유지 */
  }
}

export let renderSeq = 0;

export async function render({ replace = false } = {}) {
  const seq = ++renderSeq;
  syncUrl(replace || state.route.item ? 'replace' : 'push');
  renderDomainTabs();
  renderBreadcrumb();
  renderCompareBar();
  document.body.classList.toggle('is-home', !state.route.domain && state.route.view !== 'lighthouse');
  document.body.classList.toggle('is-lighthouse', state.route.view === 'lighthouse');
  if (state.route.view === 'lighthouse') {
    renderLighthouse();
  } else if (!state.route.domain) {
    renderHome();
  } else if (state.route.view === 'compare' && state.route.compare.length >= 2) {
    await renderCompare(seq);
  } else if (state.route.arena) {
    await renderArena(seq);
  } else if (state.route.category) {
    renderCategory();
  } else {
    renderDomain();
  }
  if (seq !== renderSeq) return;
  if (state.route.item) {
    const rec = recordById(state.route.item);
    const arenaOverride = state.route.view === 'lighthouse' ? rec?.arenas?.[0] : null;
    await showDetail(state.route.item, arenaOverride);
  } else closeDetail({ silent: true });
  $('view').focus({ preventScroll: true });
}

export async function navigate(patch, options = {}) {
  const prev = state.route;
  const next = { ...prev, ...patch };
  if (!('item' in patch)) next.item = null;
  if (!('query' in patch)) state.query = '';
  if ('domain' in patch && patch.domain !== prev.domain) {
    next.category = patch.category ?? null;
    next.arena = patch.arena ?? null;
    next.compare = [];
    next.view = patch.domain ? 'browse' : 'home';
  }
  if ('category' in patch && patch.category !== prev.category) {
    next.arena = patch.arena ?? null;
    next.compare = [];
    next.view = 'browse';
  }
  if ('arena' in patch && patch.arena !== prev.arena) {
    next.compare = [];
    next.view = 'browse';
  }
  if (patch.view === 'browse' && !patch.arena && !patch.category) {
    next.arena = null;
    next.category = null;
    next.compare = [];
  }
  if ('view' in patch && patch.view !== 'compare' && patch.view !== 'browse') next.view = patch.view;
  state.route = next;
  await render({ replace: Boolean(options.replace) });
}

function goHome() {
  state.query = '';
  state.homeDomain = 'all';
  state.route = { view: 'home', domain: null, category: null, arena: null, item: null, compare: [] };
  return render();
}

/** 기본 화면인 등대 — 로고·첫 탭이 가리킨다. */
function goLighthouse() {
  state.query = '';
  state.lh.step = 0;
  state.route = { view: 'lighthouse', domain: null, category: null, arena: null, item: null, compare: [] };
  return render();
}

/* ------------------------------------------------------------ 상단·경로 UI */

function domainFilterLabel(def) {
  const dom = state.route.domain ? state.cat.domain(state.route.domain) : null;
  return (dom?.filter_labels || {})[def.key] || labeled('filter', def.key, def.label);
}

function buildTuneBody() {
  const axes = scoringAxes();
  const dom = state.route.domain ? state.cat.domain(state.route.domain) : null;
  const packKey = dom?.filter_pack || 'core';
  const packs = state.cat.catalog.filter_packs || {};
  const orderedPacks = [packKey, ...Object.keys(packs).filter((key) => key !== packKey)];
  const filterDefs = new Map((contract().hard_filters || []).map((def) => [def.key, def]));
  const defaults = new Set(contract().default_enabled_filters || []);

  $('tuneBody').innerHTML = `
    <section class="tune-sec">
      <div class="panel-head"><h3>${esc(t('tune.presets'))}</h3><span class="panel-hint">${esc(t('tune.presetsHint'))}</span></div>
      <div class="preset-row" id="presets">
        ${PRESETS.map(
          (preset) =>
            `<button type="button" class="preset" data-preset="${esc(preset.id)}" aria-pressed="${
              state.preset === preset.id
            }" title="${esc(presetHintOf(preset.id))}">${esc(presetLabelOf(preset.id))}</button>`,
        ).join('')}
      </div>
      <div class="weights" id="weights">
        ${axes
          .map(
            (def, index) => `
          <div class="weight">
            <div class="weight-head">
              <span class="weight-name">${esc(labeled('axis', def.key, def.label))}<small>${esc(t('tune.axisN', { n: index + 1 }))}</small></span>
              <span class="weight-pct" id="pct-${esc(def.key)}">—</span>
            </div>
            <input type="range" id="range-${esc(def.key)}" min="0" max="100" step="5" value="${
              state.weights[def.key] ?? 0
            }" data-axis="${esc(def.key)}" aria-label="${esc(t('tune.axisWeightAria', { axis: labeled('axis', def.key, def.label) }))}" />
            <div class="weight-meta"><span>${esc(t('tune.default', { v: pct(def.default_weight ?? 0) }))}</span><span id="meta-${esc(def.key)}">w = 0.00</span></div>
          </div>`,
          )
          .join('')}
      </div>
      <div class="weight-bar" id="weightBar" aria-hidden="true"></div>
      <p class="hint">${esc(t('tune.presetHint'))}</p>
    </section>

    <section class="tune-sec">
      <div class="panel-head"><h3>${esc(t('tune.hardFilters'))}</h3><span class="panel-hint" id="filterCount">0/0</span></div>
      <p class="hint">${t('tune.hardFiltersHint')}</p>
      ${orderedPacks
        .map((key, index) => {
          const pack = packs[key];
          if (!pack) return '';
          const defs = (pack.filters || []).map((fkey) => filterDefs.get(fkey)).filter(Boolean);
          const extra = index > 0;
          const anyOn = defs.some((def) => state.enabledFilters.includes(def.key));
          return `<details class="filter-pack" ${extra ? '' : 'open'} ${anyOn ? 'data-active="true"' : ''}>
            <summary><b>${esc(pack.label || key)}</b> <span class="muted">${esc(pack.description || '')}</span></summary>
            <div class="filter-list">
              ${defs
                .map(
                  (def) => `
                <label class="filter${defaults.has(def.key) ? ' is-default' : ''}">
                  <input type="checkbox" data-filter="${esc(def.key)}" ${
                    state.enabledFilters.includes(def.key) ? 'checked' : ''
                  } />
                  <span class="filter-text"><span class="filter-name">${esc(domainFilterLabel(def))}</span><span class="filter-meta">${
                    defaults.has(def.key) ? esc(t('tune.isDefault')) : ''
                  }${esc(def.key)}</span></span>
                </label>`,
                )
                .join('')}
            </div>
          </details>`;
        })
        .join('')}
      <button type="button" class="text-btn" data-action="reset-filters">${esc(t('tune.reset'))}</button>
    </section>

    <section class="tune-sec">
      <div class="panel-head"><h3>${esc(t('tune.spendTitle'))}</h3><span class="panel-hint" id="strictMonetizationState">${state.strictMonetization ? 'ON' : 'OFF'}</span></div>
      <label class="switch">
        <input type="checkbox" id="strictMonetizationToggle" ${state.strictMonetization ? 'checked' : ''} />
        <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
        <span class="switch-text">${t('tune.spendToggle')}</span>
      </label>
      <p class="hint" id="strictMonetizationHint">${state.strictMonetization ? esc(t('tune.spendOn')) : esc(t('tune.spendOff'))}</p>
    </section>

    <section class="tune-sec">
      <div class="panel-head"><h3>${esc(t('tune.evidenceMode'))}</h3><span class="panel-hint" id="strictState">${state.strict ? 'ON' : 'OFF'}</span></div>
      <label class="switch">
        <input type="checkbox" id="strictToggle" ${state.strict ? 'checked' : ''} />
        <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
        <span class="switch-text">${t('tune.evidenceToggle')}</span>
      </label>
      <p class="hint" id="strictHint">${state.strict ? t('tune.evidenceOn') : t('tune.evidenceOff')}</p>
    </section>

    <footer class="tune-foot">
      <p class="mini-label">${esc(t('tune.current'))}</p>
      <p id="tuneFootText"></p>
      <button type="button" class="text-btn" data-action="open-method">${esc(t('tune.method'))}</button>
      <button type="button" class="text-btn" data-action="share-state">${esc(t('tune.copy'))}</button>
    </footer>`;

  const search = $('tuneBody').querySelector('#weights');
  search?.querySelectorAll('input[type="range"]').forEach((input) => {
    input.style.setProperty('--fill', `${Math.min(100, Number(input.value))}%`);
  });
  renderWeights();
  updateTuneMeta();
}

function scoringAxes() {
  return (contract().axes || []).filter((def) => !def.profile_scoped);
}

function detectPreset() {
  const found = PRESETS.find((preset) =>
    Object.entries(preset.weights).every(([key, value]) => Number(state.weights[key]) === value),
  );
  return found?.id || null;
}

function isPresetWeights(weights) {
  return Object.entries(weights).every(([key, value]) => Number(state.weights[key]) === value);
}

function renderWeights() {
  const axes = scoringAxes();
  const normalized = engine.normalizeWeights(state.weights, axes.map((def) => def.key));
  for (const def of axes) {
    const input = $(`range-${def.key}`);
    const raw = Number(state.weights[def.key] ?? 0);
    if (input) {
      input.style.setProperty('--fill', `${Math.min(100, raw)}%`);
      input.value = String(raw);
    }
    const pctEl = $(`pct-${def.key}`);
    if (pctEl) pctEl.textContent = pct(normalized[def.key] ?? 0);
    const meta = $(`meta-${def.key}`);
    if (meta) meta.textContent = `w = ${(normalized[def.key] ?? 0).toFixed(2)}`;
  }
  const bar = $('weightBar');
  if (bar) {
    bar.innerHTML = axes
      .map((def, index) => `<span class="seg-${index}" style="flex-basis:${(normalized[def.key] ?? 0) * 100}%"></span>`)
      .join('');
  }
  document.querySelectorAll('[data-preset]').forEach((btn) => {
    btn.setAttribute('aria-pressed', state.preset === btn.dataset.preset ? 'true' : 'false');
  });
}

function updateTuneMeta() {
  const count = $('filterCount');
  if (count) count.textContent = `${state.enabledFilters.length}/${(contract().hard_filters || []).length}`;
  const strict = $('strictState');
  if (strict) strict.textContent = state.strict ? 'ON' : 'OFF';
  const monetization = $('strictMonetizationState');
  if (monetization) monetization.textContent = state.strictMonetization ? 'ON' : 'OFF';
  const monetizationHint = $('strictMonetizationHint');
  if (monetizationHint) {
    monetizationHint.textContent = state.strictMonetization ? t('tune.spendOn') : t('tune.spendOff');
  }
  const hint = $('strictHint');
  if (hint) {
    hint.innerHTML = state.strict ? t('tune.evidenceOn') : t('tune.evidenceOff');
  }
  const foot = $('tuneFootText');
  if (foot) {
    const weights = scoringAxes().map((def) => `${labeled('axis', def.key, def.label)} ${state.weights[def.key]}%`).join(' · ');
    foot.innerHTML = t('tune.foot', {
      preset: esc(presetLabel()),
      weights: esc(weights),
      n: state.enabledFilters.length,
      mode: state.strict ? esc(t('verdict.modeStrict')) : esc(t('verdict.modeRelaxed')),
      spend: state.strictMonetization ? esc(t('tune.spendFiltered')) : esc(t('tune.spendAllowed')),
    });
  }
  const summary = $('tuneSummary');
  if (summary) summary.textContent = presetLabel();
}

function applyPreset(id) {
  const preset = PRESETS.find((row) => row.id === id);
  if (!preset) return;
  for (const [key, value] of Object.entries(preset.weights)) {
    if (key in state.weights) state.weights[key] = value;
  }
  const known = new Set((contract().hard_filters || []).map((f) => f.key));
  const leaving = PRESETS.find((row) => row.id === state.preset)?.filters || [];
  const adding = preset.filters || [];
  // 프리셋이 켠 필터만 되돌린다 — 사용자가 직접 켜 둔 필터는 건드리지 않는다.
  const kept = state.enabledFilters.filter((key) => !leaving.includes(key));
  state.enabledFilters = [...new Set([...kept, ...adding])].filter((key) => known.has(key));
  state.preset = id;
  savePrefs();
  renderWeights();
  syncFilterInputs();
  updateTuneMeta();
  refreshAfterSettingChange({ filters: true });
}

/** 프리셋이 켠·끈 필터를 드로어 체크박스에 맞춘다(applyPreset 은 드로어를 다시 그리지 않는다). */
function syncFilterInputs() {
  document.querySelectorAll('#tuneBody input[data-filter]').forEach((input) => {
    input.checked = state.enabledFilters.includes(input.dataset.filter);
  });
  renderTunePacksActiveState();
}

function refreshAfterSettingChange({ filters = false } = {}) {
  syncUrl('replace');
  if (state.route.view === 'compare') render();
  else if (state.route.arena) renderArenaResults();
  if (filters) renderTunePacksActiveState();
  if (!$('modalBackdrop')?.hidden && state.route.item) showDetail(state.route.item);
}

function renderTunePacksActiveState() {
  document.querySelectorAll('#tuneBody details.filter-pack').forEach((details) => {
    const anyOn = [...details.querySelectorAll('input[data-filter]')].some((input) => input.checked);
    details.dataset.active = anyOn ? 'true' : 'false';
  });
}

function openTune() {
  buildTuneBody();
  $('tuneBackdrop').hidden = false;
  $('tuneDrawer').hidden = false;
  $('tuneBtn').setAttribute('aria-expanded', 'true');
  document.body.classList.add('drawer-open');
  $('tuneDrawer').querySelector('button, input')?.focus({ preventScroll: true });
}

function closeTune() {
  $('tuneBackdrop').hidden = true;
  $('tuneDrawer').hidden = true;
  $('tuneBtn').setAttribute('aria-expanded', 'false');
  document.body.classList.remove('drawer-open');
  $('tuneBtn').focus({ preventScroll: true });
}

/* ------------------------------------------------------------- 방법론 모달 */

function buildMethodBody() {
  const axes = contract().axes || [];
  const rules = contract().verdict_rules || [];
  const axisWhy = {
    user_rating: t('method.b.user'),
    objective: t('method.b.objective'),
    ai_review: t('method.b.ai'),
    personal_fit: t('method.b.fit'),
  };
  $('methodBody').innerHTML = `
    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">A</span><h3>${esc(t('method.a.title'))}</h3></div>
      <p class="m-sec-note">${t('method.a.note')}</p>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>${esc(t('method.level'))}</th><th>${esc(t('method.role'))}</th><th>${esc(t('method.thisData'))}</th></tr></thead>
        <tbody>
          ${(state.cat.catalog.domains || [])
            .map(
              (dom) =>
                `<tr><td>${esc(t('method.l1'))}</td><td>${esc(dom.label)} — ${esc(dom.description)}</td><td>${state.cat
                  .arenasOf(dom.id)
                  .map((a) => esc(a.label))
                  .join(' · ')}</td></tr>`,
            )
            .join('')}
          <tr><td>${esc(t('method.l2'))}</td><td>${esc(t('method.l2role'))}</td><td>${(state.cat.catalog.categories || [])
            .map((c) => esc(c.label))
            .join(' · ')}</td></tr>
          <tr><td>${esc(t('method.l3'))}</td><td>${esc(t('method.l3role'))}</td><td>${(state.cat.catalog.arenas || []).map((a) => esc(a.label)).join(' · ')}</td></tr>
          <tr><td>${esc(t('method.l4'))}</td><td>${esc(t('method.l4role'))}</td><td>${esc(t('method.l4data'))}</td></tr>
        </tbody>
      </table></div>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">B</span><h3>${esc(t('method.b.title'))}</h3></div>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>${esc(t('method.b.axis'))}</th><th>${esc(t('method.b.what'))}</th><th>${esc(t('method.b.default'))}</th></tr></thead>
        <tbody>
          ${axes
            .map(
              (axis) =>
                `<tr><td>${esc(labeled('axis', axis.key, axis.label))}${axis.profile_scoped ? ` <span class="muted">${esc(t('method.b.profileOnly'))}</span>` : ''}</td><td>${
                  axisWhy[axis.key] || ''
                }</td><td>${pct(axis.default_weight ?? 0)}</td></tr>`,
            )
            .join('')}
        </tbody>
      </table></div>
      <p class="m-sec-note">${t('method.b.note1')}</p>
      <p class="m-sec-note">${t('method.b.note2')}</p>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">B2</span><h3>${esc(t('method.b2.title'))}</h3></div>
      <p class="m-sec-note">${t('method.b2.note1')}</p>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>${esc(t('method.b2.sample'))}</th><th>${esc(t('method.b2.grade'))}</th><th>${esc(t('method.b2.use'))}</th></tr></thead>
        <tbody>
          <tr><td>${esc(t('method.b2.r1a'))}</td><td>${esc(t('method.b2.r1b'))}</td><td>${esc(t('method.b2.r1c'))}</td></tr>
          <tr><td>${esc(t('method.b2.r2a'))}</td><td>${esc(t('method.b2.r2b'))}</td><td>${esc(t('method.b2.r2c'))}</td></tr>
          <tr><td>${esc(t('method.b2.r3a'))}</td><td>${esc(t('method.b2.r3b'))}</td><td>${esc(t('method.b2.r3c'))}</td></tr>
          <tr><td>${esc(t('method.b2.r4a'))}</td><td>${esc(t('method.b2.r4b'))}</td><td>${esc(t('method.b2.r4c'))}</td></tr>
        </tbody>
      </table></div>
      <p class="m-sec-note">${t('method.b2.note2')}</p>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">C</span><h3>${esc(t('method.c.title'))}</h3></div>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>${esc(t('method.c.grade'))}</th><th>${esc(t('method.c.def'))}</th></tr></thead>
        <tbody>
          <tr><td><span class="chip chip--A">A</span></td><td>${esc(t('method.c.a'))}</td></tr>
          <tr><td><span class="chip chip--B">B</span></td><td>${esc(t('method.c.b'))}</td></tr>
          <tr><td><span class="chip chip--C">C</span></td><td>${esc(t('method.c.c'))}</td></tr>
          <tr><td><span class="chip chip--muted">⚪</span></td><td>${esc(t('method.c.none'))}</td></tr>
        </tbody>
      </table></div>
      <p class="m-sec-note">${esc(t('method.c.note'))}</p>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">D</span><h3>${esc(t('method.d.title'))}</h3></div>
      <p class="m-sec-note">${t('method.d.note1')}</p>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>${esc(t('method.d.impact'))}</th><th>${esc(t('method.d.means'))}</th><th>${esc(t('method.d.verdict'))}</th></tr></thead>
        <tbody>
          <tr><td><span class="pill pill--ok">none</span></td><td>${esc(t('method.d.none'))}</td><td>${esc(t('method.d.noneV'))}</td></tr>
          <tr><td><span class="pill pill--sea">optional</span></td><td>${esc(t('method.d.optional'))}</td><td>${t('method.d.optionalV')}</td></tr>
          <tr><td><span class="pill pill--bad">core</span></td><td>${esc(t('method.d.core'))}</td><td>${esc(t('method.d.coreV'))}</td></tr>
        </tbody>
      </table></div>
      <p class="m-sec-note">${t('method.d.note2')}</p>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">E</span><h3>${esc(t('method.e.title'))}</h3></div>
      <ol class="rules rules--static">${rules
        .map((rule, i) => `<li class="${i === 0 ? 'is-active' : ''}" title="${esc(calcRuleText(i) || rule)}">${esc(calcRuleText(i) || rule)}</li>`)
        .join('')}</ol>
      <p class="m-sec-note">${t('method.e.note')}</p>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">F</span><h3>${esc(t('method.f.title'))}</h3></div>
      <div class="callout callout--ok">
        ${t('method.f.body')}
      </div>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">G</span><h3>${esc(t('method.g.title'))}</h3></div>
      <dl class="kv kv--glossary">
        <dt>${esc(t('method.g.evidence'))}</dt><dd>${esc(t('method.g.evidenceD'))}</dd>
        <dt>${esc(t('method.g.hard'))}</dt><dd>${esc(t('method.g.hardD'))}</dd>
        <dt>${esc(t('method.g.optional'))}</dt><dd>${esc(t('method.g.optionalD'))}</dd>
        <dt>${esc(t('method.g.core'))}</dt><dd>${esc(t('method.g.coreD'))}</dd>
        <dt>${esc(t('method.g.strictmon'))}</dt><dd>${esc(t('method.g.strictmonD'))}</dd>
        <dt>${esc(t('method.g.strict'))}</dt><dd>${esc(t('method.g.strictD'))}</dd>
        <dt>${esc(t('method.g.exempt'))}</dt><dd>${esc(t('method.g.exemptD'))}</dd>
        <dt>${esc(t('method.g.sample'))}</dt><dd>${esc(t('method.g.sampleD'))}</dd>
        <dt>${esc(t('method.g.privacy'))}</dt><dd>${esc(t('method.g.privacyD'))}</dd>
        <dt>${esc(t('method.g.arena'))}</dt><dd>${esc(t('method.g.arenaD'))}</dd>
        <dt>${esc(t('method.g.unknown'))}</dt><dd>${esc(t('method.g.unknownD'))}</dd>
        <dt>${esc(t('method.g.stale'))}</dt><dd>${esc(t('method.g.staleD', { n: contract().freshness?.review_after_days ?? 180 }))}</dd>
      </dl>
    </section>`;
}

function openMethod() {
  $('methodBackdrop').hidden = false;
  document.body.style.overflow = 'hidden';
  $('methodModal').focus({ preventScroll: true });
}

function closeMethod() {
  $('methodBackdrop').hidden = true;
  document.body.style.overflow = '';
}

/* ------------------------------------------------------------------ 등대(Lighthouse) v3
   4분야(게임 · 애니 · 영화 · 만화)와 전체 랜덤을 한 등대로 묶는다. 분야마다 흐름이 다르고
   (게임만 플랫폼·가격을 묻는다), 한 번 받은 목표는 분야와 상관없이 딱 하나만 잠긴다. */

function toggleBookmark(id) {
  if (!recordById(id)) return;
  const at = state.bookmarks.indexOf(id);
  if (at >= 0) state.bookmarks.splice(at, 1);
  else state.bookmarks.push(id);
  writeStore(LS.bookmarks, state.bookmarks);
  renderDatasetChip();
  document.querySelectorAll(`[data-bookmark="${id}"]`).forEach((el) => {
    if (el.tagName === 'BUTTON' && el.classList.contains('icon-btn')) {
      const on = state.bookmarks.includes(id);
      el.classList.toggle('is-on', on);
      el.setAttribute('aria-pressed', String(on));
      el.textContent = on ? '★' : '☆';
    } else if (el.tagName === 'BUTTON') {
      const on = state.bookmarks.includes(id);
      el.classList.toggle('is-on', on);
      el.setAttribute('aria-pressed', String(on));
      el.textContent = on ? t('bookmark.on') : t('bookmark.off');
    }
  });
  if (state.route.view === 'home' && $('bookmarkSection')) {
    const list = $('bookmarkSection').querySelector('.bookmark-list');
    const hint = $('bookmarkHint');
    if (hint) hint.textContent = t('home.bookmarkHint', { n: state.bookmarks.length });
    if (list) {
      list.innerHTML = state.bookmarks.length
        ? state.bookmarks.map((bid) => recordById(bid)).filter(Boolean).map(bookmarkRowHtml).join('')
        : `<p class="empty">${esc(t('home.bookmarkEmpty'))}</p>`;
    }
  }
  toast(state.bookmarks.includes(id) ? t('toast.bookmarkAdd') : t('toast.bookmarkRemove'));
}

async function copyShare(id) {
  const rec = recordById(id);
  if (!rec) return;
  const arenaId = state.route.arena || rec.arenas[0];
  let pool = state.store.get(arenaId);
  if (!pool) pool = await state.store.load(arenaId);
  const item = pool.find((row) => row.id === id);
  if (!item) return;
  const view = computeViews([item])[0];
  const text = engine.summaryText(view.item, view.recordTier, view.recordEval, {
    url: `${location.origin}${location.pathname}?domain=${rec.domain}&arena=${rec.arenas[0]}&item=${rec.id}`,
  });
  const ok = await writeClipboard(text);
  toast(ok ? t('toast.shareCopied') : t('toast.shareFail'), ok ? '' : text);
}

async function copyDeepLink() {
  // 지금 보고 있는 화면의 딥링크를 그대로 복사한다(도메인·비교군·항목·프리셋·필터 포함).
  const url = `${location.origin}${location.pathname}${location.search}`;
  const ok = await writeClipboard(url);
  toast(ok ? t('toast.linkCopied') : t('toast.linkFail'), ok ? '' : url);
}

async function writeClipboard(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fallthrough */
  }
  try {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  } catch {
    return false;
  }
}

let toastTimer = null;

export function toast(message, detail) {
  const el = $('toast');
  if (!el) return;
  el.textContent = message + (detail ? `\n${detail}` : '');
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.hidden = true;
  }, 3200);
}

/* ------------------------------------------------------------------ 이벤트 */

function bindEvents() {
  document.addEventListener('click', onClick);
  document.addEventListener('keydown', onKeydown);
  document.addEventListener('input', onInput);
  document.addEventListener('change', onChange);
  $('themeToggle')?.addEventListener('click', toggleTheme);
  $('tuneBtn')?.addEventListener('click', () => ($('tuneDrawer').hidden ? openTune() : closeTune()));
  $('tuneClose')?.addEventListener('click', closeTune);
  $('tuneBackdrop')?.addEventListener('click', closeTune);
  $('methodBtn')?.addEventListener('click', openMethod);
  $('methodClose')?.addEventListener('click', closeMethod);
  $('methodBackdrop')?.addEventListener('mousedown', (event) => {
    if (event.target === $('methodBackdrop')) closeMethod();
  });
  $('lhAdBackdrop')?.addEventListener('mousedown', (event) => {
    if (event.target === $('lhAdBackdrop')) lhCloseAd();
  });
  $('lhAdClose')?.addEventListener('click', lhCloseAd);
  $('lhAdSkip')?.addEventListener('click', () => {
    if (!$('lhAdSkip').disabled) lhSkipComplete();
  });
  $('bookmarkBtn')?.addEventListener('click', async () => {
    if (state.route.view !== 'home') await goHome();
    $('bookmarkSection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  // 로고는 언제나 등대(첫 화면)로 돌아온다 — 페이지를 새로 받지 않고 화면만 바꿔 퀘스트 잠금·기록을 그대로 둔다.
  document.querySelector('.brand')?.addEventListener('click', (event) => {
    event.preventDefault();
    goLighthouse();
  });
  $('modalBackdrop')?.addEventListener('mousedown', (event) => {
    if (event.target === $('modalBackdrop')) closeDetail();
  });
  $('compareOpen')?.addEventListener('click', () => {
    if (state.route.compare.length >= 2) navigate({ view: 'compare' });
  });
  $('compareClear')?.addEventListener('click', clearCompare);
  window.addEventListener('popstate', () => {
    const urlLang = new URLSearchParams(location.search).get('lang');
    if ((urlLang === 'en' || urlLang === 'ko') && urlLang !== state.lang) {
      switchLang(urlLang);
      return;
    }
    applyUrl();
  });
  $('langToggle')?.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-lang]');
    if (btn) switchLang(btn.dataset.lang);
  });
}

async function onClick(event) {
  const target = event.target;

  // 등대 — 위저드 단계 이동·분야 선택·조건 선택·추첨·완료·광고 슬롯·상세 열기
  const lhGoto = target.closest('[data-lh-goto]');
  if (lhGoto) {
    const to = lhGoto.dataset.lhGoto;
    lhSetStep(to === LH_PLEDGE || to === LH_CATEGORY ? to : Number(to));
    return;
  }
  const lhCat = target.closest('[data-lh-cat]');
  if (lhCat) {
    lhPick('category', lhCat.dataset.lhCat);
    return;
  }
  const lhOath = target.closest('[data-lh-oath]');
  if (lhOath) {
    // 체크 없이는 서약할 수 없다 — 버튼이 disabled 라 보통은 닿지 않는다.
    if (lhOath.disabled || !state.lh.pledgeAccepted) {
      document.querySelector('[data-lh-oath-check]')?.focus?.({ preventScroll: true });
      return;
    }
    lhSetStep(LH_CATEGORY);
    return;
  }
  const lhPickBtn = target.closest('[data-lh-pick]');
  if (lhPickBtn) {
    lhPick(lhPickBtn.dataset.lhPick, lhPickBtn.dataset.lhValue);
    return;
  }
  const lhDrawBtn = target.closest('[data-lh-draw]');
  if (lhDrawBtn) {
    if (!lhDrawBtn.disabled) lhDraw();
    return;
  }
  const lhDone = target.closest('[data-lh-complete]');
  if (lhDone) {
    lhComplete();
    return;
  }
  const lhAd = target.closest('[data-lh-ad]');
  if (lhAd) {
    lhOpenAd();
    return;
  }
  const lhDetail = target.closest('[data-lh-detail]');
  if (lhDetail) {
    event.preventDefault();
    openLighthouseDetail(lhDetail.dataset.lhDetail);
    return;
  }

  // 보관함·비교·공유 같은 카드 내부 버튼이 카드 열기를 가로채지 않게 먼저 처리
  const bookmark = target.closest('[data-bookmark]');
  if (bookmark) {
    event.stopPropagation();
    toggleBookmark(bookmark.dataset.bookmark);
    return;
  }
  const compareChip = target.closest('button[data-compare]');
  if (compareChip) {
    event.stopPropagation();
    toggleCompare(compareChip.dataset.compare);
    return;
  }
  const presetBtn = target.closest('[data-preset]');
  if (presetBtn) {
    event.stopPropagation();
    applyPreset(presetBtn.dataset.preset);
    return;
  }
  const share = target.closest('[data-share]');
  if (share) {
    event.preventDefault();
    copyShare(share.dataset.share);
    return;
  }
  const copyLinkBtn = target.closest('[data-copy-link]');
  if (copyLinkBtn) {
    event.preventDefault();
    copyDeepLink();
    return;
  }
  const domainChip = target.closest('[data-home-domain]');
  if (domainChip) {
    event.preventDefault();
    setHomeDomain(domainChip.dataset.homeDomain);
    return;
  }
  if (target.closest('label.compare-check')) return;

  const action = target.closest('[data-action]');
  if (action) {
    const kind = action.dataset.action;
    if (kind === 'catalog') {
      event.preventDefault();
      return goHome();
    }
    if (kind === 'lighthouse') return goLighthouse();
    if (kind === 'domain') return navigate({ view: 'browse', domain: action.dataset.domain, category: null });
    if (kind === 'category') return navigate({ domain: action.dataset.domain, category: action.dataset.category });
    if (kind === 'arena')
      return navigate({ domain: action.dataset.domain, arena: action.dataset.arena, view: 'browse' });
    if (kind === 'item') {
      event.preventDefault();
      return openDetail(action.dataset.item);
    }
    if (kind === 'open-method') return openMethod();
    if (kind === 'open-tune') return openTune();
    if (kind === 'reset-filters') {
      state.enabledFilters = [...(contract().default_enabled_filters || [])];
      state.preset = 'balanced';
      state.weights = { ...engine.defaultWeights(contract()) };
      state.strictMonetization = contract().monetization_impact?.strict_toggle?.default === true;
      state.strict = contract().evidence_rules?.strict_evidence_default !== false;
      savePrefs();
      buildTuneBody();
      refreshAfterSettingChange({ filters: true });
      return;
    }
    if (kind === 'clear-search') {
      state.query = '';
      const input = $('homeSearch');
      if (input) input.value = '';
      renderHomeSearch();
      return;
    }
    if (kind === 'open-compare') return navigate({ view: 'compare' });
    if (kind === 'clear-compare') return clearCompare();
    if (kind === 'share-state') {
      writeClipboard(location.href).then((ok) => toast(ok ? t('toast.criteriaCopied') : t('toast.copyFail'), location.href));
      return;
    }
    if (kind === 'close-tune') return closeTune();
  }

  const itemEl = target.closest('[data-item]');
  if (itemEl) return openDetail(itemEl.dataset.item);

  if (target.closest('#modalClose')) return closeDetail();
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    if (!$('lhAdBackdrop')?.hidden) return lhCloseAd();
    if (!$('methodBackdrop')?.hidden) return closeMethod();
    if (!$('modalBackdrop')?.hidden) return closeDetail();
    if (!$('tuneDrawer')?.hidden) return closeTune();
  }
  if (event.key === 'Tab') {
    if (!$('lhAdBackdrop')?.hidden) return trapFocus(event, $('lhAdModal'));
    if (!$('modalBackdrop')?.hidden) return trapFocus(event, $('modal'));
    if (!$('methodBackdrop')?.hidden) return trapFocus(event, $('methodModal'));
  }
  const card = event.target.closest?.('[data-item]');
  if (card && (event.key === 'Enter' || event.key === ' ')) {
    event.preventDefault();
    openDetail(card.dataset.item);
  }
}

function trapFocus(event, root) {
  const focusables = Array.from(
    root.querySelectorAll('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])'),
  ).filter((el) => el.offsetParent !== null);
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (event.shiftKey && (document.activeElement === first || document.activeElement === root)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function onInput(event) {
  const target = event.target;
  if (target.id === 'homeSearch') {
    state.query = target.value;
    renderHomeSearch();
  } else if (target.id === 'arenaSearch') {
    state.query = target.value;
    renderArenaResults();
  } else if (target.matches?.('input[type="range"][data-axis]')) {
    state.weights[target.dataset.axis] = Number(target.value);
    state.preset = detectPreset() || 'custom';
    renderWeights();
    savePrefs();
    refreshAfterSettingChange();
  }
}

function onChange(event) {
  const target = event.target;
  if (target.matches?.('input[data-lh-oath-check]')) {
    state.lh.pledgeAccepted = Boolean(target.checked);
    document.querySelector('.lh--pledge')?.classList.toggle('is-sworn', state.lh.pledgeAccepted);
    const go = document.querySelector('[data-lh-oath]');
    if (go) go.disabled = !state.lh.pledgeAccepted;
    return;
  }
  if (target.matches?.('input[data-compare]')) {
    toggleCompare(target.dataset.compare);
    return;
  }
  if (target.matches?.('input[data-filter]')) {
    const key = target.dataset.filter;
    if (target.checked && !state.enabledFilters.includes(key)) state.enabledFilters.push(key);
    if (!target.checked) state.enabledFilters = state.enabledFilters.filter((k) => k !== key);
    savePrefs();
    updateTuneMeta();
    refreshAfterSettingChange({ filters: true });
    return;
  }
  if (target.id === 'strictToggle') {
    state.strict = target.checked;
    savePrefs();
    updateTuneMeta();
    refreshAfterSettingChange();
    return;
  }
  if (target.id === 'strictMonetizationToggle') {
    state.strictMonetization = target.checked;
    savePrefs();
    updateTuneMeta();
    refreshAfterSettingChange();
    return;
  }
  if (target.id === 'sort') {
    state.sort = target.value;
    renderArenaResults();
    return;
  }
  if (target.id === 'showAvoided') {
    state.showAvoided = target.checked;
    renderArenaResults();
  }
}

function clearCompare() {
  state.route.compare = [];
  const target = state.route.view === 'compare' ? { view: 'browse' } : {};
  state.route = { ...state.route, ...target };
  render({ replace: true });
}

/* ------------------------------------------------------------------ 오류 UI */

function renderFatal(err) {
  $('view').innerHTML = `
    <div class="error-banner">
      <strong>${esc(t('error.data'))}</strong>
      <span>${esc(err?.message || err)}</span>
      <span>${t('error.fileHint')}</span>
    </div>`;
  $('datasetChip').textContent = t('dataset.none');
}

init();

init();
