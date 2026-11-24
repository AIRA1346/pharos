/**
 * Pharos 웹 MVP — 화면 조립과 상호작용.
 * 계산은 전부 engine.js(= x-pharos.client 계약)로 넘긴다. 이 파일은 DOM·상태만 다룬다.
 */
import * as engine from './engine.js';

// 모듈이 실행되었다면 HTTP 로 열린 것이다. file:// 안내 문구를 즉시 치운다.
document.getElementById('bootNote')?.remove();

// 배포 단위는 web/ 폴더 하나다 — 데이터·스키마 사본도 web/ 안에 둔다(scripts/sync_web_data.py 로 원본과 동기화).
const DATA_URL = './data/items.json';
const SCHEMA_URL = './schema/item.schema.json';
const THEME_KEY = 'pharos-theme';

const PRESETS = [
  {
    id: 'balanced',
    label: '균형 기본',
    weights: { user_rating: 40, objective: 35, ai_review: 25 },
    hint: '사용자 40 · 객관 35 · AI 25',
  },
  {
    id: 'popular',
    label: '대중 평가 중심',
    weights: { user_rating: 60, objective: 25, ai_review: 15 },
    hint: '최근 리뷰가 좋은 것을 먼저',
  },
  {
    id: 'comfort',
    label: '쾌적성·노과금 중심',
    weights: { user_rating: 20, objective: 60, ai_review: 20 },
    hint: '광고·과금·유지보수를 무겁게',
  },
  {
    id: 'ai',
    label: 'AI 완성도 중심',
    weights: { user_rating: 20, objective: 25, ai_review: 55 },
    hint: '본질·완성도·정직성 위주',
  },
];

const FLAG_LABEL = {
  contains_ads: '앱 내 광고 포함',
  gacha_random_items: '확률형 아이템',
  forced_ad_before_use: '강제 전면 광고',
  bait_ad: '미끼형 유입 광고',
  p2w: 'P2W(과금이 승패를 좌우)',
  iap_required_to_progress: '과금 없이 진행 불가',
  subscription_required: '구독 필수',
  account_required: '계정 필수',
  stale_over_12m: '12개월 이상 방치',
  data_collected: '과도한 데이터 수집',
  data_export: '데이터 내보내기',
};

const VERIFICATION_LABEL = {
  direct: '직접 확인',
  reported_only: '3자 서술',
  inferred: '정황 추론',
  absent: '부재 근거',
};

const EXPORT_LABEL = { full: '전체', partial: '부분', none: '불가', unknown: '미확인' };

const METHOD_LABEL = { desk_research: '데스크 리서치', hands_on: '직접 사용', mixed: '혼합' };

const TAG_LABEL = {
  'local-first': '로컬 우선(내 파일·내 기기)',
  'minimal-ui': '최소한의 UI',
  'one-time-purchase': '1회 구매',
  'no-account': '계정 불필요',
  'no-ads': '광고 없음',
  'single-player': '싱글플레이',
  markdown: 'Markdown 파일',
  'file-ownership': '파일 소유권',
  'cloud-sync': '클라우드 동기화',
  'ai-features': 'AI 기능',
  subscription: '구독형',
  gacha: '확률형 아이템',
  p2w: 'P2W',
  'server-competitive': '서버 경쟁',
  'always-online': '상시 접속',
};

const RULE_INDEX = { 1: 0, '1w': 0, '1c': 6, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5 };

// 화면용 판정 규칙 문구. 계약의 원문(x-pharos.client.verdict_rules)은 title 로 그대로 남긴다.
const RULE_TEXT_KO = [
  '켜진 하드 필터에 하나라도 걸리면 거름. (완화 모드에서 등급 C 근거만 있으면 조건부 경고)',
  '🔴 신호가 2개 이상이면 거름',
  '🔴 신호가 1개면 조건부',
  '🟡 신호가 2개 이상이면 조건부',
  '점수 80 이상이고 🟡가 1개 이하면 추천',
  '그 외에는 조건부',
  '완결작 면제에 보안·OS 호환성 신호가 붙으면 추천 대신 조건부 경고',
];

const state = {
  schema: null,
  contract: null,
  items: [],
  weights: {},
  enabledFilters: [],
  strict: true,
  category: 'all',
  arena: 'all',
  query: '',
  sort: 'score',
  showAvoided: true,
  openId: null,
  theme: 'dark',
};

const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const safeUrl = (url) => (/^https?:\/\//i.test(String(url || '')) ? url : null);
const pct = (num) => `${Math.round(num * 100)}%`;

/* --------------------------------------------------------------- 초기화 */

function initTheme() {
  let stored = null;
  try {
    stored = localStorage.getItem(THEME_KEY);
  } catch {
    stored = null;
  }
  // 등대 테마는 다크를 기본값으로 두고, 사용자가 토글로 라이트를 고를 수 있게 한다.
  state.theme = stored === 'light' || stored === 'dark' ? stored : 'dark';
  applyTheme();
}

function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
  const toggle = $('themeToggle');
  if (!toggle) return;
  toggle.setAttribute('aria-pressed', state.theme === 'dark' ? 'true' : 'false');
  const label = $('themeLabel');
  if (label) label.textContent = state.theme === 'dark' ? '다크' : '라이트';
}

function toggleTheme() {
  state.theme = state.theme === 'dark' ? 'light' : 'dark';
  try {
    localStorage.setItem(THEME_KEY, state.theme);
  } catch {
    /* 저장 실패는 무시 */
  }
  applyTheme();
}

async function loadJson(url) {
  const res = await fetch(url, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`${url} → HTTP ${res.status}`);
  return res.json();
}

async function init() {
  initTheme();
  $('themeToggle').addEventListener('click', toggleTheme);

  try {
    const [items, schema] = await Promise.all([loadJson(DATA_URL), loadJson(SCHEMA_URL)]);
    state.items = Array.isArray(items) ? items : [items];
    state.schema = schema;
    state.contract = schema?.['x-pharos']?.client;
    if (!state.contract) throw new Error('스키마에 x-pharos.client 계산 계약이 없습니다.');
  } catch (err) {
    renderFatal(err);
    return;
  }

  const axes = state.contract.axes || [];
  state.weights = Object.fromEntries(axes.map((def) => [def.key, Math.round((def.default_weight ?? 0) * 100)]));
  state.enabledFilters = [...(state.contract.default_enabled_filters || [])];
  state.strict = state.contract.evidence_rules?.strict_evidence_default !== false;

  buildWeightControls();
  buildFilterControls();
  buildArenaControls();
  buildCategoryControls();
  bindListControls();
  bindStrictControl();
  bindMobileControls();
  bindModalControls();
  renderDatasetChip();
  renderAll();

  // 검증·디버깅용 훅 (계산 결과를 브라우저 콘솔에서 그대로 확인할 수 있다)
  window.Pharos = {
    engine,
    state,
    getViews: computeViews,
    openItem: openModal,
    setArena: (id) => {
      state.arena = id;
      renderAll();
    },
  };
}

/* ------------------------------------------------------------- 컨트롤 UI */

function scoringAxes() {
  return (state.contract?.axes || []).filter((def) => !def.profile_scoped);
}

function buildWeightControls() {
  const wrap = $('weights');
  const axes = scoringAxes();
  wrap.innerHTML = axes
    .map(
      (def, index) => `
      <div class="weight">
        <div class="weight-head">
          <span class="weight-name">${esc(def.label)}<small>축 ${index + 1}</small></span>
          <span class="weight-pct" id="pct-${esc(def.key)}">—</span>
        </div>
        <input type="range" id="range-${esc(def.key)}" min="0" max="100" step="5"
               value="${Math.round((def.default_weight ?? 0) * 100)}"
               data-axis="${esc(def.key)}" aria-label="${esc(def.label)} 가중치" />
        <div class="weight-meta">
          <span>기본 ${pct(def.default_weight ?? 0)}</span>
          <span id="meta-${esc(def.key)}">w = 0.00</span>
        </div>
      </div>`,
    )
    .join('');

  wrap.querySelectorAll('input[type="range"]').forEach((input) => {
    input.addEventListener('input', () => {
      state.weights[input.dataset.axis] = Number(input.value);
      renderWeights();
      renderAll();
    });
  });

  $('presets').innerHTML = PRESETS.map(
    (preset) => `<button type="button" class="preset" data-preset="${esc(preset.id)}" title="${esc(preset.hint)}">${esc(preset.label)}</button>`,
  ).join('');

  $('presets').addEventListener('click', (event) => {
    const btn = event.target.closest('[data-preset]');
    if (!btn) return;
    const preset = PRESETS.find((p) => p.id === btn.dataset.preset);
    if (!preset) return;
    for (const [key, value] of Object.entries(preset.weights)) {
      if (key in state.weights) state.weights[key] = value;
    }
    syncSliderValues();
    renderWeights();
    renderAll();
  });

  renderWeights();
}

