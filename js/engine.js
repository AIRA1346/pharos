/**
 * Pharos 계산 엔진
 * schema/item.schema.json 의 x-pharos.client 계약을 그대로 JavaScript로 옮긴 순수 함수 모음.
 * DOM 을 모르고, 점수·판정을 하드코딩하지 않는다. 모든 값은 아이템 JSON + 사용자 설정에서 계산한다.
 */

export const SIGNAL_META = {
  green: { emoji: '🟢', label: '좋음', short: 'G' },
  yellow: { emoji: '🟡', label: '주의', short: 'Y' },
  red: { emoji: '🔴', label: '나쁨', short: 'R' },
  unknown: { emoji: '⚪', label: '미확인', short: '?' },
};

export const VERDICT_META = {
  recommend: { emoji: '🟢', label: '추천', tone: 'ok' },
  conditional: { emoji: '🟡', label: '조건부', tone: 'warn' },
  avoid: { emoji: '🔴', label: '거름', tone: 'bad' },
};

export const TRI_LABEL = {
  yes: '예',
  no: '아니오',
  unknown: '미확인',
  not_assessed: '미평가',
};

export const KIND_LABEL = {
  free: '완전 무료',
  freemium: '무료 시작(한도·광고·IAP)',
  demo: '체험판',
  one_time: '1회 구매',
  subscription: '구독',
  license: '라이선스',
  consumable: '소모성 결제',
};

export const CATEGORY_LABEL = { game: '게임', app: '앱', service: '서비스', tool: '도구' };

export const PLATFORM_LABEL = {
  steam: 'Steam',
  android: 'Android',
  ios: 'iOS',
  windows: 'Windows',
  macos: 'macOS',
  linux: 'Linux',
  web: '웹',
  console: '콘솔',
  other: '기타',
};

export const EXPOSURE_LABEL = {
  none: '없음',
  low: '낮음',
  medium: '보통',
  high: '높음',
  unknown: '미확인',
};

export const HONESTY_LABEL = {
  honest: '정직함',
  partly_misleading: '부분 과장',
  misleading: '오해 유발',
  unknown: '미확인',
  not_assessed: '미평가',
};

export const AD_TYPE_LABEL = {
  none: '광고 없음',
  rewarded: '보상형',
  interstitial: '전면',
  banner: '배너',
  native: '네이티브',
  forced_interstitial: '강제 전면',
  unknown: '미확인',
};

export const PROMPT_LABEL = {
  immediate: '즉시',
  early: '초반',
  mid: '중반',
  late: '후반',
  none: '없음',
  unknown: '미확인',
};

export const MAINTENANCE_META = {
  healthy: { label: '건강함', tone: 'ok', desc: '최근 6개월 내 업데이트 + 과금·약관 변경 없음' },
  risky_terms: { label: '위험한 변경', tone: 'bad', desc: '활발하나 과금·약관 변경이 평가 급락과 겹침' },
  stalled_but_trusted: { label: '지연됐지만 신뢰', tone: 'warn', desc: '과금 압박이 없는 지연, 신뢰 유지' },
  abandoned: { label: '방치', tone: 'bad', desc: '12개월 이상 업데이트 없음 + 공약 미이행' },
  unknown: { label: '미확인', tone: 'muted', desc: '근거 부족' },
};

/**
 * 제품의 수명 단계(v0.3.1) — 업데이트 성격(maintenance_quality)과 별개 필드다.
 * feature_complete(완결작)만 stale_over_12m 필터에서 면제된다.
 */
export const MAINTENANCE_STATUS_META = {
  active: { label: '개발 중', tone: 'ok', desc: '업데이트·운영이 이어지고 있다' },
  feature_complete: { label: '완결작', tone: 'ok', desc: '개발사가 완결을 선언 — 업데이트 공백이 방치와 다르다' },
  stale_unknown: { label: '상태 미확인', tone: 'warn', desc: '오래 멈췄고 완결인지 방치인지 확인하지 못했다' },
  abandoned: { label: '방치', tone: 'bad', desc: '12개월 이상 중단 + 공약 미이행' },
};

export const STALE_FILTER_KEY = 'stale_over_12m';

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
  active: '활발',
  irregular: '불규칙',
  dormant: '휴면',
  unknown: '미확인',
};

export const UPDATE_TYPE_LABEL = {
  bugfix: '버그 수정',
  performance: '성능·호환',
  content: '콘텐츠·기능',
  monetization_terms: '과금·가격 변경',
  policy_terms: '약관·정책 변경',
  other: '기타',
  unknown: '성격 미확인',
};

