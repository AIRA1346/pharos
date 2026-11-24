#!/usr/bin/env python3
"""Pharos v0.3.1 데이터 검증 스크립트.

1) item.schema.json 자체가 유효한 JSON Schema(Draft 2020-12)인지 검사
2) data/items.json 의 모든 아이템을 스키마로 검증 (타입/필수 필드/열거값)
3) 스키마로는 잡히지 않는 의미 규칙 검사
   (출처 참조, 티어, 플래그-필터 일치, 신호 임계값, 비교군, maintenance_status ↔ stale_over_12m)
4) 기준표 v0.3.1 산식으로 판정을 다시 계산해 저장된 판정과 대조 (완결작 면제 포함)
5) 검증기가 비어 있지 않음을 보이기 위한 음성 테스트(고의 오류를 잡는지)
6) 완결작 면제 규칙의 양성/음성 테스트 (feature_complete 는 면제, abandoned 는 거름, compat_risk 는 조건부)
7) 웹 배포 사본(web/data/items.json, web/schema/item.schema.json)이 원본과 같은지(단일 소스) 검사

사용: python3 projects/pharos/schema/validate.py
종료 코드 0 = 전부 통과, 1 = 실패.
"""

import copy
import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]  # projects/pharos
SCHEMA_PATH = ROOT / "schema" / "item.schema.json"
DATA_PATH = ROOT / "data" / "items.json"
WEB_DIR = ROOT / "web"
WEB_APP_PATH = WEB_DIR / "js" / "app.js"
WEB_DATA_PATH = WEB_DIR / "data" / "items.json"
WEB_SCHEMA_PATH = WEB_DIR / "schema" / "item.schema.json"

AXES = [("user_rating", 0.40), ("objective", 0.35), ("ai_review", 0.25)]
THRESHOLDS = {"green_min": 75, "yellow_min": 50}
DEFAULT_FILTERS = ["forced_ads", "gacha_random_items", "p2w", "stale_over_12m"]
NON_FILTER_FLAGS = {"contains_ads", "data_export", "compat_risk"}  # 표시용·보조 신호, 필터 키 없음
MAINTENANCE_STATUSES = {"active", "feature_complete", "stale_unknown", "abandoned"}

FILTER_TO_FLAG = {
    "forced_ads": "forced_ad_before_use",
    "gacha_random_items": "gacha_random_items",
    "bait_ad": "bait_ad",
    "p2w": "p2w",
    "iap_required_to_progress": "iap_required_to_progress",
    "stale_over_12m": "stale_over_12m",
    "subscription_required": "subscription_required",
    "account_required": "account_required",
    "data_collection": "data_collected",
}