function syncSliderValues() {
  for (const [key, value] of Object.entries(state.weights)) {
    const input = $(`range-${key}`);
    if (input) input.value = String(value);
    const pctEl = $(`pct-${key}`);
    if (pctEl) pctEl.textContent = `${value}%`;
  }
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
    const preset = PRESETS.find((p) => p.id === btn.dataset.preset);
    const active =
      preset &&
      Object.entries(preset.weights).every(([key, value]) => Number(state.weights[key]) === value);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
}

function buildFilterControls() {
  const defaults = state.contract.default_enabled_filters || [];
  const filters = state.contract.hard_filters || [];
  const wrap = $('filters');
  const row = (def, isDefault) => `
      <label class="filter${isDefault ? ' is-default' : ''}">
        <input type="checkbox" data-filter="${esc(def.key)}" ${state.enabledFilters.includes(def.key) ? 'checked' : ''} />
        <span class="filter-text">
          <span class="filter-name">${esc(def.label)}</span>
          <span class="filter-meta">${isDefault ? '기본 · ' : ''}${esc(def.key)}</span>
        </span>
      </label>`;
  const defaultDefs = filters.filter((def) => defaults.includes(def.key));
  const extraDefs = filters.filter((def) => !defaults.includes(def.key));
  const extraOpen = extraDefs.some((def) => state.enabledFilters.includes(def.key));
  wrap.innerHTML =
    defaultDefs.map((def) => row(def, true)).join('') +
    (extraDefs.length
      ? `<details class="filter-extra" ${extraOpen ? 'open' : ''}>
           <summary>추가 필터 ${extraDefs.length}개 — 미끼형 광고·구독 필수 등</summary>
           <div class="filter-list" style="margin:6px 0 0">${extraDefs.map((def) => row(def, false)).join('')}</div>
         </details>`
      : '');

  wrap.addEventListener('change', (event) => {
    const input = event.target.closest('[data-filter]');
    if (!input) return;
    const key = input.dataset.filter;
    if (input.checked && !state.enabledFilters.includes(key)) state.enabledFilters.push(key);
    if (!input.checked) state.enabledFilters = state.enabledFilters.filter((k) => k !== key);
    renderAll();
  });

  $('resetFilters').addEventListener('click', () => {
    state.enabledFilters = [...defaults];
    wrap.querySelectorAll('[data-filter]').forEach((input) => {
      input.checked = state.enabledFilters.includes(input.dataset.filter);
    });
    renderAll();
  });
}

function arenaDefs() {
  return state.contract?.arenas || [];
}

function arenaDef(id) {
  return arenaDefs().find((arena) => arena.id === id) || null;
}

function arenaLabel(id) {
  return arenaDef(id)?.label || id;
}

function itemArenas(item) {
  return Array.isArray(item?.arenas) ? item.arenas : [];
}

/** 현재 비교군 필터를 적용한 아이템 묶음(카테고리·검색 이전 단계). */
function arenaPool() {
  if (state.arena === 'all') return state.items;
  return state.items.filter((item) => itemArenas(item).includes(state.arena));
}

function buildArenaControls() {
  const wrap = $('arenas');
  if (!wrap) return;
  const options = [
    { key: 'all', label: `전체 ${state.items.length}` },
    ...arenaDefs().map((arena) => ({
      key: arena.id,
      label: `${arena.label} ${state.items.filter((item) => itemArenas(item).includes(arena.id)).length}`,
    })),
  ];
  wrap.innerHTML = options
    .map(
      (opt) =>
        `<button type="button" data-arena="${esc(opt.key)}" aria-pressed="${state.arena === opt.key ? 'true' : 'false'}" title="${esc(arenaDef(opt.key)?.description || '모든 비교군')}">${esc(opt.label)}</button>`,
    )
    .join('');
  wrap.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-arena]');
    if (!btn) return;
    state.arena = btn.dataset.arena;
    wrap.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'));
    renderAll();
  });
}

function buildCategoryControls() {
  $('categories').addEventListener('click', (event) => {
    const btn = event.target.closest('[data-category]');
    if (!btn) return;
    state.category = btn.dataset.category;
    renderAll();
  });
}

/** 카테고리 버튼은 현재 비교군 안의 건수로 다시 그린다(비교군 전환 시 즉시 갱신). */
function renderCategoryOptions() {
  const wrap = $('categories');
  if (!wrap) return;
  const pool = arenaPool();
  const counts = new Map();
  for (const item of pool) {
    counts.set(item.category, (counts.get(item.category) || 0) + 1);
  }
  if (state.category !== 'all' && !counts.has(state.category)) state.category = 'all';
  const options = [
    { key: 'all', label: `전체 ${pool.length}` },
    ...['game', 'app'].map((key) => ({ key, label: `${engine.CATEGORY_LABEL[key] || key} ${counts.get(key) || 0}` })),
  ].filter((opt) => opt.key === 'all' || counts.has(opt.key));
  wrap.innerHTML = options
    .map(
      (opt) =>
        `<button type="button" data-category="${esc(opt.key)}" aria-pressed="${state.category === opt.key ? 'true' : 'false'}">${esc(opt.label)}</button>`,
    )
    .join('');
}

function bindListControls() {
  $('search').addEventListener('input', (event) => {
    state.query = event.target.value.trim().toLowerCase();
    renderAll();
  });
  $('sort').addEventListener('change', (event) => {
    state.sort = event.target.value;
    renderAll();
  });
  $('showAvoided').addEventListener('change', (event) => {
    state.showAvoided = event.target.checked;
    renderAll();
  });
}

function bindStrictControl() {
  const toggle = $('strictToggle');
  toggle.checked = state.strict;
  toggle.addEventListener('change', () => {
    state.strict = toggle.checked;
    renderAll();
  });
}

