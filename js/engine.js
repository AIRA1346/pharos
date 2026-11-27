import { t, labeled, nfmt } from './i18n.js';

/**
 * Pharos 계산 엔진
 * schema/item.schema.json 의 x-pharos.client 계약을 그대로 JavaScript로 옮긴 순수 함수 모음.
 * DOM 을 모르고, 점수·판정을 하드코딩하지 않는다. 모든 값은 아이템 JSON + 사용자 설정에서 계산한다.
 */

export const SIGNAL_META = {
  green: { emoji: '🟢', get label() { return t('signal.green'); }, short: 'G' },
  yellow: { emoji: '🟡', get label() { return t('signal.yellow'); }, short: 'Y' },
  red: { emoji: '🔴', get label() { return t('signal.red'); }, short: 'R' },
  unknown: { emoji: '⚪', get label() { return t('signal.unknown'); }, short: '?' },
};

export const VERDICT_META = {
  recommend: { emoji: '🟢', get label() { return t('verdictMeta.recommend'); }, tone: 'ok' },
  conditional: { emoji: '🟡', get label() { return t('verdictMeta.conditional'); }, tone: 'warn' },
  avoid: { emoji: '🔴', get label() { return t('verdictMeta.avoid'); }, tone: 'bad' },
};

export const TRI_LABEL = {
  get yes() { return t('tri.yes'); },
  get no() { return t('tri.no'); },
  get unknown() { return t('tri.unknown'); },
  get not_assessed() { return t('tri.not_assessed'); },
};

export const KIND_LABEL = {
  get free() { return t('kind.free'); },
  get freemium() { return t('kind.freemium'); },
  get demo() { return t('kind.demo'); },
  get one_time() { return t('kind.one_time'); },
  get subscription() { return t('kind.subscription'); },
  get license() { return t('kind.license'); },
  get consumable() { return t('kind.consumable'); },
};

export const CATEGORY_LABEL = { game: '게임', app: '앱', service: '서비스', tool: '도구' };

export const PLATFORM_LABEL = {
  steam: 'Steam',
  android: 'Android',
  ios: 'iOS',
  windows: 'Windows',
  macos: 'macOS',
  linux: 'Linux',
  get web() { return t('platform.web'); },
  get console() { return t('platform.console'); },
  get other() { return t('platform.other'); },
  get tv() { return t('platform.tv'); },
  get cinema() { return t('platform.cinema'); },
  get streaming() { return t('platform.streaming'); },
  get print() { return t('platform.print'); },
  get anilist() { return t('platform.anilist'); },
  get letterboxd() { return t('platform.letterboxd'); },
};

export const EXPOSURE_LABEL = {
  get none() { return t('exposure.none'); },
  get low() { return t('exposure.low'); },
  get medium() { return t('exposure.medium'); },
  get high() { return t('exposure.high'); },
  get unknown() { return t('exposure.unknown'); },
};

export const HONESTY_LABEL = {
  get honest() { return t('honesty.honest'); },
  get partly_misleading() { return t('honesty.partly_misleading'); },
  get misleading() { return t('honesty.misleading'); },
  get unknown() { return t('honesty.unknown'); },
  get not_assessed() { return t('honesty.not_assessed'); },
};

export const AD_TYPE_LABEL = {
  get none() { return t('adType.none'); },
  get rewarded() { return t('adType.rewarded'); },
  get interstitial() { return t('adType.interstitial'); },
  get banner() { return t('adType.banner'); },
  get native() { return t('adType.native'); },
  get forced_interstitial() { return t('adType.forced_interstitial'); },
  get unknown() { return t('adType.unknown'); },
};

export const PROMPT_LABEL = {
  get immediate() { return t('prompt.immediate'); },
  get early() { return t('prompt.early'); },
  get mid() { return t('prompt.mid'); },
  get late() { return t('prompt.late'); },
  get none() { return t('prompt.none'); },
  get unknown() { return t('prompt.unknown'); },
};

