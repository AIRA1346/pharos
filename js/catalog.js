/**
 * Pharos — 카탈로그 화면: 상단 탭·경로, 홈(전체 탐색), 도메인·대분류·비교군 목록,
 * 카드, 비교 바·비교 표.
 *
 * 비교군 항목 로딩(lazy)과 판정 계산은 data.js·engine.js 가 맡고, 이 모듈은 그 결과를
 * DOM 으로 조립한다. 상세 모달은 detail.js 가 연다.
 */

import * as engine from './engine.js';
import { searchRecords } from './data.js';
import { t, labeled, days } from './i18n.js';
import { $, PRESETS, SORT_KEYS, contract, esc, iconHtml, indexRecords, locale, num, presetLabelOf, recordById, settings, shortText, sortLabel, state } from './state.js';
import { openDetail } from './detail.js';
import { navigate, render, renderSeq, syncUrl, toast } from './app.js';

export function renderDomainTabs() {
  const wrap = $('domainTabs');
  if (!wrap) return;
  const view = state.route.view;
  const active = view === 'lighthouse' ? 'lighthouse' : view === 'encyclopedia' ? 'encyclopedia' : 'recommend';
  const modes = [
    { key: 'lighthouse', label: t('nav.lighthouse'), action: 'lighthouse' },
    { key: 'recommend', label: t('nav.recommend'), action: 'recommend' },
    { key: 'encyclopedia', label: t('nav.encyclopedia'), action: 'encyclopedia' },
  ];
  wrap.innerHTML = modes
    .map(
      (mode) =>
        `<button type="button" role="tab" data-action="${mode.action}" aria-selected="${
          active === mode.key ? 'true' : 'false'
        }">${esc(mode.label)}</button>`,
    )
    .join('');
}

/**
 * 2차 분야 바 — 추천·도감 두 모드가 함께 쓴다.
 * 추천은 분야의 장르(비교군)로, 도감은 분야의 작품 목록으로 들어간다.
 * 등대(첫 화면)에서는 숨긴다 — 등대는 분야를 위저드 안에서 묻는다.
 */
export function renderDomainFilter() {
  const wrap = $('domainFilter');
  if (!wrap) return;
  const view = state.route.view;
  if (view === 'lighthouse' || !state.cat) {
    wrap.hidden = true;
    wrap.innerHTML = '';
    return;
  }
  const encyclopedia = view === 'encyclopedia';
  const counts = encyclopedia ? encDomainCounts() : null;
  const domains = state.cat.catalog.domains || [];
  const total = encyclopedia
    ? domains.reduce((sum, dom) => sum + (counts[dom.id] || 0), 0)
    : state.cat.arenasOf().length;
  const rows = [
    { id: 'all', label: t('home.domainAll'), count: total },
    ...domains.map((dom) => ({
      id: dom.id,
      label: dom.label,
      count: encyclopedia ? counts[dom.id] || 0 : state.cat.arenasOf(dom.id).length,
    })),
  ];
  wrap.hidden = false;
  wrap.dataset.mode = encyclopedia ? 'encyclopedia' : 'recommend';
  wrap.innerHTML = rows
    .map((row) => {
      const on = row.id === 'all' ? !state.route.domain : state.route.domain === row.id;
      return `<button type="button" class="domain-chip" data-action="mode-domain" data-domain="${
        row.id === 'all' ? '' : esc(row.id)
      }" aria-pressed="${on ? 'true' : 'false'}"><span>${esc(row.label)}</span><b>${num(row.count)}</b></button>`;
    })
    .join('');
}

let encCountCache = null;

/** 도감 모드의 분야별 수록 수 — 인덱스는 판마다 같으므로 한 번만 센다. */
function encDomainCounts() {
  if (encCountCache) return encCountCache;
  const counts = {};
  for (const rec of indexRecords()) counts[rec.domain] = (counts[rec.domain] || 0) + 1;
  encCountCache = counts;
  return counts;
}