function bindMobileControls() {
  const controls = $('controls');
  const toggle = $('controlsToggle');
  const mq = window.matchMedia('(max-width: 720px)');
  const sync = () => {
    if (!mq.matches) {
      controls.hidden = false;
      toggle.setAttribute('aria-expanded', 'false');
      return;
    }
    controls.hidden = toggle.getAttribute('aria-expanded') !== 'true';
  };
  toggle.addEventListener('click', () => {
    const expanded = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', expanded ? 'false' : 'true');
    sync();
    if (!expanded) controls.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  mq.addEventListener?.('change', sync);
  sync();
}

/* --------------------------------------------------------- 계산 & 필터링 */

function computeViews() {
  const settings = {
    contract: state.contract,
    weights: state.weights,
    enabledFilters: state.enabledFilters,
    strict: state.strict,
  };
  return state.items.map((item) => {
    const recordTier = engine.tierById(item, item.verdict?.tier_of_record);
    const tierEvals = (item.tiers || []).map((tier) => ({
      tier,
      evaluation: engine.evaluateTier(item, tier, settings),
    }));
    const recordEval = tierEvals.find((row) => row.tier.tier_id === recordTier?.tier_id)?.evaluation
      || engine.evaluateTier(item, recordTier, settings);
    return {
      item,
      recordTier,
      recordEval,
      tierEvals,
      cheapest: engine.recommendedTier(item),
      worstGap: worstGap(item),
    };
  });
}

function worstGap(item) {
  const gaps = (item.review_snapshot?.platforms || [])
    .map((row) => engine.reviewGap(row).gap)
    .filter((gap) => typeof gap === 'number');
  return gaps.length ? Math.min(...gaps) : 0;
}

function matchesQuery(item) {
  if (!state.query) return true;
  const haystack = [
    item.name,
    ...(item.aliases || []),
    item.developer,
    ...(item.genres || []),
    ...(item.taste_tags || []),
    item.one_liner,
  ]
    .join(' ')
    .toLowerCase();
  return haystack.includes(state.query);
}

function visibleViews() {
  const views = computeViews().filter((view) => {
    if (state.arena !== 'all' && !itemArenas(view.item).includes(state.arena)) return false;
    if (state.category !== 'all' && view.item.category !== state.category) return false;
    return matchesQuery(view.item);
  });
  const sorters = {
    score: (a, b) => (b.recordEval.score ?? -1) - (a.recordEval.score ?? -1),
    'score-asc': (a, b) => (a.recordEval.score ?? 999) - (b.recordEval.score ?? 999),
    risk: (a, b) => a.worstGap - b.worstGap,
    name: (a, b) => a.item.name.localeCompare(b.item.name, 'ko'),
  };
  return views.sort(sorters[state.sort] || sorters.score);
}

/* --------------------------------------------------------------- 렌더링 */

function renderAll() {
  renderWeights();
  renderCategoryOptions();
  $('filterCount').textContent = `${state.enabledFilters.length}/${state.contract.hard_filters.length}`;
  $('strictState').textContent = state.strict ? 'ON' : 'OFF';
  $('strictHint').innerHTML = state.strict
    ? '끄면 근거가 약한(등급 C) 필터 적중은 ‘근거 약함’ 경고가 붙은 <strong>조건부</strong>로 완화됩니다.'
    : '지금은 완화 모드입니다. 등급 C 근거의 필터 적중은 거름 대신 <strong>조건부 경고</strong>로 내려갑니다.';

  const views = visibleViews();
  renderSummary(views);
  renderCards(views);

  if (state.openId) {
    const view = computeViews().find((v) => v.item.id === state.openId);
    if (view) renderModal(view);
  }
}

function renderSummary(views) {
  const counts = { recommend: 0, conditional: 0, avoid: 0 };
  let scoreSum = 0;
  let scoreCount = 0;
  for (const view of views) {
    counts[view.recordEval.verdict] = (counts[view.recordEval.verdict] || 0) + 1;
    if (typeof view.recordEval.score === 'number') {
      scoreSum += view.recordEval.score;
      scoreCount += 1;
    }
  }
  const avg = scoreCount ? (scoreSum / scoreCount).toFixed(1) : '—';
  const axes = scoringAxes();
  const normalized = engine.normalizeWeights(state.weights, axes.map((def) => def.key));
  const weightText = axes.map((def) => `${esc(def.label)} ${pct(normalized[def.key] ?? 0)}`).join(' · ');
  const arena = state.arena === 'all' ? null : arenaDef(state.arena);
  const pool = arenaPool();

  $('summary').innerHTML = `
    <div class="arena-context" id="arenaContext">
      <span class="arena-context-label">비교군</span>
      <strong>${esc(arena ? arena.label : '전체')}</strong>
      <span class="arena-context-desc">${esc(
        arena ? arena.description : '비교군을 고르면 같은 자리를 두고 겨루는 대체제끼리만 모아 비교합니다.',
      )}</span>
      <span class="arena-context-count">${views.length}건 비교 중 · 평균 ${avg}점 · ${esc(weightText)}</span>
    </div>
    <div class="stat stat--ok">
      <span class="stat-label">추천</span>
      <span class="stat-value">${counts.recommend}</span>
      <span class="stat-sub">가중 점수 80+ · 신호 양호</span>
    </div>
    <div class="stat stat--warn">
      <span class="stat-label">조건부</span>
      <span class="stat-value">${counts.conditional}</span>
      <span class="stat-sub">감수할 조건이 있음</span>
    </div>
    <div class="stat stat--bad">
      <span class="stat-label">거름</span>
      <span class="stat-value">${counts.avoid}</span>
      <span class="stat-sub">필터·신호 기준 차단</span>
    </div>
    <div class="stat stat--avg">
      <span class="stat-label">평균 가중 점수</span>
      <span class="stat-value">${avg}</span>
      <span class="stat-sub">${weightText}</span>
    </div>`;

  $('listCount').textContent = `${views.length}/${pool.length}건`;
  const pickTotal = views.filter((view) => view.recordEval.verdict !== 'avoid').length;
  $('pickCount').textContent = `${pickTotal}건 · 가중치 실시간 재계산`;
  $('pickSection').querySelector('.section-hint').title = weightText;
  const help = $('arenaHelp');
  if (help) {
    help.textContent = '비교군을 바꾸면 요약·평균도 그 묶음 기준으로 다시 계산됩니다';
    help.title = arena ? `${arena.label} — ${arena.description}` : '비교군은 같은 자리를 두고 겨루는 대체제의 묶음입니다.';
  }
}

function renderCards(views) {
  const picks = views.filter((view) => view.recordEval.verdict !== 'avoid');
  const avoided = views.filter((view) => view.recordEval.verdict === 'avoid');

  const grid = $('grid');
  grid.innerHTML = picks.map(cardHtml).join('');
  $('emptyPick').hidden = picks.length > 0;

  $('avoidGrid').innerHTML = avoided.map(cardHtml).join('');
  $('avoidCount').textContent = `${avoided.length}건`;
  const avoidSection = $('avoidSection');
  avoidSection.hidden = !state.showAvoided;
  $('emptyAvoid').hidden = avoided.length > 0;
  $('emptyAvoid').textContent =
    state.strict || state.enabledFilters.length
      ? '지금 설정에서 거름으로 내려간 항목이 없습니다.'
      : '필터가 모두 꺼져 있어 거름 항목이 없습니다.';

  grid.querySelectorAll('.card').forEach(bindCardEvents);
  $('avoidGrid').querySelectorAll('.card').forEach(bindCardEvents);
}

function bindCardEvents(card) {
  const open = () => openModal(card.dataset.id);
  card.addEventListener('click', open);
  card.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      open();
    }
  });
}

function ring(pctValue, cls) {
  const circumference = 106.814;
  const value = Math.max(0, Math.min(100, pctValue ?? 0));
  const dash = (value / 100) * circumference;
  return `<svg class="ring" viewBox="0 0 40 40" aria-hidden="true" focusable="false">
      <circle class="ring-track" cx="20" cy="20" r="17"></circle>
      <circle class="ring-value" cx="20" cy="20" r="17" stroke-dasharray="${dash.toFixed(2)} ${circumference.toFixed(2)}"></circle>
    </svg>`;
}

function lightItem(axis) {
  const meta = engine.SIGNAL_META[axis.signal] || engine.SIGNAL_META.unknown;
  return `<li class="light light--${esc(axis.signal)}${axis.profileScoped ? ' light--profile' : ''}"
              title="${esc(`${axis.label} · ${meta.label} · ${axis.score ?? '점수 없음'}점 · 근거 ${axis.evidenceGrade || '없음'}`)}">
      <span class="light-dot" aria-hidden="true"></span>
      <span class="light-label">${esc(axis.label)}</span>
      <span class="light-score">${axis.score ?? '—'}</span>
    </li>`;
}

/** 수명 단계 배지(v0.3.1) — active 는 카드에 굳이 붙이지 않고, 완결작·상태 미확인·방치만 보인다. */
function maintenanceChip(item) {
  const key = item?.maintenance_status;
  const meta = engine.MAINTENANCE_STATUS_META[key];
  if (!meta || key === 'active') return '';
  return `<span class="chip chip--maintenance chip--maintenance--${esc(meta.tone)}" title="${esc(
    item.maintenance_note || meta.desc,
  )}">${esc(meta.label)}</span>`;
}

function reasonHtml(view) {
  const evalResult = view.recordEval;
  const chips = [];
  for (const ex of evalResult.exempts) {
    chips.push(`<span class="reason-chip reason-chip--ok" title="${esc(ex.note)}">${esc(ex.label)} 면제 · 완결작</span>`);
  }
  if (evalResult.compatWarning) {
    chips.push('<span class="reason-chip reason-chip--warn">완결작 · OS 호환성 주의</span>');
  }
  for (const fail of evalResult.blocking) {
    chips.push(`<span class="reason-chip reason-chip--bad">${esc(fail.label)} <b>${esc(engine.gradeWeakest(fail.grade))}</b></span>`);
  }
  for (const fail of evalResult.weakFails) {
    chips.push(`<span class="reason-chip reason-chip--warn">근거 약함 · ${esc(fail.label)} <b>${esc(engine.gradeWeakest(fail.grade))}</b></span>`);
  }
  if (!evalResult.blocking.length && !evalResult.weakFails.length) {
    if (evalResult.verdict === 'recommend') {
      chips.push(`<span class="reason-chip reason-chip--ok">하드 필터 통과</span>`);
    } else if (evalResult.reds >= 2) {
      chips.push(`<span class="reason-chip reason-chip--bad">🔴 신호 ${evalResult.reds}개</span>`);
    } else if (evalResult.reds === 1) {
      chips.push(`<span class="reason-chip reason-chip--warn">🔴 신호 1개</span>`);
    } else if (evalResult.yellows >= 2) {
      chips.push(`<span class="reason-chip reason-chip--warn">🟡 신호 ${evalResult.yellows}개</span>`);
    } else {
      chips.push(`<span class="reason-chip">점수 ${evalResult.score?.toFixed(1) ?? '—'}</span>`);
    }
  }
  const unknownFilters = evalResult.filterChecks.filter((f) => f.enabled && f.status === 'unknown');
  if (unknownFilters.length) {
    chips.push(`<span class="reason-chip">⚪ 미확인 ${unknownFilters.length}</span>`);
  }
  const unenabledFails = evalResult.filterChecks.filter((f) => !f.enabled && f.status === 'fail');
  if (view.recordEval.verdict === 'avoid' && unenabledFails.length) {
    chips.push(`<span class="reason-chip" title="꺼진 필터에 걸린 항목: ${esc(unenabledFails.map((f) => f.label).join(', '))}">꺼진 필터 적중 ${unenabledFails.length}</span>`);
  }
  return chips.join('');
}

