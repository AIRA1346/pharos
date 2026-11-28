/**
 * Pharos — 공유 상태·저장소·테마·언어 (app.js 에서 분리).
 *
 * 이 모듈은 화면을 그리지 않는다. localStorage 래퍼, 테마·언어 설정, 가중치 프리셋,
 * 공용 포매터($·esc·iconHtml … ) 처럼 여러 화면이 함께 쓰는 것만 모은다.
 */

import * as engine from './engine.js';
import { t, labeled, nfmt, setLang, getLang } from './i18n.js';

export const LS = {
  theme: 'pharos-theme',
  prefs: 'pharos-prefs',
  bookmarks: 'pharos-bookmarks',
  lighthouse: 'pharos_lighthouse_state_v1',
};

export const PRESETS = [
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

export const presetLabelOf = (id) => t(`preset.${id}`);

export const presetHintOf = (id) => t(`preset.${id}.hint`);

/* v31 — 영화·애니·만화는 제작진·감상 경로를 쓰는 '작품' 도메인이다. */
const WORK_DOMAINS = new Set(['movie', 'anime', 'manga']);

export const isWorkDomain = (domain) => WORK_DOMAINS.has(domain);

export const SORT_KEYS = ['score', 'score-asc', 'risk', 'name'];

/* v38 — 📖 도감 모드의 정렬·필터. 점수 순서가 아니라 사전처럼 찾아보는 축이다. */
export const ENC_SORTS = ['book', 'name', 'newest', 'scale'];
export const ENC_FILTERS = ['book', 'complete', 'free'];
export const ENC_PAGE = 120;

export const sortLabel = (key) => t(`sort.${key === 'score-asc' ? 'scoreAsc' : key}`);

/* 도메인·플랫폼·필터·축 라벨은 i18n.js 의 사전에서 온다. 데이터 라벨(비교군·대분류)은
   data/catalog.json 과 data/en/core.json 이 맡는다. */

export const RULE_INDEX = { 1: 0, '1w': 0, '1c': 6, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5 };

export const L = {
  flag: (key) => labeled('flag', key, key),
  verification: (key) => labeled('verification', key, key),
  export: (key) => labeled('export', key, key),
  freePlay: (key) => labeled('freePlay', key, key),
  method: (key) => labeled('method', key, key),
  tag: (key) => labeled('tag', key, key),
};

export const state = {
  core: null,
  cat: null,
  store: null,
  route: { view: 'home', domain: null, category: null, arena: null, item: null, compare: [] },
  query: '',
  sort: 'score',
  showAvoided: true,
  /** 📖 도감 모드 — 검색어·정렬·필터·대분류/비교군·지금까지 그린 장수(더 보기). */
  enc: {
    q: '',
    sort: 'book',
    filters: { book: false, complete: false, free: false },
    category: null,
    arena: null,
    limit: ENC_PAGE,
  },
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
    step: 0,
    filters: { category: null, price: 'all', platform: 'all', tier: 1, difficulty: 'all' },
    current: null,
    history: [],
    skips: 0,
    lastItemId: null,
    /** 항해 서약 체크 — 저장하지 않는다. 목표 탐색을 누를 때마다 새로 서약한다. */
    pledgeAccepted: false,
  },
};

export const $ = (id) => document.getElementById(id);

export const esc = (value) =>
  String(value ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

export const safeUrl = (url) => (/^https?:\/\//i.test(String(url || '')) ? url : null);

export const pct = (num) => `${Math.round(num * 100)}%`;

/** 헤더·경로 표시용 한 줄 설명 — 줄표(—) 뒤 부연을 잘라 한 줄로 만든다. */
export const shortText = (value, limit = 76) => {
  const raw = String(value ?? '').split(' — ')[0].trim();
  return raw.length > limit ? `${raw.slice(0, limit).trim()}…` : raw;
};

export const num = (value) => nfmt(value ?? 0);

export const locale = () => (getLang() === 'en' ? 'en-US' : 'ko-KR');

export const contract = () => state.core?.contract || {};

/* 공식 아이콘 — data 의 icon 경로(assets/icons/{id}.webp)를 그대로 쓴다.
   파일이 없거나 깨져 있으면 img 가 숨겨지고 CSS 가 이름 첫 글자 이니셜 배지를 보여준다. */

const iconSrc = (icon) => {
  const raw = String(icon || '').trim().replace(/^\.?\//, '');
  return raw ? `./${raw}` : null;
};

const initialOf = (name) => String(name || '?').trim().slice(0, 1).toUpperCase();

export function iconHtml(item, size = 'card') {
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

export const schemaVersion = () => state.core?.schema?.['x-pharos']?.schema_version || contract().schema_version || '0.4.0';

export const indexRecords = () => state.core?.index?.items || [];

export const recordById = (id) => indexRecords().find((rec) => rec.id === id) || null;

export const settings = () => ({
  contract: contract(),
  weights: state.weights,
  enabledFilters: state.enabledFilters,
  strict: state.strict,
  strictMonetization: state.strictMonetization,
});

/* ------------------------------------------------------------------ 초기화 */

export function readStore(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

export function writeStore(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* 저장 실패는 무시 */
  }
}

export function initTheme() {
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

export function toggleTheme() {
  state.theme = state.theme === 'dark' ? 'light' : 'dark';
  try {
    localStorage.setItem(LS.theme, state.theme);
  } catch {
    /* 무시 */
  }
  applyTheme();
}

export function loadPrefs() {
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

export function savePrefs() {
  writeStore(LS.prefs, {
    weights: state.weights,
    filters: state.enabledFilters,
    strict: state.strict,
    strictMonetization: state.strictMonetization,
    preset: state.preset,
  });
}

/** <html lang>·<title>·메타 설명·OG 를 현재 언어로 맞춘다. */
export function applyDocumentLang() {
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
export function switchLang(lang) {
  if (!lang || lang === state.lang) return;
  setLang(lang);
  state.lang = lang;
  const params = new URLSearchParams(location.search);
  params.set('lang', lang);
  location.href = `${location.pathname}?${params.toString()}`;
}

/* --------------------------------------------------------------- 라우팅 */
