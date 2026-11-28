/**
 * 파로스 — 📖 도감(encyclopedia) 모드.
 *
 * 점수·판정으로 줄을 세우는 '추천' 모드와 달리, 4,436종을 사전처럼 찾아보는 화면이다.
 * 목록은 경량 인덱스(data/search-index.json)만으로 그린다 — 비교군 파일을 내려받지 않는다.
 *
 * v40 — 카드를 '포스터 + 제목' 으로 다시 짰다.
 *   · 카드의 주인공은 큰 정사각 포스터(아이콘)다. 제목은 두 줄까지, 그 아래 보조 한 줄(장르 또는 출시연도)만.
 *   · 📖 사전 꼬리표·한 줄 개요·제작사·대분류 텍스트 줄은 뺐다 — 이미 도감에 들어왔는데 또 붙일 이유가 없다.
 *   · 모바일 3열 · 데스크톱 6열 고밀도 그리드라 한 화면에 여러 작품이 함께 보인다.
 *   · 분야를 고르면 그 분야의 대분류(장르) 칩 바가, 대분류를 고르면 비교군 칩이 이어진다.
 *
 * 정렬은 사전 등재 우선 · 이름순 · 최신 출시순 · 인기·규모순 네 가지이고,
 * 필터는 사전 수록만 · 완결작 · 무료로 시작 세 가지다. 4,436장을 한 번에 그리지 않고
 * ENC_PAGE(120)장씩 '더 보기'로 이어 그린다.
 */

import { t } from './i18n.js';
import { $, ENC_FILTERS, ENC_PAGE, ENC_SORTS, esc, num, state } from './state.js';

/* ------------------------------------------------------------------ 상태 */

export function resetEncState() {
  state.enc.q = '';
  state.enc.sort = 'book';
  state.enc.filters = { book: false, complete: false, free: false };
  state.enc.category = null;
  state.enc.arena = null;
  state.enc.limit = ENC_PAGE;
}

/** 완결작 — 이미 끝난 작품(완결 태그)이거나 더 나올 콘텐츠가 없는 단계(feature_complete). */
export const isComplete = (rec) =>
  (rec.taste_tags || []).includes('completed') || rec.maintenance_status === 'feature_complete';

const haystack = (rec) =>
  [
    rec.name,
    ...(rec.aliases || []),
    rec.developer,
    ...(rec.genres || []),
    ...(rec.keywords || []),
    rec.one_liner,
  ]
    .join(' ')
    .toLowerCase();

function matches(rec, tokens) {
  if (state.route.domain && rec.domain !== state.route.domain) return false;
  if (state.enc.category && rec.category !== state.enc.category) return false;
  if (state.enc.arena && !(rec.arenas || []).includes(state.enc.arena)) return false;
  const filters = state.enc.filters;
  if (filters.book && !rec.enc) return false;
  if (filters.complete && !isComplete(rec)) return false;
  if (filters.free && !rec.free) return false;
  if (tokens.length) {
    const hay = haystack(rec);
    for (const token of tokens) if (!hay.includes(token)) return false;
  }
  return true;
}

function collator() {
  try {
    return new Intl.Collator(state.lang === 'en' ? 'en-US' : 'ko-KR', { numeric: true, sensitivity: 'base' });
  } catch {
    return { compare: (a, b) => a.localeCompare(b) };
  }
}

export function encPool() {
  const q = state.enc.q.trim().toLowerCase();
  const tokens = q ? q.split(/\s+/).filter(Boolean) : [];
  const rows = (state.core?.index?.items || []).filter((rec) => matches(rec, tokens));
  const cmp = collator();
  const byName = (a, b) => cmp.compare(a.name, b.name);
  const sorters = {
    name: byName,
    newest: (a, b) => String(b.release_date || '').localeCompare(String(a.release_date || '')) || byName(a, b),
    book: (a, b) => (b.enc ? 1 : 0) - (a.enc ? 1 : 0) || byName(a, b),
    scale: (a, b) => (b.scale || 0) - (a.scale || 0) || (b.score ?? -1) - (a.score ?? -1) || byName(a, b),
  };
  return rows.sort(sorters[state.enc.sort] || sorters.book);
}

export function domainCounts() {
  const counts = {};
  for (const rec of (state.core?.index?.items || [])) counts[rec.domain] = (counts[rec.domain] || 0) + 1;
  return counts;
}