export const MAINTENANCE_META = {
  healthy: { get label() { return t('maint.healthy'); }, tone: 'ok', get desc() { return t('maint.healthy.desc'); } },
  risky_terms: { get label() { return t('maint.risky_terms'); }, tone: 'bad', get desc() { return t('maint.risky_terms.desc'); } },
  stalled_but_trusted: { get label() { return t('maint.stalled_but_trusted'); }, tone: 'warn', get desc() { return t('maint.stalled_but_trusted.desc'); } },
  abandoned: { get label() { return t('maint.abandoned'); }, tone: 'bad', get desc() { return t('maint.abandoned.desc'); } },
  unknown: { get label() { return t('maint.unknown'); }, tone: 'muted', get desc() { return t('maint.unknown.desc'); } },
};

/**
 * 제품의 수명 단계(v0.3.1) — 업데이트 성격(maintenance_quality)과 별개 필드다.
 * feature_complete(완결작)만 stale_over_12m 필터에서 면제된다.
 */
export const MAINTENANCE_STATUS_META = {
  active: { get label() { return t('life.active'); }, tone: 'ok', get desc() { return t('life.active.desc'); } },
  feature_complete: { get label() { return t('life.feature_complete'); }, tone: 'ok', get desc() { return t('life.feature_complete.desc'); } },
  stale_unknown: { get label() { return t('life.stale_unknown'); }, tone: 'warn', get desc() { return t('life.stale_unknown.desc'); } },
  abandoned: { get label() { return t('life.abandoned'); }, tone: 'bad', get desc() { return t('life.abandoned.desc'); } },
};

export const STALE_FILTER_KEY = 'stale_over_12m';

/**
 * 확률형·P2W 상품의 강제성 3단계(v0.4)
 * none=상품 없음 · optional=상품은 있지만 무과금으로 본편을 충분히 즐길 수 있음 · core=벽·진행 불가.
 * gacha_random_items·p2w 에만 적용하며, 값이 없으면 상태에서 추론한다(pass→none, fail→core).
 */
export const MONETIZATION_IMPACT_KEYS = ['gacha_random_items', 'p2w'];

export const IMPACT_META = {
  none: { get label() { return t('impact.none'); }, tone: 'ok', get mark() { return t('impact.mark.none'); } },
  optional: { get label() { return t('impact.optional'); }, tone: 'warn', get mark() { return t('impact.mark.optional'); } },
  core: { get label() { return t('impact.core'); }, tone: 'bad', get mark() { return t('impact.mark.core'); } },
};

export function hasMonetizationImpact(key) {
  return MONETIZATION_IMPACT_KEYS.includes(key);
}

/** 티어의 impact — 기록이 없으면 필터 상태에서 추론한다(보수적 기본값: fail→core). */
export function tierImpact(tier, key, status) {
  if (!hasMonetizationImpact(key)) return null;
  const recorded = tier?.hard_filters?.[key]?.impact;
  if (recorded === 'none' || recorded === 'optional' || recorded === 'core') return recorded;
  return status === 'fail' ? 'core' : 'none';
}

/** strict_monetization 토글(기본 OFF) — 켜면 impact optional 도 상품 존재만으로 거른다. */
export function strictMonetizationOf(settings) {
  return settings?.strictMonetization === true;
}

/** 이 아이템이 '완결작 면제' 대상인가 — maintenance_status === 'feature_complete'. */
export function isFeatureComplete(item) {
  return item?.maintenance_status === 'feature_complete';
}

/**
 * stale_over_12m 의 유효 필터 상태.
 * 데이터에 fail 로 적혀 있어도 완결작이면 'exempt'(거름 아님)로 계산하고,
 * 반대로 완결작이 아닌데 exempt 로 적혀 있으면 fail 로 되돌린다.
 */