def load(path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def grade_rank(g):
    """근거 등급의 최약 성분 순위 (A=0 < B=1 < C=2 < unknown=3)."""
    if not g or g == "unknown":
        return 3
    return max("ABC".index(part) for part in g.split("/"))


def collect_source_ids(node, out):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "source_ids" and isinstance(value, list):
                out.extend(value)
            else:
                collect_source_ids(value, out)
    elif isinstance(node, list):
        for value in node:
            collect_source_ids(value, out)


def effective_axis(item, tier, key):
    override = (tier.get("axis_overrides") or {}).get(key)
    if override is not None:
        return override["score"], override["signal"], "tier_override"
    axis = item["axes"].get(key)
    if axis is None:
        return None, None, "absent"
    return axis["score"], axis["signal"], "item"


def weighted_score(item, tier):
    total = 0.0
    weight = 0.0
    for key, w in AXES:
        score, _, _ = effective_axis(item, tier, key)
        if score is None:
            continue
        total += w * score
        weight += w
    return round(total / weight, 2) if weight else None


def stale_status(item, tier):
    """stale_over_12m 의 유효 상태 — 완결작 면제 규칙(기준표 v0.3.1 6.1)을 적용한다.

    데이터에 fail 로 기록돼 있어도 maintenance_status 가 feature_complete 면 exempt 로 계산하고,
    반대로 면제 기록이 있는데 상태가 feature_complete 가 아니면 fail 로 되돌린다.
    """
    status = tier["hard_filters"]["stale_over_12m"]["status"]
    if status == "fail" and item.get("maintenance_status") == "feature_complete":
        return "exempt"
    if status == "exempt" and item.get("maintenance_status") != "feature_complete":
        return "fail"
    return status


def filter_status(item, tier, key):
    """티어 필터의 유효 상태 (stale_over_12m 만 면제 규칙 적용)."""
    if key == "stale_over_12m":
        return stale_status(item, tier)
    return tier["hard_filters"][key]["status"]


def compute_verdict(item, tier, enabled=None, strict=True):
    """기준표 v0.3.1 8절 판정 규칙. 반환: (판정, 규칙 사유)."""
    enabled = DEFAULT_FILTERS if enabled is None else enabled
    fails = []
    for key in enabled:
        status = filter_status(item, tier, key)
        if status != "fail":
            continue
        if not strict and grade_rank(tier["hard_filters"][key]["evidence_grade"]) >= 2:
            continue  # 완화 모드: 등급 C 근거의 fail은 경고로 내림
        fails.append(key)
    if fails:
        return "avoid", f"hard_filter:{','.join(fails)}"

    signals = []
    for key in ("user_rating", "objective", "ai_review", "personal_fit"):
        _, sig, _ = effective_axis(item, tier, key)
        if sig:
            signals.append(sig)
    reds = signals.count("red")
    yellows = signals.count("yellow")
    score = weighted_score(item, tier)

    verdict, why = "conditional", "fallback"
    if reds >= 2:
        verdict, why = "avoid", f"red={reds}"
    elif reds == 1:
        verdict, why = "conditional", "red=1"
    elif yellows >= 2:
        verdict, why = "conditional", f"yellow={yellows}"
    elif score is not None and score >= 80 and yellows <= 1:
        verdict, why = "recommend", f"score={score}"

    # ⑦ 완결작 면제 + 보안·OS 호환성 별도 신호 → 추천에서 조건부 경고로 내린다
    exempted = [key for key in enabled if filter_status(item, tier, key) == "exempt"]
    compat = (item.get("flags") or {}).get("compat_risk", {}).get("value")
    if verdict == "recommend" and exempted and compat == "yes":
        return "conditional", f"compat_risk+exempt:{','.join(exempted)}"
    return verdict, why


def semantic_errors(item, arena_ids=None):
    errs = []
    warns = []
    arena_ids = arena_ids or set()

    # maintenance_status — 완결작/방치 구분(v0.3.1)
    mstatus = item.get("maintenance_status")
    if mstatus not in MAINTENANCE_STATUSES:
        errs.append(f"maintenance_status 값이 열거형 밖: {mstatus!r}")
    if mstatus in {"feature_complete", "abandoned"} and not (item.get("maintenance_note") or "").strip():
        warns.append(f"maintenance_status={mstatus} 인데 maintenance_note 가 없음")
    stale_flag = (item.get("flags", {}).get("stale_over_12m") or {}).get("value")
    if mstatus == "active" and stale_flag == "yes":
        errs.append("maintenance_status=active 인데 flags.stale_over_12m=yes (활발한 제품이 12개월 방치일 수 없음)")
    if mstatus == "feature_complete" and stale_flag != "yes":
        warns.append("maintenance_status=feature_complete 인데 12개월 공백 기록(flags.stale_over_12m=yes)이 없음")
    if mstatus == "abandoned" and stale_flag != "yes":
        errs.append("maintenance_status=abandoned 인데 flags.stale_over_12m 이 yes 가 아님")

    # 비교군: 정의된 id만, 중복 없음, arena_notes 키는 arenas 의 부분집합
    arenas = item.get("arenas") or []
    if not arenas:
        errs.append("arenas 가 비어 있음")
    duplicates = sorted({a for a in arenas if arenas.count(a) > 1})
    if duplicates:
        errs.append(f"arenas 중복: {duplicates}")
    unknown_arenas = sorted({a for a in arenas if a not in arena_ids})
    if unknown_arenas:
        errs.append(f"x-pharos.client.arenas 에 없는 비교군 id: {unknown_arenas}")
    notes = item.get("arena_notes") or {}
    stray_notes = sorted(k for k in notes if k not in arenas)
    if stray_notes:
        errs.append(f"arena_notes 키가 arenas 에 없음: {stray_notes}")
    missing_notes = sorted(a for a in arenas if a not in notes)
    if missing_notes:
        warns.append(f"arena_notes 없는 비교군: {missing_notes}")

    src_ids = [s["id"] for s in item["sources"]]
    if len(src_ids) != len(set(src_ids)):
        errs.append("sources[].id 중복")

    refs = []
    collect_source_ids(item, refs)
    unknown = sorted({r for r in refs if r not in src_ids})
    if unknown:
        errs.append(f"해석되지 않는 source_ids: {unknown}")
    unused = [s for s in src_ids if s not in refs]
    if unused:
        warns.append(f"본문에서 참조되지 않은 출처: {unused}")

    tier_ids = [t["tier_id"] for t in item["tiers"]]
    if len(tier_ids) != len(set(tier_ids)):
        errs.append("tiers[].tier_id 중복")
    if item["verdict"]["tier_of_record"] not in tier_ids:
        errs.append("verdict.tier_of_record 이 tiers 에 없음")

    rec = [t["tier_id"] for t in item["tiers"] if t["recommended_path"]]
    if len(rec) > 1:
        errs.append(f"recommended_path=true 가 {len(rec)}개: {rec}")
    if not rec and any(t["verdict"] != "avoid" for t in item["tiers"]):
        errs.append("추천 가능한 티어가 있는데 recommended_path 가 없음")

    # exempt 는 stale_over_12m 전용이고, feature_complete 에서만 허용한다
    for tier in item["tiers"]:
        for key, res in tier["hard_filters"].items():
            if res["status"] != "exempt":
                continue
            if key != "stale_over_12m":
                errs.append(f"{tier['tier_id']}.{key}: 'exempt' 는 stale_over_12m 에서만 허용")
            elif mstatus != "feature_complete":
                errs.append(f"{tier['tier_id']}.stale_over_12m: 'exempt' 인데 maintenance_status 가 {mstatus!r}")
            elif not res["note"].strip():
                errs.append(f"{tier['tier_id']}.stale_over_12m: 'exempt' 인데 사유(note)가 없음")

    # 축 신호 일관성 (임계값). review_override 는 사유가 적혀 있으면 허용한다.
    axis_nodes = [(k, item["axes"][k], bool(item["axes"][k].get("signal_basis") == "review_override"))
                  for k in item["axes"]]
    for tier in item["tiers"]:
        for key, override in (tier.get("axis_overrides") or {}).items():
            axis_nodes.append((f"{tier['tier_id']}.{key}", override, False))
    for name, axis, overridden in axis_nodes:
        score = axis.get("score")
        if score is None or overridden:
            if overridden and not axis.get("override_reason"):
                errs.append(f"축 {name}: review_override 인데 override_reason 이 없음")
            continue
        expected = "red" if score < THRESHOLDS["yellow_min"] else (
            "yellow" if score < THRESHOLDS["green_min"] else "green")
        if axis.get("signal") != expected:
            errs.append(f"축 {name}: 점수 {score} → 기대 신호 {expected}, 실제 {axis.get('signal')}")

    # flags ↔ 티어 하드필터 일치 (stale 은 완결작 면제를 허용)
    for fkey, fnode in item["flags"].items():
        if fkey == "data_export":
            continue
        filter_key = next((k for k, v in FILTER_TO_FLAG.items() if v == fkey), None)
        if filter_key is None:
            if fkey not in NON_FILTER_FLAGS:
                warns.append(f"필터에 매핑되지 않은 flag: {fkey}")
            continue
        value = fnode["value"]
        statuses = {t["tier_id"]: t["hard_filters"][filter_key] for t in item["tiers"]}
        effective = {t["tier_id"]: filter_status(item, t, filter_key) for t in item["tiers"]}
        if value == "no":
            bad = [tid for tid, status in effective.items() if status != "pass"]
            if bad:
                errs.append(f"flags.{fkey}=no 인데 {bad} 티어의 {filter_key} 가 pass 아님")
        elif value == "yes":
            if filter_key == "stale_over_12m" and mstatus == "feature_complete":
                # 12개월 공백은 사실이지만 완결작 면제로 거르지 않는다 → 기록도 fail 이 아니라 exempt 여야 한다
                fails = [tid for tid, status in effective.items() if status == "fail"]
                misrecorded = [tid for tid, st in statuses.items() if st["status"] != "exempt"]
                silent = [tid for tid, status in effective.items()
                          if status == "exempt" and not statuses[tid]["note"].strip()]
                if fails:
                    errs.append(f"feature_complete 인데 {fails} 티어의 stale_over_12m 이 fail")
                if misrecorded:
                    errs.append(f"feature_complete 인데 {misrecorded} 티어의 stale_over_12m 이 exempt 로 기록되지 않음")
                if silent:
                    errs.append(f"{silent} 티어의 stale_over_12m exempt 에 사유 없음")
            else:
                fails = [tid for tid, status in effective.items() if status == "fail"]
                silent_pass = [tid for tid, st in statuses.items()
                               if st["status"] == "pass" and not st["note"].strip()]
                if not fails:
                    errs.append(f"flags.{fkey}=yes 인데 fail 인 티어가 없음")
                if silent_pass:
                    errs.append(f"flags.{fkey}=yes 인데 {silent_pass} 가 사유 없이 pass")
        else:  # unknown / not_assessed
            bad = [tid for tid, status in effective.items() if status != "unknown"]
            if bad:
                errs.append(f"flags.{fkey}={value} 인데 {bad} 티어의 {filter_key} 가 unknown 아님")

    # 판정 재계산
    mismatches = []
    for tier in item["tiers"]:
        computed, why = compute_verdict(item, tier)
        if computed != tier["verdict"]:
            mismatches.append((tier["tier_id"], tier["verdict"], computed, why))
    if mismatches:
        errs.append(f"판정 불일치: {mismatches}")

    rec_tier = next((t for t in item["tiers"] if t["tier_id"] == item["verdict"]["tier_of_record"]), None)
    if rec_tier:
        computed, why = compute_verdict(item, rec_tier)
        if computed != item["verdict"]["overall"]:
            errs.append(
                f"verdict.overall({item['verdict']['overall']}) 이 대표 티어 재계산({computed}, {why})과 다름")

    # 필터 키 집합 일치 확인
    expected_keys = set(FILTER_TO_FLAG)
    for tier in item["tiers"]:
        if set(tier["hard_filters"]) != expected_keys:
            errs.append(f"{tier['tier_id']}: hard_filters 키 집합 불일치")

    return errs, warns


def negative_tests(schema, good_item):
    """고의로 망가뜨린 데이터를 스키마가 실제로 잡는지 확인."""
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    cases = []

    broken = copy.deepcopy(good_item)
    broken.pop("sources")
    cases.append(("필수 필드 sources 제거", broken))

    broken = copy.deepcopy(good_item)
    broken["verdict"]["overall"] = "maybe"
    cases.append(("verdict.overall 허용되지 않은 값", broken))

    broken = copy.deepcopy(good_item)
    broken["axes"]["user_rating"]["score"] = 120
    cases.append(("축 점수 100 초과", broken))

    broken = copy.deepcopy(good_item)
    broken["flags"]["unknown_new_flag"] = {"value": "no"}
    cases.append(("flags 에 정의되지 않은 키", broken))

    broken = copy.deepcopy(good_item)
    broken["tiers"][0]["hard_filters"].pop("gacha_random_items")
    cases.append(("티어 하드필터 키 누락", broken))

    broken = copy.deepcopy(good_item)
    broken["tiers"][0]["price"]["amount"] = "16500"
    cases.append(("가격 타입 오류(문자열)", broken))

    broken = copy.deepcopy(good_item)
    broken["arenas"] = "pkm-notes"
    cases.append(("arenas 배열 대신 문자열", broken))

    broken = copy.deepcopy(good_item)
    broken["arenas"] = []
    cases.append(("arenas 빈 배열", broken))

    broken = copy.deepcopy(good_item)
    broken["arenas"] = ["PKM Notes"]
    cases.append(("arenas id 규칙 위반(대문자·공백)", broken))

    broken = copy.deepcopy(good_item)
    broken["arena_notes"] = {"pkm-notes": ""}
    cases.append(("arena_notes 빈 문자열", broken))

    broken = copy.deepcopy(good_item)
    broken["arena_notes"] = {"./roguelike": "x"}
    cases.append(("arena_notes 키 규칙 위반", broken))

    broken = copy.deepcopy(good_item)
    broken.pop("maintenance_status")
    cases.append(("필수 필드 maintenance_status 제거", broken))

    broken = copy.deepcopy(good_item)
    broken["maintenance_status"] = "in_progress"
    cases.append(("maintenance_status 허용되지 않은 값", broken))

    broken = copy.deepcopy(good_item)
    broken["maintenance_note"] = ""
    cases.append(("maintenance_note 빈 문자열", broken))

    broken = copy.deepcopy(good_item)
    broken["tiers"][0]["hard_filters"]["stale_over_12m"]["status"] = "exempted"
    cases.append(("하드필터 status 허용되지 않은 값", broken))

    results = []
    for label, instance in cases:
        caught = not validator.is_valid(instance)
        results.append((label, caught))
    return results


def exemption_rule_tests(good_item, arena_ids):
    """완결작 면제 규칙(v0.3.1)의 양성/음성 테스트.

    반환: [(설명, 통과여부, 상세)]
    """
    results = []

    def make(**over):
        item = copy.deepcopy(good_item)  # 12개월 공백 + feature_complete 인 Inscryption
        item["maintenance_status"] = over.get("status", "feature_complete")
        item["flags"]["stale_over_12m"]["value"] = over.get("stale_flag", "yes")
        item["flags"].setdefault("compat_risk", {"value": "no", "evidence_grade": "unknown",
                                                "source_ids": [], "note": "테스트"})
        item["flags"]["compat_risk"]["value"] = over.get("compat", "no")
        for tier in item["tiers"]:
            tier["hard_filters"]["stale_over_12m"]["status"] = over.get("tier_status", "exempt")
            tier["hard_filters"]["stale_over_12m"]["note"] = over.get("note", "완결 선언.")
        return item

    # 양성: 데이터에 fail 로 남아 있어도 feature_complete 면 면제되어 추천
    raw_fail = make(tier_status="fail")
    tier = raw_fail["tiers"][0]
    verdict, why = compute_verdict(raw_fail, tier)
    results.append(("완결작 + 기록된 fail → 면제되어 추천(80.15)",
                    verdict == "recommend", f"{verdict} ({why})"))
    errs, _ = semantic_errors(make(tier_status="fail", note="사유"), arena_ids)
    results.append(("완결작 데이터는 exempt 로 기록(완결작 + fail 기록은 의미 검사도 차단)",
                    bool(errs), "; ".join(errs[:1]) or "차단되지 않음"))

    # 양성: 기록대로 exempt 인 데이터는 의미 검사 통과 + 추천
    stored = make(tier_status="exempt", note="완결 선언으로 면제.")
    errs, _ = semantic_errors(stored, arena_ids)
    v2, why2 = compute_verdict(stored, stored["tiers"][0])
    results.append(("면제 기록 데이터 의미 검사 통과 + 추천",
                    not errs and v2 == "recommend", f"errs={errs[:1]} / {v2} ({why2})"))

    # 음성: abandoned / stale_unknown 은 여전히 거름
    for status in ("abandoned", "stale_unknown"):
        item = make(status=status, tier_status="fail")
        verdict, why = compute_verdict(item, item["tiers"][0])
        results.append((f"{status} 는 stale_over_12m 으로 거름",
                        verdict == "avoid" and "stale_over_12m" in why, f"{verdict} ({why})"))

    # 양성: 보안·OS 호환성 별도 신호 → 추천 대신 조건부 경고
    compat = make(tier_status="exempt", compat="yes", note="완결 선언, OS 호환성 이슈 있음.")
    verdict, why = compute_verdict(compat, compat["tiers"][0])
    results.append(("compat_risk=yes → 조건부 경고",
                    verdict == "conditional" and why.startswith("compat_risk"), f"{verdict} ({why})"))

    # 음성: 다른 필터에 exempt 를 붙이면 의미 검사가 잡는다
    wrong_key = make(tier_status="exempt", note="완결 선언.")
    wrong_key["tiers"][0]["hard_filters"]["forced_ads"]["status"] = "exempt"
    errs, _ = semantic_errors(wrong_key, arena_ids)
    results.append(("stale 외 필터의 exempt → 의미 검사 차단", bool(errs), "; ".join(errs[:1]) or "차단되지 않음"))

    # 음성: active + 12개월 공백은 모순
    active = make(status="active", tier_status="exempt", note="x")
    errs, _ = semantic_errors(active, arena_ids)
    results.append(("active + 12개월 공백 → 의미 검사 차단", bool(errs), "; ".join(errs[:1]) or "차단되지 않음"))

    # 음성: exempt 인데 완결작이 아니면 fail 로 되돌려 거름
    not_complete = make(status="abandoned", tier_status="exempt", note="x")
    verdict, why = compute_verdict(not_complete, not_complete["tiers"][0])
    results.append(("완결작 아닌데 exempt 기록 → fail 로 계산해 거름",
                    verdict == "avoid", f"{verdict} ({why})"))

    return results


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    schema = load(SCHEMA_PATH)
    data = load(DATA_PATH)
    client = (schema.get("x-pharos") or {}).get("client") or {}
    arenas = client.get("arenas") or []
    arena_ids = {a["id"] for a in arenas}
    version = (schema.get("x-pharos") or {}).get("schema_version", "?")

    print("=" * 78)
    print(f"Pharos v{version} 검증")
    print(f"schema: {SCHEMA_PATH.relative_to(ROOT.parent.parent)}")
    print(f"data  : {DATA_PATH.relative_to(ROOT.parent.parent)}")
    print("=" * 78)

    # 0) 비교군·maintenance_status 메타 검사
    meta_errors = []
    if not arenas:
        meta_errors.append("x-pharos.client.arenas 가 비어 있음")
    for arena in arenas:
        missing = [k for k in ("id", "label", "category", "description") if not arena.get(k)]
        if missing:
            meta_errors.append(f"arena {arena.get('id', '?')}: 필수 키 누락 {missing}")
    duplicates = sorted({a["id"] for a in arenas if [x["id"] for x in arenas].count(a["id"]) > 1})
    if duplicates:
        meta_errors.append(f"비교군 id 중복: {duplicates}")
    statuses_meta = client.get("maintenance_statuses") or []
    if {s.get("key") for s in statuses_meta} != MAINTENANCE_STATUSES:
        meta_errors.append(f"maintenance_statuses 메타가 열거형과 다름: {[s.get('key') for s in statuses_meta]}")
    exemption = client.get("stale_exemption") or {}
    if exemption.get("exempt_value") != "feature_complete" or exemption.get("recorded_status") != "exempt":
        meta_errors.append("stale_exemption 메타(feature_complete → exempt)가 없음")
    if meta_errors:
        print(f"[0] 비교군·상태 메타 검사: FAIL — {'; '.join(meta_errors)}")
        return 1
    print(f"[0] 비교군·상태 메타 검사: PASS — 비교군 {len(arenas)}개 "
          f"({', '.join(a['id'] for a in arenas)}) · 상태 {len(statuses_meta)}종")

    # 1) 스키마 자체 검사
    try:
        Draft202012Validator.check_schema(schema)
        print("[1] 스키마 자체 검사: PASS (Draft 2020-12)")
    except Exception as exc:  # noqa: BLE001
        print(f"[1] 스키마 자체 검사: FAIL — {exc}")
        return 1

    if not isinstance(data, list):
        print("[!] items.json 최상위는 배열이어야 합니다.")
        return 1

    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    # 2) 아이템별 스키마 검증
    print(f"[2] 아이템 {len(data)}건 스키마 검증")
    schema_failures = 0
    for item in data:
        errors = sorted(validator.iter_errors(item), key=lambda e: list(e.path))
        if errors:
            schema_failures += 1
            print(f"  - {item.get('id', '?')}: FAIL ({len(errors)}건)")
            for err in errors:
                path = "/".join(str(p) for p in err.path) or "(root)"
                print(f"      · {path}: {err.message}")
        else:
            print(f"  - {item.get('id', '?')}: PASS (타입·필수 필드·열거값)")
    if schema_failures:
        print("  → 스키마 검증 실패")
        return 1

    # 3) 의미 규칙 + 4) 판정 재계산
    print("\n[3] 의미 규칙 및 판정 재계산")
    semantic_failures = 0
    for item in data:
        errs, warns = semantic_errors(item, arena_ids)
        status = "PASS" if not errs else "FAIL"
        print(f"  - {item['id']}: {status} (maintenance_status={item['maintenance_status']})")
        for w in warns:
            print(f"      ! 경고: {w}")
        for e in errs:
            print(f"      × {e}")
        semantic_failures += 1 if errs else 0
        for tier in item["tiers"]:
            score = weighted_score(item, tier)
            computed, why = compute_verdict(item, tier)
            stale = filter_status(item, tier, "stale_over_12m")
            print(f"      · {tier['tier_id']:<14} score={str(score):<6} "
                  f"판정={tier['verdict']:<11} 재계산={computed:<11} "
                  f"stale={stale:<7} ({why})")
    if semantic_failures:
        print("  → 의미 규칙 위반 있음")
        return 1

    # 3-1) 비교군 묶음 점검 — 모든 비교군에 최소 1건, 비어 있는 비교군 없음
    print("\n[3-1] 비교군 구성")
    coverage = {a["id"]: [item["id"] for item in data if a["id"] in item["arenas"]] for a in arenas}
    empty = [aid for aid, members in coverage.items() if not members]
    for arena in arenas:
        members = coverage[arena["id"]]
        print(f"  - {arena['id']:<24} {arena['label']:<12} {len(members)}건: {', '.join(members)}")
    if empty:
        print(f"  → 비어 있는 비교군: {empty}")
        return 1

    # 3-2) 정적 배포 사본(web/) 단독 동작 — 경로·단일 소스 검사
    print("\n[3-2] 정적 배포 준비(web/ 단독 폴더)")
    app_source = WEB_APP_PATH.read_text(encoding="utf-8")
    path_errors = []
    for label, needle in (
        ("DATA_URL", "const DATA_URL = './data/items.json';"),
        ("SCHEMA_URL", "const SCHEMA_URL = './schema/item.schema.json';"),
    ):
        if needle in app_source:
            print(f"  - web/js/app.js {label} = 웹 폴더 기준 상대경로")
        else:
            path_errors.append(f"web/js/app.js 의 {label} 이 웹 폴더 기준('./…')이 아님")
    if "../data/" in app_source or "../schema/" in app_source:
        path_errors.append("web/js/app.js 에 웹 폴더 밖을 가리키는 ../data/ 또는 ../schema/ 참조가 남아 있음")
    for label, web_path, src_path in (
        ("데이터", WEB_DATA_PATH, DATA_PATH),
        ("스키마", WEB_SCHEMA_PATH, SCHEMA_PATH),
    ):
        if not web_path.exists():
            path_errors.append(f"배포 사본 없음: {web_path.relative_to(ROOT.parent.parent)} "
                               "(python3 projects/pharos/scripts/sync_web_data.py 실행)")
            continue
        same = sha256(web_path) == sha256(src_path)
        print(f"  - {label} 사본 {web_path.relative_to(ROOT.parent.parent)} "
              f"{'= 원본과 동일' if same else '≠ 원본과 다름'}")
        if not same:
            path_errors.append(f"{web_path.relative_to(ROOT.parent.parent)} 가 원본과 다름 "
                               "(python3 projects/pharos/scripts/sync_web_data.py 실행)")
    if path_errors:
        for err in path_errors:
            print(f"  × {err}")
        return 1
    print("  → web/ 폴더만으로 데이터·스키마·계산 계약이 모두 해결됨(단일 소스 동기화 확인)")

    # 4) 음성 테스트
    print("\n[4] 음성 테스트 (일부러 깨뜨린 데이터를 스키마가 잡는지)")
    neg = negative_tests(schema, data[0])
    for label, caught in neg:
        print(f"  - {label}: {'차단됨 PASS' if caught else '통과됨 FAIL'}")
    if not all(caught for _, caught in neg):
        return 1

    # 5) 완결작 면제 규칙 양성/음성 테스트
    print("\n[5] 완결작 면제 규칙 테스트 (maintenance_status ↔ stale_over_12m)")
    inscryption = next((item for item in data if item.get("maintenance_status") == "feature_complete"), None)
    if inscryption is None:
        print("  → feature_complete 아이템이 없어 규칙을 확인할 수 없음")
        return 1
    rules = exemption_rule_tests(inscryption, arena_ids)
    for label, ok, detail in rules:
        print(f"  - {label}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" ← {detail}"))
    if not all(ok for _, ok, _ in rules):
        return 1

    print("\n" + "=" * 78)
    print(f"결과: PASS — 아이템 {len(data)}건 스키마 100% 충족, 의미 규칙 위반 0, "
          f"비교군 {len(arenas)}개 구성 정상, 판정 재계산 일치, "
          f"음성 테스트 {sum(1 for _, c in neg if c)}/{len(neg)} 차단, "
          f"완결작 면제 테스트 {sum(1 for _, ok, _ in rules if ok)}/{len(rules)} 통과, "
          f"web/ 단독 배포 경로·사본 일치")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