export const PROMISE_LABEL = {
  not_applicable: '해당 없음',
  on_time: '약속대로',
  delayed: '지연',
  delivered_late: '늦게라도 이행',
  unfulfilled: '미이행',
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
  if (weakest === 'unknown') return '근거 없음';
  if (weakest === 'A') return 'A · 1차 확인';
  if (weakest === 'B') return 'B · 보도·인용';
  return 'C · 3자·커뮤니티';
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
    label: def.label,
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
  const enabledFilters = settings.enabledFilters || [];
  const strict = settings.strict !== false;
  const maintenanceStatus = item.maintenance_status || 'stale_unknown';
  const filterChecks = (contract.hard_filters || []).map((def) => {
    const res = tier.hard_filters?.[def.key];
    const rawStatus = res?.status || 'unknown';
    const status = effectiveFilterStatus(item, def.key, rawStatus);
    return {
      key: def.key,
      label: def.label,
      flag: def.flag,
      enabled: enabledFilters.includes(def.key),
      rawStatus,
      status,
      exempt: status === 'exempt',
      grade: res?.evidence_grade || 'unknown',
      note: res?.note || '이 티어에는 판정이 없습니다.',
      sourceIds: res?.source_ids || [],
      weakGrade: gradeRank(res?.evidence_grade) >= 2,
    };
  });
  const activeFails = filterChecks.filter((f) => f.enabled && f.status === 'fail');
  const blocking = activeFails.filter((f) => strict || !f.weakGrade);
  const weakFails = activeFails.filter((f) => !blocking.includes(f));
  const exempts = filterChecks.filter((f) => f.enabled && f.status === 'exempt');
  const compatWarning = exempts.length > 0 && compatRiskSignal(item);

  const reds = axisStates.filter((axis) => axis.signal === 'red');
  const yellows = axisStates.filter((axis) => axis.signal === 'yellow');
  const unknowns = axisStates.filter((axis) => axis.signal === 'unknown' || axis.score === null);

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
  const amount = money.currency === 'KRW' ? money.amount.toLocaleString('ko-KR') : money.amount;
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
    return { assessedAt: raw || null, elapsed: null, limit, stale: true, label: '평가일 미확인' };
  }
  const base = now instanceof Date ? now : new Date(now);
  const elapsed = Math.floor((base.getTime() - assessed.getTime()) / 86400000);
  return {
    assessedAt: raw,
    elapsed,
    limit,
    stale: elapsed > limit,
    label: elapsed > limit ? contract?.freshness?.stale_label || '재검토 필요' : contract?.freshness?.fresh_label || '최신',
  };
}

/**
 * 같은 비교군 안의 대체제 — 거름·조건부 항목 상세 하단에 붙인다.
 * 다른 비교군·도메인으로는 건너뛰지 않고, 추천 판정인 항목만 점수 순으로 돌려준다.
 */
export function alternatives(item, pool, settings) {
  const arenas = new Set(item?.arenas || []);
  return (pool || [])
    .filter((other) => other.id !== item.id && (other.arenas || []).some((id) => arenas.has(id)))
    .map((other) => {
      const tier = recommendedTier(other) || (other.tiers || [])[0];
      return { item: other, tier, evaluation: evaluateTier(other, tier, settings) };
    })
    .filter((row) => row.evaluation.verdict === 'recommend')
    .sort((a, b) => (b.evaluation.score ?? -1) - (a.evaluation.score ?? -1));
}

/** 비교 표에 쓸 하드 필터 적중 목록(유효 상태 기준). */
export function failedFilters(evaluation) {
  return (evaluation?.filterChecks || []).filter((check) => check.status === 'fail');
}

/** 공유·복사용 한 줄 요약 텍스트. */
export function summaryText(item, tier, evaluation, options = {}) {
  const verdict = VERDICT_META[evaluation.verdict] || VERDICT_META.conditional;
  const parts = [
    `${item.name} — ${verdict.emoji} ${verdict.label}`,
    `가중 점수 ${evaluation.score != null ? evaluation.score.toFixed(1) : '—'}`,
    tier?.label ? `대표 티어 ${tier.label}` : '',
    (evaluation.axisStates || [])
      .filter((axis) => !axis.profileScoped)
      .map((axis) => `${axis.label} ${axis.score ?? '—'}`)
      .join(' · '),
    (evaluation.blocking || []).length
      ? `걸린 필터: ${evaluation.blocking.map((f) => f.label).join(', ')}`
      : '',
    item.assessed_at ? `평가일 ${item.assessed_at}` : '',
    options.url ? `기준·근거 ${options.url}` : '',
    '— 파로스 Pharos',
  ];
  return parts.filter(Boolean).join('\n');
}