export function effectiveFilterStatus(item, key, rawStatus) {
  if (key !== STALE_FILTER_KEY) return rawStatus;
  if (rawStatus === 'fail' && isFeatureComplete(item)) return 'exempt';
  if (rawStatus === 'exempt' && !isFeatureComplete(item)) return 'fail';
  return rawStatus;
}

/** 보안·OS 호환성 별도 신호(완결작 면제 시 조건부 경고로 내리는 근거). */
export function compatRiskSignal(item) {
  return item?.flags?.compat_risk?.value === 'yes';
}

export const CADENCE_LABEL = {
  get active() { return t('cadence.active'); },
  get irregular() { return t('cadence.irregular'); },
  get dormant() { return t('cadence.dormant'); },
  get unknown() { return t('cadence.unknown'); },
};

export const UPDATE_TYPE_LABEL = {
  get bugfix() { return t('updateType.bugfix'); },
  get performance() { return t('updateType.performance'); },
  get content() { return t('updateType.content'); },
  get monetization_terms() { return t('updateType.monetization_terms'); },
  get policy_terms() { return t('updateType.policy_terms'); },
  get other() { return t('updateType.other'); },
  get unknown() { return t('updateType.unknown'); },
};

export const PROMISE_LABEL = {
  get not_applicable() { return t('promise.not_applicable'); },
  get on_time() { return t('promise.on_time'); },
  get delayed() { return t('promise.delayed'); },
  get delivered_late() { return t('promise.delivered_late'); },
  get unfulfilled() { return t('promise.unfulfilled'); },
};

/** 근거 등급의 최약 성분 순위 (A=0 < B=1 < C=2 < unknown=3). */
export function gradeRank(grade) {
  if (!grade || grade === 'unknown') return 3;
  return Math.max(...String(grade).split('/').map((part) => {
    const idx = 'ABC'.indexOf(part.trim());
    return idx === -1 ? 3 : idx;
  }));
}

/** 'A/C' 처럼 복합 등급이면 카드에는 가장 약한 등급을 노출한다(기준표 0절). */
export function gradeWeakest(grade) {
  if (!grade || grade === 'unknown') return 'unknown';
  const parts = String(grade).split('/').map((p) => p.trim()).filter(Boolean);
  return parts.reduce((worst, part) => (gradeRank(part) > gradeRank(worst) ? part : worst), parts[0]);
}

export function gradeLabel(grade) {
  const weakest = gradeWeakest(grade);
  if (weakest === 'unknown') return t('grade.none');
  if (weakest === 'A') return t('grade.A');
  if (weakest === 'B') return t('grade.B');
  return t('grade.C');
}

/** ② 가중치 정규화 — 입력값 합계로 나눠 상대 비중으로 만든다. 전부 0이면 균등. */
export function normalizeWeights(raw, keys) {
  const list = keys || Object.keys(raw || {});
  const positive = (value) => {
    const num = Number(value);
    return Number.isFinite(num) && num > 0 ? num : 0;
  };
  const total = list.reduce((sum, key) => sum + positive(raw?.[key]), 0);
  if (total <= 0) {
    const even = list.length ? 1 / list.length : 0;
    return Object.fromEntries(list.map((key) => [key, even]));
  }
  return Object.fromEntries(list.map((key) => [key, positive(raw?.[key]) / total]));
}

/** 신호 임계값 — 🟢 ≥ green_min · 🟡 ≥ yellow_min · 🔴 그 아래 · ⚪ 점수 없음. */
export function signalFromScore(score, thresholds) {
  if (score === null || score === undefined || Number.isNaN(score)) return 'unknown';
  const greenMin = thresholds?.green_min ?? 75;
  const yellowMin = thresholds?.yellow_min ?? 50;
  if (score >= greenMin) return 'green';
  if (score >= yellowMin) return 'yellow';
  return 'red';
}

