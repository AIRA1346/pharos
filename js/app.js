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
import { t, labeled, nfmt, days, initLang, setLang, getLang, applyStaticI18n } from './i18n.js';

document.getElementById('bootNote')?.remove();

const LS = {
  theme: 'pharos-theme',
  prefs: 'pharos-prefs',
  bookmarks: 'pharos-bookmarks',
  lighthouse: 'pharos_lighthouse_state_v1',
};

const PRESETS = [
  { id: 'balanced', weights: { user_rating: 50, objective: 25, ai_review: 25 } },
  { id: 'popular', weights: { user_rating: 65, objective: 20, ai_review: 15 } },
  { id: 'comfort', weights: { user_rating: 20, objective: 60, ai_review: 20 } },
  {
    id: 'privacy',
    weights: { user_rating: 25, objective: 55, ai_review: 20 },
    filters: ['account_required', 'data_collection'],
  },
  { id: 'ai', weights: { user_rating: 20, objective: 25, ai_review: 55 } },
];

const presetLabelOf = (id) => t(`preset.${id}`);
const presetHintOf = (id) => t(`preset.${id}.hint`);

const SORT_KEYS = ['score', 'score-asc', 'risk', 'name'];
const sortLabel = (key) => t(`sort.${key === 'score-asc' ? 'scoreAsc' : key}`);

/* 도메인·플랫폼·필터·축 라벨은 i18n.js 의 사전에서 온다. 데이터 라벨(비교군·대분류)은
   data/catalog.json 과 data/en.json 번들이 맡는다. */
const RULE_INDEX = { 1: 0, '1w': 0, '1c': 6, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5 };

const L = {
  flag: (key) => labeled('flag', key, key),
  verification: (key) => labeled('verification', key, key),
  export: (key) => labeled('export', key, key),
  freePlay: (key) => labeled('freePlay', key, key),
  method: (key) => labeled('method', key, key),
  tag: (key) => labeled('tag', key, key),
};