export function renderBreadcrumb() {
  const wrap = $('breadcrumb');
  const note = $('crumbNote');
  if (!wrap) return;
  const route = state.route;
  const crumbs = [];
  if (route.view === 'lighthouse') {
    /* 등대는 첫 화면 — 경로 대신 화면 아래 안내를 쓴다. */
    crumbs.push({ label: t('nav.lighthouse') });
  } else if (route.view === 'encyclopedia') {
    crumbs.push({ label: t('nav.encyclopedia'), action: 'encyclopedia' });
    if (route.domain) {
      crumbs.push({ label: state.cat.domainLabel(route.domain), action: 'enc-domain', domain: route.domain });
    }
  } else {
    crumbs.push({ label: t('nav.recommend'), action: 'recommend' });
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
      if (route.view === 'compare') crumbs.push({ label: t('crumb.compare') });
    }
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
        : route.view === 'encyclopedia'
          ? t('encmode.crumbNote')
          : arena
            ? `${shortText(arena.description, 64)}`
            : route.domain
              ? `${state.cat.domain(route.domain)?.description || ''}`
              : t('crumb.homeNote');
  }
}

export function renderDatasetChip() {
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

export function renderHome() {
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
      <div class="genre-list" id="genreList">${arenas.map((arena) => genreBlockHtml(arena, { kicker: true })).join('')}</div>
      <p class="empty" id="genreEmpty" hidden>${esc(t('home.genreEmpty'))}</p>
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
 * 홈(추천 모드 첫 화면)의 장르 쇼케이스 — 비교군 12개의 추천 타일을 한눈에.
 * 분야(앱·게임·…)는 상단 2차 분야 바가 맡는다 — 예전의 홈 내부 도메인 칩은 그 바와 겹쳐서 없앴다.
 */

function homeGenreHint(arenas) {
  const scope = t('home.genreHint.all', { n: arenas.length });
  return t(state.preset === 'balanced' ? 'home.genreHint.one' : 'home.genreHint.mine', { scope });
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

export function bookmarkRowHtml(rec) {
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

export function renderHomeSearch() {
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

export function renderDomain() {
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

export function renderCategory() {
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

export async function renderArena(seq) {
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

export function computeViews(items) {
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

export function renderArenaResults() {
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

export function presetLabel() {
  if (state.preset === 'custom') return t('preset.custom');
  return PRESETS.some((p) => p.id === state.preset) ? presetLabelOf(state.preset) : t('preset.balanced');
}

/* -------------------------------------------------------------------- 카드 */

export function ring(score) {
  const circumference = 106.814;
  const value = Math.max(0, Math.min(100, score ?? 0));
  const dash = (value / 100) * circumference;
  return `<svg class="ring" viewBox="0 0 40 40" aria-hidden="true" focusable="false">
      <circle class="ring-track" cx="20" cy="20" r="17"></circle>
      <circle class="ring-value" cx="20" cy="20" r="17" stroke-dasharray="${dash.toFixed(2)} ${circumference.toFixed(2)}"></circle>
    </svg>`;
}

/* 발행 단계 배지 — `auto_fact`(공개 API 대량 적재) 항목에만 붙는다. `verified` 는 배지 없음. */
export function reviewTierChip(item) {
  if (!item || item.review_tier !== 'auto_fact') return '';
  return `<span class="chip chip--auto" title="${esc(t('reviewTier.badgeTitle'))}">${esc(t('reviewTier.badge'))}</span>`;
}

export function maintenanceChip(item) {
  const key = item?.maintenance_status;
  const meta = engine.MAINTENANCE_STATUS_META[key];
  if (!meta || key === 'active') return '';
  return `<span class="chip chip--maintenance chip--maintenance--${esc(meta.tone)}" title="${esc(
    item.maintenance_note || meta.desc,
  )}">${esc(meta.label)}</span>`;
}

export function freshnessChip(item) {
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

export function renderCompareBar() {
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

export function toggleCompare(id) {
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

export async function renderCompare(seq) {
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
    { id: 'stars', label: compareStarsLabel(views), num: (v) => storeStarsValue(v.item), render: (v) => storeStarsText(v.item) },
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
  // 미디어는 외부 평점을 쓰지 않는다(v0.8.0) — 별점·최근 리뷰 줄은 미디어만 비교할 때 뺀다.
  const mediaOnly = views.every((v) => ['movie', 'anime', 'manga'].includes(v.item.domain));
  const shownRows = mediaOnly ? rows.filter((row) => row.id !== 'stars' && row.id !== 'recent') : rows;
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
          ${shownRows
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

/** 누적 별점 행의 이름 — 실제 스토어 표본이면 '스토어 누적 별점', G2 같은 3자 집계면 '누적 평점(3자 집계)'.
 *  작품 도메인(영화·애니·만화)은 5점·100점 척도를 섞어 쓰므로 표본 척도에 맞는 이름을 고른다. */
export function storeStarsLabel(item) {
  const rows = (item.review_snapshot?.platforms || []).filter((row) => row.cumulative);
  const stars = rows
    .filter((row) => row.cumulative.scale === 'stars5')
    .sort((a, b) => (b.cumulative.count || 0) - (a.cumulative.count || 0))[0];
  if (!stars) {
    const hundred = rows.filter((row) => row.cumulative.scale === 'out_of_100');
    return hundred.length ? t('compare.row.stars.score') : t('compare.row.stars');
  }
  return STORE_PLATFORMS.includes(stars.platform) ? t('stars.store') : t('stars.aggregate');
}

/** 비교 표의 누적 평점 행 이름 — 비교 대상 중 5점 척도 표본이 없으면(미디어 도메인) 100점 척도로 부른다. */
function compareStarsLabel(views) {
  const hasStars = (views || []).some((v) =>
    (v.item?.review_snapshot?.platforms || []).some((row) => row.cumulative?.scale === 'stars5'),
  );
  return hasStars ? t('compare.row.stars') : t('compare.row.stars.score');
}

export function storeStarsText(item) {
  const rows = (item.review_snapshot?.platforms || [])
    .map((row) => ({ row, metric: row.cumulative }))
    .filter(({ metric }) => metric && (metric.scale === 'stars5' || metric.scale === 'out_of_100'))
    .sort((a, b) => (b.metric.count || 0) - (a.metric.count || 0));
  if (!rows.length) return '<span class="muted">—</span>';
  const { row, metric } = rows[0];
  const head = metric.scale === 'stars5' ? `★ ${Number(metric.value).toFixed(1)}` : `${Number(metric.value).toFixed(metric.value % 1 ? 1 : 0)}/100`;
  return `${head} <span class="muted">${engine.PLATFORM_LABEL[row.platform] || row.platform} · ${esc(
    t('reviews.count', { n: num(metric.count) }),
  )}</span>`;
}

/** 비교 표에서 '최고'를 표시할 때 쓰는 누적 평점 숫자(가장 큰 표본 — 5점 척도는 그대로, 100점 척도는 그대로 비교). */
function storeStarsValue(item) {
  const values = (item.review_snapshot?.platforms || [])
    .map((row) => row.cumulative)
    .filter((metric) => metric && (metric.scale === 'stars5' || metric.scale === 'out_of_100'))
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
      const value = metric.scale === 'percent' ? `${metric.value}%` : metric.scale === 'stars5' ? `★ ${metric.value}` : metric.scale === 'out_of_100' ? `${metric.value}/100` : `${metric.value}/10`;
      return `${esc(engine.PLATFORM_LABEL[row.platform] || row.platform)} ${value}${
        gap == null ? '' : ` <span class="muted">(${gap > 0 ? '+' : ''}${gap.toFixed(1)}p)</span>`
      }`;
    })
    .join('<br>');
}

/* ---------------------------------------------------------------- 상세 모달 */