/* ------------------------------------------------------------------ 카드 */

const yearOf = (rec) =>
  rec.release_date
    ? t('encmode.releaseYear', { year: String(rec.release_date).slice(0, 4) })
    : t('encmode.releaseUnknown');

const posterSrc = (icon) => {
  const raw = String(icon || '').trim().replace(/^\.?\//, '');
  return raw ? `./${raw}` : null;
};

/** 카드 보조 한 줄 — 장르 1~2개, 없으면 출시연도. 텍스트를 더 얹지 않는다. */
function subLine(rec) {
  const genres = (rec.genres || []).slice(0, 2).join(' · ');
  return genres || yearOf(rec);
}

function encCard(rec) {
  const src = posterSrc(rec.icon);
  const initial = String(rec.name || '?').trim().slice(0, 1).toUpperCase();
  const complete = isComplete(rec);
  return `
  <article class="enc-card" role="button" tabindex="0" data-item="${esc(rec.id)}" data-id="${esc(rec.id)}"
    data-release="${esc(rec.release_date || '')}" data-scale="${Number(rec.scale || 0)}" data-book="${rec.enc ? 1 : 0}"
    aria-label="${esc(t('encmode.cardAria', { name: rec.name }))}">
    <span class="item-icon item-icon--poster" data-initial="${esc(initial)}" aria-hidden="true">${
      src ? `<img src="${esc(src)}" alt="" loading="lazy" decoding="async" />` : ''
    }</span>
    <div class="enc-card-body">
      <h3 class="enc-card-title" title="${esc(rec.name)}">${esc(rec.name)}</h3>
      <p class="enc-card-sub">${esc(subLine(rec))}</p>
    </div>
    ${complete ? `<span class="enc-done-chip">${esc(t('encmode.badge.complete'))}</span>` : ''}
  </article>`;
}

/* -------------------------------------------------------- 장르·비교군 칩 */

/**
 * 분야를 골랐을 때만 나오는 2단 칩 바.
 * 1단은 그 분야의 대분류(장르), 대분류를 고르면 2단으로 그 안의 비교군이 이어진다.
 * '전체' 칩은 상위 단계를 푸는 역할이라 항상 맨 앞에 둔다.
 */
function genreBar(records) {
  const domain = state.route.domain;
  if (!domain) return '';
  const cats = state.cat.categoriesOf(domain);
  if (!cats.length) return '';

  const inDomain = records.filter((rec) => rec.domain === domain);
  const catCount = new Map();
  for (const rec of inDomain) catCount.set(rec.category, (catCount.get(rec.category) || 0) + 1);
  const shape = (key, label, count) => {
    const on = key ? state.enc.category === key : !state.enc.category;
    return `<button type="button" class="enc-genre${on ? ' is-on' : ''}" data-action="enc-category"
      data-category="${esc(key || '')}" aria-pressed="${on ? 'true' : 'false'}"><span>${esc(label)}</span><b>${num(
      count,
    )}</b></button>`;
  };
  const rows = [
    `<nav class="enc-genres" id="encGenres" aria-label="${esc(t('encmode.genreAria'))}">`,
    shape('', t('encmode.genreAll'), inDomain.length),
    ...cats.map((cat) => shape(cat.id, cat.label, catCount.get(cat.id) || 0)),
    '</nav>',
  ];

  if (state.enc.category) {
    const arenas = state.cat.arenasOf(domain, state.enc.category);
    const arenaCount = new Map();
    for (const rec of inDomain) {
      if (rec.category !== state.enc.category) continue;
      for (const id of rec.arenas || []) arenaCount.set(id, (arenaCount.get(id) || 0) + 1);
    }
    if (arenas.length > 1) {
      const on = (id) => (id ? state.enc.arena === id : !state.enc.arena);
      rows.push(`<nav class="enc-genres enc-genres--sub" id="encArenas" aria-label="${esc(t('encmode.arenaAria'))}">`);
      rows.push(
        `<button type="button" class="enc-genre enc-genre--sm${on(null) ? ' is-on' : ''}" data-action="enc-arena"
          data-arena="" aria-pressed="${on(null) ? 'true' : 'false'}"><span>${esc(t('encmode.genreAll'))}</span></button>`,
      );
      for (const arena of arenas) {
        rows.push(
          `<button type="button" class="enc-genre enc-genre--sm${on(arena.id) ? ' is-on' : ''}" data-action="enc-arena"
            data-arena="${esc(arena.id)}" aria-pressed="${on(arena.id) ? 'true' : 'false'}"><span>${esc(
            arena.label,
          )}</span><b>${num(arenaCount.get(arena.id) || 0)}</b></button>`,
        );
      }
      rows.push('</nav>');
    }
  }
  return rows.join('');
}

/* ------------------------------------------------------------- 결과 그리기 */

export function renderEncResults() {
  const grid = $('encGrid');
  if (!grid) return;
  const pool = encPool();
  const limit = Math.min(state.enc.limit, pool.length);
  grid.innerHTML = pool.slice(0, limit).map(encCard).join('');
  const empty = $('encEmpty');
  if (empty) empty.hidden = pool.length > 0;

  const count = $('encCount');
  if (count) {
    count.textContent = t('encmode.count', {
      shown: num(pool.length),
      n: num((state.core?.index?.items || []).length),
    });
  }
  const more = $('encMore');
  if (more) {
    const all = limit >= pool.length;
    more.hidden = all;
    more.disabled = all;
    if (!all) more.textContent = t('encmode.more', { shown: num(limit), n: num(pool.length) });
  }
  const done = $('encDone');
  if (done) {
    done.hidden = limit < pool.length;
    done.textContent = t('encmode.allShown', { n: num(pool.length) });
  }
}

/* ------------------------------------------------------------------ 화면 */

export function renderEncyclopedia() {
  const records = (state.core?.index?.items || []);
  const counts = state.core.index.counts;
  const books = records.filter((rec) => rec.enc).length;
  const domain = state.route.domain ? state.cat.domain(state.route.domain) : null;
  const last = records.map((rec) => rec.assessed_at).filter(Boolean).sort().pop();

  const filterCell = (key) =>
    `<label class="enc-filter"><input type="checkbox" data-enc-filter="${esc(key)}" ${
      state.enc.filters[key] ? 'checked' : ''
    } /><span>${esc(t(`encmode.filter.${key}`))}</span></label>`;

  const meta = [
    t('encmode.meta.items', { n: num(counts.items) }),
    t('encmode.meta.books', { n: num(books) }),
    t('encmode.meta.arena', { n: counts.arenas }),
    last ? t('encmode.meta.last', { date: last }) : '',
  ]
    .filter(Boolean)
    .join(' · ');

  $('view').innerHTML = `
  <section class="level enc-mode">
    <header class="enc-head">
      <div class="enc-head-main">
        <p class="eyebrow">${esc(t('encmode.eyebrow'))}</p>
        <h1>${domain ? `${esc(domain.label)}<span class="enc-h1-sub">${esc(t('encmode.titleShort'))}</span>` : esc(t('encmode.title'))}</h1>
      </div>
      <p class="enc-head-meta">${esc(meta)}</p>
    </header>

    <div class="enc-toolbar">
      <label class="search enc-search">
        <span class="search-ico" aria-hidden="true">⌕</span>
        <input type="search" id="encSearch" autocomplete="off" value="${esc(state.enc.q)}"
               placeholder="${esc(t('encmode.searchPlaceholder'))}" aria-label="${esc(t('encmode.searchAria'))}" />
        <button type="button" class="text-btn enc-search-clear" data-action="enc-clear" ${
          state.enc.q ? '' : 'hidden'
        }>${esc(t('encmode.searchClear'))}</button>
      </label>
      <div class="select-row">
        <select id="encSort" aria-label="${esc(t('encmode.sortAria'))}">${ENC_SORTS.map(
          (key) =>
            `<option value="${key}" ${state.enc.sort === key ? 'selected' : ''}>${esc(t(`encmode.sort.${key}`))}</option>`,
        ).join('')}</select>
      </div>
      <div class="enc-filters">${ENC_FILTERS.map(filterCell).join('')}</div>
      <span class="enc-count" id="encCount"></span>
    </div>

    ${genreBar(records)}

    <div class="enc-grid" id="encGrid"></div>
    <p class="empty" id="encEmpty" hidden>${esc(t('encmode.empty'))}</p>
    <div class="enc-foot">
      <button type="button" class="ghost-btn enc-more" id="encMore" data-action="enc-more"></button>
      <p class="enc-done" id="encDone" hidden></p>
    </div>
  </section>`;

  renderEncResults();
}