const state = {
  core: null,
  cat: null,
  store: null,
  route: { view: 'home', domain: null, category: null, arena: null, item: null, compare: [] },
  query: '',
  sort: 'score',
  showAvoided: true,
  homeDomain: 'all',
  weights: {},
  enabledFilters: [],
  strict: true,
  strictMonetization: false,
  preset: 'balanced',
  bookmarks: [],
  theme: 'dark',
  lang: 'ko',
  lastFocus: null,
  lh: {
    data: null,
    filters: { price: 'all', platform: 'all', tier: 1 },
    current: null,
    history: [],
    skips: 0,
    lastGameId: null,
  },
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
const num = (value) => nfmt(value ?? 0);
const locale = () => (getLang() === 'en' ? 'en-US' : 'ko-KR');
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
  if (label) label.textContent = state.theme === 'dark' ? t('nav.theme.dark') : t('nav.theme.light');
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

/** <html lang>·<title>·메타 설명·OG 를 현재 언어로 맞춘다. */
function applyDocumentLang() {
  document.documentElement.lang = state.lang;
  document.title = t('meta.title');
  const description = document.querySelector('meta[name="description"]');
  if (description) description.setAttribute('content', t('meta.description'));
  const ogTitle = document.querySelector('meta[property="og:title"]');
  if (ogTitle) ogTitle.setAttribute('content', t('meta.ogTitle'));
  const ogDescription = document.querySelector('meta[property="og:description"]');
  if (ogDescription) ogDescription.setAttribute('content', t('meta.ogDescription'));
  renderLangToggle();
}

function renderLangToggle() {
  const wrap = $('langToggle');
  if (!wrap) return;
  wrap.querySelectorAll('[data-lang]').forEach((btn) => {
    btn.setAttribute('aria-pressed', btn.dataset.lang === state.lang ? 'true' : 'false');
  });
}

/** 언어 전환 — 저장하고 URL 에 lang 을 박은 뒤 같은 화면을 그 언어로 다시 연다. */
function switchLang(lang) {
  if (!lang || lang === state.lang) return;
  setLang(lang);
  state.lang = lang;
  const params = new URLSearchParams(location.search);
  params.set('lang', lang);
  location.href = `${location.pathname}?${params.toString()}`;
}

/* --------------------------------------------------------------- 라우팅 */

function parseUrl() {
  const params = new URLSearchParams(location.search);
  const route = { view: 'home', domain: null, category: null, arena: null, item: null, compare: [] };
  const tab = params.get('tab');
  const domain = params.get('domain');
  const wantsLighthouse = domain === 'lighthouse' || tab === 'lighthouse';
  if (wantsLighthouse) {
    route.view = 'lighthouse';
    const tier = Number(params.get('lh_tier'));
    if ([1, 2, 3].includes(tier)) state.lh.filters.tier = tier;
    const price = params.get('lh_price');
    if (price === 'free' || price === 'all') state.lh.filters.price = price;
    const platform = params.get('lh_platform');
    if (platform === 'pc' || platform === 'mobile' || platform === 'all') state.lh.filters.platform = platform;
  } else if (domain && state.cat.domain(domain)) {
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
    const { tier, price, platform } = state.lh.filters;
    if (tier !== 1) params.set('lh_tier', String(tier));
    if (price !== 'all') params.set('lh_price', price);
    if (platform !== 'all') params.set('lh_platform', platform);
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
  document.body.classList.toggle('is-home', !state.route.domain && state.route.view !== 'lighthouse');
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
  state.homeDomain = 'all';
  state.route = { view: 'home', domain: null, category: null, arena: null, item: null, compare: [] };
  return render();
}

/* ------------------------------------------------------------ 상단·경로 UI */

function renderDomainTabs() {
  const wrap = $('domainTabs');
  if (!wrap) return;
  const items = [
    { key: 'home', label: t('nav.home'), active: !state.route.domain && state.route.view !== 'lighthouse', action: 'home' },
    ...(state.cat?.catalog.domains || []).map((dom) => ({
      key: dom.id,
      label: dom.label,
      active: state.route.domain === dom.id,
      action: 'domain',
    })),
    { key: 'lighthouse', label: t('nav.lighthouse'), active: state.route.view === 'lighthouse', action: 'lighthouse' },
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
  const crumbs = [{ label: t('nav.home'), action: 'home' }];
  if (route.view === 'lighthouse') {
    crumbs.push({ label: t('nav.lighthouse') });
  } else if (route.domain) {
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
    if (route.view === 'compare') crumbs.push({ label: t('crumb.compare') });
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
    note.textContent =
      route.view === 'lighthouse'
        ? t('lh.crumbNote')
        : arena
          ? `${shortText(arena.description, 64)}`
          : route.domain
            ? `${state.cat.domain(route.domain)?.description || ''}`
            : t('crumb.homeNote');
  }
}

function renderDatasetChip() {
  const chip = $('datasetChip');
  if (!chip) return;
  const version = state.core?.schema?.title?.match(/v([\d.]+)/)?.[1] || contract().schema_version || '?';
  const idx = state.core.index;
  chip.textContent = t('dataset.chip', {
    v: version,
    n: num(idx.counts.items),
    a: idx.counts.arenas,
  });
  chip.title = t('dataset.chipTitle', {
    v: version,
    d: idx.counts.domains,
    c: idx.counts.categories,
    a: idx.counts.arenas,
  });
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
        <p class="eyebrow">${esc(t('home.eyebrow'))}</p>
        <h1>${t('home.title.before')}<span class="hl">${t('home.title.hl')}</span>${t('home.title.after')}</h1>
        <p class="lede">${t('home.lede')}</p>
      </div>
      <form class="home-search" id="homeSearchForm" role="search" autocomplete="off">
        <span class="search-ico" aria-hidden="true">⌕</span>
        <input type="search" id="homeSearch" placeholder="${esc(t('home.search.placeholder'))}"
               aria-label="${esc(t('home.search.aria'))}" value="${esc(state.query)}" />
        <button type="submit" class="primary-btn">${esc(t('home.search.btn'))}</button>
      </form>
      <div class="hero-meta">
        <span>${t('home.meta.items', { n: num(counts.items) })}</span>
        <span>${t('home.meta.domains', { n: counts.domains })}</span>
        <span>${t('home.meta.arenas', { n: counts.arenas })}</span>
        <span>${esc(t('home.meta.schema', { v: contract().schema_version || '0.4.0' }))}</span>
        ${lastAssessed ? `<span>${esc(t('home.meta.lastAssessed', { date: lastAssessed }))}</span>` : ''}
        <span class="hero-meta-actions">
          <button type="button" class="text-btn" data-action="open-method">${esc(t('home.meta.method'))}</button>
          <button type="button" class="text-btn" data-action="open-tune">${esc(t('home.meta.tune', { preset: presetLabel() }))}</button>
        </span>
      </div>
    </div>

    <div id="homeSearchResults" class="home-search-results" ${state.query ? '' : 'hidden'}></div>

    <section class="home-block genre-showcase" id="genreShowcase">
      <div class="section-head">
        <h2>${esc(t('home.genreTitle'))}</h2>
        <span class="section-hint" id="genreHint">${esc(homeGenreHint(arenas))}</span>
      </div>
      ${homeDomainFilterHtml(arenas)}
      <div class="genre-list" id="genreList">${homeArenas(arenas).map((arena) => genreBlockHtml(arena, { kicker: true })).join('')}</div>
      <p class="empty" id="genreEmpty" ${homeArenas(arenas).length ? 'hidden' : ''}>${esc(t('home.genreEmpty'))}</p>
    </section>

    <section class="home-block" id="gapReport">
      <div class="section-head">
        <h2><span class="verdict-dot verdict-dot--bad"></span>${esc(
          state.cat.catalog.home?.gap_report?.title || t('home.gapTitle'),
        )}</h2>
        <span class="section-hint">${esc(t('home.gapHint', { n: (state.cat.catalog.home?.gap_report?.min_store_stars ?? 4).toFixed(1) }))}</span>
      </div>
      <p class="section-sub">${esc(
        state.cat.catalog.home?.gap_report?.note || '',
      )}</p>
      <div class="gap-list">
        ${gapItems.length ? gapItems.map(gapRowHtml).join('') : `<p class="empty">${esc(t('home.gapEmpty'))}</p>`}
      </div>
    </section>

    <section class="home-block" id="bookmarkSection">
      <div class="section-head">
        <h2>${esc(t('home.bookmarksTitle'))}</h2>
        <span class="section-hint" id="bookmarkHint">${esc(t('home.bookmarkHint', { n: state.bookmarks.length }))}</span>
      </div>
      <div class="bookmark-list">
        ${
          state.bookmarks.length
            ? state.bookmarks
                .map((id) => recordById(id))
                .filter(Boolean)
                .map(bookmarkRowHtml)
                .join('')
            : `<p class="empty">${esc(t('home.bookmarkEmpty'))}</p>`
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
 * 홈 장르 쇼케이스의 도메인 필터 — 12개 장르가 세로로 길게 이어지므로
 * 전체 · 앱 · 게임 · AI 도구 건수를 먼저 보여 주고, 누른 도메인의 장르만 남긴다.
 * 필터 바는 스크롤해도 상단에 붙어 있어 목록 어디서든 도메인을 바꿀 수 있다.
 */
function homeArenas(arenas) {
  return state.homeDomain === 'all' ? arenas : arenas.filter((arena) => arena.domain === state.homeDomain);
}

function homeDomainFilterHtml(arenas) {
  const rows = [
    { id: 'all', label: t('home.domainAll'), count: arenas.length },
    ...(state.cat.catalog.domains || [])
      .map((dom) => ({ id: dom.id, label: dom.label, count: arenas.filter((a) => a.domain === dom.id).length }))
      .filter((row) => row.count > 0),
  ];
  return `<div class="domain-filter" id="homeDomainFilter" role="group" aria-label="${esc(t('home.domainFilterAria'))}">${rows
    .map(
      (row) =>
        `<button type="button" class="domain-chip" data-home-domain="${esc(row.id)}" aria-pressed="${
          state.homeDomain === row.id ? 'true' : 'false'
        }"><span>${esc(row.label)}</span><b>${row.count}</b></button>`,
    )
    .join('')}</div>`;
}

function homeGenreHint(arenas) {
  const shown = homeArenas(arenas);
  const scope =
    state.homeDomain === 'all'
      ? t('home.genreHint.all', { n: shown.length })
      : t('home.genreHint.domain', { domain: state.cat.domainLabel(state.homeDomain), n: shown.length });
  return t(state.preset === 'balanced' ? 'home.genreHint.one' : 'home.genreHint.mine', { scope });
}

/** 도메인 필터 클릭 — 목록 DOM만 다시 그려 검색어·스크롤 상태를 건드리지 않는다. */
function setHomeDomain(id) {
  const valid = ['all', ...(state.cat.catalog.domains || []).map((dom) => dom.id)];
  if (!valid.includes(id) || state.homeDomain === id) return;
  state.homeDomain = id;
  const featured = (state.cat.catalog.home?.featured_arenas || []).map((aid) => state.cat.arena(aid)).filter(Boolean);
  const arenas = featured.length ? featured : state.cat.arenasOf();
  const shown = homeArenas(arenas);
  document.querySelectorAll('#homeDomainFilter [data-home-domain]').forEach((chip) => {
    chip.setAttribute('aria-pressed', chip.dataset.homeDomain === id ? 'true' : 'false');
  });
  const list = $('genreList');
  if (list) list.innerHTML = shown.map((arena) => genreBlockHtml(arena, { kicker: true })).join('');
  const empty = $('genreEmpty');
  if (empty) empty.hidden = shown.length > 0;
  const hint = $('genreHint');
  if (hint) hint.textContent = homeGenreHint(arenas);
  const showcase = $('genreShowcase');
  if (showcase && window.scrollY > showcase.offsetTop) {
    showcase.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
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
      a.name.localeCompare(b.name, locale()),
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
          aria-label="${esc(t('tile.aria', { name: rec.name, verdict: verdict.label, score }))}">
    ${iconHtml(rec, 'pick')}
    <span class="pick-text">
      <span class="pick-name">${esc(shortName)}</span>
      <span class="pick-tagline">${esc(tagline)}</span>
    </span>
    <span class="pick-meta">
      <span class="verdict verdict--${verdict.tone}"><span class="v-emoji" aria-hidden="true">${verdict.emoji}</span>${verdict.label}</span>
      <span class="pick-score" title="${esc(t('tile.scoreTitle'))}">${score}</span>
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
      <span class="genre-stat">${esc(t('genre.entries', { n: count }))}${
        stat ? ` · <span class="ok">${esc(t('genre.recommended', { n: stat.verdicts.recommend }))}</span>` : ''
      }</span>
      <button type="button" class="genre-more" ${go}>${esc(t('genre.more', { n: count }))}</button>
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
      <span class="gap-stars"><b>★ ${Number(stars || 0).toFixed(1)}</b><small>${count ? esc(t('home.gapCount', { n: num(count), platform: rec.store_stars?.platform || '' })) : esc(t('home.gapStoreTotal'))}</small></span>
      <span class="gap-vs">${esc(t('home.gapStars'))}</span>
      <span class="gap-score"><b>${rec.score ?? '—'}</b><small>${esc(t('home.gapScore'))}</small></span>
      <span class="verdict verdict--${verdict.tone}">${verdict.emoji} ${verdict.label}</span>
    </div>
    <p class="gap-drivers">${(rec.drivers || []).slice(0, 3).map((d) => `<span class="reason-chip reason-chip--${esc(d.tone || 'warn')}">${esc(d.label)}</span>`).join('') || `<span class="reason-chip">${esc(t('home.gapSignal'))}</span>`}</p>
    <span class="gap-more">${esc(t('home.gapMore'))}</span>
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
    <button type="button" class="text-btn" data-bookmark="${esc(rec.id)}" aria-label="${esc(t('card.bookmarkRemove', { name: rec.name }))}">${esc(t('bookmark.remove'))}</button>
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
      <span class="mini-label">${esc(t('search.head'))}</span>
      <strong>‘${esc(q)}’</strong>
      <span class="muted">${esc(t('search.count', { n: rows.length }))}</span>
      <button type="button" class="text-btn" data-action="clear-search">${esc(t('search.clear'))}</button>
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
          : `<p class="empty">${esc(t('search.empty'))}</p>`
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
      <h1>${esc(t('domain.heading', { label: dom.label, g: arenas.length, n: total }))}</h1>
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
        <span class="chip chip--muted">${esc(t('domain.filterPack', { pack: pack?.label || dom.filter_pack }))}</span>
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
      <p class="eyebrow">${esc(t('category.eyebrow', { domain: dom.label }))}</p>
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
    $('view').innerHTML = `<div class="error-banner"><strong>${esc(t('arena.error'))}</strong><span>${esc(
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
        <span class="chip">${esc(t('arena.entries', { n: items.length }))}</span>
        <span class="chip chip--muted">${esc(pack?.label ? t('arena.filterPack', { pack: pack.label }) : t('arena.filterPackCore'))}</span>
        <button type="button" class="ghost-btn ghost-btn--tune" data-action="open-tune">⚙ ${esc(t('arena.tuneLead'))} <b id="tuneSummary">${esc(presetLabel())}</b></button>
        <button type="button" class="ghost-btn ghost-btn--copy" data-copy-link title="${esc(t('arena.copyLinkTitle'))}">${esc(t('arena.copyLink'))}</button>
      </div>
    </header>
    <div class="toolbar">
      <label class="search toolbar-search">
        <span class="search-ico" aria-hidden="true">⌕</span>
        <input type="search" id="arenaSearch" placeholder="${esc(t('arena.searchPlaceholder'))}" autocomplete="off" value="${esc(state.query)}" aria-label="${esc(t('arena.searchAria'))}" />
      </label>
      <div class="select-row">
        <label class="select-label" for="sort">${esc(t('arena.sort'))}</label>
        <select id="sort">${SORT_KEYS
          .map((key) => `<option value="${key}" ${state.sort === key ? 'selected' : ''}>${esc(sortLabel(key))}</option>`)
          .join('')}</select>
      </div>
      <label class="check-row"><input type="checkbox" id="showAvoided" ${state.showAvoided ? 'checked' : ''} /><span>${esc(t('arena.showAvoided'))}</span></label>
      <span class="panel-hint" id="listCount">${esc(t('arena.listCount'))}</span>
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
    name: (a, b) => a.item.name.localeCompare(b.item.name, locale()),
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
      <div class="stat stat--ok"><span class="stat-label">${esc(t('stats.recommend'))}</span><span class="stat-value">${counts.recommend}</span><span class="stat-sub">${esc(t('stats.recommendSub'))}</span></div>
      <div class="stat stat--warn"><span class="stat-label">${esc(t('stats.conditional'))}</span><span class="stat-value">${counts.conditional}</span><span class="stat-sub">${esc(t('stats.conditionalSub'))}</span></div>
      <div class="stat stat--bad"><span class="stat-label">${esc(t('stats.avoid'))}</span><span class="stat-value">${counts.avoid}</span><span class="stat-sub">${esc(t('stats.avoidSub'))}</span></div>
      <div class="stat stat--avg"><span class="stat-label">${esc(t('stats.avg'))}</span><span class="stat-value">${avg}</span><span class="stat-sub">${esc(t('stats.avgSub', { preset: presetLabel(), n: views.length }))}</span></div>
    </div>
    <div class="section-head">
      <h2>${esc(t('arena.resultsTitle'))}</h2>
      <span class="section-hint">${esc(t('arena.resultsHint', { n: picks.length }))}</span>
    </div>
    <div class="grid" id="grid">${picks.map(cardHtml).join('')}</div>
    <p class="empty" id="emptyPick" ${picks.length ? 'hidden' : ''}>${esc(t('arena.pickEmpty'))}</p>
    <section class="result-section" id="avoidSection" ${state.showAvoided && avoided.length ? '' : 'hidden'}>
      <div class="section-head">
        <h2><span class="verdict-dot verdict-dot--bad"></span>${esc(t('arena.avoidTitle'))}</h2>
        <span class="section-hint">${esc(t('arena.entries', { n: avoided.length }))}</span>
      </div>
      <p class="hint section-sub">${esc(t('arena.avoidHint'))}</p>
      <div class="grid grid--avoided" id="avoidGrid">${avoided.map(cardHtml).join('')}</div>
      <p class="empty" id="emptyAvoid" hidden>${esc(t('arena.avoidEmpty'))}</p>
    </section>`;
  $('listCount').textContent = t('arena.listCountValue', { shown: views.length, total: (state.arenaItems || []).length });
  renderCompareBar();
}

function presetLabel() {
  if (state.preset === 'custom') return t('preset.custom');
  return PRESETS.some((p) => p.id === state.preset) ? presetLabelOf(state.preset) : t('preset.balanced');
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

/* 발행 단계 배지 — `auto_fact`(공개 API 대량 적재) 항목에만 붙는다. `verified` 는 배지 없음. */
function reviewTierChip(item) {
  if (!item || item.review_tier !== 'auto_fact') return '';
  return `<span class="chip chip--auto" title="${esc(t('reviewTier.badgeTitle'))}">${esc(t('reviewTier.badge'))}</span>`;
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
  const text = fresh.stale ? fresh.label : t('verdict.fresh', { n: days(fresh.elapsed) });
  return `<span class="chip chip--fresh chip--fresh--${tone}" title="${esc(
    t('fresh.chipTitle', { date: fresh.assessedAt || t('modal.na'), limit: fresh.limit }),
  )}">${esc(text)}</span>`;
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
    push(`<span class="chip chip--warn" title="${esc(t('card.weakEvidenceTitle', { note: fail.note }))}">${esc(t('card.weakEvidence', { label: fail.label }))}</span>`);
  }
  if (e.optionalFails?.length) {
    push(`<span class="chip chip--optional" title="${esc(t('card.optionalTitle'))}">${esc(t('card.optional'))}</span>`);
  }
  if (e.verdict === 'avoid' && !e.blocking.length && e.reds >= 2) {
    push(`<span class="chip chip--core">${esc(t('card.redSignals', { n: e.reds }))}</span>`);
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
  if (!tags.length) push(`<span class="chip chip--pass">${esc(t('card.filterPass'))}</span>`);
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
           aria-label="${esc(t('card.aria', { name: item.name, verdict: verdictMeta.label, score: scoreText }))}">
    <header class="card-head">
      ${iconHtml(item, 'card')}
      <div class="card-name-text">
        <h3>${esc(item.name)}</h3>
        <p class="card-dev">${esc(devLine)}</p>
        ${reviewTierChip(item)}
      </div>
      <div class="card-score">
        <span class="verdict verdict--${verdictMeta.tone}"><span class="v-emoji" aria-hidden="true">${verdictMeta.emoji}</span>${verdictMeta.label}</span>
        <span class="score-num">${scoreText}</span>
        <span class="score-cap">${esc(t('card.weighted'))}</span>
      </div>
    </header>

    <p class="one-liner">${esc(summary)}</p>
    <div class="card-tags">${cardTagsHtml(view)}</div>

    <div class="card-tools">
      ${selectable ? `<label class="compare-check" title="${esc(t('card.compareTitle'))}"><input type="checkbox" data-compare="${esc(item.id)}" ${checked ? 'checked' : ''}/><span>${esc(t('card.compare'))}</span></label>` : ''}
      <button type="button" class="icon-btn icon-btn--sm ${bookmarked ? 'is-on' : ''}" data-bookmark="${esc(item.id)}" aria-pressed="${bookmarked}" aria-label="${esc(bookmarked ? t('card.bookmarkRemove', { name: item.name }) : t('card.bookmarkAdd', { name: item.name }))}">${bookmarked ? '★' : '☆'}</button>
      <span class="card-more">${esc(t('card.more'))}</span>
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
  document.body.classList.toggle('has-compare-bar', show);
  if (!show) return;
  const label = bar.querySelector('.compare-bar-label');
  if (label) label.textContent = t('compareBar.label', { n: ids.length });
  $('compareList').innerHTML = ids
    .map((id) => `<span class="compare-chip">${esc(recordById(id)?.name || id)}<button type="button" class="chip-x" data-compare="${esc(id)}" aria-label="${esc(
      t('compareBar.remove', { name: recordById(id)?.name || id }),
    )}">✕</button></span>`)
    .join('');
  $('compareOpen').disabled = ids.length < 2;
  $('compareOpen').textContent = ids.length < 2 ? t('compareBar.openOne') : t('compareBar.open');
  $('compareClear').textContent = t('compareBar.clear');
}

function toggleCompare(id) {
  if (!state.route.arena) return;
  const rec = recordById(id);
  if (!rec || !rec.arenas.includes(state.route.arena)) {
    toast(t('compare.onlySameArena'));
    return;
  }
  const current = [...state.route.compare];
  const at = current.indexOf(id);
  if (at >= 0) current.splice(at, 1);
  else {
    if (current.length >= 3) {
      toast(t('compare.max'));
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
    $('view').innerHTML = `<div class="error-banner"><strong>${esc(t('compare.error'))}</strong><span>${esc(
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
  const axisLabel = (key) => labeled('axis', key, contract().axes?.find((def) => def.key === key)?.label || key);
  const axisScore = (v, key) => v.recordEval.axisStates.find((row) => row.key === key)?.score;
  const rows = [
    {
      id: 'score',
      label: t('compare.row.score'),
      num: (v) => v.recordEval.score,
      showDiff: true,
      render: (v) => `<b class="cmp-score">${v.recordEval.score?.toFixed(1) ?? '—'}</b>`,
    },
    {
      id: 'tier',
      label: t('compare.row.tier'),
      render: (v) => `${esc(v.recordTier?.label || '—')}<br><span class="muted">${esc(v.recordTier?.price?.display || '—')}</span>`,
    },
    { id: 'cheapest', label: t('compare.row.cheapest'), render: (v) => (v.cheapest ? esc(v.cheapest.label) : '—') },
    ...['user_rating', 'objective', 'ai_review'].map((key) => ({
      id: key,
      label: t('compare.row.axis', { axis: axisLabel(key) }),
      num: (v) => axisScore(v, key),
      render: (v) => {
        const axis = v.recordEval.axisStates.find((row) => row.key === key);
        const meta = engine.SIGNAL_META[axis?.signal] || engine.SIGNAL_META.unknown;
        return axis ? `${meta.emoji} <b>${axis.score ?? '—'}</b>` : '—';
      },
    })),
    {
      id: 'impact',
      label: t('compare.row.impact'),
      render: (v) => {
        const impact = engine.monetizationImpactOf(v.recordEval);
        if (impact === 'none') return `<span class="muted">${esc(t('compare.noImpact'))}</span>`;
        return `<span class="pill pill--${impact === 'optional' ? 'sea' : 'bad'}">${esc(
          engine.IMPACT_META[impact]?.label || impact,
        )}</span>`;
      },
    },
    {
      id: 'filters',
      label: t('compare.row.filters'),
      render: (v) => {
        const fails = engine.failedFilters(v.recordEval);
        const optional = engine.optionalFilters(v.recordEval);
        const chips = [
          ...fails.map((f) => `<span class="reason-chip reason-chip--bad">${esc(f.label)}</span>`),
          ...optional.map((f) => `<span class="reason-chip reason-chip--sea">${esc(t('compare.optionalSuffix', { label: f.label }))}</span>`),
        ];
        return chips.length ? chips.join('') : `<span class="muted">${esc(t('compare.none'))}</span>`;
      },
    },
    { id: 'stars', label: t('compare.row.stars'), num: (v) => storeStarsValue(v.item), render: (v) => storeStarsText(v.item) },
    { id: 'recent', label: t('compare.row.recent'), render: (v) => recentReviewText(v.item) },
    { id: 'life', label: t('compare.row.life'), render: (v) => esc(engine.MAINTENANCE_STATUS_META[v.item.maintenance_status]?.label || v.item.maintenance_status) },
    { id: 'freshness', label: t('compare.row.freshness'), render: (v) => {
      const fresh = v.fresh;
      return `${esc(v.item.assessed_at)}<br><span class="chip chip--fresh chip--fresh--${fresh.stale ? 'warn' : 'ok'}">${esc(
        fresh.stale ? fresh.label : t('verdict.fresh', { n: days(fresh.elapsed) }),
      )}</span>`;
    } },
    { id: 'grade', label: t('compare.row.grade'), render: (v) => esc(engine.gradeWeakest(v.item.data_quality?.overall_grade)) },
    { id: 'more', label: '', render: (v) => `<button type="button" class="ghost-btn" data-action="item" data-item="${esc(v.item.id)}">${esc(t('card.more'))}</button>` },
  ];
  const bestOf = (def) => {
    if (!def.num) return -1;
    let at = -1;
    let value = null;
    let count = 0;
    views.forEach((v, i) => {
      const n = def.num(v);
      if (typeof n === 'number' && Number.isFinite(n)) {
        count += 1;
        if (value === null || n > value) {
          value = n;
          at = i;
        }
      }
    });
    // 값이 하나뿐이면 '최고'로 강조하지 않는다(비교가 아니라 단독 표시).
    return count >= 2 ? at : -1;
  };
  const scoreAt = bestOf(rows[0]);
  const scoreValues = views.map((v) => v.recordEval.score).filter((n) => typeof n === 'number');
  const topScore = scoreValues.length ? Math.max(...scoreValues) : null;
  const lowScore = scoreValues.length ? Math.min(...scoreValues) : null;
  const topView = scoreAt >= 0 ? views[scoreAt] : null;
  const lowView = scoreValues.length ? views[views.findIndex((v) => v.recordEval.score === lowScore)] : null;
  $('view').innerHTML = `
  <section class="level">
    <header class="level-head level-head--arena">
      <p class="eyebrow">${esc(state.cat.domainLabel(arena.domain))} · ${esc(state.cat.categoryLabel(arena.category))}</p>
      <h1>${esc(t('compare.title', { arena: arena.label }))}</h1>
      <p class="lede">${esc(t('compare.lede', { n: views.length, preset: presetLabel() }))}</p>
      <div class="level-badges">
        <button type="button" class="ghost-btn" data-action="arena" data-domain="${esc(arena.domain)}" data-arena="${esc(arena.id)}">${esc(t('compare.back'))}</button>
        <button type="button" class="ghost-btn" data-copy-link title="${esc(t('compare.copyTitle'))}">${esc(t('arena.copyLink'))}</button>
        <button type="button" class="text-btn" data-action="clear-compare">${esc(t('compare.clear'))}</button>
      </div>
    </header>
    <div class="compare-summary" id="compareSummary">
      ${topView && topScore !== null ? `<span>${t('compare.top', { name: esc(topView.item.name), score: topScore.toFixed(1) })}</span>` : ''}
      ${lowScore !== null ? `<span>${t('compare.low', { name: esc(lowView?.item.name || ''), score: lowScore.toFixed(1) })}</span>` : ''}
      ${topScore !== null && lowScore !== null ? `<span>${t('compare.diff', { n: (topScore - lowScore).toFixed(1) })}</span>` : ''}
      <span class="compare-summary-hint">${esc(t('compare.summaryHint', { preset: presetLabel() }))}</span>
    </div>
    <p class="scroll-hint">${esc(t('compare.scrollHint'))}</p>
    <div class="table-wrap compare-wrap">
      <table class="data compare-table" id="compareTable">
        <thead>
          <tr>
            <th class="compare-rowlabel" scope="col">${esc(t('compare.basis'))}</th>
            ${views.map((v) => `<th scope="col"><span class="compare-head-name">${iconHtml(v.item, 'compare')}<span class="compare-head-text">${esc(v.item.name)}</span></span><span class="verdict verdict--${
              engine.VERDICT_META[v.recordEval.verdict].tone
            }">${engine.VERDICT_META[v.recordEval.verdict].emoji} ${engine.VERDICT_META[v.recordEval.verdict].label}</span></th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${rows
            .map((def) => {
              const best = bestOf(def);
              return `<tr class="${def.id === 'score' ? 'cmp-row--score' : ''}"><th scope="row" class="compare-rowlabel">${esc(def.label)}</th>${views
                .map((v, i) => {
                  const isBest = Boolean(def.num) && best === i;
                  const gap =
                    def.showDiff && def.num && best >= 0 && !isBest && typeof def.num(v) === 'number' && typeof def.num(views[best]) === 'number'
                      ? def.num(views[best]) - def.num(v)
                      : null;
                  return `<td class="cmp-cell${isBest ? ' cmp-cell--best' : ''}">${def.render(v)}${
                    isBest ? `<span class="cmp-best">${esc(t('compare.best'))}</span>` : gap ? `<span class="cmp-diff">−${gap.toFixed(1)}</span>` : ''
                  }</td>`;
                })
                .join('')}</tr>`;
            })
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
  if (!top) return t('compare.row.stars');
  return STORE_PLATFORMS.includes(top.platform) ? t('stars.store') : t('stars.aggregate');
}

function storeStarsText(item) {
  const rows = (item.review_snapshot?.platforms || [])
    .map((row) => ({ row, metric: row.cumulative }))
    .filter(({ metric }) => metric && metric.scale === 'stars5')
    .sort((a, b) => (b.metric.count || 0) - (a.metric.count || 0));
  if (!rows.length) return '<span class="muted">—</span>';
  const { row, metric } = rows[0];
  return `★ ${Number(metric.value).toFixed(1)} <span class="muted">${engine.PLATFORM_LABEL[row.platform] || row.platform} · ${esc(
    t('reviews.count', { n: num(metric.count) }),
  )}</span>`;
}

/** 비교 표에서 '최고'를 표시할 때 쓰는 누적 별점 숫자(가장 큰 표본의 stars5 값). */
function storeStarsValue(item) {
  const values = (item.review_snapshot?.platforms || [])
    .map((row) => row.cumulative)
    .filter((metric) => metric && metric.scale === 'stars5')
    .sort((a, b) => (b.count || 0) - (a.count || 0));
  return values.length ? Number(values[0].value) : undefined;
}

function recentReviewText(item) {
  const rows = (item.review_snapshot?.platforms || []).filter((row) => row.recent);
  if (!rows.length) return `<span class="muted">${esc(t('compare.noRecent'))}</span>`;
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

async function showDetail(id, arenaOverride = null) {
  const rec = recordById(id);
  if (!rec) return;
  const arenaId = arenaOverride || state.route.arena || rec.arenas[0];
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
    t('modal.assessed', { date: item.assessed_at }),
    L.method(item.method) || item.method,
  ]
    .filter(Boolean)
    .join(' · ');
  $('modalChips').innerHTML = [
    `<span class="chip chip--cat">${esc(state.cat.domainLabel(item.domain))} · ${esc(state.cat.categoryLabel(item.category))}</span>`,
    ...(item.arenas || []).map((aid) => `<span class="chip chip--arena">${esc(state.cat.arenaLabel(aid))}</span>`),
    reviewTierChip(item),
    maintenanceChip(item),
    freshnessChip(item),
    `<span class="chip chip--grade chip--${esc(engine.gradeWeakest(item.data_quality?.overall_grade))}">${esc(
      t('modal.grade', { grade: engine.gradeWeakest(item.data_quality?.overall_grade) }),
    )}</span>`,
  ].join('');

  const bookmarked = state.bookmarks.includes(item.id);
  const saveLabel = bookmarked ? t('modal.unsave', { name: item.name }) : t('modal.save', { name: item.name });
  $('modalActions').innerHTML = `
    <button type="button" class="ghost-btn" data-copy-link title="${esc(t('modal.copyLinkTitle'))}">${esc(t('modal.copyLink'))}</button>
    <button type="button" class="ghost-btn" data-share="${esc(item.id)}">${esc(t('modal.share'))}</button>
    <a class="ghost-btn" href="${correctionUrl(item)}" target="_blank" rel="noopener noreferrer">${esc(t('modal.correction'))}</a>
    <button type="button" class="icon-btn ${bookmarked ? 'is-on' : ''}" data-bookmark="${esc(item.id)}" aria-pressed="${bookmarked}" title="${esc(saveLabel)}" aria-label="${esc(saveLabel)}">${bookmarked ? '★' : '☆'}</button>
    <button type="button" class="icon-btn" id="modalClose" aria-label="${esc(t('modal.detailClose'))}">✕</button>`;

  const tierNotice = item.review_tier === 'auto_fact'
    ? `<div class="callout callout--auto" role="note">${t('reviewTier.notice')}</div>`
    : '';
  $('modalBody').innerHTML = [
    tierNotice,
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
  ].filter(Boolean).join('');

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
  const title = encodeURIComponent(t('correction.title', { name: item.name, id: item.id }));
  const body = encodeURIComponent(
    t('correction.body', {
      name: item.name,
      id: item.id,
      arenas: (item.arenas || []).join(', '),
      date: item.assessed_at,
    }),
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
    <div class="m-sec-head"><span class="sec-num">01</span><h3>${esc(t('modal.sec1'))}</h3>
      <span class="pill pill--beam">${esc(view.recordTier?.label || t('verdict.representative'))}</span>
      ${view.cheapest ? `<span class="pill pill--sea">${esc(t('verdict.cheapest', { tier: view.cheapest.label }))}</span>` : ''}
      ${view.recordEval.optionalMonetization ? `<span class="pill pill--sea">${esc(t('verdict.optional'))}</span>` : ''}
      <span class="pill pill--${view.fresh.stale ? 'warn' : 'ok'}">${esc(
        view.fresh.stale ? view.fresh.label : t('verdict.fresh', { n: days(view.fresh.elapsed) }),
      )}</span>
    </div>
    ${view.fresh.stale
      ? `<div class="callout callout--warn">${t('verdict.staleCallout', {
          date: esc(view.fresh.assessedAt),
          days: view.fresh.elapsed,
          limit: view.fresh.limit,
        })}</div>`
      : ''}
    <div class="verdict-hero verdict-hero--${verdictMeta.tone}">
      <div class="hero-score">
        <div class="score">${ring(e.score ?? 0)}
          <div class="score-inner"><span class="score-num">${e.score != null ? e.score.toFixed(1) : '—'}</span><span class="score-cap">${esc(t('card.weighted'))}</span></div>
        </div>
        <span class="hero-verdict hero-verdict--${verdictMeta.tone}">${verdictMeta.emoji} ${verdictMeta.label}</span>
      </div>
      <div class="hero-body">
        <p class="hero-oneliner">${esc(view.recordTier?.one_liner || view.item.verdict?.one_liner || view.item.one_liner)}</p>
        <div class="hero-signals">${signals}</div>
        <p class="rule-line">${t('verdict.rule', {
          rule: esc(rule.short),
          weak: e.weakFails.length ? esc(t('verdict.weakWarn')) : '',
          unknown: e.unknowns ? esc(t('verdict.unknownAxes', { n: e.unknowns })) : '',
        })}</p>
        <div class="m-sec-note">${t('verdict.activeFilters', { chips: filterChips || `<span class="muted">${esc(t('verdict.noFilters'))}</span>` })}</div>
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
      <p class="mini-label">${esc(t('verdict.arenaNotes'))}</p>
      ${ids
        .map(
          (id) => `<div class="arena-note"><span class="chip chip--arena">${esc(state.cat.arenaLabel(id))}</span><p>${esc(
            notes[id] || t('verdict.noArenaNote'),
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
    ? t('filter.mark.exempt')
    : optional
      ? t('filter.mark.optional')
      : check.status === 'fail'
        ? t('filter.mark.fail')
        : check.status === 'unknown'
          ? t('filter.mark.unknown')
          : t('filter.mark.pass');
  return `<span class="pill pill--${tone}" title="${esc(check.note)}">${check.enabled ? '' : t('filter.off')}${esc(check.label)} ${esc(mark)}${
    exempt ? esc(t('filter.exemptSuffix')) : ''
  }${check.status === 'fail' ? ` (${esc(engine.gradeWeakest(check.grade))})` : ''}</span>`;
}

function ruleDescription(evaluation) {
  const rules = contract().verdict_rules || [];
  const index = RULE_INDEX[evaluation.rule] ?? 0;
  const shortMap = {
    1: t('rule.short.1'),
    '1w': t('rule.short.1w'),
    '1c': t('rule.short.1c'),
    2: t('rule.short.2', { n: evaluation.reds }),
    3: t('rule.short.3'),
    4: t('rule.short.4', { n: evaluation.yellows }),
    5: t('rule.short.5', { score: evaluation.score?.toFixed(1), n: evaluation.yellows }),
    6: t('rule.short.6'),
  };
  return { short: shortMap[evaluation.rule] || shortMap[6], raw: (rules[index] || '').replace(/^\s*\d+\.\s*/, ''), index };
}

function calcRuleText(i) {
  const text = t(`rule.text.${i}`);
  return text.startsWith('rule.text.') ? '' : text;
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
      <summary class="calc-summary">${esc(t('verdict.calcOpen', {
        w: pct(e.denominator),
        n: e.filterChecks.filter((f) => f.enabled).length,
        mode: e.strict ? t('verdict.modeStrict') : t('verdict.modeRelaxed'),
      }))}</summary>
      <div class="calc">
        <p class="mini-label" style="margin:10px 0 4px">${esc(t('verdict.calcScore'))}</p>
        ${lines || `<p class="muted">${esc(t('verdict.noScore'))}</p>`}
        <div class="calc-total"><span>Σ(w×s) = ${e.numerator.toFixed(2)} · Σw = ${e.denominator.toFixed(2)}</span><b>${e.score != null ? e.score.toFixed(2) : '—'}</b></div>
        <p class="mini-label" style="margin:12px 0 4px">${t('verdict.calcFilters', { tier: esc(e.tierId) })}</p>
        <div class="tag-cloud">${e.filterChecks.filter((f) => f.enabled).map(filterPill).join('') || `<span class="muted">${esc(t('verdict.noFilters'))}</span>`}</div>
        ${e.blocking.length ? `<div class="callout callout--bad">${t('verdict.blocked', { list: e.blocking.map((f) => `${esc(f.label)}(${esc(engine.gradeWeakest(f.grade))})`).join(' · ') })}</div>` : ''}
        ${e.optionalFails.length ? `<div class="callout callout--warn">${t('verdict.optionalFails', { list: e.optionalFails.map((f) => `${esc(f.label)}(${esc(engine.gradeWeakest(f.grade))})`).join(' · ') })}</div>` : ''}
        ${e.weakFails.length ? `<div class="callout callout--warn">${t('verdict.weakFails', { list: e.weakFails.map((f) => `${esc(f.label)}(${esc(engine.gradeWeakest(f.grade))})`).join(' · ') })}</div>` : ''}
        ${disabled.length ? `<details><summary class="calc-summary">${esc(t('verdict.disabledFilters', { n: disabled.length }))}</summary><div class="tag-cloud" style="margin-top:6px">${disabled.map(filterPill).join('')}</div></details>` : ''}
        <p class="mini-label" style="margin:12px 0 4px">${esc(t('verdict.calcRules'))}</p>
        <ol class="rules">${rules
          .map((rule, i) => `<li class="${i === activeIndex ? 'is-active' : ''}" title="${esc(calcRuleText(i) || rule)}">${esc(calcRuleText(i) || rule)}</li>`)
          .join('')}</ol>
        <p class="table-note">${t('verdict.defaultSet', {
          set: esc((contract().default_enabled_filters || []).join(', ')),
          result: engine.defaultBlocked(view.item, view.recordTier, contract()) ? esc(t('verdict.avoid')) : esc(t('verdict.pass')),
          stored: esc(engine.VERDICT_META[e.storedVerdict]?.label || e.storedVerdict),
        })}</p>
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
    [t('facts.developer'), `${esc(item.developer)}<br><span class="muted">${(item.platforms || [])
      .map((p) => esc(engine.PLATFORM_LABEL[p] || p))
      .join(' · ')}${item.release_date ? ` · ${esc(t('facts.released', { date: item.release_date }))}` : ''}</span>`],
    [t('facts.price'), `${esc(tier?.price?.display || '—')}<br><span class="muted">${esc(tier?.label || '')}${
      tier?.kind && (engine.KIND_LABEL[tier.kind] || '') !== (tier?.label || '')
        ? ` · ${esc(engine.KIND_LABEL[tier.kind] || tier.kind)}`
        : ''
    }</span>`],
    [t('facts.storeAds'), ads.store_declares_ads === true ? t('modal.yes') : ads.store_declares_ads === false ? t('modal.no') : t('modal.na')],
    [t('facts.randomItems'), esc(engine.TRI_LABEL[iap.random_items] || t('modal.na'))],
    [t('facts.latestUpdate'), `${esc(item.update_profile?.latest_update || t('modal.na'))}${
      item.update_profile?.latest_update_platform
        ? ` · ${esc(engine.PLATFORM_LABEL[item.update_profile.latest_update_platform] || item.update_profile.latest_update_platform)}`
        : ''
    }`],
    [starsLabel, stars],
    [t('facts.assessed'), esc(item.assessed_at)],
  ];
  return `
  <section class="m-sec" id="secFacts">
    <div class="m-sec-head"><span class="sec-num">02</span><h3>${esc(t('modal.sec2'))}</h3>
      <span class="pill pill--ok">${esc(t('facts.badge'))}</span>
    </div>
    <p class="m-sec-note">${t('facts.note')}</p>
    <div class="table-wrap">
      <table class="data fact-table">
        <tbody>${rows.map(([label, value]) => `<tr><th scope="row">${esc(label)}</th><td>${value}</td></tr>`).join('')}</tbody>
      </table>
    </div>
    <p class="table-note">${esc(t('facts.tableNote'))}</p>
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
    <div class="m-sec-head"><span class="sec-num">03</span><h3>${esc(t('modal.sec3'))}</h3>
      <span class="pill pill--warn">${esc(t('opinion.badge'))}</span>
    </div>
    <p class="m-sec-note">${t('opinion.note', { v: esc(schemaVersion()) })}</p>
    <div class="opinion-grid">
      <article class="opinion-card">
        <h4>${esc(t('opinion.reasons'))}</h4>
        ${reasons.length ? `<ul class="list">${reasons.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>` : `<p class="muted">${esc(t('opinion.noReasons'))}</p>`}
        ${conditions.length ? `<div class="callout callout--warn"><b>${esc(t('opinion.conditions'))}</b><ul class="list list--muted">${conditions
          .map((n) => `<li>${esc(n)}</li>`)
          .join('')}</ul></div>` : ''}
      </article>
      <article class="opinion-card">
        <h4>${esc(t('opinion.aiSummary'))} <span class="chip chip--grade chip--${esc(engine.gradeWeakest(ai?.evidence_grade))}">${esc(
          t('axes.evidence', { grade: engine.gradeWeakest(ai?.evidence_grade || 'unknown') }),
        )}</span></h4>
        <p class="axis-summary">${esc(ai?.summary || t('opinion.noAi'))}</p>
        <p class="source-meta">${esc(t('opinion.deductions'))}</p>
      </article>
      <article class="opinion-card">
        <h4>${esc(t('opinion.fit'))}</h4>
        <p class="axis-summary">${esc(
          (item.taste_tags || []).length
            ? t('opinion.fitLine', { tags: (item.taste_tags || []).map((tag) => L.tag(tag)).join(' · ') })
            : t('opinion.noTags'),
        )}</p>
        ${e.reds ? `<p class="source-meta">${esc(t('opinion.redNote', { n: e.reds }))}</p>` : ''}
      </article>
    </div>
    <p class="m-sec-note">${t('opinion.correction', { url: correctionUrl(item) })}</p>
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
                `${f.enabled ? '' : `<span class="muted">${esc(t('tiers.offNote'))}</span>`}${esc(f.label)} <b>${esc(
                  engine.gradeWeakest(f.grade),
                )}</b>${f.optional ? ` <span class="pill pill--sea">${esc(t('filter.mark.optional'))}</span>` : ''}${f.weakGrade && !evaluation.strict ? ` <span class="muted">${esc(t('tiers.weakEvidence'))}</span>` : ''}`,
            )
            .join('<br>')
        : '<span class="muted">—</span>';
      return `
      <tr>
        <td class="tier-name">
          <div>${esc(tier.label)}${tier.tier_id === view.recordTier?.tier_id ? ` <span class="pill pill--beam">${esc(t('tiers.main'))}</span>` : ''}${
            tier.recommended_path ? ` <span class="pill pill--sea">${esc(t('tiers.cheapest'))}</span>` : ''
          }</div>
          <div class="source-meta">${esc(tier.tier_id)} · ${esc(engine.KIND_LABEL[tier.kind] || tier.kind)}</div>
          ${(tier.limits || []).length ? `<div class="source-meta">${esc(t('tiers.limits', { limits: tier.limits.join(', ') }))}</div>` : ''}
        </td>
        <td>${esc(tier.price?.display || '—')}</td>
        <td><span class="pill pill--${meta.tone}">${meta.emoji} ${meta.label}</span><div class="source-meta">${esc(
          t('tiers.recorded', { verdict: engine.VERDICT_META[evaluation.storedVerdict]?.label || evaluation.storedVerdict }),
        )}</div>${
          evaluation.optionalFails.length
            ? `<div class="source-meta">${esc(t('verdict.optional'))}</div>`
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
    <div class="m-sec-head"><span class="sec-num">04</span><h3>${esc(t('modal.sec4'))}</h3>
      <span class="pill">${esc(t('tiers.badge', { n: view.tierEvals.length }))}</span>
    </div>
    <p class="m-sec-note">${esc(t('tiers.note'))}</p>
    <div class="table-wrap">
      <table class="data tier-table">
        <thead><tr><th>${esc(t('tiers.name'))}</th><th>${esc(t('tiers.price'))}</th><th>${esc(t('tiers.verdict'))}</th><th>${esc(t('tiers.score'))}</th><th>${esc(t('tiers.filters'))}</th><th>${esc(t('tiers.oneLiner'))}</th></tr></thead>
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
      return `
      <article class="axis-card">
        <div class="axis-card-head">
          <h4>${esc(axis.label)}${axis.profileScoped ? `<small>${esc(t('axes.profileOnly'))}</small>` : ''}</h4>
          <span class="axis-score axis-score--${esc(axis.signal)}">${axis.score ?? '—'}</span>
        </div>
        <div class="axis-meta">
          <span class="pill pill--${axis.signal === 'green' ? 'ok' : axis.signal === 'yellow' ? 'warn' : axis.signal === 'red' ? 'bad' : 'muted'}">${meta.emoji} ${meta.label}</span>
          <span class="pill">${esc(t('axes.evidence', { grade: engine.gradeWeakest(axis.evidenceGrade || 'unknown') }))}</span>
          <span class="pill">${esc(t('axes.confidence', { level: { high: t('axes.confidenceHigh'), medium: t('axes.confidenceMedium'), low: t('axes.confidenceLow') }[axis.confidence] || '—' }))}</span>
          ${axis.source === 'tier' ? `<span class="pill pill--beam">${esc(t('axes.tierOverride'))}</span>` : ''}
          ${axis.profileScoped && axis.weight <= 0 ? `<span class="pill">${esc(t('axes.weightZero'))}</span>` : ''}
        </div>
        <p class="axis-summary">${esc(axis.summary || axis.note || t('axes.noSummary'))}</p>
        ${axis.overrideScore != null && axis.axisScore !== axis.overrideScore
          ? `<p class="source-meta">${esc(t('axes.overrideNote', { base: axis.axisScore, score: axis.overrideScore, note: axis.note }))}</p>`
          : ''}
        ${(axis.sourceIds || []).length ? `<div class="axis-meta">${sourceChips(axis.sourceIds, view.item)}</div>` : ''}
      </article>`;
    })
    .join('');
  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">05</span><h3>${esc(t('modal.sec5'))}</h3>
      <span class="pill">🟢 ≥ ${contract().signal_thresholds?.green_min ?? 75} · 🟡 ≥ ${contract().signal_thresholds?.yellow_min ?? 50}</span>
    </div>
    <div class="axis-grid">${cards}</div>
    ${view.item.one_liner ? `<p class="m-sec-note">${esc(t('axes.note', { text: view.item.one_liner }))}</p>` : ''}
    ${scoreNoteHtml(view.item)}
  </section>`;
}

/** v0.5.0 산정 메모 — 점수 원칙(표본 규모 검증·객관 비편향)이 어떻게 적용됐는지 보인다. */
function scoreNoteHtml(item) {
  const notes = item.score_notes || {};
  const rows = [
    ['user_rating', labeled('axis', 'user_rating', 'User Rating')],
    ['objective', labeled('axis', 'objective', 'Objective Trust')],
    ['ai_review', labeled('axis', 'ai_review', 'AI Review')],
  ].filter(([key]) => notes[key]);
  if (!rows.length) return '';
  return `<div class="callout callout--ok"><b>${esc(t('axes.scoreNotes'))}</b>${rows
    .map(([key, label]) => `<p class="m-sec-note"><b>${esc(label)}</b> — ${esc(notes[key])}</p>`)
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
    <div class="m-sec-head"><span class="sec-num">06</span><h3>${esc(isBad ? t('modal.sec6a') : t('modal.sec6b'))}</h3>
      <span class="pill pill--sea">${esc(t('alt.scope', { arena: state.cat.arenaLabel(state.route.arena) }))}</span>
    </div>
    <p class="m-sec-note">${esc(t('alt.note'))}</p>
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
          <span class="alt-more">${esc(t('alt.see'))}</span>
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
        metric ? `${metric.window || t('reviews.periodUnknown')} · ${engine.reviewToHundred(metric.value, metric.scale)?.toFixed(1)}/100 · ${t('axes.evidence', { grade: engine.gradeWeakest(metric.evidence_grade) })}` : '';
      const metricValue = (metric) =>
        metric
          ? `${metric.value}${metric.scale === 'percent' ? '%' : metric.scale === 'stars5' ? '★' : '/10'} <span class="muted">· ${esc(t('reviews.count', { n: num(metric.count) }))}</span>`
          : `<span class="muted">${esc(t('reviews.none'))}</span>`;
      const gapState = gap == null ? '' : gap <= -15 ? t('reviews.gapDamaged') : gap <= -5 ? t('reviews.gapDown') : gap >= 5 ? t('reviews.gapUp') : t('reviews.gapStable');
      return `
      <div class="review-row">
        <div class="review-top">
          <h4>${esc(engine.PLATFORM_LABEL[platform.platform] || platform.platform)}</h4>
          ${
            gap == null
              ? `<span class="review-gap">${esc(t('reviews.noRecent'))}</span>`
              : `<span class="review-gap review-gap--${gapTone}">${t('reviews.gap', { gap: `${gap > 0 ? '+' : ''}${gap.toFixed(1)}`, state: esc(gapState) })}</span>`
          }
        </div>
        <div class="review-bars">
          <div class="bar-row"><span class="bar-label">${esc(t('reviews.cumulative'))}</span><span class="bar-track"><span class="bar-fill bar-fill--cum" style="width:${Math.max(0, Math.min(100, cumulative ?? 0))}%"></span></span><span class="bar-value">${metricValue(platform.cumulative)}</span></div>
          <div class="bar-row"><span class="bar-label">${esc(t('reviews.recent'))}</span><span class="bar-track"><span class="bar-fill bar-fill--recent" style="width:${Math.max(0, Math.min(100, recent ?? 0))}%"></span></span><span class="bar-value">${metricValue(platform.recent)}</span></div>
        </div>
        <p class="review-meta">${esc(t('reviews.metaCumulative', { meta: metricMeta(platform.cumulative) }))}</p>
        ${platform.recent ? `<p class="review-meta">${esc(t('reviews.metaRecent', { meta: metricMeta(platform.recent) }))}</p>` : ''}
        ${platform.note ? `<p class="money-note">${esc(platform.note)}</p>` : ''}
      </div>`;
    })
    .join('');

  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">07</span><h3>${esc(t('modal.sec7'))}</h3>
      <span class="pill ${sample.needsDowngrade ? 'pill--bad' : 'pill--ok'}">${esc(t('reviews.minSample', {
        n: sample.min,
        state: sample.needsDowngrade ? t('reviews.minSampleShort', { n: sample.insufficient.length }) : t('reviews.minSampleOk'),
      }))}</span>
    </div>
    <p class="m-sec-note">${esc(t('reviews.note'))}</p>
    ${rows}
    ${snapshot.summary ? `<p class="money-note">${esc(snapshot.summary)}</p>` : ''}
    <div class="callout${sample.needsDowngrade ? ' callout--warn' : ''}">
      ${t('reviews.rule', {
        min: sample.min,
        checked: sample.checked,
        need: sample.needsDowngrade ? t('reviews.needYes') : t('reviews.needNo'),
        state: sample.needsDowngrade
          ? (sample.applied ? t('reviews.applied') : t('reviews.notApplied'))
          : (sample.sampleSufficient ? t('reviews.sufficient') : t('reviews.unknownState')),
      })}
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
    <div class="m-sec-head"><span class="sec-num">08</span><h3>${esc(t('modal.sec8'))}</h3>
      <span class="pill ${iap.random_items === 'yes' ? 'pill--bad' : ''}">${esc(t('money.randomBadge', { v: engine.TRI_LABEL[iap.random_items] || t('modal.na') }))}</span>
      <span class="pill">${esc(t('money.iapBadge', { v: engine.TRI_LABEL[iap.present] || t('modal.na') }))}</span>
    </div>
    <p class="m-sec-note">${esc(t('money.note'))}</p>
    <div class="money-grid">
      <article class="money-card"><h4>${esc(t('money.adsExposure'))}</h4><div class="money-value">${esc(engine.EXPOSURE_LABEL[ads.in_app_exposure] || ads.in_app_exposure || t('modal.na'))}</div><div class="money-tags">${tags(ads.ad_types)}</div><p class="money-note">${esc(t('money.adsStore', { v: ads.store_declares_ads === true ? t('modal.yes') : ads.store_declares_ads === false ? t('modal.no') : t('modal.na') }))}</p></article>
      <article class="money-card"><h4>${esc(t('money.inflow'))}</h4><div class="money-value">${esc(engine.HONESTY_LABEL[ads.inflow_ad?.honesty] || t('money.notAssessed'))}</div><div class="money-tags"><span class="pill">${esc(t('money.inflowExists', { v: engine.TRI_LABEL[ads.inflow_ad?.present] || t('money.notAssessed') }))}</span><span class="pill">${esc(t('money.inflowGrade', { grade: engine.gradeWeakest(ads.inflow_ad?.evidence_grade || 'unknown') }))}</span></div><p class="money-note">${esc(ads.inflow_ad?.note || t('money.noRecord'))}</p></article>
      <article class="money-card"><h4>${esc(t('money.random'))}</h4><div class="money-value">${esc(engine.TRI_LABEL[iap.random_items] || t('modal.na'))}</div><div class="money-tags"><span class="pill">${esc(t('money.iapExists', { v: engine.TRI_LABEL[iap.present] || t('modal.na') }))}</span><span class="pill">${esc(t('money.inflowGrade', { grade: engine.gradeWeakest(iap.evidence_grade || 'unknown') }))}</span></div><p class="money-note">${esc(t('money.randomNote'))}</p></article>
      <article class="money-card"><h4>${esc(t('money.price'))}</h4><div class="money-value">${minText || maxText ? esc(t('money.priceRange', { min: minText || '?', max: maxText || '?' })) : (iap.present === 'yes' ? esc(t('money.priceUnknown')) : esc(t('money.noIap')))}</div><div class="money-tags"><span class="pill">${esc(t('money.firstPrompt', { v: engine.PROMPT_LABEL[iap.first_purchase_prompt] || t('modal.na') }))}</span><span class="pill ${iap.p2w === 'yes' ? 'pill--bad' : ''}">${esc(t('money.p2w', { v: engine.TRI_LABEL[iap.p2w] || t('modal.na') }))}</span><span class="pill ${iap.required_to_progress === 'yes' ? 'pill--bad' : ''}">${esc(t('money.required', { v: engine.TRI_LABEL[iap.required_to_progress] || t('modal.na') }))}</span><span class="pill">${esc(t('money.inflowGrade', { grade: engine.gradeWeakest(range.evidence_grade || 'unknown') }))}</span></div><p class="money-note">${esc(range.note || t('money.priceNoteNone'))}</p></article>
    </div>
    ${impactBlockHtml(view)}
    <dl class="kv"><dt>${esc(t('money.subscription'))}</dt><dd>${esc(engine.TRI_LABEL[money.subscription?.present] || t('modal.na'))} · ${esc(money.subscription?.display || '—')}</dd><dt>${esc(t('money.summary'))}</dt><dd>${esc(money.summary || '—')}</dd></dl>
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
      <p class="mini-label" style="margin:14px 0 6px">${esc(t('money.impactTitle'))}</p>
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
          ? `<p class="money-note">${t('money.freePlay', {
              v: esc(L.freePlay(free.value) || free.value),
              grade: esc(engine.gradeWeakest(free.evidence_grade || 'unknown')),
              note: esc(free.note || ''),
            })}</p>`
          : `<p class="money-note">${esc(t('money.freePlayNone'))}</p>`
      }
      <p class="money-note">${t('money.impactNote')}</p>
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
        <td class="num">${esc(entry.date || t('updates.dateUnknown'))}</td>
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
    <div class="m-sec-head"><span class="sec-num">09</span><h3>${esc(t('modal.sec9'))}</h3>
      ${life ? `<span class="pill pill--${life.tone}">${esc(t('updates.lifeStage', { label: life.label }))}</span>` : ''}
      <span class="pill pill--${meta.tone}">${esc(meta.label)}</span>
      <span class="pill">${esc(t('updates.cadence', { v: engine.CADENCE_LABEL[profile.cadence] || profile.cadence }))}</span>
      <span class="pill">${esc(t('updates.latest', { date: profile.latest_update || t('modal.na'), platform: profile.latest_update_platform ? ` · ${engine.PLATFORM_LABEL[profile.latest_update_platform] || profile.latest_update_platform}` : '' }))}</span>
    </div>
    <p class="m-sec-note">${t('updates.note', { desc: esc(meta.desc) })}</p>
    ${life && lifeKey !== 'active' ? `<div class="callout">${t('updates.lifeCallout', {
      label: esc(life.label),
      note: esc(view.item.maintenance_note || life.desc),
      extra: lifeKey === 'feature_complete' ? t('updates.lifeExtra') : '',
    })}</div>` : ''}
    ${risky ? `<div class="callout callout--bad">${t('updates.risky')}</div>` : ''}
    ${compat ? `<p class="money-note">${t('updates.compat', { v: esc(engine.TRI_LABEL[compat.value] || compat.value), note: esc(compat.note || t('updates.noCompatNote')) })}</p>` : ''}
    <div class="table-wrap">
      <table class="data">
        <thead><tr><th>${esc(t('updates.date'))}</th><th>${esc(t('updates.type'))}</th><th>${esc(t('updates.platform'))}</th><th>${esc(t('updates.promise'))}</th><th>${esc(t('updates.evidence'))}</th><th>${esc(t('updates.memo'))}</th></tr></thead>
        <tbody>${rows || `<tr><td colspan="6" class="muted">${esc(t('updates.noUpdates'))}</td></tr>`}</tbody>
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
          <div class="source-meta">${esc(source.type)} · ${esc(t('evidence.access', { date: source.accessed_at }))} · ${esc(source.id)}</div>
        </div>
        ${url ? `<a class="source-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(t('evidence.open'))}</a>` : `<span class="source-link muted">${esc(t('evidence.noLink'))}</span>`}
      </div>`;
    })
    .join('');
  const flags = Object.entries(item.flags || {})
    .map(([key, node]) => {
      const isExport = key === 'data_export';
      const value = isExport ? L.export(node.value) || node.value : engine.TRI_LABEL[node.value] || node.value;
      const tone = isExport ? 'unknown' : node.value === 'yes' ? 'yes' : node.value === 'no' ? 'no' : 'unknown';
      return `
      <tr>
        <td class="flag-name">${esc(key)}</td>
        <td>${esc(L.flag(key))}</td>
        <td><span class="flag-value flag-value--${tone}">${esc(value)}</span></td>
        <td>${esc(engine.gradeWeakest(node.evidence_grade || 'unknown'))}</td>
        <td>${esc(L.verification(node.verification) || '—')}</td>
        <td class="flag-note">${esc(node.note || '')}</td>
      </tr>`;
    })
    .join('');
  const quality = item.data_quality || {};
  const conflicts = (quality.conflicts || [])
    .map(
      (conflict) =>
        `<li><b>${esc(conflict.field)}</b> — ${esc((conflict.values || []).join(' vs '))}<br><span class="muted">${esc(t('evidence.resolution', { v: conflict.resolution }))}</span></li>`,
    )
    .join('');
  return `
  <section class="m-sec">
    <div class="m-sec-head"><span class="sec-num">10</span><h3>${esc(t('modal.sec10'))}</h3>
      <span class="pill pill--beam">${esc(t('evidence.grade', { grade: engine.gradeWeakest(quality.overall_grade || 'unknown') }))}</span>
      <span class="pill">${esc(t('evidence.method', { v: L.method(item.method) || item.method || '—' }))}</span>
    </div>
    <p class="m-sec-note">${esc(t('evidence.note'))}</p>
    <div class="sources">${sources}</div>
    ${(quality.unverified || []).length ? `<div class="callout"><b>${esc(t('evidence.unverified'))}</b><ul class="list list--muted" style="margin-top:6px">${quality.unverified
      .map((u) => `<li>${esc(u)}</li>`)
      .join('')}</ul></div>` : ''}
    ${conflicts ? `<div class="callout callout--warn"><b>${esc(t('evidence.conflicts'))}</b><ul class="list" style="margin-top:6px">${conflicts}</ul></div>` : ''}
    ${quality.limitations ? `<p class="money-note">${esc(t('evidence.limitations', { v: quality.limitations }))}</p>` : ''}
    <details class="calc-block">
      <summary class="calc-summary">${esc(t('evidence.flags', { n: Object.keys(item.flags || {}).length }))}</summary>
      <div class="table-wrap" style="margin-top:8px">
        <table class="data flag-table">
          <thead><tr><th>${esc(t('evidence.key'))}</th><th>${esc(t('evidence.item'))}</th><th>${esc(t('evidence.value'))}</th><th>${esc(t('evidence.grade'))}</th><th>${esc(t('evidence.verification'))}</th><th>${esc(t('updates.memo'))}</th></tr></thead>
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

/* ------------------------------------------------------------------ 등대(Lighthouse)
   조건(가격·플랫폼·단계)을 고르면 명작 하나를 추첨해 그 게임의 실제 퀘스트를 고정한다.
   한 번 받은 퀘스트는 완료하거나 광고 슬롯으로 건너뛰기 전까지 localStorage 에 남는다. */

const LH_TIERS = [1, 2, 3];
const lhText = (row, field) =>
  String((getLang() === 'en' ? row?.[`${field}_en`] : row?.[`${field}_ko`]) ?? '');

function lhLoadState() {
  const raw = readStore(LS.lighthouse, null);
  if (!raw || typeof raw !== 'object') return;
  const filters = raw.filters || {};
  if (filters.price === 'free' || filters.price === 'all') state.lh.filters.price = filters.price;
  if (['pc', 'mobile', 'all'].includes(filters.platform)) state.lh.filters.platform = filters.platform;
  if (LH_TIERS.includes(Number(filters.tier))) state.lh.filters.tier = Number(filters.tier);
  if (Array.isArray(raw.history)) {
    state.lh.history = raw.history.filter((row) => row && typeof row.game_id === 'string').slice(-100);
  }
  if (Number.isFinite(Number(raw.skips))) state.lh.skips = Math.max(0, Number(raw.skips));
  if (typeof raw.last_game_id === 'string') state.lh.lastGameId = raw.last_game_id;
  const current = raw.current;
  if (current && typeof current.game_id === 'string' && LH_TIERS.includes(Number(current.tier))) {
    state.lh.current = {
      game_id: current.game_id,
      tier: Number(current.tier),
      issued_at: current.issued_at || null,
      filters: {
        price: current.filters?.price === 'free' ? 'free' : 'all',
        platform: ['pc', 'mobile'].includes(current.filters?.platform) ? current.filters.platform : 'all',
        tier: LH_TIERS.includes(Number(current.filters?.tier)) ? Number(current.filters.tier) : Number(current.tier),
      },
    };
    state.lh.filters = { ...state.lh.current.filters };
  }
}

function lhSaveState() {
  writeStore(LS.lighthouse, {
    version: 1,
    filters: state.lh.filters,
    current: state.lh.current,
    history: state.lh.history,
    skips: state.lh.skips,
    last_game_id: state.lh.lastGameId,
  });
}

async function loadLighthouse() {
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

const lhGameById = (id) => (state.lh.data?.games || []).find((game) => game.game_id === id) || null;
const lhQuizOf = (game, tier) => (game?.quests || []).find((quest) => quest.tier === Number(tier)) || null;
const lhTierMeta = (tier) => (state.lh.data?.tiers || []).find((row) => row.tier === Number(tier)) || null;

/** 저장된 퀘스트가 데이터에서 사라졌으면 잠금을 풀어 준다(데이터 개편 대비). */
function lhPruneCurrent() {
  const current = state.lh.current;
  if (!current) return;
  const game = lhGameById(current.game_id);
  if (!game || !lhQuizOf(game, current.tier)) {
    state.lh.current = null;
    lhSaveState();
  }
}

function lhDrawableGames() {
  const { price, platform } = state.lh.filters;
  return (state.lh.data?.games || []).filter(
    (game) => (price !== 'free' || game.free_to_play) && (platform === 'all' || game.platforms.includes(platform)),
  );
}

function lhDraw() {
  if (!state.lh.data) {
    toast(t('lh.toast.noData'));
    return;
  }
  if (state.lh.current) return;
  let pool = lhDrawableGames();
  if (!pool.length) {
    toast(t('lh.toast.noMatch'));
    return;
  }
  if (pool.length > 1 && state.lh.lastGameId) {
    const fresh = pool.filter((game) => game.game_id !== state.lh.lastGameId);
    if (fresh.length) pool = fresh;
  }
  const game = pool[Math.floor(Math.random() * pool.length)];
  const tier = state.lh.filters.tier;
  state.lh.current = {
    game_id: game.game_id,
    tier,
    issued_at: new Date().toISOString(),
    filters: { ...state.lh.filters },
  };
  state.lh.lastGameId = game.game_id;
  lhSaveState();
  syncUrl('replace');
  renderLighthouse();
  toast(t('lh.toast.drawn'), lhQuizOf(game, tier)?.[getLang() === 'en' ? 'title_en' : 'title_ko'] || '');
}

function lhComplete() {
  const current = state.lh.current;
  if (!current) return;
  const game = lhGameById(current.game_id);
  const quest = lhQuizOf(game, current.tier);
  if (!game || !quest) {
    state.lh.current = null;
    lhSaveState();
    renderLighthouse();
    return;
  }
  state.lh.history.push({
    game_id: game.game_id,
    tier: current.tier,
    title_ko: quest.title_ko,
    title_en: quest.title_en,
    completed_at: new Date().toISOString(),
  });
  state.lh.history = state.lh.history.slice(-100);
  state.lh.current = null;
  lhSaveState();
  renderLighthouse();
  toast(t('lh.toast.completed', { name: recordById(game.game_id)?.name || game.game_id }), lhText(quest, 'title'));
}

function lhSkipComplete() {
  if (!state.lh.current) return;
  state.lh.skips += 1;
  state.lh.current = null;
  lhSaveState();
  lhCloseAd();
  renderLighthouse();
  toast(t('lh.toast.skipped'));
}

let lhAdTimer = null;

function lhOpenAd() {
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

function lhCloseAd() {
  clearInterval(lhAdTimer);
  lhAdTimer = null;
  const backdrop = $('lhAdBackdrop');
  if (backdrop) backdrop.hidden = true;
  document.body.style.overflow = '';
}

function lhFilterButtons(group, value, options) {
  return options
    .map(
      (opt) =>
        `<button type="button" role="radio" aria-checked="${value === opt.value ? 'true' : 'false'}"` +
        ` data-lh-${group}="${esc(opt.value)}"${state.lh.current ? ' disabled' : ''}>${esc(opt.label)}</button>`,
    )
    .join('');
}

function lhQuestHtml(game, tier) {
  const quest = lhQuizOf(game, tier);
  if (!quest) return '';
  const meta = lhTierMeta(tier);
  return `
    <div class="lh-quest" data-lh-tier-view="${tier}">
      <p class="lh-quest-kicker"><span class="lh-tier-badge">${esc(lhText(meta, 'label'))}</span><span>${esc(lhText(meta, 'window'))}</span><span>${esc(t('lh.questKicker'))}</span></p>
      <h3 class="lh-quest-title">${esc(lhText(quest, 'title'))}</h3>
      <p class="lh-quest-desc">${esc(lhText(quest, 'desc'))}</p>
      <p class="lh-quest-tip"><b>${esc(t('lh.tipLabel'))}</b> ${esc(lhText(quest, 'tip'))}</p>
      <p class="lh-quest-time"><span aria-hidden="true">⏱</span> ${esc(t('lh.estLabel'))} <b>${esc(lhText(quest, 'est_time'))}</b></p>
    </div>`;
}

function lhResultHtml() {
  const current = state.lh.current;
  if (!state.lh.data) {
    return `<div class="lh-empty"><p>${esc(t('lh.toast.noData'))}</p></div>`;
  }
  if (!current) {
    return `
      <div class="lh-empty">
        <span class="lh-empty-glyph" aria-hidden="true">🚨</span>
        <h2>${esc(t('lh.emptyTitle'))}</h2>
        <p>${esc(t('lh.emptyBody'))}</p>
      </div>`;
  }
  const game = lhGameById(current.game_id);
  const rec = recordById(current.game_id);
  if (!game || !rec) return '';
  const verdict = engine.VERDICT_META[rec.verdict] || engine.VERDICT_META.conditional;
  const scoreText = typeof rec.score === 'number' ? rec.score.toFixed(1) : '—';
  const tier = current.tier;
  const freeLabel = game.free_to_play ? t('lh.badge.free') : t('lh.badge.paid');
  const platformLabel = game.platforms.map((p) => (p === 'pc' ? 'PC' : t('lh.platform.mobile'))).join(' · ');
  return `
    <article class="lh-card" data-lh-game="${esc(game.game_id)}">
      <div class="lh-card-top">
        ${iconHtml(rec, 'detail')}
        <div class="lh-card-id">
          <div class="lh-card-chips">
            <span class="verdict verdict--${verdict.tone}"><span class="v-emoji" aria-hidden="true">${verdict.emoji}</span>${esc(verdict.label)}</span>
            <span class="lh-score">${esc(t('lh.score', { score: scoreText }))}</span>
            <span class="lh-chip">${esc(freeLabel)}</span>
            <span class="lh-chip">${esc(platformLabel)}</span>
          </div>
          <h2 class="lh-game-name">${esc(rec.name)}</h2>
          <p class="lh-game-meta">${esc(state.cat.categoryLabel(rec.category))}${rec.developer ? ` · ${esc(rec.developer)}` : ''}</p>
        </div>
      </div>
      ${lhQuestHtml(game, tier)}
      <div class="lh-actions">
        <button type="button" class="primary-btn" data-lh-complete>${esc(t('lh.complete'))}</button>
        <button type="button" class="ghost-btn" data-lh-ad>${esc(t('lh.adSkip'))}</button>
        <button type="button" class="text-btn" data-lh-detail="${esc(game.game_id)}">${esc(t('lh.detail'))} →</button>
      </div>
    </article>`;
}

function lhHistoryHtml() {
  const history = state.lh.history || [];
  const rows = [...history].reverse().slice(0, 8);
  return `
    <section class="lh-history" id="lhHistory">
      <div class="section-head">
        <h2>${esc(t('lh.historyTitle'))}</h2>
        <span class="section-hint">${esc(t('lh.historyCount', { n: history.length, s: state.lh.skips }))}</span>
      </div>
      <div class="lh-history-list">
        ${
          rows.length
            ? rows
                .map((row) => {
                  const rec = recordById(row.game_id);
                  const date = row.completed_at ? new Date(row.completed_at) : null;
                  const dateText = date && !Number.isNaN(date.getTime())
                    ? date.toLocaleDateString(locale(), { month: 'short', day: 'numeric' })
                    : '';
                  const title = getLang() === 'en' ? row.title_en : row.title_ko;
                  return `<span class="lh-badge" title="${esc(title || '')}">${rec ? iconHtml(rec, 'small') : ''}<span class="lh-badge-text">${esc(rec?.name || row.game_id)}<b>${esc(title || '')}</b></span><span class="lh-badge-date">${esc(dateText)}</span></span>`;
                })
                .join('')
            : `<p class="empty">${esc(t('lh.historyEmpty'))}</p>`
        }
      </div>
    </section>`;
}

function renderLighthouse() {
  const wrap = $('view');
  if (!wrap) return;
  const { price, platform, tier } = state.lh.filters;
  const locked = Boolean(state.lh.current);
  const count = state.lh.data?.counts || {};
  const pool = lhDrawableGames();
  wrap.innerHTML = `
    <section class="lh">
      <div class="hero hero--compact lh-hero">
        <p class="eyebrow">${esc(t('lh.eyebrow'))}</p>
        <h1>${esc(t('lh.titleBefore'))}<span class="hl">${esc(t('lh.titleHl'))}</span></h1>
        <p class="lede">${esc(t('lh.lede'))}</p>
        <div class="lh-stats">
          <span>${t('lh.statGames', { n: count.games ?? 0, q: count.quests ?? 0 })}</span>
          <span>${t('lh.statFree', { n: count.free_to_play ?? 0 })}</span>
          <span>${t('lh.statDone', { n: state.lh.history.length })}</span>
        </div>
      </div>

      <div class="lh-controls" role="group" aria-label="${esc(t('lh.filtersAria'))}">
        <div class="lh-group">
          <span class="lh-label">${esc(t('lh.price'))}</span>
          <div class="lh-seg" role="radiogroup" aria-label="${esc(t('lh.price'))}">
            ${lhFilterButtons('price', price, [
              { value: 'all', label: t('lh.price.all') },
              { value: 'free', label: t('lh.price.free') },
            ])}
          </div>
        </div>
        <div class="lh-group">
          <span class="lh-label">${esc(t('lh.platform'))}</span>
          <div class="lh-seg" role="radiogroup" aria-label="${esc(t('lh.platform'))}">
            ${lhFilterButtons('platform', platform, [
              { value: 'all', label: t('lh.platform.all') },
              { value: 'pc', label: 'PC' },
              { value: 'mobile', label: t('lh.platform.mobile') },
            ])}
          </div>
        </div>
        <div class="lh-group lh-group--tier">
          <span class="lh-label">${esc(t('lh.tier'))}</span>
          <div class="lh-seg" role="radiogroup" aria-label="${esc(t('lh.tier'))}">
            ${lhFilterButtons(
              'tier',
              String(tier),
              LH_TIERS.map((n) => ({ value: String(n), label: t('lh.tierShort', { n }) })),
            )}
          </div>
          <span class="lh-tier-hint">${esc(lhText(lhTierMeta(tier), 'window'))} — ${esc(lhText(lhTierMeta(tier), 'hint'))}</span>
        </div>
        <div class="lh-draw-row">
          <button type="button" class="primary-btn lh-draw" data-lh-draw${locked ? ' disabled' : ''}>${esc(
            locked ? t('lh.drawLocked') : t('lh.draw'),
          )}</button>
          <span class="lh-hint">${esc(
            locked ? t('lh.lockedNote') : t('lh.poolNote', { n: pool.length }),
          )}</span>
        </div>
      </div>

      <div id="lhResult" class="lh-result" aria-live="polite">${lhResultHtml()}</div>
      ${lhHistoryHtml()}
    </section>`;
}

async function openLighthouseDetail(id) {
  const rec = recordById(id);
  if (!rec) return;
  state.lastFocus = document.activeElement;
  state.route = { ...state.route, item: id };
  syncUrl('replace');
  await showDetail(id, rec.arenas[0]);
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

  // 등대 — 필터·추첨·완료·광고 슬롯·상세 열기
  const lhPrice = target.closest('[data-lh-price]');
  if (lhPrice) {
    if (!state.lh.current) {
      state.lh.filters.price = lhPrice.dataset.lhPrice;
      lhSaveState();
      syncUrl('replace');
      renderLighthouse();
    }
    return;
  }
  const lhPlatform = target.closest('[data-lh-platform]');
  if (lhPlatform) {
    if (!state.lh.current) {
      state.lh.filters.platform = lhPlatform.dataset.lhPlatform;
      lhSaveState();
      syncUrl('replace');
      renderLighthouse();
    }
    return;
  }
  const lhTier = target.closest('[data-lh-tier]');
  if (lhTier) {
    if (!state.lh.current) {
      state.lh.filters.tier = Number(lhTier.dataset.lhTier) || 1;
      lhSaveState();
      syncUrl('replace');
      renderLighthouse();
    }
    return;
  }
  const lhDrawBtn = target.closest('[data-lh-draw]');
  if (lhDrawBtn) {
    lhDraw();
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
    if (kind === 'home') return goHome();
    if (kind === 'lighthouse') return navigate({ view: 'lighthouse', domain: null });
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