/** 리뷰 척도를 0~100 으로 맞춘다(5점 ×20, 10점 ×10, % 그대로). */
export function reviewToHundred(value, scale) {
  if (typeof value !== 'number' || Number.isNaN(value)) return null;
  if (scale === 'stars5') return value * 20;
  if (scale === 'out_of_10') return value * 10;
  return value;
}

/** 축 유효 점수·신호 — 티어 오버라이드가 있으면 그 값, 없으면 아이템 축 값. */
export function buildAxisState(item, tier, def, normalizedWeights, thresholds) {
  const base = item.axes?.[def.key];
  const override = tier.axis_overrides?.[def.key];
  const hasOverrideScore = override && typeof override.score === 'number';
  const score = hasOverrideScore ? override.score : (typeof base?.score === 'number' ? base.score : null);
  const signal = override?.signal || base?.signal || signalFromScore(score, thresholds);
  return {
    key: def.key,
    label: labeled('axis', def.key, def.label),
    profileScoped: Boolean(def.profile_scoped),
    weight: normalizedWeights[def.key] ?? 0,
    score,
    signal,
    source: override ? 'tier' : (base ? 'item' : 'absent'),
    signalBasis: override?.signal ? 'tier_override' : (base?.signal_basis || 'score'),
    note: override?.note ?? base?.summary ?? '',
    evidenceGrade: base?.evidence_grade ?? null,
    confidence: base?.confidence ?? null,
    summary: base?.summary ?? '',
    sourceIds: base?.source_ids ?? [],
    overrideScore: hasOverrideScore ? override.score : null,
    axisScore: typeof base?.score === 'number' ? base.score : null,
  };
}

/**
 * 티어 1건 평가 — 기준표 v0.2 8절.
 * @param {object} item 파일럿 아이템
 * @param {object} tier 티어
 * @param {object} settings { contract, weights, enabledFilters, strict }
 */