function cardHtml(view) {
  const { item, recordTier, recordEval, cheapest } = view;
  const verdictMeta = engine.VERDICT_META[recordEval.verdict];
  const tierBadges = [];
  if (recordTier) {
    tierBadges.push(`<span class="chip chip--tier">대표 · ${esc(recordTier.label)}</span>`);
  }
  if (cheapest && cheapest.tier_id !== recordTier?.tier_id) {
    tierBadges.push(`<span class="chip chip--path">최저 비용 · ${esc(cheapest.label)}</span>`);
  } else if (cheapest) {
    tierBadges.push(`<span class="chip chip--path">최저 비용 경로</span>`);
  }
  const platforms = (item.platforms || []).map((p) => engine.PLATFORM_LABEL[p] || p);
  // 긴 플램폼 목록이 카드 폭을 넘어 옆 카드를 침범하지 않도록 최대 4개만 보이고 나머지는 '외 N'
  const platformLabel = platforms.length > 4
    ? `${platforms.slice(0, 4).join(' · ')} 외 ${platforms.length - 4}`
    : platforms.join(' · ');
  const arenaChips = itemArenas(item)
    .map((id) => `<span class="chip chip--arena">${esc(arenaLabel(id))}</span>`)
    .join('');
  const scoreText = typeof recordEval.score === 'number' ? recordEval.score.toFixed(1) : '—';
  const scorePct = typeof recordEval.score === 'number' ? recordEval.score : 0;

  return `
  <article class="card card--${verdictMeta.tone}" role="button" tabindex="0"
           data-id="${esc(item.id)}" data-verdict="${esc(recordEval.verdict)}"
           data-score="${typeof recordEval.score === 'number' ? recordEval.score.toFixed(2) : ''}"
           aria-label="${esc(`${item.name} 상세 보기 — ${verdictMeta.label}, 가중 점수 ${scoreText}`)}">
    <header class="card-head">
      <div class="card-titles">
        <div class="chips">
          <span class="chip chip--cat">${esc(engine.CATEGORY_LABEL[item.category] || item.category)}</span>
          ${arenaChips}
          <span class="chip" title="${esc(platforms.join(' · '))}">${esc(platformLabel)}</span>
          ${maintenanceChip(item)}
        </div>
        <h3>${esc(item.name)}</h3>
        <p class="card-dev">${esc(item.developer)}${item.genres?.length ? ` · ${esc(item.genres.slice(0, 2).join(' / '))}` : ''}</p>
      </div>
      <span class="verdict verdict--${verdictMeta.tone}"><span class="v-emoji" aria-hidden="true">${verdictMeta.emoji}</span>${verdictMeta.label}</span>
    </header>

    <div class="card-mid">
      <div class="score" style="--p:${scorePct}">
        ${ring(scorePct, verdictMeta.tone)}
        <div class="score-inner">
          <span class="score-num">${scoreText}</span>
          <span class="score-cap">가중 점수</span>
        </div>
      </div>
      <ul class="lights" aria-label="축별 신호">${recordEval.axisStates.map(lightItem).join('')}</ul>
    </div>

    <p class="one-liner">${esc(recordTier?.one_liner || item.verdict?.one_liner || item.one_liner)}</p>

    <div class="tier-badges">${tierBadges.join('')}</div>

    <footer class="card-foot">
      <span class="reason">${reasonHtml(view)}</span>
      <span class="card-more">상세 →</span>
    </footer>
  </article>`;
}

function renderDatasetChip() {
  const version = state.schema?.title?.match(/v([\d.]+)/)?.[1] || state.contract?.schema_version || '?';
  const arenaCount = arenaDefs().length;
  $('datasetChip').textContent = `스키마 v${version} · ${state.items.length}건 · 비교군 ${arenaCount}`;
  $('datasetChip').title = `item.schema.json v${version} · data/items.json ${state.items.length}건 · x-pharos.client.arenas ${arenaCount}개`;
  const assessed = state.items.map((item) => item.assessed_at).filter(Boolean).sort().pop();
  $('controlsFoot').innerHTML = [
    'data/items.json',
    'schema/item.schema.json · x-pharos.client',
    assessed ? `${esc(assessed)} 기준` : '',
  ]
    .filter(Boolean)
    .join('<br>');
  $('footData').textContent = `파로스 기준표 v${state.contract?.schema_version || version} · ${state.items.length}건 · 비교군 ${arenaCount}개 · 평가 방법 데스크 리서치`;
}

/* ---------------------------------------------------------------- 모달 */

function bindModalControls() {
  $('modalClose').addEventListener('click', closeModal);
  $('modalBackdrop').addEventListener('mousedown', (event) => {
    if (event.target === $('modalBackdrop')) closeModal();
  });
  document.addEventListener('keydown', (event) => {
    if ($('modalBackdrop').hidden) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeModal();
    }
    if (event.key === 'Tab') trapFocus(event);
  });
}

let lastFocused = null;

function openModal(id) {
  const view = computeViews().find((v) => v.item.id === id);
  if (!view) return;
  state.openId = id;
  lastFocused = document.activeElement;
  renderModal(view);
  const backdrop = $('modalBackdrop');
  backdrop.hidden = false;
  document.body.style.overflow = 'hidden';
  $('modal').focus({ preventScroll: true });
  $('modalBody').scrollTop = 0;
}

function closeModal() {
  $('modalBackdrop').hidden = true;
  document.body.style.overflow = '';
  state.openId = null;
  if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus({ preventScroll: true });
  lastFocused = null;
}

