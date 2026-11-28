/**
 * Pharos — 상세 모달: 판정 요약·사실·의견·축별 점수·사전(제원표·관련작)·과금·근거.
 *
 * 계산은 engine.js, 문구는 i18n.js, 상태는 state.js 에서 가져와 조립만 한다.
 */

import * as engine from './engine.js';
import { t, labeled, days } from './i18n.js';
import { $, L, RULE_INDEX, contract, esc, iconHtml, isWorkDomain, num, pct, recordById, safeUrl, schemaVersion, settings, state } from './state.js';
import { computeViews, freshnessChip, maintenanceChip, reviewTierChip, ring, storeStarsLabel, storeStarsText } from './catalog.js';
import { render, syncUrl } from './app.js';

export async function openDetail(id) {
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

export async function showDetail(id, arenaOverride = null) {
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
    sectionEncyclopedia(view),
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

export function closeDetail({ silent = false } = {}) {
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

/* --- 📖 기본 정보 · 사전 --- */
/**
 * 평가(점수·티어·판정)와 분리된 사전 섹션.
 * encyclopedia 블록이 있으면 개요·핵심 제원·핵심 특징·관련작·공식 링크를,
 * 없으면 기존 필드(one_liner·developer·release_date·genres·platforms·sources)를
 * 조합한 기본 제원 폴백을 그린다 — 2,000여 전 항목이 같은 자리에서 사전처럼 보인다.
 */

function sectionEncyclopedia(view) {
  const item = view.item;
  const tier = view.recordTier;
  const enc = item.encyclopedia;
  const lines = (value) => String(value || '').split(/\n+/).map((line) => line.trim()).filter(Boolean);
  const paragraphs = (value) =>
    lines(value)
      .map((line) => `<p>${esc(line)}</p>`)
      .join('');

  /* 기본 제원 폴백 — 이미 수집된 사실만 쓴다(새 수치를 만들지 않는다). */
  const fallbackFacts = () => {
    const rows = [];
    if (item.one_liner) rows.push({ key: t('enc.field.overview'), value: item.one_liner });
    if (item.developer || item.publisher) {
      const creator = [item.developer, item.publisher].filter(Boolean);
      rows.push({ key: t(isWorkDomain(item.domain) ? 'enc.field.creator' : 'enc.field.developer'), value: creator.join(' · ') });
    }
    if (item.release_date) rows.push({ key: t('enc.field.release'), value: item.release_date });
    if ((item.genres || []).length) rows.push({ key: t('enc.field.genres'), value: item.genres.join(' · ') });
    if ((item.platforms || []).length) {
      rows.push({
        key: t('enc.field.platforms'),
        value: item.platforms.map((p) => engine.PLATFORM_LABEL[p] || p).join(' · '),
      });
    }
    if (tier?.price?.display) rows.push({ key: t('enc.field.price'), value: tier.price.display });
    const arenas = (item.arenas || []).map((aid) => state.cat.arenaLabel(aid)).filter(Boolean);
    if (arenas.length) rows.push({ key: t('enc.field.arena'), value: arenas.join(' · ') });
    return rows;
  };

  const facts = enc?.key_facts?.length ? enc.key_facts : fallbackFacts();
  const factsHtml = facts.length
    ? `<dl class="enc-facts">${facts
        .map(
          (row) => `<div class="enc-fact"><dt>${esc(row.key)}</dt><dd>${esc(row.value)}${
            row.note ? `<span class="enc-fact-note">${esc(row.note)}</span>` : ''
          }</dd></div>`,
        )
        .join('')}</dl>`
    : '';

  const highlights = enc?.highlights || [];
  const highlightsHtml = highlights.length
    ? `<div class="enc-block"><p class="mini-label">${esc(t('enc.highlightsLabel'))}</p><ul class="enc-highlights">${highlights
        .map((line) => `<li>${esc(line)}</li>`)
        .join('')}</ul></div>`
    : '';

  const related = (enc?.related || []).filter((row) => recordById(row.id));
  const relatedHtml = related.length
    ? `<div class="enc-block"><p class="mini-label">${esc(t('enc.relatedLabel'))}</p>
        <div class="enc-related">${related
          .map((row) => {
            const rec = recordById(row.id);
            const name = rec?.name || row.id;
            const relation = t(`enc.relation.${row.relation}`);
            return `<button type="button" class="enc-rel" data-item="${esc(row.id)}" aria-label="${esc(
              t('enc.jump', { name }),
            )}">${iconHtml(rec || { name }, 'small')}<span class="enc-rel-body"><span class="enc-rel-name">${esc(
              name,
            )}</span><span class="enc-rel-meta"><span class="enc-rel-type enc-rel-type--${esc(row.relation)}">${esc(
              relation,
            )}</span>${row.note ? ` · ${esc(row.note)}` : ''}</span></span><span class="enc-rel-arrow" aria-hidden="true">→</span></button>`;
          })
          .join('')}</div>
        <p class="m-sec-note">${esc(t('enc.relatedNote'))}</p></div>`
    : '';

  const links = (enc?.official_links || []).filter((row) => safeUrl(row.url));
  const linksHtml = links.length
    ? `<div class="enc-block"><p class="mini-label">${esc(t('enc.linksLabel'))}</p><div class="enc-links">${links
        .map(
          (row) => `<a class="enc-link" href="${esc(safeUrl(row.url))}" target="_blank" rel="noopener noreferrer"><span>${esc(
            row.label,
          )}</span><span aria-hidden="true">↗</span></a>${row.note ? `<span class="enc-link-note">${esc(row.note)}</span>` : ''}`,
        )
        .join('')}</div></div>`
    : '';

  const sources = item.sources || [];
  const sourcesHtml =
    !enc && sources.length
      ? `<div class="enc-block"><p class="mini-label">${esc(t('enc.field.sources'))}</p><div class="enc-sources">${sources
          .map((source) => {
            const url = safeUrl(source.url);
            const label = esc(source.title);
            return url
              ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label}</a>`
              : `<span>${label}</span>`;
          })
          .join('')}</div></div>`
      : '';

  const summaryHtml = enc?.summary
    ? `<div class="enc-summary">${paragraphs(enc.summary)}</div>`
    : '';

  return `
  <section class="m-sec" id="secEncyclopedia">
    <div class="m-sec-head"><span class="sec-num">📖</span><h3>${esc(t('enc.title'))}</h3>
      <span class="pill pill--${enc ? 'beam' : 'muted'}">${esc(t(enc ? 'enc.badge.book' : 'enc.badge.fallback'))}</span>
    </div>
    ${enc ? '' : `<p class="m-sec-note">${esc(t('enc.fallbackNote'))}</p>`}
    ${summaryHtml}
    ${factsHtml}
    ${highlightsHtml}
    ${relatedHtml}
    ${linksHtml}
    ${sourcesHtml}
  </section>`;
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

export function calcRuleText(i) {
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
    [t(isWorkDomain(item.domain) ? 'facts.creator' : 'facts.developer'), `${esc(item.developer)}<br><span class="muted">${(item.platforms || [])
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
function isMediaWork(item) {
  return ['movie', 'anime', 'manga'].includes(item?.domain);
}

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
    ${isMediaWork(view.item)
      ? `<p class="m-sec-note">${esc(t('axes.mediaNote'))}</p><p class="m-sec-note">${esc(t('axes.mediaCraftNote'))}</p>`
      : ''}
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
          ? `${metric.value}${metric.scale === 'percent' ? '%' : metric.scale === 'stars5' ? '★' : metric.scale === 'out_of_100' ? '/100' : '/10'} <span class="muted">· ${esc(t('reviews.count', { n: num(metric.count) }))}</span>`
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
