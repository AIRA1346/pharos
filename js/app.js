/**
 * Pharos 웹 v2 — 4단 탐색(홈 → 도메인 → 대분류 → 비교군 → 항목)과 화면 조립.
 * 계산은 전부 engine.js(= x-pharos.client 계약)로 넘긴다. 이 파일은 상태·라우팅·DOM만 다룬다.
 *
 * 데이터
 *   - data/catalog.json       도메인·대분류·비교군 정의(어디에 무엇이 있는가)
 *   - data/search-index.json  통합 검색·홈 리포트용 경량 인덱스(모두의 요약)
 *   - data/{domain}/{arena}.json  비교군 항목 전체 — 목록·상세·비교에서만 지연 로딩
 */
import * as engine from './engine.js';
import { loadCore, createCatalogView, createArenaStore, searchRecords } from './data.js';

document.getElementById('bootNote')?.remove();

const LS = {
  theme: 'pharos-theme',
  prefs: 'pharos-prefs',
  bookmarks: 'pharos-bookmarks',
};

const PRESETS = [
  {
    id: 'balanced',
    label: '균형 기본',
    weights: { user_rating: 50, objective: 25, ai_review: 25 },
    hint: '사용자 50 · 객관 25 · AI 25',
  },
  {
    id: 'popular',
    label: '대중 평가 중심',
    weights: { user_rating: 65, objective: 20, ai_review: 15 },
    hint: '수십만~수백만 명이 매긴 평점을 가장 무겁게',
  },
  {
    id: 'comfort',
    label: '쾌적성·노과금 중심',
    weights: { user_rating: 20, objective: 60, ai_review: 20 },
    hint: '광고·과금·유지보수를 무겁게',
  },
  {
    id: 'privacy',
    label: '프라이버시·로컬 중시',
    weights: { user_rating: 25, objective: 55, ai_review: 20 },
    filters: ['account_required', 'data_collection'],
    hint: '계정·데이터 수집 필터를 함께 켭니다',
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
  compat_risk: '보안·OS 호환성 위험',
};

const VERIFICATION_LABEL = {
  direct: '직접 확인',
  reported_only: '3자 서술',
  inferred: '정황 추론',
  absent: '부재 근거',
};

const EXPORT_LABEL = { full: '전체', partial: '부분', none: '불가', unknown: '미확인' };
const FREE_PLAY_LABEL = {
  sufficient: '무과금으로 충분',
  constrained: '무과금은 제한적',
  blocked: '무과금 진행 불가',
  unknown: '미확인',
};
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

const RULE_TEXT_KO = [
  '켜진 하드 필터에 걸리면 거름. 단 확률형·P2W의 「선택 과금(impact: optional)」은 기본 설정에서 거르지 않고 배지로만 알린다. (완화 모드에서 등급 C 근거만 있으면 조건부 경고)',
  '🔴 신호가 2개 이상이면 거름',
  '🔴 신호가 1개면 조건부',
  '🟡 신호가 2개 이상이면 조건부',
  '점수 80 이상이고 🟡가 1개 이하면 추천',
  '그 외에는 조건부',
  '완결작 면제에 보안·OS 호환성 신호가 붙으면 추천 대신 조건부 경고',
];

const SORT_LABEL = { score: '점수 높은 순', 'score-asc': '점수 낮은 순', risk: '최근 평가 위험 순', name: '이름순' };

const state = {
  core: null,
  cat: null,
  store: null,
  route: { view: 'home', domain: null, category: null, arena: null, item: null, compare: [] },
  query: '',
  sort: 'score',
  showAvoided: true,
  weights: {},
  enabledFilters: [],
  strict: true,
  strictMonetization: false,
  preset: 'balanced',
  bookmarks: [],
  theme: 'dark',
  lastFocus: null,
};

const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const safeUrl = (url) => (/^https?:\/\//i.test(String(url || '')) ? url : null);
const pct = (num) => `${Math.round(num * 100)}%`;
/** 헤더·경로 표시용 한 줄 설명 — 줄표(—) 뒤 부연을 잘라 한 줄로 만든다. */
const shortText = (value, limit = 76) => {
  const raw = String(value ?? '').split(' — ')[0].trim();
  return raw.length > limit ? `${raw.slice(0, limit).trim()}…` : raw;
};
const num = (value) => Number(value ?? 0).toLocaleString('ko-KR');
const contract = () => state.core?.contract || {};

/* 공식 아이콘 — data 의 icon 경로(assets/icons/{id}.webp)를 그대로 쓴다.
   파일이 없거나 깨져 있으면 img 가 숨겨지고 CSS 가 이름 첫 글자 이니셜 배지를 보여준다. */
const iconSrc = (icon) => {
  const raw = String(icon || '').trim().replace(/^\.?\//, '');
  return raw ? `./${raw}` : null;
};
const initialOf = (name) => String(name || '?').trim().slice(0, 1).toUpperCase();
function iconHtml(item, size = 'card') {
  const src = iconSrc(item?.icon);
  const initial = initialOf(item?.name);
  return `<span class="item-icon item-icon--${size}" data-initial="${esc(initial)}" aria-hidden="true">${
    src ? `<img src="${esc(src)}" alt="" decoding="async" />` : ''
  }</span>`;
}
document.addEventListener(
  'error',
  (event) => {
    const img = event.target;
    if (img instanceof HTMLImageElement && img.closest('.item-icon')) img.hidden = true;
  },
  true,
);
const schemaVersion = () => state.core?.schema?.['x-pharos']?.schema_version || contract().schema_version || '0.4.0';
const indexRecords = () => state.core?.index?.items || [];
const recordById = (id) => indexRecords().find((rec) => rec.id === id) || null;
const settings = () => ({
  contract: contract(),
  weights: state.weights,
  enabledFilters: state.enabledFilters,
  strict: state.strict,
  strictMonetization: state.strictMonetization,
});

/* ------------------------------------------------------------------ 초기화 */

function readStore(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeStore(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* 저장 실패는 무시 */
  }
}

function initTheme() {
  let stored = null;
  try {
    stored = localStorage.getItem(LS.theme);
  } catch {
    stored = null;
  }
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
    localStorage.setItem(LS.theme, state.theme);
  } catch {
    /* 무시 */
  }
  applyTheme();
}

function loadPrefs() {
  const defaults = engine.defaultWeights(contract());
  const prefs = readStore(LS.prefs, null);
  state.weights = { ...defaults };
  state.enabledFilters = [...(contract().default_enabled_filters || [])];
  state.strict = contract().evidence_rules?.strict_evidence_default !== false;
  state.strictMonetization = contract().monetization_impact?.strict_toggle?.default === true;
  state.preset = 'balanced';
  if (prefs && typeof prefs === 'object') {
    if (prefs.weights && typeof prefs.weights === 'object') {
      for (const key of Object.keys(defaults)) {
        const value = Number(prefs.weights[key]);
        if (Number.isFinite(value) && value >= 0 && value <= 100) state.weights[key] = value;
      }
    }
    if (Array.isArray(prefs.filters)) {
      const known = new Set((contract().hard_filters || []).map((f) => f.key));
      state.enabledFilters = prefs.filters.filter((key) => known.has(key));
    }
    if (typeof prefs.strict === 'boolean') state.strict = prefs.strict;
    if (typeof prefs.strictMonetization === 'boolean') state.strictMonetization = prefs.strictMonetization;
    if (typeof prefs.preset === 'string' && PRESETS.some((p) => p.id === prefs.preset)) state.preset = prefs.preset;
  }
  state.bookmarks = (readStore(LS.bookmarks, []) || []).filter((id) => typeof id === 'string');
}

function savePrefs() {
  writeStore(LS.prefs, {
    weights: state.weights,
    filters: state.enabledFilters,
    strict: state.strict,
    strictMonetization: state.strictMonetization,
    preset: state.preset,
  });
}

async function init() {
  initTheme();
  bindEvents();
  try {
    const core = await loadCore();
    state.core = core;
    state.cat = createCatalogView(core.catalog);
    state.store = createArenaStore(core.catalog);
  } catch (err) {
    renderFatal(err);
    return;
  }
  loadPrefs();
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

/* --------------------------------------------------------------- 라우팅 */

function parseUrl() {
  const params = new URLSearchParams(location.search);
  const route = { view: 'home', domain: null, category: null, arena: null, item: null, compare: [] };
  const domain = params.get('domain');
  if (domain && state.cat.domain(domain)) {
    route.view = 'browse';
    route.domain = domain;
    const category = params.get('category');
    if (category && state.cat.category(category) && state.cat.category(category).domain === domain) {
      route.category = category;
    }
    const arena = params.get('arena');
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
      if (!route.arena && rec.arenas.length) {
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
  if (route.domain) {
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

function syncUrl(mode = 'push') {
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

let renderSeq = 0;

async function render({ replace = false } = {}) {
  const seq = ++renderSeq;
  syncUrl(replace || state.route.item ? 'replace' : 'push');
  renderDomainTabs();
  renderBreadcrumb();
  renderCompareBar();
  if (!state.route.domain) {
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
  if (state.route.item) await showDetail(state.route.item);
  else closeDetail({ silent: true });
  $('view').focus({ preventScroll: true });
}

async function navigate(patch, options = {}) {
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
  state.route = { view: 'home', domain: null, category: null, arena: null, item: null, compare: [] };
  return render();
}

/* ------------------------------------------------------------ 상단·경로 UI */

function renderDomainTabs() {
  const wrap = $('domainTabs');
  if (!wrap) return;
  const items = [
    { key: 'home', label: '홈', active: !state.route.domain, action: 'home' },
    ...(state.cat?.catalog.domains || []).map((dom) => ({
      key: dom.id,
      label: dom.label,
      active: state.route.domain === dom.id,
      action: 'domain',
    })),
  ];
  wrap.innerHTML = items
    .map(
      (item) =>
        `<button type="button" role="tab" data-action="${item.action}"${
          item.action === 'domain' ? ` data-domain="${esc(item.key)}"` : ''
        } aria-selected="${item.active ? 'true' : 'false'}">${esc(item.label)}</button>`,
    )
    .join('');
}

function renderBreadcrumb() {
  const wrap = $('breadcrumb');
  const note = $('crumbNote');
  if (!wrap) return;
  const route = state.route;
  const crumbs = [{ label: '홈', action: 'home' }];
  if (route.domain) {
    const dom = state.cat.domain(route.domain);
    crumbs.push({ label: dom?.label || route.domain, action: 'domain', domain: route.domain });
    if (route.category && !route.arena) {
      crumbs.push({ label: state.cat.categoryLabel(route.category) });
    }
    if (route.arena) {
      const cat = state.cat.category(state.cat.arena(route.arena)?.category);
      crumbs.push({ label: cat?.label || '', action: 'category', domain: route.domain, category: cat?.id });
      crumbs.push({ label: state.cat.arenaLabel(route.arena) });
    }
    if (route.view === 'compare') crumbs.push({ label: '나란히 비교' });
  }
  wrap.innerHTML = crumbs
    .map((crumb, i) => {
      const last = i === crumbs.length - 1;
      const label = esc(crumb.label);
      if (last || !crumb.action) return `<li${last ? ' aria-current="page"' : ''}>${label}</li>`;
      const attrs = [`data-action="${crumb.action}"`];
      if (crumb.domain) attrs.push(`data-domain="${esc(crumb.domain)}"`);
      if (crumb.category) attrs.push(`data-category="${esc(crumb.category)}"`);
      return `<li><button type="button" ${attrs.join(' ')}>${label}</button></li>`;
    })
    .join('<li class="crumb-sep" aria-hidden="true">/</li>');
  if (note) {
    const arena = route.arena ? state.cat.arena(route.arena) : null;
    note.textContent = arena
      ? `${shortText(arena.description, 64)}`
      : route.domain
        ? `${state.cat.domain(route.domain)?.description || ''}`
        : '도메인 → 대분류 → 비교군 → 항목 순으로 좁혀 봅니다. 평균은 같은 비교군 안에서만 계산합니다.';
  }
}

function renderDatasetChip() {
  const chip = $('datasetChip');
  if (!chip) return;
  const version = state.core?.schema?.title?.match(/v([\d.]+)/)?.[1] || contract().schema_version || '?';
  const idx = state.core.index;
  chip.textContent = `스키마 v${version} · ${idx.counts.items}건 · 비교군 ${idx.counts.arenas}`;
  chip.title = `item.schema.json v${version} · catalog.json ${idx.counts.domains}도메인/${idx.counts.categories}대분류/${idx.counts.arenas}비교군 · data/{domain}/{arena}.json 지연 로딩`;
  const count = $('bookmarkCount');
  if (count) count.textContent = String(state.bookmarks.length);
}

/* ------------------------------------------------------------------ 홈 화면 */

function renderHome() {
  const idx = state.core.index;
  const featured = (state.cat.catalog.home?.featured_arenas || []).map((id) => state.cat.arena(id)).filter(Boolean);
  const arenas = featured.length ? featured : state.cat.arenasOf();
  const gapLimit = state.cat.catalog.home?.gap_report?.limit ?? 4;
  const gapItems = idx.gap_report.items.slice(0, gapLimit).map(recordById).filter(Boolean);
  const lastAssessed = indexRecords().map((rec) => rec.assessed_at).filter(Boolean).sort().pop();
  const counts = idx.counts;

  $('view').innerHTML = `
  <section class="home">
    <div class="hero hero--compact">
      <div class="hero-lead">
        <p class="eyebrow">PHAROS · 파로스</p>
        <h1>별점 대신, <span class="hl">내 기준</span>으로 거르는 앱·게임·AI 도구 선별</h1>
        <p class="lede">강제 광고·확률형 뽑기·불투명 크레딧·계정 필수 같은 <strong>절대 거름 조건</strong>을 먼저 적용하고, 같은 자리의 대체제끼리만 비교합니다.</p>
      </div>
      <form class="home-search" id="homeSearchForm" role="search" autocomplete="off">
        <span class="search-ico" aria-hidden="true">⌕</span>
        <input type="search" id="homeSearch" placeholder="‘에버노트 대신 뭐 쓰지?’ — 이름·대체제·키워드로 검색"
               aria-label="통합 검색" value="${esc(state.query)}" />
        <button type="submit" class="primary-btn">검색</button>
      </form>
      <div class="hero-meta">
        <span><b>${counts.items}</b>건 평가</span>
        <span><b>${counts.domains}</b>도메인</span>
        <span><b>${counts.arenas}</b>비교군</span>
        <span>스키마 v${esc(contract().schema_version || '0.4.0')}</span>
        ${lastAssessed ? `<span>마지막 평가 ${esc(lastAssessed)}</span>` : ''}
        <span class="hero-meta-actions">
          <button type="button" class="text-btn" data-action="open-method">점수 매기는 법</button>
          <button type="button" class="text-btn" data-action="open-tune">⚙ 내 기준 · ${esc(presetLabel())}</button>
        </span>
      </div>
    </div>

    <div id="homeSearchResults" class="home-search-results" ${state.query ? '' : 'hidden'}></div>

    <section class="home-block genre-showcase" id="genreShowcase">
      <div class="section-head">
        <h2>장르별 추천</h2>
        <span class="section-hint">${
          state.preset === 'balanced'
            ? '장르를 누르면 전체 비교군 · 항목을 누르면 상세가 바로 열립니다'
            : '타일 점수·판정은 균형 기본 기준 · 장르를 열면 내 기준으로 다시 계산합니다'
        }</span>
      </div>
      <div class="genre-list">${arenas.map((arena) => genreBlockHtml(arena, { kicker: true })).join('')}</div>
    </section>

    <section class="home-block" id="gapReport">
      <div class="section-head">
        <h2><span class="verdict-dot verdict-dot--bad"></span>${esc(
          state.cat.catalog.home?.gap_report?.title || '별점은 높은데 거름 판정',
        )}</h2>
        <span class="section-hint">스토어 누적 별점 ${(state.cat.catalog.home?.gap_report?.min_store_stars ?? 4).toFixed(1)}★ 이상인데 파로스 판정은 낮은 항목</span>
      </div>
      <p class="section-sub">${esc(
        state.cat.catalog.home?.gap_report?.note || '별점 하나로는 보이지 않는 과금·광고 구조를 드러냅니다.',
      )}</p>
      <div class="gap-list">
        ${gapItems.length ? gapItems.map(gapRowHtml).join('') : '<p class="empty">아직 이 조건에 걸리는 항목이 없습니다.</p>'}
      </div>
    </section>

    <section class="home-block" id="bookmarkSection">
      <div class="section-head">
        <h2>☆ 내 보관함</h2>
        <span class="section-hint" id="bookmarkHint">${state.bookmarks.length}건 · 이 브라우저에만 저장</span>
      </div>
      <div class="bookmark-list">
        ${
          state.bookmarks.length
            ? state.bookmarks
                .map((id) => recordById(id))
                .filter(Boolean)
                .map(bookmarkRowHtml)
                .join('')
            : '<p class="empty">카드나 상세의 ☆ 버튼을 누르면 여기에 모입니다. (localStorage)</p>'
        }
      </div>
    </section>
  </section>`;

  const input = $('homeSearch');
  if (input && input.value !== state.query) input.value = state.query;
  const form = $('homeSearchForm');
  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    const rows = searchRecords(state.core.index, state.cat, state.query);
    if (rows.length === 1) openDetail(rows[0].record.id);
  });
  renderHomeSearch();
}

/**
 * 장르(비교군) 추천 목록 — 경량 인덱스만으로 그린다(비교군 파일은 내려받지 않는다).
 * 추천 🟢 을 먼저, 그다음 조건부 🟡 를 점수 순으로. 거름 🔴 은 쇼케이스에서 빼고 비교군 화면에서만 보인다.
 * 점수·판정은 '균형 기본' 가중치·기본 필터로 계산된 값이다(내 기준은 비교군 화면에서 다시 계산).
 */
function arenaPickRecords(arenaId, limit = 4) {
  const rank = { recommend: 0, conditional: 1, avoid: 2 };
  const recs = indexRecords().filter((rec) => (rec.arenas || []).includes(arenaId));
  const sorted = [...recs].sort(
    (a, b) =>
      (rank[a.verdict] ?? 9) - (rank[b.verdict] ?? 9) ||
      (b.score ?? -1) - (a.score ?? -1) ||
      a.name.localeCompare(b.name, 'ko'),
  );
  const picks = sorted.filter((rec) => rec.verdict !== 'avoid');
  return (picks.length ? picks : sorted).slice(0, limit);
}

/** 장르 쇼케이스 타일 — 공식 아이콘 + 이름 + 판정 배지 + 가중 점수. 누르면 상세 모달이 열린다. */
function pickTileHtml(rec) {
  const verdict = engine.VERDICT_META[rec.verdict] || engine.VERDICT_META.conditional;
  const score = typeof rec.score === 'number' ? rec.score.toFixed(1) : '—';
  const tagline = rec.tagline || rec.one_liner || '';
  // 타일에는 한글 이름만 — 영어 원어가 괄호로 붙은 이름은 좁은 폭에서 먼저 잘린다(전체 이름은 상세·title).
  const shortName = String(rec.name || '').replace(/\s*[(\(][^)\)]*[)\)]\s*$/, '').trim() || rec.name;
  return `
  <button type="button" class="pick-tile pick-tile--${verdict.tone}" data-action="item" data-item="${esc(rec.id)}"
          data-verdict="${esc(rec.verdict)}" data-score="${typeof rec.score === 'number' ? rec.score.toFixed(2) : ''}"
          title="${esc(rec.name)}"
          aria-label="${esc(`${rec.name} 상세 보기 — ${verdict.label}, 가중 점수 ${score}`)}">
    ${iconHtml(rec, 'pick')}
    <span class="pick-text">
      <span class="pick-name">${esc(shortName)}</span>
      <span class="pick-tagline">${esc(tagline)}</span>
    </span>
    <span class="pick-meta">
      <span class="verdict verdict--${verdict.tone}"><span class="v-emoji" aria-hidden="true">${verdict.emoji}</span>${verdict.label}</span>
      <span class="pick-score" title="가중 점수(균형 기본 기준)">${score}</span>
    </span>
  </button>`;
}

/** 장르 한 블록 — 장르 이름(헤더 클릭 = 비교군 이동)과 추천 타일 줄. */
function genreBlockHtml(arena, options = {}) {
  const stat = state.core.index.arena_stats[arena.id];
  const picks = arenaPickRecords(arena.id, options.limit ?? 4);
  if (!picks.length) return '';
  const cat = state.cat.category(arena.category);
  const kicker = options.kicker
    ? `${state.cat.domainLabel(arena.domain)} · ${cat?.label || arena.category}`
    : cat?.label || arena.category;
  const count = stat?.count ?? picks.length;
  const go = `data-action="arena" data-domain="${esc(arena.domain)}" data-arena="${esc(arena.id)}"`;
  return `
  <article class="genre-block" data-arena="${esc(arena.id)}">
    <header class="genre-head">
      <button type="button" class="genre-title" ${go}>
        <span class="genre-kicker">${esc(kicker)}</span>
        <span class="genre-name">${esc(arena.label)}</span>
      </button>
      <span class="genre-stat">${count}종${
        stat ? ` · <span class="ok">추천 ${stat.verdicts.recommend}</span>` : ''
      }</span>
      <button type="button" class="genre-more" ${go}>전체 ${count}종 비교 →</button>
    </header>
    <div class="pick-row">${picks.map(pickTileHtml).join('')}</div>
  </article>`;
}

function gapRowHtml(rec) {
  const verdict = engine.VERDICT_META[rec.verdict];
  const stars = rec.gap?.stars ?? rec.store_stars?.value;
  const count = rec.store_stars?.count;
  return `
  <article class="gap-row" data-item="${esc(rec.id)}" role="button" tabindex="0">
    <div class="gap-title">
      ${iconHtml(rec, 'small')}
      <strong>${esc(rec.name)}</strong>
      <span class="chips">
        <span class="chip chip--cat">${esc(state.cat.domainLabel(rec.domain))}</span>
        <span class="chip chip--arena">${esc(state.cat.arenaLabel(rec.arenas[0]))}</span>
      </span>
    </div>
    <div class="gap-scale">
      <span class="gap-stars"><b>★ ${Number(stars || 0).toFixed(1)}</b><small>${count ? `${num(count)}개 · ${esc(rec.store_stars?.platform || '')}` : '스토어 누적'}</small></span>
      <span class="gap-vs">별점</span>
      <span class="gap-score"><b>${rec.score ?? '—'}</b><small>파로스 가중 점수</small></span>
      <span class="verdict verdict--${verdict.tone}">${verdict.emoji} ${verdict.label}</span>
    </div>
    <p class="gap-drivers">${(rec.drivers || []).slice(0, 3).map((d) => `<span class="reason-chip reason-chip--${esc(d.tone || 'warn')}">${esc(d.label)}</span>`).join('') || '<span class="reason-chip">신호 기준</span>'}</p>
    <span class="gap-more">근거 보기 →</span>
  </article>`;
}

function bookmarkRowHtml(rec) {
  const verdict = engine.VERDICT_META[rec.verdict];
  return `
  <article class="bookmark-row" data-item="${esc(rec.id)}" role="button" tabindex="0">
    <span class="bookmark-name">${iconHtml(rec, 'small')}<span class="search-row-text">${esc(rec.name)}</span></span>
    <span class="chip chip--arena">${esc(state.cat.arenaLabel(rec.arenas[0]))}</span>
    <span class="verdict verdict--${verdict.tone}">${verdict.emoji} ${verdict.label}</span>
    <span class="bookmark-score">${rec.score ?? '—'}</span>
    <button type="button" class="text-btn" data-bookmark="${esc(rec.id)}" aria-label="${esc(rec.name)} 보관함에서 빼기">빼기</button>
  </article>`;
}

function renderHomeSearch() {
  const wrap = $('homeSearchResults');
  if (!wrap) return;
  const q = state.query.trim();
  if (!q) {
    wrap.hidden = true;
    wrap.innerHTML = '';
    return;
  }
  const rows = searchRecords(state.core.index, state.cat, q);
  wrap.hidden = false;
  wrap.innerHTML = `
    <div class="search-result-head">
      <span class="mini-label">통합 검색</span>
      <strong>‘${esc(q)}’</strong>
      <span class="muted">${rows.length}건 · 경량 인덱스에서 즉시 검색</span>
      <button type="button" class="text-btn" data-action="clear-search">지우기</button>
    </div>
    <div class="search-rows">
      ${
        rows.length
          ? rows
              .slice(0, 8)
              .map(({ record }) => {
                const verdict = engine.VERDICT_META[record.verdict];
                return `<button type="button" class="search-row" data-action="item" data-item="${esc(record.id)}">
                  <span class="search-row-name">${iconHtml(record, 'small')}<span class="search-row-text">${esc(record.name)}</span></span>
                  <span class="chip chip--arena">${esc(state.cat.arenaLabel(record.arenas[0]))}</span>
                  <span class="search-row-desc">${esc(record.one_liner)}</span>
                  <span class="verdict verdict--${verdict.tone}">${verdict.emoji} ${verdict.label}</span>
                  <span class="search-row-score">${record.score ?? '—'}</span>
                </button>`;
              })
              .join('')
          : '<p class="empty">맞는 항목이 없습니다. 이름·별칭·대체제 키워드로 다시 찾아보세요.</p>'
      }
    </div>`;
}

/* ------------------------------------------------------- 도메인·대분류·비교군 */

function renderDomain() {
  const dom = state.cat.domain(state.route.domain);
  const categories = state.cat.categoriesOf(dom.id);
  const arenas = state.cat.arenasOf(dom.id);
  const pack = state.cat.filterPack(dom.filter_pack);
  const total = arenas.reduce((sum, arena) => sum + (state.core.index.arena_stats[arena.id]?.count || 0), 0);
  $('view').innerHTML = `
  <section class="level">
    <header class="level-head level-head--compact">
      <p class="eyebrow">${esc(dom.label)}</p>
      <h1>${esc(dom.label)} — 장르 ${arenas.length} · ${total}건</h1>
      <p class="lede lede--line">${esc(dom.description)}</p>
      <div class="level-badges">
        ${categories
          .map((cat) => {
            const members = state.cat.arenasOf(dom.id, cat.id);
            return `<button type="button" class="chip chip--link" data-action="category" data-domain="${esc(dom.id)}" data-category="${esc(cat.id)}">${esc(
              cat.label,
            )} <b>${members.length}</b></button>`;
          })
          .join('')}
        <span class="chip chip--muted">필터 팩 · ${esc(pack?.label || dom.filter_pack)}</span>
      </div>
    </header>
    <div class="genre-list">${arenas.map((arena) => genreBlockHtml(arena)).join('')}</div>
  </section>`;
}

function renderCategory() {
  const dom = state.cat.domain(state.route.domain);
  const cat = state.cat.category(state.route.category);
  const arenas = state.cat.arenasOf(dom.id, cat.id);
  $('view').innerHTML = `
  <section class="level">
    <header class="level-head level-head--compact">
      <p class="eyebrow">${esc(dom.label)} · 대분류</p>
      <h1>${esc(cat.label)}</h1>
      <p class="lede lede--line">${esc(cat.description)}</p>
    </header>
    <div class="genre-list">${arenas.map((arena) => genreBlockHtml(arena)).join('')}</div>
  </section>`;
}

/* ------------------------------------------------------------- 비교군 목록 */

async function renderArena(seq) {
  const arena = state.cat.arena(state.route.arena);
  if (!arena) return;
  let items;
  try {
    items = await state.store.load(arena.id);
  } catch (err) {
    $('view').innerHTML = `<div class="error-banner"><strong>비교군 데이터를 불러오지 못했습니다.</strong><span>${esc(
      err?.message || err,
    )}</span></div>`;
    return;
  }
  if (seq !== renderSeq) return;
  state.arenaItems = items;
  const cat = state.cat.category(arena.category);
  const pack = state.cat.filterPack(state.cat.domain(arena.domain)?.filter_pack);
  $('view').innerHTML = `
  <section class="level">
    <header class="level-head level-head--arena">
      <p class="eyebrow">${esc(state.cat.domainLabel(arena.domain))} · ${esc(cat?.label || arena.category)}</p>
      <h1>${esc(arena.label)}</h1>
      <p class="lede lede--line">${esc(shortText(arena.description))}</p>
      <div class="level-badges">
        <span class="chip">${items.length}건</span>
        <span class="chip chip--muted">필터 팩 · ${esc(pack?.label || '공통')}</span>
        <button type="button" class="ghost-btn ghost-btn--tune" data-action="open-tune">⚙ 내 기준 <b id="tuneSummary">${esc(presetLabel())}</b></button>
      </div>
    </header>
    <div class="toolbar">
      <label class="search toolbar-search">
        <span class="search-ico" aria-hidden="true">⌕</span>
        <input type="search" id="arenaSearch" placeholder="이 비교군 안에서 이름·키워드 검색" autocomplete="off" value="${esc(state.query)}" aria-label="비교군 내 검색" />
      </label>
      <div class="select-row">
        <label class="select-label" for="sort">정렬</label>
        <select id="sort">${Object.entries(SORT_LABEL)
          .map(([key, label]) => `<option value="${key}" ${state.sort === key ? 'selected' : ''}>${label}</option>`)
          .join('')}</select>
      </div>
      <label class="check-row"><input type="checkbox" id="showAvoided" ${state.showAvoided ? 'checked' : ''} /><span>거름 항목 표시</span></label>
      <span class="panel-hint" id="listCount">0건</span>
    </div>
    <div id="arenaResults"></div>
  </section>`;
  const search = $('arenaSearch');
  search?.addEventListener('input', () => {
    state.query = search.value;
    renderArenaResults();
  });
  $('sort')?.addEventListener('change', (event) => {
    state.sort = event.target.value;
    renderArenaResults();
  });
  $('showAvoided')?.addEventListener('change', (event) => {
    state.showAvoided = event.target.checked;
    renderArenaResults();
  });
  renderArenaResults();
}

function arenaPool() {
  const items = state.arenaItems || [];
  if (!state.query.trim()) return items;
  const rows = searchRecords(state.core.index, state.cat, state.query).map((row) => row.record.id);
  const allowed = new Set(rows.filter((id) => recordById(id)?.arenas.includes(state.route.arena)));
  return items.filter((item) => allowed.has(item.id));
}

function computeViews(items) {
  const cfg = settings();
  return items.map((item) => {
    const recordTier = engine.tierById(item, item.verdict?.tier_of_record);
    const tierEvals = (item.tiers || []).map((tier) => ({ tier, evaluation: engine.evaluateTier(item, tier, cfg) }));
    const recordEval =
      tierEvals.find((row) => row.tier.tier_id === recordTier?.tier_id)?.evaluation ||
      engine.evaluateTier(item, recordTier, cfg);
    return {
      item,
      recordTier,
      recordEval,
      tierEvals,
      cheapest: engine.recommendedTier(item),
      fresh: engine.freshness(item, cfg.contract),
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

function sortViews(views) {
  const sorters = {
    score: (a, b) => (b.recordEval.score ?? -1) - (a.recordEval.score ?? -1),
    'score-asc': (a, b) => (a.recordEval.score ?? 999) - (b.recordEval.score ?? 999),
    risk: (a, b) => a.worstGap - b.worstGap,
    name: (a, b) => a.item.name.localeCompare(b.item.name, 'ko'),
  };
  return [...views].sort(sorters[state.sort] || sorters.score);
}

function renderArenaResults() {
  const wrap = $('arenaResults');
  if (!wrap) return;
  const pool = arenaPool();
  const views = sortViews(computeViews(pool));
  const picks = views.filter((view) => view.recordEval.verdict !== 'avoid');
  const avoided = views.filter((view) => view.recordEval.verdict === 'avoid');
  const counts = { recommend: 0, conditional: 0, avoid: 0 };
  let sum = 0;
  let n = 0;
  for (const view of views) {
    counts[view.recordEval.verdict] += 1;
    if (typeof view.recordEval.score === 'number') {
      sum += view.recordEval.score;
      n += 1;
    }
  }
  const avg = n ? (sum / n).toFixed(1) : '—';

  wrap.innerHTML = `
    <div class="arena-summary" id="arenaSummary">
      <div class="stat stat--ok"><span class="stat-label">추천</span><span class="stat-value">${counts.recommend}</span><span class="stat-sub">가중 점수 80+ · 신호 양호</span></div>
      <div class="stat stat--warn"><span class="stat-label">조건부</span><span class="stat-value">${counts.conditional}</span><span class="stat-sub">감수할 조건이 있음</span></div>
      <div class="stat stat--bad"><span class="stat-label">거름</span><span class="stat-value">${counts.avoid}</span><span class="stat-sub">필터·신호 기준 차단</span></div>
      <div class="stat stat--avg"><span class="stat-label">평균 가중 점수</span><span class="stat-value">${avg}</span><span class="stat-sub">${esc(presetLabel())} · 이 비교군 ${views.length}건</span></div>
    </div>
    <div class="section-head">
      <h2>선별 결과</h2>
      <span class="section-hint">${picks.length}건 · 2~3개를 체크하면 나란히 비교</span>
    </div>
    <div class="grid" id="grid">${picks.map(cardHtml).join('')}</div>
    <p class="empty" id="emptyPick" ${picks.length ? 'hidden' : ''}>조건에 맞는 항목이 없습니다. 필터를 줄이거나 검색어를 비워보세요.</p>
    <section class="result-section" id="avoidSection" ${state.showAvoided ? '' : 'hidden'}>
      <div class="section-head">
        <h2><span class="verdict-dot verdict-dot--bad"></span>거름 — 왜 걸렸는지</h2>
        <span class="section-hint">${avoided.length}건</span>
      </div>
      <p class="hint section-sub">켜진 필터에 걸린 항목은 점수와 무관하게 아래로 내려갑니다.</p>
      <div class="grid grid--avoided" id="avoidGrid">${avoided.map(cardHtml).join('')}</div>
      <p class="empty" id="emptyAvoid" ${avoided.length ? 'hidden' : ''}>지금 설정에서 거름으로 내려간 항목이 없습니다.</p>
    </section>`;
  $('listCount').textContent = `${views.length}/${(state.arenaItems || []).length}건`;
  renderCompareBar();
}

function presetLabel() {
  if (state.preset === 'custom') return '직접 설정';
  return PRESETS.find((p) => p.id === state.preset)?.label || '균형 기본';
}

/* -------------------------------------------------------------------- 카드 */

function ring(score) {
  const circumference = 106.814;
  const value = Math.max(0, Math.min(100, score ?? 0));
  const dash = (value / 100) * circumference;
  return `<svg class="ring" viewBox="0 0 40 40" aria-hidden="true" focusable="false">
      <circle class="ring-track" cx="20" cy="20" r="17"></circle>
      <circle class="ring-value" cx="20" cy="20" r="17" stroke-dasharray="${dash.toFixed(2)} ${circumference.toFixed(2)}"></circle>
    </svg>`;
}

function maintenanceChip(item) {
  const key = item?.maintenance_status;
  const meta = engine.MAINTENANCE_STATUS_META[key];
  if (!meta || key === 'active') return '';
  return `<span class="chip chip--maintenance chip--maintenance--${esc(meta.tone)}" title="${esc(
    item.maintenance_note || meta.desc,
  )}">${esc(meta.label)}</span>`;
}

function freshnessChip(item) {
  const fresh = engine.freshness(item, contract());
  const tone = fresh.stale ? 'warn' : 'ok';
  const text = fresh.stale ? fresh.label : `${fresh.label} · ${fresh.elapsed}일`;
  return `<span class="chip chip--fresh chip--fresh--${tone}" title="평가일 ${esc(
    fresh.assessedAt || '미확인',
  )} · ${fresh.limit}일 초과 시 재검토">${esc(text)}</span>`;
}

/* ---- 카드 한 줄 태그(최대 2개) — 상세는 모달에서.

   목록 카드에는 판정을 가른 핵심만 남긴다. 3축 점수·필터 통과 목록·가격 티어는
   카드에서 빼고 상세 모달(01 계산 과정·04 티어별·05 축별 신호)에만 둔다. */
function cardTagsHtml(view) {
  const { item, recordEval: e } = view;
  const tags = [];
  const push = (html) => {
    if (tags.length < 2 && !tags.includes(html)) tags.push(html);
  };
  for (const fail of e.blocking) {
    if (fail.impact === 'core') {
      push(
        `<span class="chip chip--core" title="${esc(fail.note)}">${esc(engine.IMPACT_META.core.label)}</span>`,
      );
    } else {
      push(`<span class="chip chip--core" title="${esc(fail.note)}">${esc(fail.label)}</span>`);
    }
  }
  for (const fail of e.weakFails) {
    push(`<span class="chip chip--warn" title="근거가 약함 · ${esc(fail.note)}">근거 약함 · ${esc(fail.label)}</span>`);
  }
  if (e.optionalFails?.length) {
    push(
      `<span class="chip chip--optional" title="상점에 확률형·편의 상품이 있지만 인게임 재화·무과금으로 본편을 즐길 수 있어 거르지 않습니다.">선택 과금 · 무과금 가능</span>`,
    );
  }
  if (e.verdict === 'avoid' && !e.blocking.length && e.reds >= 2) {
    push(`<span class="chip chip--core">🔴 신호 ${e.reds}개</span>`);
  }
  const maintKey = item.maintenance_status;
  const maint = engine.MAINTENANCE_STATUS_META[maintKey];
  if (maint && maintKey !== 'active') {
    push(
      `<span class="chip chip--maintenance chip--maintenance--${esc(maint.tone)}" title="${esc(
        item.maintenance_note || maint.desc,
      )}">${esc(maint.label)}</span>`,
    );
  }
  if (!tags.length) push('<span class="chip chip--pass">하드 필터 통과</span>');
  return tags.join('');
}

function cardHtml(view) {
  const { item, recordTier, recordEval } = view;
  const verdictMeta = engine.VERDICT_META[recordEval.verdict];
  const scoreText = typeof recordEval.score === 'number' ? recordEval.score.toFixed(1) : '—';
  const genres = (item.genres || []).slice(0, 2).join(' / ');
  const devLine = [item.developer, genres].filter(Boolean).join(' · ');
  const summary = recordTier?.one_liner || item.verdict?.one_liner || item.one_liner || '';
  const selectable = state.route.arena && state.route.view !== 'compare';
  const checked = state.route.compare.includes(item.id);
  const bookmarked = state.bookmarks.includes(item.id);

  return `
  <article class="card card--${verdictMeta.tone}" role="button" tabindex="0" data-item="${esc(item.id)}" data-id="${esc(item.id)}"
           data-verdict="${esc(recordEval.verdict)}" data-score="${typeof recordEval.score === 'number' ? recordEval.score.toFixed(2) : ''}"
           aria-label="${esc(`${item.name} 상세 보기 — ${verdictMeta.label}, 가중 점수 ${scoreText}`)}">
    <header class="card-head">
      ${iconHtml(item, 'card')}
      <div class="card-name-text">
        <h3>${esc(item.name)}</h3>
        <p class="card-dev">${esc(devLine)}</p>
      </div>
      <div class="card-score">
        <span class="verdict verdict--${verdictMeta.tone}"><span class="v-emoji" aria-hidden="true">${verdictMeta.emoji}</span>${verdictMeta.label}</span>
        <span class="score-num">${scoreText}</span>
        <span class="score-cap">가중 점수</span>
      </div>
    </header>

    <p class="one-liner">${esc(summary)}</p>
    <div class="card-tags">${cardTagsHtml(view)}</div>

    <div class="card-tools">
      ${selectable ? `<label class="compare-check" title="같은 비교군 2~3개를 체크해 나란히 비교"><input type="checkbox" data-compare="${esc(item.id)}" ${checked ? 'checked' : ''}/><span>비교</span></label>` : ''}
      <button type="button" class="icon-btn icon-btn--sm ${bookmarked ? 'is-on' : ''}" data-bookmark="${esc(item.id)}" aria-pressed="${bookmarked}" aria-label="${esc(item.name)} 보관함 ${bookmarked ? '빼기' : '담기'}">${bookmarked ? '★' : '☆'}</button>
      <span class="card-more">상세 →</span>
    </div>
  </article>`;
}

/* ------------------------------------------------------------- 비교 바·비교 뷰 */

function renderCompareBar() {
  const bar = $('compareBar');
  if (!bar) return;
  const ids = state.route.compare;
  const show = Boolean(state.route.arena) && ids.length > 0 && state.route.view !== 'compare';
  bar.hidden = !show;
  if (!show) return;
  $('compareList').innerHTML = ids
    .map((id) => `<span class="compare-chip">${esc(recordById(id)?.name || id)}<button type="button" class="chip-x" data-compare="${esc(id)}" aria-label="${esc(
      recordById(id)?.name || id,
    )} 비교에서 빼기">✕</button></span>`)
    .join('');
  $('compareOpen').disabled = ids.length < 2;
  $('compareOpen').textContent = ids.length < 2 ? '1개 더 선택' : `${ids.length}개 나란히 비교`;
}

function toggleCompare(id) {
  if (!state.route.arena) return;
  const rec = recordById(id);
  if (!rec || !rec.arenas.includes(state.route.arena)) {
    toast('같은 비교군 항목만 비교할 수 있습니다.');
    return;
  }
  const current = [...state.route.compare];
  const at = current.indexOf(id);
  if (at >= 0) current.splice(at, 1);
  else {
    if (current.length >= 3) {
      toast('한 번에 최대 3개까지 비교합니다.');
      return;
    }
    current.push(id);
  }
  state.route.compare = current;
  // 체크박스 상태만 맞춰 주고 목록을 다시 그리지 않는다(포커스 유지)
  document.querySelectorAll('[data-compare]').forEach((el) => {
    if (el.tagName === 'INPUT') el.checked = current.includes(el.dataset.compare);
  });
  renderCompareBar();
  syncUrl('replace');
  if (state.route.view === 'compare') render();
}

async function renderCompare(seq) {
  const ids = state.route.compare.slice(0, 3);
  const arenaId = state.route.arena;
  const records = ids.map(recordById).filter(Boolean);
  let pool = [];
  try {
    pool = await state.store.load(arenaId);
  } catch (err) {
    $('view').innerHTML = `<div class="error-banner"><strong>비교할 데이터를 불러오지 못했습니다.</strong><span>${esc(
      err?.message || err,
    )}</span></div>`;
    return;
  }
  if (seq !== renderSeq) return;
  state.arenaItems = pool;
  const views = ids
    .map((id) => {
      const item = pool.find((row) => row.id === id);
      return item ? computeViews([item])[0] : null;
    })
    .filter(Boolean);
  if (views.length < 2) {
    await navigate({ view: 'browse' }, { replace: true });
    return;
  }
  const arena = state.cat.arena(arenaId);
  const rows = [
    ['가중 점수', (v) => `<b class="cmp-score">${v.recordEval.score?.toFixed(1) ?? '—'}</b>`],
    ['대표 티어 · 가격', (v) => `${esc(v.recordTier?.label || '—')}<br><span class="muted">${esc(v.recordTier?.price?.display || '—')}</span>`],
    ['최저 비용 경로', (v) => (v.cheapest ? esc(v.cheapest.label) : '—')],
    ...['user_rating', 'objective', 'ai_review'].map((key) => {
      const label = contract().axes?.find((def) => def.key === key)?.label || key;
      return [
        `축 · ${label}`,
        (v) => {
          const axis = v.recordEval.axisStates.find((row) => row.key === key);
          const meta = engine.SIGNAL_META[axis?.signal] || engine.SIGNAL_META.unknown;
          return axis ? `${meta.emoji} <b>${axis.score ?? '—'}</b>` : '—';
        },
      ];
    }),
    [
      '확률형·P2W 강도',
      (v) => {
        const impact = engine.monetizationImpactOf(v.recordEval);
        if (impact === 'none') return '<span class="muted">상품 없음</span>';
        return `<span class="pill pill--${impact === 'optional' ? 'sea' : 'bad'}">${esc(
          engine.IMPACT_META[impact]?.label || impact,
        )}</span>`;
      },
    ],
    [
      '걸린 하드 필터',
      (v) => {
        const fails = engine.failedFilters(v.recordEval);
        const optional = engine.optionalFilters(v.recordEval);
        const chips = [
          ...fails.map((f) => `<span class="reason-chip reason-chip--bad">${esc(f.label)}</span>`),
          ...optional.map((f) => `<span class="reason-chip reason-chip--sea">${esc(f.label)} · 선택 과금</span>`),
        ];
        return chips.length ? chips.join('') : '<span class="muted">없음</span>';
      },
    ],
    ['누적 별점·평점', (v) => storeStarsText(v.item)],
    ['최근 리뷰', (v) => recentReviewText(v.item)],
    ['수명 단계', (v) => esc(engine.MAINTENANCE_STATUS_META[v.item.maintenance_status]?.label || v.item.maintenance_status)],
    ['평가 신선도', (v) => {
      const fresh = v.fresh;
      return `${esc(v.item.assessed_at)}<br><span class="chip chip--fresh chip--fresh--${fresh.stale ? 'warn' : 'ok'}">${esc(
        fresh.stale ? fresh.label : `${fresh.label} · ${fresh.elapsed}일`,
      )}</span>`;
    }],
    ['근거 등급', (v) => esc(engine.gradeWeakest(v.item.data_quality?.overall_grade))],
    ['', (v) => `<button type="button" class="ghost-btn" data-action="item" data-item="${esc(v.item.id)}">상세 →</button>`],
  ];
  $('view').innerHTML = `
  <section class="level">
    <header class="level-head level-head--arena">
      <p class="eyebrow">${esc(state.cat.domainLabel(arena.domain))} · ${esc(state.cat.categoryLabel(arena.category))}</p>
      <h1>${esc(arena.label)} — 나란히 비교</h1>
      <p class="lede">같은 비교군 ${views.length}개를 한 표에 놓았습니다. 점수·판정은 지금 내 기준(${esc(presetLabel())})으로 다시 계산됩니다.</p>
      <div class="level-badges">
        <button type="button" class="ghost-btn" data-action="arena" data-domain="${esc(arena.domain)}" data-arena="${esc(arena.id)}">← 목록으로</button>
        <button type="button" class="text-btn" data-action="clear-compare">비교 비우기</button>
      </div>
    </header>
    <div class="table-wrap compare-wrap">
      <table class="data compare-table" id="compareTable">
        <thead>
          <tr>
            <th class="compare-rowlabel" scope="col">기준</th>
            ${views.map((v) => `<th scope="col"><span class="compare-head-name">${iconHtml(v.item, 'compare')}<span class="compare-head-text">${esc(v.item.name)}</span></span><span class="verdict verdict--${
              engine.VERDICT_META[v.recordEval.verdict].tone
            }">${engine.VERDICT_META[v.recordEval.verdict].emoji} ${engine.VERDICT_META[v.recordEval.verdict].label}</span></th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${rows
            .map(
              ([label, render]) =>
                `<tr><th scope="row" class="compare-rowlabel">${esc(label)}</th>${views
                  .map((v) => `<td>${render(v)}</td>`)
                  .join('')}</tr>`,
            )
            .join('')}
        </tbody>
      </table>
    </div>
  </section>`;
}

const STORE_PLATFORMS = ['android', 'ios', 'steam'];

/** 누적 별점 행의 이름 — 실제 스토어 표본이면 '스토어 누적 별점', G2 같은 3자 집계면 '누적 평점(3자 집계)'. */
function storeStarsLabel(item) {
  const top = (item.review_snapshot?.platforms || [])
    .filter((row) => row.cumulative && row.cumulative.scale === 'stars5')
    .sort((a, b) => (b.cumulative.count || 0) - (a.cumulative.count || 0))[0];
  if (!top) return '누적 별점·평점';
  return STORE_PLATFORMS.includes(top.platform) ? '스토어 누적 별점' : '누적 평점(3자 집계)';
}

function storeStarsText(item) {
  const rows = (item.review_snapshot?.platforms || [])
    .map((row) => ({ row, metric: row.cumulative }))
    .filter(({ metric }) => metric && metric.scale === 'stars5')
    .sort((a, b) => (b.metric.count || 0) - (a.metric.count || 0));
  if (!rows.length) return '<span class="muted">—</span>';
  const { row, metric } = rows[0];
  return `★ ${Number(metric.value).toFixed(1)} <span class="muted">${engine.PLATFORM_LABEL[row.platform] || row.platform} · ${num(
    metric.count,
  )}개</span>`;
}

function recentReviewText(item) {
  const rows = (item.review_snapshot?.platforms || []).filter((row) => row.recent);
  if (!rows.length) return '<span class="muted">최근 구간 없음</span>';
  return rows
    .map((row) => {
      const { gap } = engine.reviewGap(row);
      const metric = row.recent;
      const value = metric.scale === 'percent' ? `${metric.value}%` : metric.scale === 'stars5' ? `★ ${metric.value}` : `${metric.value}/10`;
      return `${esc(engine.PLATFORM_LABEL[row.platform] || row.platform)} ${value}${
        gap == null ? '' : ` <span class="muted">(${gap > 0 ? '+' : ''}${gap.toFixed(1)}p)</span>`
      }`;
    })
    .join('<br>');
}

/* ---------------------------------------------------------------- 상세 모달 */

async function openDetail(id) {
  const rec = recordById(id);
  if (!rec) return;
  const arena = state.cat.arena(rec.arenas[0]);
  if (!arena) return;
  const patch = {
    view: state.route.view === 'compare' ? 'compare' : 'browse',
    domain: arena.domain,
    category: arena.category,
    arena: arena.id,
    item: id,
  };
  if (state.route.domain === arena.domain && state.route.arena === arena.id) {
    state.route = { ...state.route, item: id };
    syncUrl('replace');
    await showDetail(id);
    return;
  }
  const keepCompare = state.route.arena === arena.id ? state.route.compare : [];
  state.route = { ...state.route, ...patch, compare: keepCompare };
  await render();
}

async function showDetail(id) {
  const rec = recordById(id);
  if (!rec) return;
  const arenaId = state.route.arena || rec.arenas[0];
  let pool = state.store.get(arenaId);
  if (!pool) pool = await state.store.load(arenaId);
  const item = pool.find((row) => row.id === id);
  if (!item) return;
  const view = computeViews([item])[0];
  const verdictMeta = engine.VERDICT_META[view.recordEval.verdict];
  const fresh = view.fresh;

  state.lastFocus = document.activeElement;
  $('modalIcon').hidden = false;
  $('modalIcon').innerHTML = iconHtml(item, 'detail');
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
    `<span class="chip chip--cat">${esc(state.cat.domainLabel(item.domain))} · ${esc(state.cat.categoryLabel(item.category))}</span>`,
    ...(item.arenas || []).map((aid) => `<span class="chip chip--arena">${esc(state.cat.arenaLabel(aid))}</span>`),
    maintenanceChip(item),
    freshnessChip(item),
    `<span class="chip chip--grade chip--${esc(engine.gradeWeakest(item.data_quality?.overall_grade))}">근거 ${esc(
      engine.gradeWeakest(item.data_quality?.overall_grade),
    )}</span>`,
  ].join('');

  const bookmarked = state.bookmarks.includes(item.id);
  $('modalActions').innerHTML = `
    <button type="button" class="ghost-btn" data-share="${esc(item.id)}">공유 요약 복사</button>
    <a class="ghost-btn" href="${correctionUrl(item)}" target="_blank" rel="noopener noreferrer">정정 제보</a>
    <button type="button" class="ghost-btn ${bookmarked ? 'is-on' : ''}" data-bookmark="${esc(item.id)}" aria-pressed="${bookmarked}">${bookmarked ? '★ 보관됨' : '☆ 보관'}</button>
    <button type="button" class="icon-btn" id="modalClose" aria-label="상세 닫기">✕</button>`;

  $('modalBody').innerHTML = [
    sectionVerdict(view, verdictMeta),
    sectionFacts(view),
    sectionOpinion(view),
    sectionTiers(view),
    sectionAxes(view),
    sectionAlternatives(view),
    sectionReviews(view),
    sectionMoney(view),
    sectionUpdates(view),
    sectionEvidence(view),
  ].join('');

  const backdrop = $('modalBackdrop');
  backdrop.hidden = false;
  document.body.style.overflow = 'hidden';
  $('modal').focus({ preventScroll: true });
  $('modalBody').scrollTop = 0;
}

function closeDetail({ silent = false } = {}) {
  const backdrop = $('modalBackdrop');
  if (!backdrop || backdrop.hidden) return;
  backdrop.hidden = true;
  document.body.style.overflow = '';
  state.route = { ...state.route, item: null };
  if (!silent) {
    syncUrl('replace');
    if (state.lastFocus && typeof state.lastFocus.focus === 'function') state.lastFocus.focus({ preventScroll: true });
  }
  state.lastFocus = null;
}

function correctionUrl(item) {
  const title = encodeURIComponent(`[정정] ${item.name} (${item.id})`);
  const body = encodeURIComponent(
    `대상 항목: ${item.name} (${item.id})\n비교군: ${(item.arenas || []).join(', ')}\n평가일: ${item.assessed_at}\n\n정정할 내용:\n\n근거 URL:\n\n`,
  );
  return `https://github.com/AIRA1346/pharos/issues/new?template=correction.yml&title=${title}&body=${body}`;
}

/* --- 01 판정 요약 --- */
function sectionVerdict(view, verdictMeta) {
  const e = view.recordEval;
  const rule = ruleDescription(e);
  const signals = e.axisStates
    .map(
      (axis) =>
        `<span class="sig-pill sig-pill--${esc(axis.signal)}">${esc(engine.SIGNAL_META[axis.signal]?.emoji || '')} ${esc(
          axis.label,
        )} <b>${axis.score ?? '—'}</b></span>`,
    )
    .join('');
  const filterChips = e.filterChecks.filter((f) => f.enabled).map(filterPill).join('');

  return `
  <section class="m-sec" id="secVerdict">
    <div class="m-sec-head"><span class="sec-num">01</span><h3>판정 요약</h3>
      <span class="pill pill--beam">${esc(view.recordTier?.label || '대표 티어')}</span>
      ${view.cheapest ? `<span class="pill pill--sea">최저 비용 · ${esc(view.cheapest.label)}</span>` : ''}
      ${view.recordEval.optionalMonetization ? '<span class="pill pill--sea">선택 과금 · 무과금 가능</span>' : ''}
      <span class="pill pill--${view.fresh.stale ? 'warn' : 'ok'}">${esc(
        view.fresh.stale ? view.fresh.label : `최신 · ${view.fresh.elapsed}일`,
      )}</span>
    </div>
    ${view.fresh.stale
      ? `<div class="callout callout--warn"><b>재검토 필요</b> 평가일 ${esc(view.fresh.assessedAt)} 이후 ${view.fresh.elapsed}일이 지났습니다(기준 ${view.fresh.limit}일). 앱·게임·AI 도구는 업데이트 한 번으로 과금·광고 정책이 바뀌므로 최신 사실로 읽지 마세요.</div>`
      : ''}
    <div class="verdict-hero verdict-hero--${verdictMeta.tone}">
      <div class="hero-score">
        <div class="score">${ring(e.score ?? 0)}
          <div class="score-inner"><span class="score-num">${e.score != null ? e.score.toFixed(1) : '—'}</span><span class="score-cap">가중 점수</span></div>
        </div>
        <span class="hero-verdict hero-verdict--${verdictMeta.tone}">${verdictMeta.emoji} ${verdictMeta.label}</span>
      </div>
      <div class="hero-body">
        <p class="hero-oneliner">${esc(view.recordTier?.one_liner || view.item.verdict?.one_liner || view.item.one_liner)}</p>
        <div class="hero-signals">${signals}</div>
        <p class="rule-line">판정 규칙 <b>${esc(rule.short)}</b>${e.weakFails.length ? ' · 근거 약함 경고' : ''}${
          e.unknowns ? ` · ⚪ 미확인 축 ${e.unknowns}개` : ''
        }</p>
        <div class="m-sec-note">활성 필터 점검: ${filterChips || '<span class="muted">켜진 필터 없음</span>'}</div>
      </div>
    </div>
    ${arenaNotesHtml(view.item)}
    ${renderCalc(view)}
  </section>`;
}

function arenaNotesHtml(item) {
  const ids = item.arenas || [];
  if (!ids.length) return '';
  const notes = item.arena_notes || {};
  return `
    <div class="arena-notes">
      <p class="mini-label">비교군 메모</p>
      ${ids
        .map(
          (id) => `<div class="arena-note"><span class="chip chip--arena">${esc(state.cat.arenaLabel(id))}</span><p>${esc(
            notes[id] || '기록된 비교 포인트가 없습니다.',
          )}</p></div>`,
        )
        .join('')}
    </div>`;
}

function filterPill(check) {
  const exempt = check.status === 'exempt';
  const optional = check.status === 'fail' && check.optional;
  const tone = exempt
    ? 'ok'
    : optional
      ? 'sea'
      : check.status === 'fail'
        ? (check.enabled ? 'bad' : 'warn')
        : check.status === 'unknown'
          ? 'muted'
          : 'ok';
  const mark = exempt
    ? '면제'
    : optional
      ? '선택 과금'
      : check.status === 'fail'
        ? '적중'
        : check.status === 'unknown'
          ? '미확인'
          : '통과';
  return `<span class="pill pill--${tone}" title="${esc(check.note)}">${check.enabled ? '' : '꺼짐 · '}${esc(check.label)} ${mark}${
    exempt ? ' · 완결작' : ''
  }${check.status === 'fail' ? ` (${esc(engine.gradeWeakest(check.grade))})` : ''}</span>`;
}

function ruleDescription(evaluation) {
  const rules = contract().verdict_rules || [];
  const index = RULE_INDEX[evaluation.rule] ?? 0;
  const shortMap = {
    1: '① 활성 필터 적중 → 거름',
    '1w': '① 완화 모드 · 등급 C 필터 적중 → 조건부 경고',
    '1c': '⑦ 완결작 면제 · 호환성 주의 → 조건부',
    2: `② 🔴 신호 ${evaluation.reds}개 → 거름`,
    3: '③ 🔴 신호 1개 → 조건부',
    4: `④ 🟡 신호 ${evaluation.yellows}개 → 조건부`,
    5: `⑤ 점수 ${evaluation.score?.toFixed(1)} ≥ 80·🟡 ${evaluation.yellows}개 → 추천`,
    6: '⑥ 그 외 → 조건부',
  };
  return { short: shortMap[evaluation.rule] || shortMap[6], raw: (rules[index] || '').replace(/^\s*\d+\.\s*/, ''), index };
}

function renderCalc(view) {
  const e = view.recordEval;
  const rules = (contract().verdict_rules || []).map((rule) => rule.replace(/^\s*\d+\.\s*/, ''));
  const activeIndex = ruleDescription(e).index;
  const contributions = e.axisStates.filter((axis) => axis.weight > 0 && axis.score != null);
  const maxPart = Math.max(...contributions.map((axis) => axis.weight * axis.score), 1);
  const lines = contributions
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
        ${lines || '<p class="muted">계산 가능한 축 점수가 없습니다.</p>'}
        <div class="calc-total"><span>Σ(w×s) = ${e.numerator.toFixed(2)} · Σw = ${e.denominator.toFixed(2)}</span><b>${e.score != null ? e.score.toFixed(2) : '—'}</b></div>
        <p class="mini-label" style="margin:12px 0 4px">① 하드 필터 — 티어 <code>${esc(e.tierId)}</code></p>
        <div class="tag-cloud">${e.filterChecks.filter((f) => f.enabled).map(filterPill).join('') || '<span class="muted">켜진 필터 없음</span>'}</div>
        ${e.blocking.length ? `<div class="callout callout--bad"><b>차단</b> ${e.blocking.map((f) => `${esc(f.label)}(${esc(engine.gradeWeakest(f.grade))})`).join(' · ')}</div>` : ''}
        ${e.optionalFails.length ? `<div class="callout callout--warn"><b>선택 과금</b> ${e.optionalFails.map((f) => `${esc(f.label)}(${esc(engine.gradeWeakest(f.grade))})`).join(' · ')} — 확률형·P2W 상품은 있지만 무과금으로 본편을 즐길 수 있어 기본 모드에서는 거르지 않고 배지로만 알립니다. <code>strict_monetization</code> 을 켜면 거름이 됩니다.</div>` : ''}
        ${e.weakFails.length ? `<div class="callout callout--warn"><b>근거 약함</b> ${e.weakFails.map((f) => `${esc(f.label)}(${esc(engine.gradeWeakest(f.grade))})`).join(' · ')} — 완화 모드에서 조건부 경고로 처리</div>` : ''}
        ${disabled.length ? `<details><summary class="calc-summary">꺼진 필터 ${disabled.length}개 보기</summary><div class="tag-cloud" style="margin-top:6px">${disabled.map(filterPill).join('')}</div></details>` : ''}
        <p class="mini-label" style="margin:12px 0 4px">④ 판정 규칙 (위에서부터 먼저 맞는 것)</p>
        <ol class="rules">${rules
          .map((rule, i) => `<li class="${i === activeIndex ? 'is-active' : ''}" title="${esc(rule)}">${esc(RULE_TEXT_KO[i] || rule)}</li>`)
          .join('')}</ol>
        <p class="table-note">기본 활성 세트(${esc((contract().default_enabled_filters || []).join(', '))}) + 엄격 모드 기준 이 티어: <b>${
          engine.defaultBlocked(view.item, view.recordTier, contract()) ? '거름' : '통과'
        }</b> · 데이터에 기록된 판정: <b>${esc(engine.VERDICT_META[e.storedVerdict]?.label || e.storedVerdict)}</b></p>
      </div>
    </details>`;
}

/* --- 02 사실(Fact) --- */
function sectionFacts(view) {
  const item = view.item;
  const ads = item.monetization?.ads || {};
  const iap = item.monetization?.iap || {};
  const tier = view.recordTier;
  const stars = storeStarsText(item);
  const starsLabel = storeStarsLabel(item);
  const rows = [
    ['개발사 · 플랫폼', `${esc(item.developer)}<br><span class="muted">${(item.platforms || [])
      .map((p) => esc(engine.PLATFORM_LABEL[p] || p))
      .join(' · ')}${item.release_date ? ` · 출시 ${esc(item.release_date)}` : ''}</span>`],
    ['가격 표기(대표 티어)', `${esc(tier?.price?.display || '—')}<br><span class="muted">${esc(tier?.label || '')}${
      tier?.kind && (engine.KIND_LABEL[tier.kind] || '') !== (tier?.label || '')
        ? ` · ${esc(engine.KIND_LABEL[tier.kind] || tier.kind)}`
        : ''
    }</span>`],
    ['스토어 광고 표기', ads.store_declares_ads === true ? '있음' : ads.store_declares_ads === false ? '없음' : '미확인'],
    ['확률형 아이템 표기', esc(engine.TRI_LABEL[iap.random_items] || '미확인')],
    ['최근 업데이트', `${esc(item.update_profile?.latest_update || '미확인')}${
      item.update_profile?.latest_update_platform
        ? ` · ${esc(engine.PLATFORM_LABEL[item.update_profile.latest_update_platform] || item.update_profile.latest_update_platform)}`
        : ''
    }`],
    [starsLabel, stars],
    ['평가일', esc(item.assessed_at)],
  ];
  return `
  <section class="m-sec" id="secFacts">
    <div class="m-sec-head"><span class="sec-num">02</span><h3>사실 (Fact)</h3>
      <span class="pill pill--ok">스토어·공식 표기 · 출처 고정</span>
    </div>
    <p class="m-sec-note">스토어 표기·가격·업데이트 날짜처럼 <b>확인 가능한 사실</b>만 모았습니다. 각 값의 출처는 08번 근거·출처에 있습니다. 사실과 판단을 섞지 않기 위해 이 표에는 점수·의견을 넣지 않습니다.</p>
    <div class="table-wrap">
      <table class="data fact-table">
        <tbody>${rows.map(([label, value]) => `<tr><th scope="row">${esc(label)}</th><td>${value}</td></tr>`).join('')}</tbody>
      </table>
    </div>
    <p class="table-note">가격은 통화·기간을 분리해 기록하며 환산값을 임의로 만들지 않습니다. 확인하지 못한 값은 추정으로 채우지 않고 ⚪ 미확인으로 둡니다.</p>
  </section>`;
}

/* --- 03 의견(Opinion) --- */
function sectionOpinion(view) {
  const item = view.item;
  const e = view.recordEval;
  const reasons = item.verdict?.reasons || [];
  const conditions = item.verdict?.condition_notes || [];
  const ai = item.axes?.ai_review;
  return `
  <section class="m-sec" id="secOpinion">
    <div class="m-sec-head"><span class="sec-num">03</span><h3>의견 (Opinion)</h3>
      <span class="pill pill--warn">AI·편집 검토 · 사실과 구분</span>
    </div>
    <p class="m-sec-note">아래는 기준표 v${esc(schemaVersion())}에 따라 AI와 편집자가 내린 <b>판단</b>입니다. 02번 사실과 섞이지 않게 따로 두었고, 판정 규칙과 계산 과정은 01번에서 그대로 공개합니다.</p>
    <div class="opinion-grid">
      <article class="opinion-card">
        <h4>판정 이유</h4>
        ${reasons.length ? `<ul class="list">${reasons.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>` : '<p class="muted">기록된 이유가 없습니다.</p>'}
        ${conditions.length ? `<div class="callout callout--warn"><b>조건·주의</b><ul class="list list--muted">${conditions
          .map((n) => `<li>${esc(n)}</li>`)
          .join('')}</ul></div>` : ''}
      </article>
      <article class="opinion-card">
        <h4>AI 검토 요약 <span class="chip chip--grade chip--${esc(engine.gradeWeakest(ai?.evidence_grade))}">근거 ${esc(
          engine.gradeWeakest(ai?.evidence_grade || 'unknown'),
        )}</span></h4>
        <p class="axis-summary">${esc(ai?.summary || 'AI 검토 서술이 없습니다.')}</p>
        <p class="source-meta">감점 사유는 05번 축별 신호와 04번 티어별 판정에 반영되어 있습니다.</p>
      </article>
      <article class="opinion-card">
        <h4>적합 대상</h4>
        <p class="axis-summary">${esc(
          (item.taste_tags || []).length
            ? `이런 결을 원하는 사람: ${(item.taste_tags || []).map((t) => TAG_LABEL[t] || t).join(' · ')}`
            : '취향 태그가 기록되지 않았습니다.',
        )}</p>
        ${e.reds ? `<p class="source-meta">🔴 신호 ${e.reds}개 — 이 감점 요인을 감수하기 어려운 사용자에게는 맞지 않습니다.</p>` : ''}
      </article>
    </div>
    <p class="m-sec-note">판정이 낡았거나 사실과 다르다면 <a href="${correctionUrl(item)}" target="_blank" rel="noopener noreferrer">정정 제보</a>로 근거와 함께 알려 주세요.</p>
  </section>`;
}

/* --- 04 티어별 --- */
function sectionTiers(view) {
  const rows = view.tierEvals
    .map(({ tier, evaluation }) => {
      const meta = engine.VERDICT_META[evaluation.verdict];
      const allFails = evaluation.filterChecks.filter((f) => f.status === 'fail');
      const fails = allFails.length
        ? allFails
            .map(
              (f) =>
                `${f.enabled ? '' : '<span class="muted">(꺼짐)</span> '}${esc(f.label)} <b>${esc(
                  engine.gradeWeakest(f.grade),
                )}</b>${f.optional ? ' <span class="pill pill--sea">선택 과금</span>' : ''}${f.weakGrade && !evaluation.strict ? ' <span class="muted">근거 약함</span>' : ''}`,
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
        <td><span class="pill pill--${meta.tone}">${meta.emoji} ${meta.label}</span><div class="source-meta">기록: ${esc(
          engine.VERDICT_META[evaluation.storedVerdict]?.label || evaluation.storedVerdict,
        )}</div>${
          evaluation.optionalFails.length
            ? '<div class="source-meta">선택 과금 · 무과금 가능</div>'
            : ''
        }</td>
        <td class="num">${evaluation.score != null ? evaluation.score.toFixed(1) : '—'}</td>
        <td>${fails}</td>
        <td>${esc(tier.one_liner || '')}</td>
      </tr>`;
    })
    .join('');

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">04</span><h3>티어별 판정 비교</h3>
      <span class="pill">${view.tierEvals.length}개 티어</span>
    </div>
    <p class="m-sec-note">무료·구독·1회 구매는 사실상 다른 제품입니다. 판정은 현재 가중치·필터·엄격도로 티어마다 다시 계산됩니다.</p>
    <div class="table-wrap">
      <table class="data tier-table">
        <thead><tr><th>티어</th><th>가격</th><th>판정</th><th>점수</th><th>걸린 필터</th><th>한 줄</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </section>`;
}

/* --- 05 축별 --- */
function sectionAxes(view) {
  const cards = view.recordEval.axisStates
    .map((axis) => {
      const meta = engine.SIGNAL_META[axis.signal] || engine.SIGNAL_META.unknown;
      const base = view.item.axes?.[axis.key];
      return `
      <article class="axis-card">
        <div class="axis-card-head">
          <h4>${esc(axis.label)}${axis.profileScoped ? '<small>P1 프로필 전용</small>' : ''}</h4>
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
      </article>`;
    })
    .join('');
  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">05</span><h3>축별 신호와 근거</h3>
      <span class="pill">🟢 ≥ ${contract().signal_thresholds?.green_min ?? 75} · 🟡 ≥ ${contract().signal_thresholds?.yellow_min ?? 50}</span>
    </div>
    <div class="axis-grid">${cards}</div>
    ${view.item.one_liner ? `<p class="m-sec-note">한 줄 정의: ${esc(view.item.one_liner)}</p>` : ''}
    ${scoreNoteHtml(view.item)}
  </section>`;
}

/** v0.5.0 산정 메모 — 점수 원칙(표본 규모 검증·객관 비편향)이 어떻게 적용됐는지 보인다. */
function scoreNoteHtml(item) {
  const notes = item.score_notes || {};
  const rows = [
    ['user_rating', '사용자 평가'],
    ['objective', '객관·신뢰 지표'],
    ['ai_review', 'AI 검토'],
  ].filter(([key]) => notes[key]);
  if (!rows.length) return '';
  return `<div class="callout callout--ok"><b>v0.5.0 산정 메모</b>${rows
    .map(([key, label]) => `<p class="m-sec-note"><b>${label}</b> — ${esc(notes[key])}</p>`)
    .join('')}</div>`;
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

/* --- 06 대체제 --- */
function sectionAlternatives(view) {
  const item = view.item;
  const pool = state.store.get(state.route.arena) || [];
  const alts = engine.alternatives(item, pool, settings()).slice(0, 3);
  if (!alts.length) return '';
  const isBad = view.recordEval.verdict !== 'recommend';
  return `
  <section class="m-sec" id="secAlternatives">
    <div class="m-sec-head"><span class="sec-num">06</span><h3>${isBad ? '같은 비교군 상위 추천 대체제' : '같은 비교군의 다른 선택'}</h3>
      <span class="pill pill--sea">${esc(state.cat.arenaLabel(state.route.arena))} 안에서만</span>
    </div>
    <p class="m-sec-note">다른 분야로 건너뛰지 않습니다. 같은 자리를 두고 겨루는 대체제 중 지금 내 기준에서 추천 판정인 항목만 점수 순으로 보여줍니다.</p>
    <div class="alt-list">
      ${alts
        .map(
          ({ item: alt, tier, evaluation }) => `
        <button type="button" class="alt-row" data-action="item" data-item="${esc(alt.id)}">
          <span class="alt-name">${iconHtml(alt, 'small')}<span class="search-row-text">${esc(alt.name)}</span></span>
          <span class="alt-tier">${esc(tier?.label || '')}</span>
          <span class="alt-score">${evaluation.score?.toFixed(1) ?? '—'}</span>
          <span class="verdict verdict--${engine.VERDICT_META[evaluation.verdict].tone}">${engine.VERDICT_META[evaluation.verdict].emoji} ${
            engine.VERDICT_META[evaluation.verdict].label
          }</span>
          <span class="alt-more">보기 →</span>
        </button>`,
        )
        .join('')}
    </div>
  </section>`;
}

/* --- 07 리뷰 --- */
function sectionReviews(view) {
  const snapshot = view.item.review_snapshot;
  if (!snapshot) return '';
  const sample = engine.reviewSampleCheck(view.item, contract());
  const rows = (snapshot.platforms || [])
    .map((platform) => {
      const { cumulative, recent, gap } = engine.reviewGap(platform);
      const gapTone = gap == null ? '' : gap <= -15 ? 'bad' : gap <= -5 ? 'warn' : gap >= 5 ? 'ok' : '';
      const metricMeta = (metric) =>
        metric ? `${metric.window || '기간 미상'} · ${engine.reviewToHundred(metric.value, metric.scale)?.toFixed(1)}/100 · 근거 ${esc(engine.gradeWeakest(metric.evidence_grade))}` : '';
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
          <div class="bar-row"><span class="bar-label">누적</span><span class="bar-track"><span class="bar-fill bar-fill--cum" style="width:${Math.max(0, Math.min(100, cumulative ?? 0))}%"></span></span><span class="bar-value">${metricValue(platform.cumulative)}</span></div>
          <div class="bar-row"><span class="bar-label">최근</span><span class="bar-track"><span class="bar-fill bar-fill--recent" style="width:${Math.max(0, Math.min(100, recent ?? 0))}%"></span></span><span class="bar-value">${metricValue(platform.recent)}</span></div>
        </div>
        <p class="review-meta">누적 · ${metricMeta(platform.cumulative)}</p>
        ${platform.recent ? `<p class="review-meta">최근 · ${metricMeta(platform.recent)}</p>` : ''}
        ${platform.note ? `<p class="money-note">${esc(platform.note)}</p>` : ''}
      </div>`;
    })
    .join('');

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">07</span><h3>누적 vs 최근 리뷰</h3>
      <span class="pill ${sample.needsDowngrade ? 'pill--bad' : 'pill--ok'}">최소 표본 ${sample.min}건 ${sample.needsDowngrade ? `· 부족 ${sample.insufficient.length}곳` : '· 충족'}</span>
    </div>
    <p class="m-sec-note">5점 척도는 ×20, 10점 척도는 ×10으로 0~100에 맞춰 비교합니다. 누적값만 보면 놓치는 ‘최근 망가짐’을 겨냥합니다.</p>
    ${rows}
    ${snapshot.summary ? `<p class="money-note">${esc(snapshot.summary)}</p>` : ''}
    <div class="callout${sample.needsDowngrade ? ' callout--warn' : ''}">
      <b>표본 규칙</b> 최근 표본이 ${sample.min}건 미만이면 신호를 한 단계 낮춥니다. 점검한 플랫폼 ${sample.checked}곳 · 하향 필요 ${
        sample.needsDowngrade ? '있음' : '없음'
      } · 데이터 ${
        sample.needsDowngrade ? (sample.applied ? '하향 적용됨' : '하향 미적용') : sample.sampleSufficient ? '표본 충분(하향 미적용)' : '표본 상태 미기재'
      }
    </div>
  </section>`;
}

/* --- 08 과금·광고 --- */
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
    <div class="m-sec-head"><span class="sec-num">08</span><h3>과금·광고 4분해</h3>
      <span class="pill ${iap.random_items === 'yes' ? 'pill--bad' : ''}">확률형 ${esc(engine.TRI_LABEL[iap.random_items] || '미확인')}</span>
      <span class="pill">IAP ${esc(engine.TRI_LABEL[iap.present] || '미확인')}</span>
    </div>
    <p class="m-sec-note">‘광고 있음/없음’ 한 칸으로는 미끼형 유입 광고 피해를 잡지 못합니다. 인앱 노출과 유입 정직성을 분리합니다.</p>
    <div class="money-grid">
      <article class="money-card"><h4>⑴ 인앱 광고 노출</h4><div class="money-value">${esc(engine.EXPOSURE_LABEL[ads.in_app_exposure] || ads.in_app_exposure || '미확인')}</div><div class="money-tags">${tags(ads.ad_types)}</div><p class="money-note">스토어 광고 표기: ${ads.store_declares_ads === true ? '있음' : ads.store_declares_ads === false ? '없음' : '미확인'}</p></article>
      <article class="money-card"><h4>⑵ 유입 광고 정직성</h4><div class="money-value">${esc(engine.HONESTY_LABEL[ads.inflow_ad?.honesty] || '미평가')}</div><div class="money-tags"><span class="pill">존재 ${esc(engine.TRI_LABEL[ads.inflow_ad?.present] || '미평가')}</span><span class="pill">근거 ${esc(engine.gradeWeakest(ads.inflow_ad?.evidence_grade || 'unknown'))}</span></div><p class="money-note">${esc(ads.inflow_ad?.note || '평가 기록 없음')}</p></article>
      <article class="money-card"><h4>⑶ 확률형 아이템</h4><div class="money-value">${esc(engine.TRI_LABEL[iap.random_items] || '미확인')}</div><div class="money-tags"><span class="pill">IAP 존재 ${esc(engine.TRI_LABEL[iap.present] || '미확인')}</span><span class="pill">근거 ${esc(engine.gradeWeakest(iap.evidence_grade || 'unknown'))}</span></div><p class="money-note">확률형 여부는 스토어 표기(‘Includes Random Items’)를 그대로 지표로 씁니다 — 등급 A.</p></article>
      <article class="money-card"><h4>⑷ IAP 최고가·첫 결제 유도</h4><div class="money-value">${minText || maxText ? `${esc(minText || '?')} ~ ${esc(maxText || '?')}` : (iap.present === 'yes' ? '가격대 미확인' : '인앱결제 없음')}</div><div class="money-tags"><span class="pill">첫 유도 ${esc(engine.PROMPT_LABEL[iap.first_purchase_prompt] || '미확인')}</span><span class="pill ${iap.p2w === 'yes' ? 'pill--bad' : ''}">P2W ${esc(engine.TRI_LABEL[iap.p2w] || '미확인')}</span><span class="pill ${iap.required_to_progress === 'yes' ? 'pill--bad' : ''}">진행 필수 ${esc(engine.TRI_LABEL[iap.required_to_progress] || '미확인')}</span><span class="pill">근거 ${esc(engine.gradeWeakest(range.evidence_grade || 'unknown'))}</span></div><p class="money-note">${esc(range.note || '가격대 기록 없음')}</p></article>
    </div>
    ${impactBlockHtml(view)}
    <dl class="kv"><dt>구독</dt><dd>${esc(engine.TRI_LABEL[money.subscription?.present] || '미확인')} · ${esc(money.subscription?.display || '—')}</dd><dt>과금 요약</dt><dd>${esc(money.summary || '—')}</dd></dl>
  </section>`;
}

/* --- 08-1 확률형·P2W 강도 --- */
function impactBlockHtml(view) {
  const checks = view.recordEval.filterChecks.filter((check) => check.impactKey);
  const free = view.item.monetization?.free_play;
  if (!checks.length) return '';
  const tone = (check) =>
    check.status === 'pass' ? 'ok' : check.status === 'fail' ? (check.impact === 'optional' ? 'sea' : 'bad') : 'muted';
  return `
    <div class="impact-block">
      <p class="mini-label" style="margin:14px 0 6px">확률형·P2W 강도 (impact)</p>
      <div class="tag-cloud">
        ${checks
          .map(
            (check) =>
              `<span class="pill pill--${tone(check)}" title="${esc(check.note)}">${esc(check.label)} · ${esc(
                engine.IMPACT_META[check.impact]?.label || check.impact || '—',
              )}</span>`,
          )
          .join('')}
      </div>
      ${
        free
          ? `<p class="money-note">무과금 충분성: <b>${esc(FREE_PLAY_LABEL[free.value] || free.value)}</b> · 근거 ${esc(
              engine.gradeWeakest(free.evidence_grade || 'unknown'),
            )} — ${esc(free.note || '')}</p>`
          : '<p class="money-note">무과금 충분성은 기록되지 않았습니다(⚪).</p>'
      }
      <p class="money-note">impact <code>optional</code> 은 상품이 있어도 무과금으로 본편을 즐길 수 있다는 뜻이며, 기본 모드에서는 거르지 않고 배지로 알립니다. <code>core</code> 는 과금 없이 진행이 막혀 거름입니다.</p>
    </div>`;
}

/* --- 09 업데이트 --- */
function sectionUpdates(view) {
  const profile = view.item.update_profile;
  if (!profile) return '';
  const meta = engine.MAINTENANCE_META[profile.maintenance_quality] || engine.MAINTENANCE_META.unknown;
  const lifeKey = view.item.maintenance_status;
  const life = engine.MAINTENANCE_STATUS_META[lifeKey] || null;
  const compat = view.item.flags?.compat_risk;
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
  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">09</span><h3>업데이트 성격</h3>
      ${life ? `<span class="pill pill--${life.tone}">수명 단계 · ${esc(life.label)}</span>` : ''}
      <span class="pill pill--${meta.tone}">${esc(meta.label)}</span>
      <span class="pill">주기 ${esc(engine.CADENCE_LABEL[profile.cadence] || profile.cadence)}</span>
      <span class="pill">최근 업데이트 ${esc(profile.latest_update || '미확인')}${profile.latest_update_platform ? ` · ${esc(engine.PLATFORM_LABEL[profile.latest_update_platform] || profile.latest_update_platform)}` : ''}</span>
    </div>
    <p class="m-sec-note">‘활발한가’가 아니라 ‘무엇을 실어 나르는가’를 봅니다 — ${esc(meta.desc)}.</p>
    ${life && lifeKey !== 'active' ? `<div class="callout"><b>수명 단계 · ${esc(life.label)}</b> ${esc(
      view.item.maintenance_note || life.desc,
    )}${lifeKey === 'feature_complete' ? ' — 완결작은 <code>stale_over_12m</code> 필터가 켜져 있어도 면제(exempt)로 계산합니다. 단 보안·OS 호환성 문제가 별도 신호로 잡히면 추천 대신 조건부 경고로 내립니다.' : ''}</div>` : ''}
    ${risky ? '<div class="callout callout--bad"><b>경고 고정</b> 과금·약관 변경이 최근 평가 하락과 겹칩니다. 최근 업데이트 일자만으로 유지보수 신호를 🟢로 주지 않습니다.</div>' : ''}
    ${compat ? `<p class="money-note">보안·OS 호환성 신호: <b>${esc(engine.TRI_LABEL[compat.value] || compat.value)}</b> — ${esc(compat.note || '기록 없음')}</p>` : ''}
    <div class="table-wrap">
      <table class="data">
        <thead><tr><th>날짜</th><th>성격</th><th>플랫폼</th><th>공약</th><th>근거</th><th>메모</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="6" class="muted">기록된 업데이트가 없습니다.</td></tr>'}</tbody>
      </table>
    </div>
    <p class="money-note">${esc(profile.assessment || '')}</p>
  </section>`;
}

/* --- 10 근거·출처 --- */
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
    <div class="m-sec-head"><span class="sec-num">10</span><h3>근거·출처</h3>
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

/* ------------------------------------------------------------ 미세조정 드로어 */

/**
 * 도메인별 필터 표시 이름(v0.4.2) — catalog.json 의 domains[].filter_labels 가 있으면 그 이름을 쓴다.
 * 같은 9개 필터를 AI 도구에서는 '불투명 크레딧·한도 함정 제외'처럼 도메인 문법으로 부른다(스키마·엔진은 그대로).
 */
function domainFilterLabel(def) {
  const dom = state.route.domain ? state.cat.domain(state.route.domain) : null;
  return (dom?.filter_labels || {})[def.key] || def.label;
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
      <div class="panel-head"><h3>가중치 프리셋</h3><span class="panel-hint">합계 100%로 정규화</span></div>
      <div class="preset-row" id="presets">
        ${PRESETS.map(
          (preset) =>
            `<button type="button" class="preset" data-preset="${esc(preset.id)}" aria-pressed="${
              state.preset === preset.id
            }" title="${esc(preset.hint)}">${esc(preset.label)}</button>`,
        ).join('')}
      </div>
      <div class="weights" id="weights">
        ${axes
          .map(
            (def, index) => `
          <div class="weight">
            <div class="weight-head">
              <span class="weight-name">${esc(def.label)}<small>축 ${index + 1}</small></span>
              <span class="weight-pct" id="pct-${esc(def.key)}">—</span>
            </div>
            <input type="range" id="range-${esc(def.key)}" min="0" max="100" step="5" value="${
              state.weights[def.key] ?? 0
            }" data-axis="${esc(def.key)}" aria-label="${esc(def.label)} 가중치" />
            <div class="weight-meta"><span>기본 ${pct(def.default_weight ?? 0)}</span><span id="meta-${esc(def.key)}">w = 0.00</span></div>
          </div>`,
          )
          .join('')}
      </div>
      <div class="weight-bar" id="weightBar" aria-hidden="true"></div>
      <p class="hint">‘균형 기본’은 처음 온 사람을 위한 기본값입니다. 슬라이더를 움직이면 지금 보고 있는 비교군이 즉시 다시 계산됩니다.</p>
    </section>

    <section class="tune-sec">
      <div class="panel-head"><h3>하드 필터</h3><span class="panel-hint" id="filterCount">0/0</span></div>
      <p class="hint">켜진 필터에 하나라도 걸리면 그 티어는 곧바로 <strong>거름</strong>입니다. 지금 도메인의 팩을 먼저 보여줍니다.</p>
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
                    defaults.has(def.key) ? '기본 · ' : ''
                  }${esc(def.key)}</span></span>
                </label>`,
                )
                .join('')}
            </div>
          </details>`;
        })
        .join('')}
      <button type="button" class="text-btn" data-action="reset-filters">기본 세트로 되돌리기</button>
    </section>

    <section class="tune-sec">
      <div class="panel-head"><h3>과금 강도</h3><span class="panel-hint" id="strictMonetizationState">${state.strictMonetization ? 'ON' : 'OFF'}</span></div>
      <label class="switch">
        <input type="checkbox" id="strictMonetizationToggle" ${state.strictMonetization ? 'checked' : ''} />
        <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
        <span class="switch-text"><code>strict_monetization</code> — 상점에 확률형·P2W 상품이 하나라도 있으면 거름</span>
      </label>
      <p class="hint" id="strictMonetizationHint">${
        state.strictMonetization
          ? '지금은 상품이 있기만 해도 거름입니다(기존 v0.3.1 동작). 무과금으로 충분한 작품까지 걸러집니다.'
          : '기본값은 OFF 입니다. 확률형·P2W 상품이 있어도 무과금으로 본편을 즐길 수 있으면 「선택 과금 · 무과금 가능」 배지로만 알리고, 점수·신호로 추천·조건부를 정합니다. 과금 없이 진행이 막히는 작품(impact: core)은 이 설정과 무관하게 거름입니다.'
      }</p>
    </section>

    <section class="tune-sec">
      <div class="panel-head"><h3>근거 엄격 모드</h3><span class="panel-hint" id="strictState">${state.strict ? 'ON' : 'OFF'}</span></div>
      <label class="switch">
        <input type="checkbox" id="strictToggle" ${state.strict ? 'checked' : ''} />
        <span class="switch-track" aria-hidden="true"><span class="switch-thumb"></span></span>
        <span class="switch-text"><code>strict_evidence</code> — 등급 C 근거만 있는 필터 적중도 거름으로 처리</span>
      </label>
      <p class="hint" id="strictHint">${
        state.strict
          ? '끄면 근거가 약한(등급 C) 필터 적중은 ‘근거 약함’ 경고가 붙은 <strong>조건부</strong>로 완화됩니다.'
          : '지금은 완화 모드입니다. 등급 C 근거의 필터 적중은 거름 대신 <strong>조건부 경고</strong>로 내려갑니다.'
      }</p>
    </section>

    <footer class="tune-foot">
      <p class="mini-label">현재 설정</p>
      <p id="tuneFootText"></p>
      <button type="button" class="text-btn" data-action="open-method">방법론·용어 보기</button>
      <button type="button" class="text-btn" data-action="share-state">이 기준 링크 복사</button>
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
    monetizationHint.textContent = state.strictMonetization
      ? '지금은 상품이 있기만 해도 거름입니다(기존 v0.3.1 동작). 무과금으로 충분한 작품까지 걸러집니다.'
      : '기본값은 OFF 입니다. 확률형·P2W 상품이 있어도 무과금으로 본편을 즐길 수 있으면 「선택 과금 · 무과금 가능」 배지로만 알리고, 점수·신호로 추천·조건부를 정합니다. 과금 없이 진행이 막히는 작품(impact: core)은 이 설정과 무관하게 거름입니다.';
  }
  const hint = $('strictHint');
  if (hint) {
    hint.innerHTML = state.strict
      ? '끄면 근거가 약한(등급 C) 필터 적중은 ‘근거 약함’ 경고가 붙은 <strong>조건부</strong>로 완화됩니다.'
      : '지금은 완화 모드입니다. 등급 C 근거의 필터 적중은 거름 대신 <strong>조건부 경고</strong>로 내려갑니다.';
  }
  const foot = $('tuneFootText');
  if (foot) {
    const weights = scoringAxes().map((def) => `${def.label} ${state.weights[def.key]}%`).join(' · ');
    foot.innerHTML = `${esc(presetLabel())} · ${esc(weights)}<br>필터 ${state.enabledFilters.length}개 · ${
      state.strict ? '엄격' : '완화'
    } 모드 · 선택 과금 ${state.strictMonetization ? '거름' : '허용'}`;
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
  $('methodBody').innerHTML = `
    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">A</span><h3>4단 구조 — 무엇을 같은 표에 놓는가</h3></div>
      <p class="m-sec-note">도메인(앱·게임·AI 도구) → 대분류 → 비교군 → 항목·티어. <b>점수 평균·순위·요약은 오직 같은 비교군 안에서만</b> 계산합니다. 노트 앱과 카드 게임을 한 줄에 섞어 평균 내지 않습니다.</p>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>단계</th><th>역할</th><th>이 데이터</th></tr></thead>
        <tbody>
          ${(state.cat.catalog.domains || [])
            .map(
              (dom) =>
                `<tr><td>1 도메인</td><td>${esc(dom.label)} — ${esc(dom.description)}</td><td>${state.cat
                  .arenasOf(dom.id)
                  .map((a) => esc(a.label))
                  .join(' · ')}</td></tr>`,
            )
            .join('')}
          <tr><td>2 대분류</td><td>도메인 안의 큰 갈래</td><td>${(state.cat.catalog.categories || [])
            .map((c) => esc(c.label))
            .join(' · ')}</td></tr>
          <tr><td>3 비교군</td><td>실제 대체제 묶음</td><td>${(state.cat.catalog.arenas || []).map((a) => esc(a.label)).join(' · ')}</td></tr>
          <tr><td>4 항목·티어</td><td>선택·판정 단위(무료/구독/1회 구매)</td><td>같은 앱이라도 티어마다 따로 판정</td></tr>
        </tbody>
      </table></div>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">B</span><h3>네 축과 가중 점수</h3></div>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>축</th><th>무엇을 보는가</th><th>기본 가중치</th></tr></thead>
        <tbody>
          ${axes
            .map(
              (axis) =>
                `<tr><td>${esc(axis.label)}${axis.profile_scoped ? ' <span class="muted">(프로필 전용)</span>' : ''}</td><td>${
                  {
                    user_rating: '최근 구간 vs 누적 괴리 + 표본 규모 검증(수십만~수백만 누적 우대)',
                    objective: '기능 완성도·생태계/연동성·안정성·보안·정책/과금 투명성 — 클라우드·비공개 소스라는 이유만으로 깎지 않음',
                    ai_review: '본질 완성도·함정 구조·강점/약점',
                    personal_fit: '취향 태그·프로필 적합도(있을 때만 — 켜지지 않은 프로필 축은 판정에 세지 않음)',
                  }[axis.key] || ''
                }</td><td>${pct(axis.default_weight ?? 0)}</td></tr>`,
            )
            .join('')}
        </tbody>
      </table></div>
      <p class="m-sec-note">가중 점수 = Σ(w×s) ÷ Σw. 점수가 없는 축(⚪)은 분자·분모에서 모두 빠집니다. 입력 가중치는 합계로 정규화합니다. 과금의 <b>강도</b>는 점수 대신 impact·free_play 로 따로 기록해, 같은 사실을 두 번 감점하지 않습니다.</p>
      <p class="m-sec-note"><b>v0.5.0 기본 배분은 사용자 50 · 객관 25 · AI 25.</b> 대중이 실제로 검증한 평점의 무게를 높였습니다. 가중치가 0인 축(내 기준 적합)은 신호가 있어도 추천/거름 계산에 세지 않습니다 — 프로필을 켰을 때만 네 번째 축이 됩니다.</p>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">B2</span><h3>사용자 평가의 표본 규모 검증</h3></div>
      <p class="m-sec-note">같은 4.4~4.6★이라도 <b>리뷰 1만 개와 수십만~수백만 개</b>는 검증의 무게가 다릅니다. 누적 표본으로 규모 등급을 매기고, 얇은 3자 최근 표본이 큰 스토어 누적을 통째로 덮지 않게 합니다.</p>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>누적 표본</th><th>규모 등급</th><th>쓰는 법</th></tr></thead>
        <tbody>
          <tr><td>100만 이상</td><td>대규모 활성 유저</td><td>4.4★(88) 이상 유지 시 🟢 검증 하한(75)</td></tr>
          <tr><td>10만~100만</td><td>대형</td><td>같은 하한 적용</td></tr>
          <tr><td>1만~10만</td><td>중형</td><td>점수 보정 없음 — 있는 그대로</td></tr>
          <tr><td>1천 미만</td><td>소형·미세 표본</td><td>최근 값 우선 + 신호 한 단계 하향(과대평가 방지)</td></tr>
        </tbody>
      </table></div>
      <p class="m-sec-note">최근 구간이 <b>3자 집계(등급 C)·1,000건 미만</b>인데 스토어 누적이 <b>등급 A/B·10만 건 이상·4.4★ 이상</b>이면, 최근 값은 ‘하락 방향 신호’로만 쓰고 그 플랫폼 점수는 (누적+최근)÷2로 둡니다. 단 과금·약관 변경이 급락과 겹친 경우(예: 에버노트 가격 인상)는 완화하지 않습니다 — 돈·조건이 바뀌어 생긴 하락은 표본이 얇아도 실제 신호입니다.</p>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">C</span><h3>근거 등급 A/B/C</h3></div>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>등급</th><th>정의</th></tr></thead>
        <tbody>
          <tr><td><span class="chip chip--A">A</span></td><td>스토어·공식 가격 페이지·개발자 공지에서 직접 확인</td></tr>
          <tr><td><span class="chip chip--B">B</span></td><td>언론 보도·공식 발표 인용(1차를 인용한 신뢰 매체)</td></tr>
          <tr><td><span class="chip chip--C">C</span></td><td>3자 집계·개별 리뷰·커뮤니티(교차 확인 전 신뢰도 중간)</td></tr>
          <tr><td><span class="chip chip--muted">⚪</span></td><td>확인하지 못한 값 — 추정으로 채우지 않고 계산에서 제외</td></tr>
        </tbody>
      </table></div>
      <p class="m-sec-note">최근 리뷰 표본이 100건 미만이면 신호를 한 단계 낮춥니다. 복합 등급(A/C)은 가장 약한 등급으로 표기합니다.</p>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">D</span><h3>확률형·P2W 강도 3단계</h3></div>
      <p class="m-sec-note">상점에 확률형·P2W 상품이 <b>하나라도 있으면 거름</b>이 아니라, 그 상품을 사지 않아도 게임이 성립하는지를 먼저 봅니다. 필터 상태는 <code>fail</code> 로 남겨 상품이 있다는 사실을 숨기지 않고, 판정만 강도에 따라 나뉩니다.</p>
      <div class="table-wrap"><table class="data">
        <thead><tr><th>impact</th><th>뜻</th><th>기본 모드의 판정</th></tr></thead>
        <tbody>
          <tr><td><span class="pill pill--ok">none</span></td><td>상품 자체가 없다</td><td>필터 통과</td></tr>
          <tr><td><span class="pill pill--sea">optional</span></td><td>상품은 있으나 인게임 재화·무과금으로 본편·핵심 콘텐츠를 충분히 즐길 수 있다</td><td><b>거르지 않고</b> 「선택 과금 · 무과금 가능」 배지 · 점수·신호로 추천/조건부</td></tr>
          <tr><td><span class="pill pill--bad">core</span></td><td>과금·확률형 뽑기 없이는 성장 벽에 막히거나 진행·경쟁이 실질적으로 불가능하다</td><td>거름(🔴)</td></tr>
        </tbody>
      </table></div>
      <p class="m-sec-note">근거는 <code>monetization.free_play</code>(무과금 충분성)에 남깁니다. <code>impact: optional</code> 이면 무과금으로 충분하다는 근거가 있어야 하고 검증기가 이를 확인합니다. ‘내 기준 미세조정’의 <code>strict_monetization</code>(기본 OFF)을 켜면 optional 까지 상품 존재만으로 거릅니다 — v0.3.1 과 같은 동작입니다.</p>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">E</span><h3>판정 규칙 (위에서부터 먼저 맞는 것)</h3></div>
      <ol class="rules rules--static">${rules
        .map((rule, i) => `<li class="${i === 0 ? 'is-active' : ''}" title="${esc(rule)}">${esc(RULE_TEXT_KO[i] || rule)}</li>`)
        .join('')}</ol>
      <p class="m-sec-note">티어 단위로 판정하고, 최소 비용 추천 경로를 함께 냅니다. 완결작(<code>maintenance_status=feature_complete</code>)은 업데이트 공백 필터에서 면제하되, 보안·OS 호환성 신호가 있으면 조건부 경고로 내립니다.</p>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">F</span><h3>독립성 — 무엇을 받지 않는가</h3></div>
      <div class="callout callout--ok">
        <b>파로스는 어필리에이트 링크·유료 광고·협찬 배치를 쓰지 않습니다.</b>
        순위·판정·점수는 어떤 대가와도 무관하며, 스토어 이미지도 복제하지 않고 텍스트·수치·공식 링크만 씁니다.
        판정이 틀렸거나 낡았다면 누구나 근거와 함께 정정을 제보할 수 있습니다.
      </div>
    </section>

    <section class="m-sec">
      <div class="m-sec-head"><span class="sec-num">G</span><h3>용어 도움말</h3></div>
      <dl class="kv kv--glossary">
        <dt>근거 등급</dt><dd>A/B/C — 값이 어디서 왔는지. C뿐이면 판정을 낮게 잡습니다.</dd>
        <dt>하드 필터</dt><dd>점수와 무관하게 거르는 절대 조건(강제 광고·확률형 뽑기·P2W·계정 필수 등).</dd>
        <dt>선택 과금(impact: optional)</dt><dd>상점에 확률형·P2W 상품이 있어도 인게임 재화·무과금으로 본편을 충분히 즐길 수 있는 상태. 기본 모드에서는 거르지 않고 「선택 과금 · 무과금 가능」 배지로 알립니다.</dd>
        <dt>핵심 과금(impact: core)</dt><dd>과금·확률형 뽑기 없이는 성장 벽에 막히거나 진행·경쟁이 실질적으로 불가능한 상태. 기본 모드에서도 거름입니다.</dd>
        <dt>strict_monetization</dt><dd>‘내 기준 미세조정’의 토글(기본 OFF). 켜면 상품이 있기만 해도 거름 — v0.3.1 과 같은 동작입니다.</dd>
        <dt>엄격 모드</dt><dd>등급 C 근거의 필터 적중도 거름으로 처리. 끄면 ‘근거 약함’ 조건부 경고로 완화합니다.</dd>
        <dt>면제(exempt)</dt><dd>완결작이 12개월 넘게 업데이트가 없어도 방치가 아니라고 판단한 상태. 거름이 아닙니다.</dd>
        <dt>표본 규모 검증</dt><dd>수십만~수백만 명이 매긴 누적 평점은 수백 건짜리 3자 최근 표본보다 무겁게 봅니다. 얇은 최근 표본은 ‘하락 방향 신호’로만 쓰고, 큰 누적과 반씩 섞습니다(v0.5.0).</dd>
        <dt>프라이버시·로컬 중시 프리셋</dt><dd>객관 비중을 높이고 ‘계정 필수·과도한 데이터 수집’ 필터를 함께 켜는 프리셋. 기본 화면은 클라우드·비공개 소스를 깎지 않고, 로컬·프라이버시가 목적일 때 이 프리셋으로 가릅니다.</dd>
        <dt>비교군</dt><dd>같은 자리를 두고 겨루는 대체제 묶음. 평균·순위는 이 안에서만 냅니다.</dd>
        <dt>⚪ 미확인</dt><dd>근거를 찾지 못한 값. 통과로 치지 않고 ‘주의’로 표시합니다.</dd>
        <dt>재검토 필요</dt><dd>평가일 이후 ${contract().freshness?.review_after_days ?? 180}일이 지난 판정. 최신 사실로 읽지 마세요.</dd>
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

/* ------------------------------------------------------------- 보관함·공유 */

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
      el.textContent = on ? '★ 보관됨' : '☆ 보관';
    }
  });
  if (state.route.view === 'home' && $('bookmarkSection')) {
    const list = $('bookmarkSection').querySelector('.bookmark-list');
    const hint = $('bookmarkHint');
    if (hint) hint.textContent = `${state.bookmarks.length}건 · 이 브라우저에만 저장`;
    if (list) {
      list.innerHTML = state.bookmarks.length
        ? state.bookmarks.map((bid) => recordById(bid)).filter(Boolean).map(bookmarkRowHtml).join('')
        : '<p class="empty">카드나 상세의 ☆ 버튼을 누르면 여기에 모입니다. (localStorage)</p>';
    }
  }
  toast(state.bookmarks.includes(id) ? '보관함에 담았습니다.' : '보관함에서 뺐습니다.');
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
  toast(ok ? '공유용 요약을 복사했습니다.' : '복사 권한이 없습니다. 아래 요약을 직접 선택해 주세요.', ok ? '' : text);
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
function toast(message, detail) {
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
  $('bookmarkBtn')?.addEventListener('click', async () => {
    if (state.route.view !== 'home') await goHome();
    $('bookmarkSection')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  $('modalBackdrop')?.addEventListener('mousedown', (event) => {
    if (event.target === $('modalBackdrop')) closeDetail();
  });
  $('compareOpen')?.addEventListener('click', () => {
    if (state.route.compare.length >= 2) navigate({ view: 'compare' });
  });
  $('compareClear')?.addEventListener('click', clearCompare);
  window.addEventListener('popstate', () => {
    applyUrl();
  });
}

async function onClick(event) {
  const target = event.target;

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
  if (target.closest('label.compare-check')) return;

  const action = target.closest('[data-action]');
  if (action) {
    const kind = action.dataset.action;
    if (kind === 'home') return goHome();
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
      writeClipboard(location.href).then((ok) => toast(ok ? '현재 기준 링크를 복사했습니다.' : '복사하지 못했습니다.', location.href));
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
    if (!$('methodBackdrop')?.hidden) return closeMethod();
    if (!$('modalBackdrop')?.hidden) return closeDetail();
    if (!$('tuneDrawer')?.hidden) return closeTune();
  }
  if (event.key === 'Tab') {
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
      <strong>데이터를 불러오지 못했습니다.</strong>
      <span>${esc(err?.message || err)}</span>
      <span>이 페이지는 <code>index.html</code>을 파일로 직접 열면 <code>fetch</code>가 차단됩니다. <code>projects/pharos/web</code> 폴더에서
      <code>python3 -m http.server 8000</code> 을 실행한 뒤 <code>http://localhost:8000/</code> 로 접속하세요.
      (<code>data/</code>·<code>schema/</code> 사본이 없으면 <code>python3 projects/pharos/scripts/sync_web_data.py</code> 로 원본과 맞춥니다.)</span>
    </div>`;
  $('datasetChip').textContent = '데이터 없음';
}

init();