function trapFocus(event) {
  const modal = $('modal');
  const focusables = Array.from(
    modal.querySelectorAll('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])'),
  ).filter((el) => el.offsetParent !== null);
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (event.shiftKey && (document.activeElement === first || document.activeElement === modal)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function renderModal(view) {
  const { item, recordTier, recordEval, tierEvals } = view;
  const verdictMeta = engine.VERDICT_META[recordEval.verdict];

  $('modalTitle').textContent = item.name;
  $('modalDev').textContent = [
    item.developer,
    item.genres?.join(' / '),
    `평가 ${item.assessed_at}`,
    METHOD_LABEL[item.method] || item.method,
  ]
    .filter(Boolean)
    .join(' · ');

  $('modalChips').innerHTML = [
    `<span class="chip chip--cat">${esc(engine.CATEGORY_LABEL[item.category] || item.category)}</span>`,
    maintenanceChip(item),
    ...itemArenas(item).map((id) => `<span class="chip chip--arena">${esc(arenaLabel(id))}</span>`),
    ...(item.platforms || []).map((p) => `<span class="chip">${esc(engine.PLATFORM_LABEL[p] || p)}</span>`),
    `<span class="chip chip--grade chip--${esc(engine.gradeWeakest(item.data_quality?.overall_grade))}">근거 ${esc(engine.gradeWeakest(item.data_quality?.overall_grade))}</span>`,
    `<span class="chip">스키마 v${esc(item.schema_version)}</span>`,
  ].join('');

  $('modalBody').innerHTML = [
    sectionVerdict(view, verdictMeta),
    sectionTiers(view),
    sectionAxes(view),
    sectionReviews(view),
    sectionMoney(view),
    sectionUpdates(view),
    sectionAi(view),
    sectionEvidence(view),
  ].join('');
}

/* --- 01 판정 요약 --- */
function sectionVerdict(view, verdictMeta) {
  const e = view.recordEval;
  const ruleText = ruleDescription(e).short;
  const signals = e.axisStates
    .map(
      (axis) =>
        `<span class="sig-pill sig-pill--${esc(axis.signal)}">${esc(engine.SIGNAL_META[axis.signal]?.emoji || '')} ${esc(axis.label)} <b>${axis.score ?? '—'}</b></span>`,
    )
    .join('');

  const filterChips = e.filterChecks
    .filter((f) => f.enabled)
    .map((f) => filterPill(f))
    .join('');

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">01</span><h3>판정 요약</h3>
      <span class="pill pill--beam">${esc(view.recordTier?.label || '대표 티어')}</span>
      ${view.cheapest ? `<span class="pill pill--sea">최저 비용 · ${esc(view.cheapest.label)}</span>` : ''}
    </div>
    <div class="verdict-hero verdict-hero--${verdictMeta.tone}">
      <div class="hero-score">
        <div class="score">${ring(e.score ?? 0, verdictMeta.tone)}
          <div class="score-inner"><span class="score-num">${e.score != null ? e.score.toFixed(1) : '—'}</span><span class="score-cap">가중 점수</span></div>
        </div>
        <span class="hero-verdict hero-verdict--${verdictMeta.tone}">${verdictMeta.emoji} ${verdictMeta.label}</span>
      </div>
      <div class="hero-body">
        <p class="hero-oneliner">${esc(view.recordTier?.one_liner || item_one_liner(view))}</p>
        <div class="hero-signals">${signals}</div>
        <p class="rule-line">판정 규칙 <b>${esc(ruleText)}</b>${e.weakFails.length ? ' · 근거 약함 경고' : ''}${
          e.unknowns ? ` · ⚪ 미확인 축 ${e.unknowns}개` : ''
        }</p>
        <div class="m-sec-note">활성 필터 점검: ${filterChips || '<span class="muted">켜진 필터 없음</span>'}</div>
      </div>
    </div>
    ${arenaNotesHtml(view.item)}
    ${(view.item.verdict?.reasons || []).length ? `<ul class="list">${view.item.verdict.reasons.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}
    ${(view.item.verdict?.condition_notes || []).length
      ? `<div class="callout callout--warn"><b>조건·주의</b><ul class="list list--muted" style="margin-top:6px">${view.item.verdict.condition_notes
          .map((note) => `<li>${esc(note)}</li>`)
          .join('')}</ul></div>`
      : ''}
    ${renderCalc(view)}
  </section>`;
}

function item_one_liner(view) {
  return view.item.verdict?.one_liner || view.item.one_liner || '';
}

/** 비교군별 핵심 비교 포인트 한 줄 — 상세 모달 01번 섹션에 고정 노출. */
function arenaNotesHtml(item) {
  const ids = itemArenas(item);
  if (!ids.length) return '';
  const notes = item.arena_notes || {};
  return `
    <div class="arena-notes">
      <p class="mini-label">비교군 메모</p>
      ${ids
        .map(
          (id) => `
        <div class="arena-note">
          <span class="chip chip--arena">${esc(arenaLabel(id))}</span>
          <p>${esc(notes[id] || '기록된 비교 포인트가 없습니다.')}</p>
        </div>`,
        )
        .join('')}
    </div>`;
}

function filterPill(check) {
  const exempt = check.status === 'exempt';
  const tone = exempt
    ? 'ok'
    : check.status === 'fail' ? (check.enabled ? 'bad' : 'warn') : check.status === 'unknown' ? 'muted' : 'ok';
  const mark = exempt ? '면제' : check.status === 'fail' ? '적중' : check.status === 'unknown' ? '미확인' : '통과';
  return `<span class="pill pill--${tone}" title="${esc(check.note)}">${check.enabled ? '' : '꺼짐 · '}${esc(check.label)} ${mark}${
    exempt ? ' · 완결작' : ''
  }${check.status === 'fail' ? ` (${esc(engine.gradeWeakest(check.grade))})` : ''}</span>`;
}

function ruleDescription(evaluation) {
  const rules = state.contract.verdict_rules || [];
  const index = RULE_INDEX[evaluation.rule] ?? 0;
  const raw = rules[index] || '';
  const clean = raw.replace(/^\s*\d+\.\s*/, '');
  const ko = RULE_TEXT_KO[index] || clean;
  const shortMap = {
    1: '① 활성 필터 적중 → 거름',
    '1w': '① 완화 모드 · 등급 C 필터 적중 → 조건부 경고',
    '1c': `⑦ 완결작 면제 · 호환성 주의 → 조건부`,
    2: `② 🔴 신호 ${evaluation.reds}개 → 거름`,
    3: '③ 🔴 신호 1개 → 조건부',
    4: `④ 🟡 신호 ${evaluation.yellows}개 → 조건부`,
    5: `⑤ 점수 ${evaluation.score?.toFixed(1)} ≥ 80·🟡 ${evaluation.yellows}개 → 추천`,
    6: '⑥ 그 외 → 조건부',
  };
  return { short: shortMap[evaluation.rule] || shortMap[6], raw: clean, index, ko };
}

function renderCalc(view) {
  const e = view.recordEval;
  const rules = (state.contract.verdict_rules || []).map((rule) => rule.replace(/^\s*\d+\.\s*/, ''));
  const activeIndex = ruleDescription(e).index;
  const contributions = e.axisStates.filter((axis) => axis.weight > 0 && axis.score != null);
  const maxPart = Math.max(...contributions.map((axis) => axis.weight * axis.score), 1);
  const calcLines = contributions
    .map(
      (axis) => `
      <div class="calc-line">
        <span class="calc-label">${esc(axis.label)} ${pct(axis.weight)}</span>
        <span class="calc-bar"><span style="width:${((axis.weight * axis.score) / maxPart) * 100}%"></span></span>
        <span class="calc-val">${axis.weight.toFixed(2)} × ${axis.score} = ${(axis.weight * axis.score).toFixed(2)}</span>
      </div>`,
    )
    .join('');

  const disabled = e.filterChecks.filter((f) => !f.enabled);

  return `
    <details class="calc-block" ${e.verdict === 'avoid' || e.weakFails.length ? 'open' : ''}>
      <summary class="calc-summary">계산 과정 보기 — 가중치 ${pct(e.denominator)} · 필터 ${e.filterChecks.filter((f) => f.enabled).length}개 · ${
        e.strict ? '엄격' : '완화'
      } 모드</summary>
      <div class="calc">
        <p class="mini-label" style="margin:10px 0 4px">② 가중 점수 (점수 없는 축은 분자·분모에서 제외)</p>
        ${calcLines || '<p class="muted">계산 가능한 축 점수가 없습니다.</p>'}
        <div class="calc-total"><span>Σ(w×s) = ${e.numerator.toFixed(2)} · Σw = ${e.denominator.toFixed(2)}</span><b>${e.score != null ? e.score.toFixed(2) : '—'}</b></div>

        <p class="mini-label" style="margin:12px 0 4px">① 하드 필터 — 티어 <code>${esc(e.tierId)}</code></p>
        <div class="tag-cloud">${e.filterChecks.filter((f) => f.enabled).map(filterPill).join('') || '<span class="muted">켜진 필터 없음</span>'}</div>
        ${e.blocking.length ? `<div class="callout callout--bad"><b>차단</b> ${e.blocking.map((f) => `${esc(f.label)}(${esc(engine.gradeWeakest(f.grade))})`).join(' · ')}</div>` : ''}
        ${e.weakFails.length ? `<div class="callout callout--warn"><b>근거 약함</b> ${e.weakFails
          .map((f) => `${esc(f.label)}(${esc(engine.gradeWeakest(f.grade))})`)
          .join(' · ')} — 완화 모드에서 조건부 경고로 처리</div>` : ''}
        ${disabled.length ? `<details><summary class="calc-summary">꺼진 필터 ${disabled.length}개 보기</summary><div class="tag-cloud" style="margin-top:6px">${disabled.map(filterPill).join('')}</div></details>` : ''}

        <p class="mini-label" style="margin:12px 0 4px">④ 판정 규칙 (위에서부터 먼저 맞는 것)</p>
        <ol class="rules">${rules
          .map(
            (rule, i) =>
              `<li class="${i === activeIndex ? 'is-active' : ''}" title="${esc(rule)}">${esc(RULE_TEXT_KO[i] || rule)}</li>`,
          )
          .join('')}</ol>
        <p class="table-note">기본 활성 세트(${esc((state.contract.default_enabled_filters || []).join(', '))}) + 엄격 모드 기준 이 티어: <b>${
          engine.defaultBlocked(view.item, view.recordTier, state.contract) ? '거름' : '통과'
        }</b> · 데이터에 기록된 판정: <b>${esc(engine.VERDICT_META[e.storedVerdict]?.label || e.storedVerdict)}</b></p>
      </div>
    </details>`;
}

/* --- 02 티어별 판정 --- */
function sectionTiers(view) {
  const rows = view.tierEvals
    .map(({ tier, evaluation }) => {
      const meta = engine.VERDICT_META[evaluation.verdict];
      const allFails = evaluation.filterChecks.filter((f) => f.status === 'fail');
      const fails = allFails.length
        ? allFails
            .map(
              (f) =>
                `${f.enabled ? '' : '<span class="muted">(꺼짐)</span> '}${esc(f.label)} <b>${esc(engine.gradeWeakest(f.grade))}</b>${f.weakGrade && !evaluation.strict ? ' <span class="muted">근거 약함</span>' : ''}`,
            )
            .join('<br>')
        : '<span class="muted">—</span>';
      return `
      <tr>
        <td class="tier-name">
          <div>${esc(tier.label)}${tier.tier_id === view.recordTier?.tier_id ? ' <span class="pill pill--beam">대표</span>' : ''}${
            tier.recommended_path ? ' <span class="pill pill--sea">최저 비용</span>' : ''
          }</div>
          <div class="source-meta">${esc(tier.tier_id)} · ${esc(engine.KIND_LABEL[tier.kind] || tier.kind)}</div>
          ${(tier.limits || []).length ? `<div class="source-meta">한도: ${esc(tier.limits.join(', '))}</div>` : ''}
        </td>
        <td>${esc(tier.price?.display || '—')}</td>
        <td>
          <span class="pill pill--${meta.tone}">${meta.emoji} ${meta.label}</span>
          <div class="source-meta">기록: ${esc(engine.VERDICT_META[evaluation.storedVerdict]?.label || evaluation.storedVerdict)}</div>
        </td>
        <td class="num">${evaluation.score != null ? evaluation.score.toFixed(1) : '—'}</td>
        <td>${fails}</td>
        <td>${esc(tier.one_liner || '')}</td>
      </tr>`;
    })
    .join('');

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">02</span><h3>티어별 판정 비교</h3>
      <span class="pill">${view.tierEvals.length}개 티어</span>
    </div>
    <p class="m-sec-note">무료·구독·1회 구매는 사실상 다른 제품입니다. 판정은 현재 가중치·필터·엄격도로 티어마다 다시 계산됩니다.</p>
    <div class="table-wrap">
      <table class="data tier-table">
        <thead><tr><th>티어</th><th>가격</th><th>판정</th><th>점수</th><th>걸린 필터</th><th>한 줄</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    ${(view.recordTier?.notes || view.recordTier?.axis_overrides)
      ? `<p class="table-note">대표 티어 메모: ${esc(view.recordTier?.notes || '')}${
          view.recordTier?.axis_overrides
            ? ` · 축 오버라이드: ${Object.entries(view.recordTier.axis_overrides)
                .map(([key, value]) => `${esc(key)} ${value.score}(사유: ${esc(value.note)})`)
                .join(' / ')}`
            : ''
        }</p>`
      : ''}
  </section>`;
}

/* --- 03 축별 신호 --- */
function sectionAxes(view) {
  const e = view.recordEval;
  const cards = e.axisStates
    .map((axis) => {
      const meta = engine.SIGNAL_META[axis.signal] || engine.SIGNAL_META.unknown;
      const base = view.item.axes?.[axis.key];
      return `
      <article class="axis-card">
        <div class="axis-card-head">
          <h4>${esc(axis.label)}${axis.profileScoped ? `<small>P1 프로필 전용</small>` : ''}</h4>
          <span class="axis-score axis-score--${esc(axis.signal)}">${axis.score ?? '—'}</span>
        </div>
        <div class="axis-meta">
          <span class="pill pill--${axis.signal === 'green' ? 'ok' : axis.signal === 'yellow' ? 'warn' : axis.signal === 'red' ? 'bad' : 'muted'}">${meta.emoji} ${meta.label}</span>
          <span class="pill">근거 ${esc(engine.gradeWeakest(axis.evidenceGrade || 'unknown'))}</span>
          <span class="pill">확신 ${esc({ high: '높음', medium: '보통', low: '낮음' }[axis.confidence] || '—')}</span>
          ${axis.source === 'tier' ? '<span class="pill pill--beam">티어 오버라이드</span>' : ''}
        </div>
        <p class="axis-summary">${esc(axis.summary || axis.note || '서술 없음')}</p>
        ${axis.overrideScore != null && axis.axisScore !== axis.overrideScore
          ? `<p class="source-meta">앱 공통 점수 ${axis.axisScore} → 이 티어 ${axis.overrideScore} (사유: ${esc(axis.note)})</p>`
          : ''}
        ${(axis.sourceIds || []).length ? `<div class="axis-meta">${sourceChips(axis.sourceIds, view.item)}</div>` : ''}
        ${base?.override_reason ? `<p class="source-meta">신호 재정의: ${esc(base.override_reason)}</p>` : ''}
      </article>`;
    })
    .join('');

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">03</span><h3>축별 신호와 근거</h3>
      <span class="pill">🟢 ≥ ${state.contract.signal_thresholds?.green_min ?? 75} · 🟡 ≥ ${state.contract.signal_thresholds?.yellow_min ?? 50}</span>
    </div>
    <div class="axis-grid">${cards}</div>
    ${view.item.one_liner ? `<p class="m-sec-note">한 줄 정의: ${esc(view.item.one_liner)}</p>` : ''}
  </section>`;
}

function sourceChips(ids, item) {
  const map = new Map((item.sources || []).map((s) => [s.id, s]));
  return ids
    .map((id) => {
      const source = map.get(id);
      if (!source) return `<span class="pill">${esc(id)}</span>`;
      const url = safeUrl(source.url);
      const title = `${source.title} (${source.type} · ${source.grade})`;
      return url
        ? `<a class="pill" href="${esc(url)}" target="_blank" rel="noopener noreferrer" title="${esc(title)}">${esc(id)} ↗</a>`
        : `<span class="pill" title="${esc(title)}">${esc(id)}</span>`;
    })
    .join('');
}

/* --- 04 리뷰 --- */
function sectionReviews(view) {
  const snapshot = view.item.review_snapshot;
  if (!snapshot) return '';
  const sample = engine.reviewSampleCheck(view.item, state.contract);
  const rows = (snapshot.platforms || [])
    .map((platform) => {
      const { cumulative, recent, gap } = engine.reviewGap(platform);
      const gapTone = gap == null ? '' : gap <= -15 ? 'bad' : gap <= -5 ? 'warn' : gap >= 5 ? 'ok' : '';
      const metricMeta = (metric) =>
        metric
          ? `${metric.window || '기간 미상'} · ${engine.reviewToHundred(metric.value, metric.scale)?.toFixed(1)}/100 · 근거 ${esc(engine.gradeWeakest(metric.evidence_grade))}`
          : '';
      const metricValue = (metric) =>
        metric
          ? `${metric.value}${metric.scale === 'percent' ? '%' : metric.scale === 'stars5' ? '★' : '/10'} <span class="muted">· ${metric.count?.toLocaleString('ko-KR') ?? '—'}건</span>`
          : '<span class="muted">없음</span>';
      return `
      <div class="review-row">
        <div class="review-top">
          <h4>${esc(engine.PLATFORM_LABEL[platform.platform] || platform.platform)}</h4>
          ${
            gap == null
              ? '<span class="review-gap">최근 구간 없음</span>'
              : `<span class="review-gap review-gap--${gapTone}">격차 <b>${gap > 0 ? '+' : ''}${gap.toFixed(1)}p</b> ${
                  gap <= -15 ? '· 최근 평가 훼손' : gap <= -5 ? '· 하락' : gap >= 5 ? '· 개선' : '· 안정'
                }</span>`
          }
        </div>
        <div class="review-bars">
          <div class="bar-row">
            <span class="bar-label">누적</span>
            <span class="bar-track"><span class="bar-fill bar-fill--cum" style="width:${Math.max(0, Math.min(100, cumulative ?? 0))}%"></span></span>
            <span class="bar-value">${metricValue(platform.cumulative)}</span>
          </div>
          <div class="bar-row">
            <span class="bar-label">최근</span>
            <span class="bar-track"><span class="bar-fill bar-fill--recent" style="width:${Math.max(0, Math.min(100, recent ?? 0))}%"></span></span>
            <span class="bar-value">${metricValue(platform.recent)}</span>
          </div>
        </div>
        <p class="review-meta">누적 · ${metricMeta(platform.cumulative)}</p>
        ${platform.recent ? `<p class="review-meta">최근 · ${metricMeta(platform.recent)}</p>` : ''}
        ${platform.note ? `<p class="money-note">${esc(platform.note)}</p>` : ''}
      </div>`;
    })
    .join('');

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">04</span><h3>누적 vs 최근 리뷰</h3>
      <span class="pill ${sample.needsDowngrade ? 'pill--bad' : 'pill--ok'}">최소 표본 ${sample.min}건 ${
        sample.needsDowngrade ? `· 부족 ${sample.insufficient.length}곳` : '· 충족'
      }</span>
    </div>
    <p class="m-sec-note">5점 척도는 ×20, 10점 척도는 ×10으로 0~100에 맞춰 비교합니다. 누적값만 보면 놓치는 ‘최근 망가짐’을 겨냥합니다.</p>
    ${rows}
    ${snapshot.summary ? `<p class="money-note">${esc(snapshot.summary)}</p>` : ''}
    <div class="callout${sample.needsDowngrade ? ' callout--warn' : ''}">
      <b>표본 규칙</b> 최근 표본이 ${sample.min}건 미만이면 신호를 한 단계 낮춥니다.
      점검한 플랫폼 ${sample.checked}곳 · 하향 필요 ${sample.needsDowngrade ? '있음' : '없음'} · 데이터 ${
        sample.needsDowngrade
          ? sample.applied ? '하향 적용됨' : '하향 미적용'
          : sample.sampleSufficient ? '표본 충분(하향 미적용)' : '표본 상태 미기재'
      }
    </div>
  </section>`;
}

/* --- 05 과금·광고 --- */
function sectionMoney(view) {
  const money = view.item.monetization;
  if (!money) return '';
  const ads = money.ads || {};
  const iap = money.iap || {};
  const range = iap.price_range || {};
  const minText = engine.moneyText(range.min);
  const maxText = engine.moneyText(range.max);
  const tags = (list) => (list || []).map((type) => `<span class="pill">${esc(engine.AD_TYPE_LABEL[type] || type)}</span>`).join('');

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">05</span><h3>과금·광고 4분해</h3>
      <span class="pill ${iap.random_items === 'yes' ? 'pill--bad' : ''}">확률형 ${esc(engine.TRI_LABEL[iap.random_items] || '미확인')}</span>
      <span class="pill">IAP ${esc(engine.TRI_LABEL[iap.present] || '미확인')}</span>
    </div>
    <p class="m-sec-note">‘광고 있음/없음’ 한 칸으로는 미끼형 유입 광고 피해를 잡지 못합니다. 인앱 노출과 유입 정직성을 분리합니다.</p>
    <div class="money-grid">
      <article class="money-card">
        <h4>⑴ 인앱 광고 노출</h4>
        <div class="money-value">${esc(engine.EXPOSURE_LABEL[ads.in_app_exposure] || ads.in_app_exposure || '미확인')}</div>
        <div class="money-tags">${tags(ads.ad_types)}</div>
        <p class="money-note">스토어 광고 표기: ${ads.store_declares_ads === true ? '있음' : ads.store_declares_ads === false ? '없음' : '미확인'}</p>
      </article>
      <article class="money-card">
        <h4>⑵ 유입 광고 정직성</h4>
        <div class="money-value">${esc(engine.HONESTY_LABEL[ads.inflow_ad?.honesty] || '미평가')}</div>
        <div class="money-tags">
          <span class="pill">존재 ${esc(engine.TRI_LABEL[ads.inflow_ad?.present] || '미평가')}</span>
          <span class="pill">근거 ${esc(engine.gradeWeakest(ads.inflow_ad?.evidence_grade || 'unknown'))}</span>
        </div>
        <p class="money-note">${esc(ads.inflow_ad?.note || '평가 기록 없음')}</p>
      </article>
      <article class="money-card">
        <h4>⑶ 확률형 아이템</h4>
        <div class="money-value">${esc(engine.TRI_LABEL[iap.random_items] || '미확인')}</div>
        <div class="money-tags">
          <span class="pill">IAP 존재 ${esc(engine.TRI_LABEL[iap.present] || '미확인')}</span>
          <span class="pill">근거 ${esc(engine.gradeWeakest(iap.evidence_grade || 'unknown'))}</span>
        </div>
        <p class="money-note">확률형 여부는 스토어 표기(‘Includes Random Items’)를 그대로 지표로 씁니다 — 등급 A.</p>
      </article>
      <article class="money-card">
        <h4>⑷ IAP 최고가·첫 결제 유도</h4>
        <div class="money-value">${minText || maxText ? `${esc(minText || '?')} ~ ${esc(maxText || '?')}` : '인앱결제 없음'}</div>
        <div class="money-tags">
          <span class="pill">첫 유도 ${esc(engine.PROMPT_LABEL[iap.first_purchase_prompt] || '미확인')}</span>
          <span class="pill ${iap.p2w === 'yes' ? 'pill--bad' : ''}">P2W ${esc(engine.TRI_LABEL[iap.p2w] || '미확인')}</span>
          <span class="pill ${iap.required_to_progress === 'yes' ? 'pill--bad' : ''}">진행 필수 ${esc(engine.TRI_LABEL[iap.required_to_progress] || '미확인')}</span>
          <span class="pill">근거 ${esc(engine.gradeWeakest(range.evidence_grade || 'unknown'))}</span>
        </div>
        <p class="money-note">${esc(range.note || '가격대 기록 없음')}</p>
      </article>
    </div>
    <dl class="kv">
      <dt>구독</dt><dd>${esc(engine.TRI_LABEL[money.subscription?.present] || '미확인')} · ${esc(money.subscription?.display || '—')}</dd>
      <dt>과금 요약</dt><dd>${esc(money.summary || '—')}</dd>
    </dl>
  </section>`;
}

/* --- 06 업데이트 --- */
function sectionUpdates(view) {
  const profile = view.item.update_profile;
  if (!profile) return '';
  const meta = engine.MAINTENANCE_META[profile.maintenance_quality] || engine.MAINTENANCE_META.unknown;
  const rows = (profile.entries || [])
    .map(
      (entry) => `
      <tr>
        <td class="num">${esc(entry.date || '날짜 미상')}</td>
        <td><span class="pill">${esc(engine.UPDATE_TYPE_LABEL[entry.type] || entry.type)}</span></td>
        <td>${esc(engine.PLATFORM_LABEL[entry.platform] || entry.platform || '—')}</td>
        <td>${esc(engine.PROMISE_LABEL[entry.promise_status] || '—')}</td>
        <td>${esc(engine.gradeWeakest(entry.evidence_grade || 'unknown'))}</td>
        <td class="flag-note">${esc(entry.note || '')}</td>
      </tr>`,
    )
    .join('');

  const risky = profile.maintenance_quality === 'risky_terms' && view.worstGap <= -5;
  const lifeKey = view.item.maintenance_status;
  const life = engine.MAINTENANCE_STATUS_META[lifeKey] || null;
  const compat = view.item.flags?.compat_risk;

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">06</span><h3>업데이트 성격</h3>
      ${life ? `<span class="pill pill--${life.tone}">수명 단계 · ${esc(life.label)}</span>` : ''}
      <span class="pill pill--${meta.tone}">${esc(meta.label)}</span>
      <span class="pill">주기 ${esc(engine.CADENCE_LABEL[profile.cadence] || profile.cadence)}</span>
      <span class="pill">최근 업데이트 ${esc(profile.latest_update || '미확인')}${
        profile.latest_update_platform ? ` · ${esc(engine.PLATFORM_LABEL[profile.latest_update_platform] || profile.latest_update_platform)}` : ''
      }</span>
    </div>
    <p class="m-sec-note">‘활발한가’가 아니라 ‘무엇을 실어 나르는가’를 봅니다 — ${esc(meta.desc)}.</p>
    ${life && lifeKey !== 'active'
      ? `<div class="callout"><b>수명 단계 · ${esc(life.label)}</b> ${esc(view.item.maintenance_note || life.desc)}
          ${
            lifeKey === 'feature_complete'
              ? ' — 완결작은 <code>stale_over_12m</code> 필터가 켜져 있어도 면제(exempt)로 계산합니다. 단 보안·OS 호환성 문제가 별도 신호로 잡히면 추천 대신 조건부 경고로 내립니다.'
              : ''
          }</div>`
      : ''}
    ${risky ? '<div class="callout callout--bad"><b>경고 고정</b> 과금·약관 변경이 최근 평가 하락과 겹칩니다. 최근 업데이트 일자만으로 유지보수 신호를 🟢로 주지 않습니다.</div>' : ''}
    ${
      compat
        ? `<p class="money-note">보안·OS 호환성 신호: <b>${esc(engine.TRI_LABEL[compat.value] || compat.value)}</b> — ${esc(compat.note || '기록 없음')}</p>`
        : ''
    }
    <div class="table-wrap">
      <table class="data">
        <thead><tr><th>날짜</th><th>성격</th><th>플랫폼</th><th>공약</th><th>근거</th><th>메모</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="6" class="muted">기록된 업데이트가 없습니다.</td></tr>'}</tbody>
      </table>
    </div>
    <p class="money-note">${esc(profile.assessment || '')}</p>
  </section>`;
}

/* --- 07 AI 검토 --- */
function sectionAi(view) {
  const axis = view.item.axes?.ai_review;
  const fit = view.item.axes?.personal_fit;
  if (!axis) return '';
  const sentences = String(axis.summary || '')
    .split(/(?<=[.!?。])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 1);
  const weakHint = /(감점|단점|다만|그러나|지적|결함|지연|괴리|부담|학습|미확인|막|모자|불편|문제|경고|소모|불일치|어긋|위험)/;
  const strongHint = /(장점|강점|일치|유지|없음|무료|통과|활발|우수|선택|적합|최적|정확|깨끗|단순)/;
  const strengths = sentences.filter((s) => !weakHint.test(s) && strongHint.test(s));
  const weaknesses = sentences.filter((s) => weakHint.test(s));
  const leftovers = sentences.filter((s) => !strengths.includes(s) && !weaknesses.includes(s));

  const tagList = (view.item.taste_tags || []).map((tag) => `<span class="pill">${esc(TAG_LABEL[tag] || tag)}</span>`).join('');
  const fitSignal = fit ? engine.SIGNAL_META[fit.signal] || engine.SIGNAL_META.unknown : null;

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">07</span><h3>AI 검토 · 적합 대상</h3>
      <span class="pill">근거 ${esc(engine.gradeWeakest(axis.evidence_grade || 'unknown'))}</span>
      <span class="pill">확신 ${esc({ high: '높음', medium: '보통', low: '낮음' }[axis.confidence] || '—')}</span>
    </div>
    <div class="axis-grid">
      <article class="axis-card">
        <h4 style="color:var(--green)">강점</h4>
        ${strengths.length ? `<ul class="list list--ok">${strengths.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>` : '<p class="axis-summary muted">문장에서 뚜렷한 강점 표현을 찾지 못했습니다. 아래 원문을 참고하세요.</p>'}
      </article>
      <article class="axis-card">
        <h4 style="color:var(--red)">약점·감점</h4>
        ${weaknesses.length ? `<ul class="list list--bad">${weaknesses.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>` : '<p class="axis-summary muted">명시된 감점 요인이 없습니다.</p>'}
      </article>
      <article class="axis-card">
        <h4>적합 대상</h4>
        <p class="axis-summary">${esc(
          (view.item.taste_tags || []).length
            ? `이런 결을 원하는 사람: ${(view.item.taste_tags || []).map((t) => TAG_LABEL[t] || t).join(' · ')}`
            : '취향 태그가 기록되지 않았습니다.',
        )}</p>
        ${fit ? `<div class="axis-meta"><span class="pill pill--${fit.signal === 'green' ? 'ok' : fit.signal === 'yellow' ? 'warn' : fit.signal === 'red' ? 'bad' : 'muted'}">${fitSignal.emoji} P1 적합 ${fit.score}</span></div>
        <p class="axis-summary">${esc(fit.summary || '')}</p>` : ''}
        ${weaknesses.length ? `<p class="source-meta">맞지 않는 경우: 위 감점 요인(${esc(weaknesses.length)}건)을 감수하기 어려운 사용자.</p>` : ''}
      </article>
    </div>
    <div class="tag-cloud">${tagList}</div>
    <p class="money-note">AI 검토 원문: ${esc(axis.summary || '')}</p>
    ${leftovers.length ? `<p class="source-meta">분류 밖 문장: ${esc(leftovers.join(' '))}</p>` : ''}
  </section>`;
}

/* --- 08 근거·출처 --- */
function sectionEvidence(view) {
  const item = view.item;
  const sources = (item.sources || [])
    .map((source) => {
      const url = safeUrl(source.url);
      const grade = engine.gradeWeakest(source.grade);
      return `
      <div class="source">
        <span class="source-grade source-grade--${esc(grade)}">${esc(grade)}</span>
        <div>
          <div class="source-title">${esc(source.title)}</div>
          <div class="source-note">${esc(source.note || '')}</div>
          <div class="source-meta">${esc(source.type)} · 접근 ${esc(source.accessed_at)} · ${esc(source.id)}</div>
        </div>
        ${url ? `<a class="source-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">열기 ↗</a>` : '<span class="source-link muted">링크 없음</span>'}
      </div>`;
    })
    .join('');

  const flags = Object.entries(item.flags || {})
    .map(([key, node]) => {
      const isExport = key === 'data_export';
      const value = isExport ? EXPORT_LABEL[node.value] || node.value : engine.TRI_LABEL[node.value] || node.value;
      const tone = isExport ? 'unknown' : node.value === 'yes' ? 'yes' : node.value === 'no' ? 'no' : 'unknown';
      return `
      <tr>
        <td class="flag-name">${esc(key)}</td>
        <td>${esc(FLAG_LABEL[key] || key)}</td>
        <td><span class="flag-value flag-value--${tone}">${esc(value)}</span></td>
        <td>${esc(engine.gradeWeakest(node.evidence_grade || 'unknown'))}</td>
        <td>${esc(VERIFICATION_LABEL[node.verification] || '—')}</td>
        <td class="flag-note">${esc(node.note || '')}</td>
      </tr>`;
    })
    .join('');

  const quality = item.data_quality || {};
  const conflicts = (quality.conflicts || [])
    .map(
      (conflict) =>
        `<li><b>${esc(conflict.field)}</b> — ${esc((conflict.values || []).join(' vs '))}<br><span class="muted">해결: ${esc(conflict.resolution)}</span></li>`,
    )
    .join('');

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">08</span><h3>근거·출처</h3>
      <span class="pill pill--beam">데이터 신뢰도 ${esc(engine.gradeWeakest(quality.overall_grade || 'unknown'))}</span>
      <span class="pill">평가 방법 ${esc(METHOD_LABEL[item.method] || item.method || '—')}</span>
    </div>
    <p class="m-sec-note">등급 A=스토어·공식 직접 확인, B=언론·공식 발표 인용, C=3자 집계·개별 리뷰·커뮤니티. 복합 등급은 가장 약한 등급으로 표기합니다.</p>
    <div class="sources">${sources}</div>
    ${(quality.unverified || []).length ? `<div class="callout"><b>확인하지 못한 값</b><ul class="list list--muted" style="margin-top:6px">${quality.unverified
      .map((u) => `<li>${esc(u)}</li>`)
      .join('')}</ul></div>` : ''}
    ${conflicts ? `<div class="callout callout--warn"><b>출처 충돌</b><ul class="list" style="margin-top:6px">${conflicts}</ul></div>` : ''}
    ${quality.limitations ? `<p class="money-note">한계: ${esc(quality.limitations)}</p>` : ''}
    <details class="calc-block">
      <summary class="calc-summary">판정에 쓰인 원자료(flags) ${Object.keys(item.flags || {}).length}개</summary>
      <div class="table-wrap" style="margin-top:8px">
        <table class="data flag-table">
          <thead><tr><th>키</th><th>항목</th><th>값</th><th>근거</th><th>검증</th><th>메모</th></tr></thead>
          <tbody>${flags}</tbody>
        </table>
      </div>
    </details>
  </section>`;
}

/* --------------------------------------------------------------- 오류 UI */

function renderFatal(err) {
  const results = $('results');
  results.innerHTML = `
    <div class="error-banner">
      <strong>데이터를 불러오지 못했습니다.</strong>
      <span>${esc(err?.message || err)}</span>
      <span>이 페이지는 <code>index.html</code>을 파일로 직접 열면 <code>fetch</code>가 차단됩니다. <code>projects/pharos/web</code> 폴더에서
      <code>python3 -m http.server 8000</code> 을 실행한 뒤 <code>http://localhost:8000/</code> 로 접속하세요.
      (<code>data/</code>·<code>schema/</code> 사본이 없으면 <code>python3 projects/pharos/scripts/sync_web_data.py</code> 로 원본과 맞춥니다.)</span>
    </div>`;
  $('datasetChip').textContent = '데이터 없음';
  $('controlsFoot').textContent = '로드 실패';
}

init();
