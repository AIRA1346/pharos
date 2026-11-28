/**
 * 파로스 — 📖 도감(encyclopedia) 모드.
 *
 * 점수·판정으로 줄을 세우는 '추천' 모드와 달리, 3,661종을 사전처럼 찾아보는 화면이다.
 * 목록은 경량 인덱스(data/search-index.json)만으로 그린다 — 비교군 파일을 내려받지 않는다.
 * 카드에는 포스터/아이콘·제목·제작·출시연도·장르·한 줄 개요·📖 사전 배지만 두고,
 * 점수·거름/조건부 판정·비교 체크박스 같은 추천 전용 UI 는 싣지 않는다.
 *
 * 정렬은 사전 등재 우선 · 이름순 · 최신 출시순 · 인기·규모순 네 가지이고,
 * 필터는 사전 수록만 · 완결작 · 무료로 시작 세 가지다. 3,661장을 한 번에 그리지 않고
 * ENC_PAGE(120)장씩 '더 보기'로 이어 그린다.
 */

import { t } from './i18n.js';
import { $, ENC_FILTERS, ENC_PAGE, ENC_SORTS, esc, iconHtml, indexRecords, locale, num, state } from './state.js';

/* ------------------------------------------------------------------ 상태 */

export function resetEncState() {
  state.enc.q = '';
  state.enc.sort = 'book';
  state.enc.filters = { book: false, complete: false, free: false };
  state.enc.limit = ENC_PAGE;
}

/** 완결작 — 이미 끝난 작품(완결 태그)이거나 더 나올 콘텐츠가 없는 단계(feature_complete). */
const isComplete = (rec) =>
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
    return new Intl.Collator(locale(), { numeric: true, sensitivity: 'base' });
  } catch {
    return { compare: (a, b) => a.localeCompare(b) };
  }
}

export function encPool() {
  const q = state.enc.q.trim().toLowerCase();
  const tokens = q ? q.split(/\s+/).filter(Boolean) : [];
  const rows = indexRecords().filter((rec) => matches(rec, tokens));
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
  for (const rec of indexRecords()) counts[rec.domain] = (counts[rec.domain] || 0) + 1;
  return counts;
}

/* ------------------------------------------------------------------ 카드 */

const yearOf = (rec) =>
  rec.release_date ? t('encmode.releaseYear', { year: String(rec.release_date).slice(0, 4) }) : t('encmode.releaseUnknown');

function encCard(rec) {
  const kicker = `${state.cat.domainLabel(rec.domain)} · ${state.cat.categoryLabel(rec.category)}`;
  const meta = [rec.developer, yearOf(rec)].filter(Boolean).join(' · ');
  const genres = (rec.genres || []).slice(0, 3).join(' · ');
  return `
  <article class="enc-card" role="button" tabindex="0" data-item="${esc(rec.id)}" data-id="${esc(rec.id)}"
    data-release="${esc(rec.release_date || '')}" data-scale="${Number(rec.scale || 0)}" data-book="${rec.enc ? 1 : 0}"
    aria-label="${esc(t('encmode.cardAria', { name: rec.name }))}">
    ${iconHtml(rec, 'enc')}
    <div class="enc-card-body">
      <p class="enc-card-kicker">${esc(kicker)}</p>
      <h3 class="enc-card-title">${esc(rec.name)}${
        rec.enc ? `<span class="enc-book" title="${esc(t('encmode.filter.book'))}">${esc(t('encmode.book'))}</span>` : ''
      }</h3>
      <p class="enc-card-meta">${esc(meta)}</p>
      <p class="enc-card-line">${esc(rec.one_liner || '')}</p>
      ${genres ? `<p class="enc-card-tags">${esc(genres)}</p>` : ''}
    </div>
  </article>`;
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
      n: num(indexRecords().length),
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
  const idx = state.core.index;
  const counts = idx.counts;
  const records = indexRecords();
  const books = records.filter((rec) => rec.enc).length;
  const domain = state.route.domain ? state.cat.domain(state.route.domain) : null;
  const title = domain ? `${domain.label} · ${t('encmode.title')}` : t('encmode.title');
  const last = records.map((rec) => rec.assessed_at).filter(Boolean).sort().pop();

  const filterCell = (key) =>
    `<label class="enc-filter"><input type="checkbox" data-enc-filter="${esc(key)}" ${
      state.enc.filters[key] ? 'checked' : ''
    } /><span>${esc(t(`encmode.filter.${key}`))}</span></label>`;

  $('view').innerHTML = `
  <section class="level enc-mode">
    <header class="level-head level-head--enc">
      <p class="eyebrow">${esc(t('encmode.eyebrow'))}</p>
      <h1>${esc(title)}</h1>
      <p class="lede lede--line">${esc(domain ? domain.description : t('encmode.lede'))}</p>
      <div class="level-badges">
        <span class="chip">${esc(t('encmode.meta.items', { n: num(counts.items) }))}</span>
        <span class="chip chip--book">${esc(t('encmode.meta.books', { n: num(books) }))}</span>
        <span class="chip chip--muted">${esc(t('encmode.meta.arena', { n: counts.arenas }))}</span>
        ${last ? `<span class="chip chip--muted">${esc(t('encmode.meta.last', { date: last }))}</span>` : ''}
      </div>
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
        <label class="select-label" for="encSort">${esc(t('encmode.sortAria'))}</label>
        <select id="encSort" aria-label="${esc(t('encmode.sortAria'))}">${ENC_SORTS.map(
          (key) =>
            `<option value="${key}" ${state.enc.sort === key ? 'selected' : ''}>${esc(t(`encmode.sort.${key}`))}</option>`,
        ).join('')}</select>
      </div>
      <div class="enc-filters">${ENC_FILTERS.map(filterCell).join('')}</div>
      <span class="panel-hint enc-count" id="encCount"></span>
    </div>

    <div class="enc-grid" id="encGrid"></div>
    <p class="empty" id="encEmpty" hidden>${esc(t('encmode.empty'))}</p>
    <div class="enc-foot">
      <button type="button" class="ghost-btn enc-more" id="encMore" data-action="enc-more"></button>
      <p class="enc-done" id="encDone" hidden></p>
    </div>
  </section>`;

  renderEncResults();
}