export function evaluateTier(item, tier, settings) {
  tier = tier || {};
  const contract = settings.contract || {};
  const thresholds = contract.signal_thresholds || { green_min: 75, yellow_min: 50 };
  const axisDefs = contract.axes || [];
  const axisKeys = axisDefs.map((def) => def.key);
  const normalized = normalizeWeights(settings.weights || {}, axisKeys);

  const axisStates = axisDefs.map((def) => buildAxisState(item, tier, def, normalized, thresholds));

  // ② 가중 점수: 점수가 null 인 축은 분자·분모에서 모두 제외
  let numerator = 0;
  let denominator = 0;
  const contributions = [];
  for (const axis of axisStates) {
    if (axis.score === null || axis.weight <= 0) continue;
    numerator += axis.weight * axis.score;
    denominator += axis.weight;
    contributions.push({
      key: axis.key,
      label: axis.label,
      weight: axis.weight,
      score: axis.score,
      part: axis.weight * axis.score,
    });
  }
  const score = denominator > 0 ? numerator / denominator : null;

  // ① 하드 필터 — 켜진 필터 중 fail 이 하나라도 있으면 거름. 완결작은 stale_over_12m 면제.
  //    단 확률형·P2W 의 impact 'optional' 은 strict_monetization 을 켜지 않는 한 거름이 아니라 배지다.
  const enabledFilters = settings.enabledFilters || [];
  const strict = settings.strict !== false;
  const strictMonetization = strictMonetizationOf(settings);
  const maintenanceStatus = item.maintenance_status || 'stale_unknown';
  const filterChecks = (contract.hard_filters || []).map((def) => {
    const res = tier.hard_filters?.[def.key];
    const rawStatus = res?.status || 'unknown';
    const status = effectiveFilterStatus(item, def.key, rawStatus);
    const impact = tierImpact(tier, def.key, status);
    return {
      key: def.key,
      label: labeled('filter', def.key, def.label),
      flag: def.flag,
      impactKey: hasMonetizationImpact(def.key),
      impact,
      enabled: enabledFilters.includes(def.key),
      rawStatus,
      status,
      exempt: status === 'exempt',
      grade: res?.evidence_grade || 'unknown',
      note: res?.note || t('filter.noVerdict'),
      sourceIds: res?.source_ids || [],
      weakGrade: gradeRank(res?.evidence_grade) >= 2,
    };
  });
  // impact optional 은 기본 모드에서 차단하지 않는다 — 안내 배지로만 쓴다.
  const isOptionalImpact = (check) => check.impact === 'optional' && !strictMonetization;
  const activeFails = filterChecks.filter((f) => f.enabled && f.status === 'fail');
  const blocking = activeFails.filter((f) => !isOptionalImpact(f) && (strict || !f.weakGrade));
  const weakFails = activeFails.filter((f) => !isOptionalImpact(f) && !blocking.includes(f));
  const optionalFails = activeFails.filter((f) => isOptionalImpact(f));
  const exempts = filterChecks.filter((f) => f.enabled && f.status === 'exempt');
  const compatWarning = exempts.length > 0 && compatRiskSignal(item);
  for (const check of filterChecks) {
    check.blocking = blocking.includes(check);
    check.optional = optionalFails.includes(check);
  }

  // 가중치 0인 축(프로필 전용 personal_fit 등)은 판정 개수에 세지 않는다 — 기본 화면에는 프로필이 없다(v0.5.0).
  const counted = axisStates.filter((axis) => axis.weight > 0);
  const reds = counted.filter((axis) => axis.signal === 'red');
  const yellows = counted.filter((axis) => axis.signal === 'yellow');
  // 프로필 전용 축(personal_fit)이 데이터에 없을 때는 '미확인 축'으로 세지 않는다 — 그 축은 기본 가중치 0이다.
  const unknowns = counted.filter((axis) => axis.signal === 'unknown' || axis.score === null);

  let verdict;
  let rule;
  if (blocking.length) {
    verdict = 'avoid';
    rule = 1;
  } else if (weakFails.length) {
    // strict_evidence=false 일 때: 등급 C(또는 미확인) 근거의 필터 적중은 거름이 아니라 '조건부 경고'
    verdict = 'conditional';
    rule = '1w';
  } else if (reds.length >= 2) {
    verdict = 'avoid';
    rule = 2;
  } else if (reds.length === 1) {
    verdict = 'conditional';
    rule = 3;
  } else if (yellows.length >= 2) {
    verdict = 'conditional';
    rule = 4;
  } else if (score !== null && score >= 80 && yellows.length <= 1) {
    verdict = 'recommend';
    rule = 5;
  } else {
    verdict = 'conditional';
    rule = 6;
  }

  // ⑦ 완결작 면제 + 보안·OS 호환성 별도 신호 → 추천에서 조건부 경고로 내린다
  if (verdict === 'recommend' && compatWarning) {
    verdict = 'conditional';
    rule = '1c';
  }

  return {
    tierId: tier.tier_id,
    label: tier.label,
    kind: tier.kind,
    price: tier.price,
    verdict,
    rule,
    score,
    numerator,
    denominator,
    axisStates,
    filterChecks,
    activeFails,
    blocking,
    weakFails,
    optionalFails,
    optionalMonetization: optionalFails.length > 0,
    strictMonetization,
    exempts,
    compatWarning,
    maintenanceStatus,
    featureComplete: isFeatureComplete(item),
    reds: reds.length,
    yellows: yellows.length,
    unknowns: unknowns.length,
    signals: Object.fromEntries(axisStates.map((axis) => [axis.key, axis.signal])),
    storedVerdict: tier.verdict,
    recommendedPath: Boolean(tier.recommended_path),
    strict,
  };
}

/**
 * 기본 설정(스키마의 default_enabled_filters + strict) 기준으로 대표 티어가 걸리는지.
 * verdict.hard_filter_blocked 의 정의와 같다.
 */
export function defaultBlocked(item, tier, contract) {
  const result = evaluateTier(item, tier, {
    contract,
    weights: Object.fromEntries((contract.axes || []).map((def) => [def.key, def.default_weight ?? 0])),
    enabledFilters: contract.default_enabled_filters || [],
    strict: contract.evidence_rules?.strict_evidence_default !== false,
    strictMonetization: false,
  });
  return result.blocking.length > 0;
}

/** 최소 비용 추천 경로 티어(카드 하단 고정). */
export function recommendedTier(item) {
  return (item.tiers || []).find((tier) => tier.recommended_path) || null;
}

export function tierById(item, tierId) {
  return (item.tiers || []).find((tier) => tier.tier_id === tierId) || (item.tiers || [])[0] || null;
}

/** 최근 리뷰 표본 규칙 점검 (evidence_rules.recent_sample_min). */
export function reviewSampleCheck(item, contract) {
  const min = item.review_snapshot?.min_sample ?? contract?.evidence_rules?.recent_sample_min ?? 100;
  const withRecent = (item.review_snapshot?.platforms || []).filter((row) => row.recent);
  const insufficient = withRecent
    .filter((row) => (row.recent?.count ?? 0) < min)
    .map((row) => row.platform);
  return {
    min,
    checked: withRecent.length,
    insufficient,
    needsDowngrade: insufficient.length > 0,
    applied: Boolean(item.review_snapshot?.downgrade_applied),
    sampleSufficient: Boolean(item.review_snapshot?.sample_sufficient),
  };
}

/** 플랫폼별 누적 vs 최근 괴리(0~100 환산 기준). */
export function reviewGap(platformRow) {
  const cumulative = platformRow.cumulative
    ? reviewToHundred(platformRow.cumulative.value, platformRow.cumulative.scale)
    : null;
  const recent = platformRow.recent ? reviewToHundred(platformRow.recent.value, platformRow.recent.scale) : null;
  const gap = cumulative !== null && recent !== null ? recent - cumulative : null;
  return { cumulative, recent, gap };
}

export function moneyText(money) {
  if (!money || typeof money.amount !== 'number') return null;
  const symbols = { KRW: '₩', USD: '$', EUR: '€', JPY: '¥', GBP: '£' };
  const symbol = symbols[money.currency] || `${money.currency} `;
  const amount = money.currency === 'KRW' ? nfmt(money.amount) : money.amount;
  return `${symbol}${amount}`;
}

/** 근거 등급 표기(A/B/C 중 최약). */
export function weakestGradeOf(item) {
  return gradeWeakest(item.data_quality?.overall_grade || 'unknown');
}

/* ------------------------------------------------ v0.4.0 — 4단 탐색·상세 보강 도우미 */

/** 스키마 계약의 기본 가중치(0~100 표기). */
export function defaultWeights(contract) {
  const axes = (contract?.axes || []).filter((def) => !def.profile_scoped);
  return Object.fromEntries(axes.map((def) => [def.key, Math.round((def.default_weight ?? 0) * 100)]));
}

/**
 * 평가 신선도 — assessed_at 기준 경과일과 '재검토 필요' 여부.
 * 임계값은 스키마 계약(x-pharos.client.freshness.review_after_days, 기본 180일)을 따른다.
 */
export function freshness(item, contract, now = new Date()) {
  const limit = contract?.freshness?.review_after_days ?? 180;
  const raw = item?.assessed_at;
  const assessed = raw ? new Date(`${raw}T00:00:00`) : null;
  if (!assessed || Number.isNaN(assessed.getTime())) {
    return { assessedAt: raw || null, elapsed: null, limit, stale: true, label: t('fresh.unknown') };
  }
  const base = now instanceof Date ? now : new Date(now);
  const elapsed = Math.floor((base.getTime() - assessed.getTime()) / 86400000);
  return {
    assessedAt: raw,
    elapsed,
    limit,
    stale: elapsed > limit,
    label: elapsed > limit ? t('fresh.stale') : t('fresh.current'),
  };
}

/**
 * 같은 비교군 안의 대체제 — 거름·조건부 항목 상세 하단에 붙인다.
 * 다른 비교군·도메인으로는 건너뛰지 않고, 추천 판정인 티어가 하나라도 있는 항목만 돌려준다.
 * 티어가 여러 개면(예: PC 1회 구매 + 모바일 무료) 추천 판정인 티어 중 점수가 가장 높은 것을 쓴다 —
 * 최소 비용 경로(recommended_path)가 조건부인 경우에도 그 항목을 대체제로 보여주기 위해서다.
 */
export function alternatives(item, pool, settings) {
  const arenas = new Set(item?.arenas || []);
  return (pool || [])
    .filter((other) => other.id !== item.id && (other.arenas || []).some((id) => arenas.has(id)))
    .map((other) => {
      const evaluated = (other.tiers || []).map((tier) => ({ tier, evaluation: evaluateTier(other, tier, settings) }));
      const recommended = evaluated
        .filter((row) => row.evaluation.verdict === 'recommend')
        .sort((a, b) => (b.evaluation.score ?? -1) - (a.evaluation.score ?? -1))[0];
      if (recommended) return { item: other, tier: recommended.tier, evaluation: recommended.evaluation };
      const fallbackTier = recommendedTier(other) || (other.tiers || [])[0];
      const fallbackRow = evaluated.find((row) => row.tier === fallbackTier);
      return {
        item: other,
        tier: fallbackTier,
        evaluation: fallbackRow ? fallbackRow.evaluation : evaluateTier(other, fallbackTier, settings),
      };
    })
    .filter((row) => row.evaluation.verdict === 'recommend')
    .sort((a, b) => (b.evaluation.score ?? -1) - (a.evaluation.score ?? -1));
}

/** 비교 표에 쓸 하드 필터 적중 목록(유효 상태 기준, 거름으로 잡힌 것). */
export function failedFilters(evaluation) {
  return (evaluation?.blocking || []).slice();
}

/** impact 'optional' 로 차단되지 않은 확률형·P2W 적중(안내 배지용). */
export function optionalFilters(evaluation) {
  return (evaluation?.optionalFails || []).slice();
}

/** 티어의 확률형·P2W 강도 한 줄 — 대표 배지에 쓴다. */
export function monetizationImpactOf(evaluation) {
  const fails = (evaluation?.filterChecks || []).filter(
    (check) => check.impactKey && check.enabled && check.status === 'fail',
  );
  if (fails.some((check) => check.impact === 'core')) return 'core';
  if (fails.some((check) => check.impact === 'optional')) return 'optional';
  return 'none';
}

/** 공유·복사용 한 줄 요약 텍스트. */
export function summaryText(item, tier, evaluation, options = {}) {
  const verdict = VERDICT_META[evaluation.verdict] || VERDICT_META.conditional;
  const parts = [
    `${item.name} — ${verdict.emoji} ${verdict.label}`,
    t('summary.score', { score: evaluation.score != null ? evaluation.score.toFixed(1) : '—' }),
    tier?.label ? t('summary.tier', { tier: tier.label }) : '',
    (evaluation.axisStates || [])
      .filter((axis) => !axis.profileScoped)
      .map((axis) => `${axis.label} ${axis.score ?? '—'}`)
      .join(' · '),
    (evaluation.optionalFails || []).length
      ? t('summary.optional', { list: evaluation.optionalFails.map((f) => f.label).join(', ') })
      : '',
    (evaluation.blocking || []).length
      ? t('summary.filters', { list: evaluation.blocking.map((f) => f.label).join(', ') })
      : '',
    item.assessed_at ? t('summary.assessed', { date: item.assessed_at }) : '',
    options.url ? t('summary.url', { url: options.url }) : '',
    t('summary.signature'),
  ];
  return parts.filter(Boolean).join('\n');
}
