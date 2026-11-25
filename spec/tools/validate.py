#!/usr/bin/env python3
"""Pharos v0.4.0 데이터 검증 스크립트.

검사 항목
  1) 스키마(item.schema.json) 자체가 유효한 JSON Schema(Draft 2020-12)인지
  2) 카탈로그(data/catalog.json) — 도메인 → 대분류 → 비교군 계층, data_file 존재·중복 없음
  3) 비교군별 분할 데이터(data/{domain}/{arena}.json) — 스키마 검증 + 의미 규칙 + 판정 재계산
     · 아이템의 domain·category 가 소속 비교군과 일치하는지, 파일과 비교군이 맞는지
     · 출처 참조, 티어, 플래그-필터 일치, 신호 임계값, arena_notes, maintenance_status ↔ stale_over_12m
  4) 경량 인덱스(data/search-index.json)가 분할 데이터에서 자동 생성한 결과와 같은지(신선도)
  5) 음성 테스트(고의 오류를 잡는지) — 스키마·카탈로그·인덱스
  6) 완결작 면제 규칙(feature_complete ↔ stale_over_12m) 양성/음성 테스트
  7) 웹 배포 사본(web/)이 원본과 바이트 단위로 같은지(단일 소스), 웹 JS 가 웹 폴더 밖을 참조하지 않는지

사용:
  python3 projects/pharos/schema/validate.py
  (웹 사본이 낡았다면 python3 projects/pharos/scripts/sync_web_data.py 먼저 실행)
종료 코드 0 = 전부 통과, 1 = 실패.
"""

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]  # projects/pharos
SCHEMA_PATH = ROOT / "schema" / "item.schema.json"
CATALOG_PATH = ROOT / "data" / "catalog.json"
INDEX_PATH = ROOT / "data" / "search-index.json"
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
WEB_DATA_DIR = WEB_DIR / "data"
WEB_SCHEMA_PATH = WEB_DIR / "schema" / "item.schema.json"
WEB_JS_DIR = WEB_DIR / "js"

AXES = [("user_rating", 0.50), ("objective", 0.25), ("ai_review", 0.25)]
THRESHOLDS = {"green_min": 75, "yellow_min": 50}
DEFAULT_FILTERS = ["forced_ads", "gacha_random_items", "p2w", "stale_over_12m"]
MONETIZATION_IMPACT_KEYS = {"gacha_random_items", "p2w"}
IMPACT_VALUES = {"none", "optional", "core"}
NON_FILTER_FLAGS = {"contains_ads", "data_export", "compat_risk"}
MAINTENANCE_STATUSES = {"active", "feature_complete", "stale_unknown", "abandoned"}
# 갭 리포트의 '스토어 별점'은 실제 스토어 표본만 쓴다. G2·Trustpilot 같은 3자 집계(platform: web·other)는
# 별점이 아니라 평점 집계이므로 '별점은 높은데 거름' 비교에 섞지 않는다(v0.4.2).
STORE_PLATFORMS = {"android", "ios", "steam"}
ID_PATTERN = "^[a-z0-9][a-z0-9_-]*$"

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
    """stale_over_12m 의 유효 상태 — 완결작 면제 규칙(기준표 v0.3.1 6.1)을 적용한다."""
    status = tier["hard_filters"]["stale_over_12m"]["status"]
    if status == "fail" and item.get("maintenance_status") == "feature_complete":
        return "exempt"
    if status == "exempt" and item.get("maintenance_status") != "feature_complete":
        return "fail"
    return status


def filter_status(item, tier, key):
    if key == "stale_over_12m":
        return stale_status(item, tier)
    return tier["hard_filters"][key]["status"]


def tier_impact(tier, key, status):
    """확률형·P2W 의 강도(v0.4) — 기록이 없으면 상태에서 추론한다(fail→core, 그 외 none)."""
    if key not in MONETIZATION_IMPACT_KEYS:
        return None
    recorded = (tier["hard_filters"].get(key) or {}).get("impact")
    if recorded in IMPACT_VALUES:
        return recorded
    return "core" if status == "fail" else "none"


def blocking_fails(item, tier, enabled, strict=True, strict_monetization=False):
    """거름으로 잡히는 필터 목록. impact optional 은 strict_monetization 을 켰을 때만 거른다."""
    out = []
    for key in enabled:
        status = filter_status(item, tier, key)
        if status != "fail":
            continue
        impact = tier_impact(tier, key, status)
        if impact == "optional" and not strict_monetization:
            continue
        if not strict and grade_rank(tier["hard_filters"][key]["evidence_grade"]) >= 2:
            continue
        out.append(key)
    return out


def compute_verdict(item, tier, enabled=None, strict=True, strict_monetization=False):
    """기준표 8절 판정 규칙. 반환: (판정, 규칙 사유)."""
    enabled = DEFAULT_FILTERS if enabled is None else enabled
    fails = blocking_fails(item, tier, enabled, strict, strict_monetization)
    if fails:
        return "avoid", f"hard_filter:{','.join(fails)}"

    signals = []
    for key in ("user_rating", "objective", "ai_review", "personal_fit"):
        weight = dict(AXES).get(key, 0.0)
        if weight <= 0:
            # 가중치 0인 축(프로필 전용 personal_fit 등)은 판정 개수에 세지 않는다(v0.5.0).
            continue
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

    exempted = [key for key in enabled if filter_status(item, tier, key) == "exempt"]
    compat = (item.get("flags") or {}).get("compat_risk", {}).get("value")
    if verdict == "recommend" and exempted and compat == "yes":
        return "conditional", f"compat_risk+exempt:{','.join(exempted)}"
    return verdict, why


# --------------------------------------------------------------------------- 카탈로그

def catalog_errors(catalog, data_dir):
    """도메인 → 대분류 → 비교군 계층과 데이터 파일 정의 검사."""
    errs = []
    if not isinstance(catalog, dict):
        return ["catalog.json 최상위는 객체여야 함"]
    domains = catalog.get("domains") or []
    categories = catalog.get("categories") or []
    arenas = catalog.get("arenas") or []
    if not domains:
        errs.append("domains 가 비어 있음")
    if not categories:
        errs.append("categories 가 비어 있음")
    if not arenas:
        errs.append("arenas 가 비어 있음")

    domain_ids = [d.get("id") for d in domains]
    if len(domain_ids) != len(set(domain_ids)):
        errs.append(f"domains id 중복: {domain_ids}")
    for dom in domains:
        for key in ("id", "label", "description", "filter_pack"):
            if not dom.get(key):
                errs.append(f"domain {dom.get('id', '?')}: 필수 키 누락 {key}")
        if dom.get("id") and not re.match(ID_PATTERN, dom["id"]):
            errs.append(f"domain id 규칙 위반: {dom['id']!r}")
    planned = [d.get("id") for d in catalog.get("planned_domains") or []]
    if set(planned) & set(domain_ids):
        errs.append(f"planned_domains 가 domains 와 겹침: {sorted(set(planned) & set(domain_ids))}")

    packs = catalog.get("filter_packs") or {}
    filter_keys = set(FILTER_TO_FLAG)
    for key, pack in packs.items():
        bad = sorted(set(pack.get("filters") or []) - filter_keys)
        if bad:
            errs.append(f"filter_pack {key}: 스키마에 없는 필터 {bad}")
        if not pack.get("filters"):
            errs.append(f"filter_pack {key}: filters 가 비어 있음")
    for dom in domains:
        if dom.get("filter_pack") and dom["filter_pack"] not in packs:
            errs.append(f"domain {dom.get('id')}: 정의되지 않은 filter_pack {dom['filter_pack']!r}")

    # 도메인별 필터 표시 이름(v0.4.2) — 같은 9개 필터를 도메인 문법으로 다시 부르는 표시용 이름이다.
    for dom in domains:
        labels = dom.get("filter_labels") or {}
        unknown = sorted(set(labels) - filter_keys)
        if unknown:
            errs.append(f"domain {dom.get('id')}: filter_labels 에 없는 필터 {unknown}")
        empty = sorted(key for key, value in labels.items() if not str(value).strip())
        if empty:
            errs.append(f"domain {dom.get('id')}: filter_labels 빈 이름 {empty}")

    category_ids = [c.get("id") for c in categories]
    if len(category_ids) != len(set(category_ids)):
        errs.append(f"categories id 중복: {category_ids}")
    for cat in categories:
        for key in ("id", "domain", "label"):
            if not cat.get(key):
                errs.append(f"category {cat.get('id', '?')}: 필수 키 누락 {key}")
        if cat.get("domain") and cat["domain"] not in domain_ids:
            errs.append(f"category {cat.get('id')}: 정의되지 않은 도메인 {cat['domain']!r}")
        if cat.get("id") and not re.match(ID_PATTERN, cat["id"]):
            errs.append(f"category id 규칙 위반: {cat['id']!r}")
    for dom in domains:
        if not any(c.get("domain") == dom.get("id") for c in categories):
            errs.append(f"도메인 {dom.get('id')} 에 대분류가 하나도 없음")

    arena_ids = [a.get("id") for a in arenas]
    if len(arena_ids) != len(set(arena_ids)):
        errs.append(f"arenas id 중복: {arena_ids}")
    data_files = []
    for arena in arenas:
        for key in ("id", "domain", "category", "label", "description", "data_file"):
            if not arena.get(key):
                errs.append(f"arena {arena.get('id', '?')}: 필수 키 누락 {key}")
        if arena.get("id") and not re.match(ID_PATTERN, arena["id"]):
            errs.append(f"arena id 규칙 위반: {arena['id']!r}")
        if arena.get("domain") and arena["domain"] not in domain_ids:
            errs.append(f"arena {arena.get('id')}: 정의되지 않은 도메인 {arena['domain']!r}")
        cat = next((c for c in categories if c.get("id") == arena.get("category")), None)
        if cat is None:
            errs.append(f"arena {arena.get('id')}: 정의되지 않은 대분류 {arena.get('category')!r}")
        elif arena.get("domain") and cat.get("domain") != arena["domain"]:
            errs.append(f"arena {arena.get('id')}: 도메인 {arena['domain']!r} 와 대분류 {cat['id']!r} 의 도메인 {cat.get('domain')!r} 불일치")
        file_name = arena.get("data_file") or ""
        data_files.append(file_name)
        if file_name:
            path = data_dir / file_name
            if not path.exists():
                errs.append(f"arena {arena.get('id')}: data_file 없음 {file_name}")
            if path.suffix != ".json":
                errs.append(f"arena {arena.get('id')}: data_file 확장자가 .json 아님 ({file_name})")
    duplicates = sorted({f for f in data_files if f and data_files.count(f) > 1})
    if duplicates:
        errs.append(f"data_file 중복: {duplicates}")
    for cat in categories:
        if not any(a.get("category") == cat.get("id") for a in arenas):
            errs.append(f"대분류 {cat.get('id')} 에 비교군이 하나도 없음")

    # 파일 목록에 남은 고아 데이터(카탈로그에 없는 json)
    declared = {(data_dir / f).resolve() for f in data_files if f}
    for path in sorted(data_dir.rglob("*.json")):
        if path.name in {"catalog.json", "search-index.json"}:
            continue
        if path.resolve() not in declared:
            errs.append(f"카탈로그에 없는 데이터 파일: {path.relative_to(ROOT)}")
    return errs


def load_items_by_arena(catalog, data_dir):
    """비교군별 분할 데이터 로드 — {arena_id: (path, items)}."""
    out = {}
    for arena in catalog.get("arenas") or []:
        name = arena.get("data_file")
        if not name:
            continue
        path = data_dir / name
        if not path.exists():
            continue
        items = load(path)
        out[arena["id"]] = (path, items if isinstance(items, list) else [])
    return out


def semantic_errors(item, ctx, arena_id=None):
    """아이템 1건의 의미 규칙. ctx: {arenas, domains, categories}."""
    errs = []
    warns = []
    arenas = ctx["arenas"]
    arena_ids = set(arenas)

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

    # 도메인·대분류 ↔ 비교군 일치
    item_arenas = item.get("arenas") or []
    if not item_arenas:
        errs.append("arenas 가 비어 있음")
    duplicates = sorted({a for a in item_arenas if item_arenas.count(a) > 1})
    if duplicates:
        errs.append(f"arenas 중복: {duplicates}")
    unknown_arenas = sorted({a for a in item_arenas if a not in arena_ids})
    if unknown_arenas:
        errs.append(f"catalog.json 에 없는 비교군 id: {unknown_arenas}")
    if arena_id and item_arenas and arena_id not in item_arenas:
        errs.append(f"이 아이템은 {arena_id} 파일에 있지만 arenas 에 {arena_id} 가 없음")
    pairs = {(arenas[a]["domain"], arenas[a]["category"]) for a in item_arenas if a in arenas}
    if len(pairs) > 1:
        errs.append(f"한 아이템의 비교군들이 서로 다른 도메인·대분류에 속함: {sorted(pairs)}")
    elif pairs:
        want_domain, want_category = pairs.pop()
        if item.get("domain") != want_domain:
            errs.append(f"domain={item.get('domain')!r} 이 소속 비교군의 도메인 {want_domain!r} 과 다름")
        if item.get("category") != want_category:
            errs.append(f"category={item.get('category')!r} 이 소속 비교군의 대분류 {want_category!r} 과 다름")
    if item.get("domain") not in ctx["domains"]:
        errs.append(f"domain={item.get('domain')!r} 이 catalog.json domains 에 없음")
    if item.get("category") not in ctx["categories"]:
        errs.append(f"category={item.get('category')!r} 이 catalog.json categories 에 없음")

    notes = item.get("arena_notes") or {}
    stray_notes = sorted(k for k in notes if k not in item_arenas)
    if stray_notes:
        errs.append(f"arena_notes 키가 arenas 에 없음: {stray_notes}")
    missing_notes = sorted(a for a in item_arenas if a not in notes)
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

    # 확률형·P2W 강도 3단계(v0.4) — impact ↔ status ↔ free_play 일관성
    free_play = (item.get("monetization") or {}).get("free_play") or {}
    for tier in item["tiers"]:
        for key, res in tier["hard_filters"].items():
            impact = res.get("impact")
            if impact is None:
                continue
            if key not in MONETIZATION_IMPACT_KEYS:
                errs.append(f"{tier['tier_id']}.{key}: impact 는 gacha_random_items·p2w 에만 쓸 수 있음")
                continue
            if impact not in IMPACT_VALUES:
                errs.append(f"{tier['tier_id']}.{key}: impact 값이 열거형 밖: {impact!r}")
                continue
            status = filter_status(item, tier, key)
            if impact == "none" and status != "pass":
                errs.append(f"{tier['tier_id']}.{key}: impact 'none' 인데 status 가 {status!r}")
            if impact in {"optional", "core"} and status != "fail":
                errs.append(f"{tier['tier_id']}.{key}: impact {impact!r} 인데 status 가 fail 이 아님({status!r})")
            if impact == "optional" and free_play.get("value") != "sufficient":
                errs.append(
                    f"{tier['tier_id']}.{key}: impact 'optional' 인데 monetization.free_play.value 가 "
                    f"'sufficient' 가 아님({free_play.get('value')!r}) — 무과금 충분성 근거 필요")
            if impact == "core" and free_play.get("value") == "sufficient":
                errs.append(f"{tier['tier_id']}.{key}: impact 'core' 인데 free_play 가 'sufficient' 로 모순")
    if free_play:
        value = free_play.get("value")
        if value not in {"sufficient", "constrained", "blocked", "unknown"}:
            errs.append(f"monetization.free_play.value 가 열거형 밖: {value!r}")
        if not (free_play.get("note") or "").strip():
            errs.append("monetization.free_play.note 가 비어 있음")
        cores = [t["tier_id"] for t in item["tiers"]
                 if any(tier_impact(t, k, filter_status(item, t, k)) == "core" for k in MONETIZATION_IMPACT_KEYS)]
        if value in {"constrained", "blocked"} and not cores:
            warns.append("free_play 가 제한/불가인데 impact 'core' 로 기록된 확률형·P2W 가 없음")

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

    # 표본 규모 검증(v0.5.0) — 얇은 3자 최근 표본이 큰 스토어 누적을 덮은 경우 산정 메모를 요구한다.
    notes = item.get("score_notes") or {}
    risky_terms = (item.get("update_profile") or {}).get("maintenance_quality") == "risky_terms"
    needs_scale_note = False
    if not risky_terms:
        for row in item.get("review_snapshot", {}).get("platforms") or []:
            recent = row.get("recent") or {}
            cumulative = row.get("cumulative") or {}
            count = recent.get("count")
            base = cumulative.get("count")
            if (
                recent
                and recent.get("evidence_grade") == "C"
                and isinstance(count, int) and count < 1000
                and cumulative.get("evidence_grade") in ("A", "B")
                and isinstance(base, int) and base >= max(100000, count * 100)
                and isinstance(cumulative.get("value"), (int, float))
                and cumulative.get("scale") == "stars5" and cumulative["value"] >= 4.4
            ):
                needs_scale_note = True
    if needs_scale_note and not (notes.get("user_rating") or "").strip():
        errs.append("표본 규모 검증 대상인데 score_notes.user_rating 산정 메모가 없음")

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

    expected_keys = set(FILTER_TO_FLAG)
    for tier in item["tiers"]:
        if set(tier["hard_filters"]) != expected_keys:
            errs.append(f"{tier['tier_id']}: hard_filters 키 집합 불일치")

    return errs, warns


# ------------------------------------------------------------------ 인덱스 생성/검증

def build_search_index(catalog, items_by_arena, contract):
    """분할 데이터 → 통합 검색·홈 리포트용 경량 인덱스(결정적, 타임스탬프 없음)."""
    arenas = {a["id"]: a for a in catalog.get("arenas") or []}
    domains = {d["id"]: d for d in catalog.get("domains") or []}
    categories = {c["id"]: c for c in catalog.get("categories") or []}
    filters = {f["key"]: f["label"] for f in contract.get("hard_filters") or []}
    axis_labels = {a["key"]: a["label"] for a in contract.get("axes") or []}
    signal_mark = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⚪"}
    gap_rule = (catalog.get("home") or {}).get("gap_report") or {}
    min_stars = gap_rule.get("min_store_stars", 4.0)
    min_delta = gap_rule.get("min_delta", 12.0)
    gap_verdicts = set(gap_rule.get("verdicts") or ["avoid", "conditional"])
    records = []
    for arena_id, (_path, items) in items_by_arena.items():
        for item in items:
            tier = next((t for t in item["tiers"] if t["tier_id"] == item["verdict"]["tier_of_record"]),
                        item["tiers"][0])
            score = weighted_score(item, tier)
            verdict = compute_verdict(item, tier)[0]
            stars = None
            for row in item.get("review_snapshot", {}).get("platforms") or []:
                if row.get("platform") not in STORE_PLATFORMS:
                    continue
                metric = row.get("cumulative") or {}
                if metric.get("scale") != "stars5":
                    continue
                candidate = {
                    "value": metric.get("value"),
                    "count": metric.get("count") or 0,
                    "platform": row.get("platform"),
                    "evidence_grade": metric.get("evidence_grade"),
                }
                if stars is None or (candidate["count"] or 0) > (stars["count"] or 0):
                    stars = candidate
            drivers = []
            for key in (contract.get("default_enabled_filters") or DEFAULT_FILTERS):
                if filter_status(item, tier, key) == "fail":
                    drivers.append({"label": filters.get(key, key), "tone": "bad"})
            if not drivers:
                for key in ("user_rating", "objective", "ai_review"):
                    axis_score, sig, _ = effective_axis(item, tier, key)
                    if sig in ("red", "yellow"):
                        drivers.append({
                            "label": f"{axis_labels.get(key, key)} {signal_mark.get(sig, '')} {axis_score if axis_score is not None else '—'}".strip(),
                            "tone": "bad" if sig == "red" else "warn",
                        })
            record = {
                "id": item["id"],
                "name": item["name"],
                "icon": item.get("icon"),
                "aliases": item.get("aliases") or [],
                "domain": item["domain"],
                "category": item["category"],
                "arenas": item["arenas"],
                "developer": item.get("developer") or "",
                "genres": item.get("genres") or [],
                "platforms": item.get("platforms") or [],
                "one_liner": item.get("one_liner") or "",
                # 홈·도메인의 장르별 추천 타일 한 줄 — 대표 티어의 한 줄이 있으면 그쪽을 쓴다.
                "tagline": tier.get("one_liner") or item.get("one_liner") or "",
                "taste_tags": item.get("taste_tags") or [],
                "keywords": item.get("keywords") or [],
                "verdict": verdict,
                "stored_verdict": item["verdict"]["overall"],
                "tier_of_record": tier["tier_id"],
                "score": score,
                "maintenance_status": item.get("maintenance_status"),
                "assessed_at": item.get("assessed_at"),
                "evidence_grade": item.get("data_quality", {}).get("overall_grade"),
                "user_rating": item.get("axes", {}).get("user_rating", {}).get("score"),
                "store_stars": stars,
                "drivers": drivers,
            }
            if stars and (stars.get("value") or 0) >= min_stars and verdict in gap_verdicts:
                delta = round((stars["value"] or 0) * 20 - (score or 0), 1)
                record["gap"] = ({
                    "stars": stars["value"],
                    "platform": stars["platform"],
                    "count": stars["count"],
                    "stars_score": round((stars["value"] or 0) * 20, 1),
                    "score": score,
                    "delta": delta,
                    "verdict": verdict,
                } if delta >= min_delta else None)
            else:
                record["gap"] = None
            records.append(record)

    records.sort(key=lambda r: r["id"])
    arena_stats = {}
    for arena_id, arena in arenas.items():
        members = [r for r in records if arena_id in r["arenas"]]
        scored = [r["score"] for r in members if r["score"] is not None]
        top = max(members, key=lambda r: r["score"] if r["score"] is not None else -1) if members else None
        arena_stats[arena_id] = {
            "label": arena["label"],
            "domain": arena["domain"],
            "category": arena["category"],
            "count": len(members),
            "avg_score": round(sum(scored) / len(scored), 1) if scored else None,
            "verdicts": {v: sum(1 for r in members if r["verdict"] == v)
                         for v in ("recommend", "conditional", "avoid")},
            "top_item": {"id": top["id"], "name": top["name"], "score": top["score"]} if top else None,
            "items": [r["id"] for r in members],
        }
    gap_reports = sorted(
        [r for r in records if r.get("gap")],
        key=lambda r: -(r["gap"]["delta"] or 0),
    )
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": contract.get("schema_version") or "0.4.0",
        "note": "분할 데이터에서 자동 생성된 경량 인덱스. 손으로 고치지 않는다(scripts/sync_web_data.py).",
        "weights": {key: w for key, w in AXES},
        "counts": {
            "items": len(records),
            "domains": len(domains),
            "categories": len(categories),
            "arenas": len(arenas),
        },
        "content_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "arena_stats": arena_stats,
        "gap_report": {
            "title": gap_rule.get("title"),
            "min_store_stars": min_stars,
            "items": [r["id"] for r in gap_reports],
        },
        "items": records,
    }


def index_errors(index, expected):
    """생성 결과와 파일이 같은지(신선도) + 필수 필드 검사."""
    errs = []
    if index != expected:
        # 어느 부분이 다른지 짧게 알려준다
        if index.get("content_hash") != expected.get("content_hash"):
            errs.append("search-index.json 이 분할 데이터와 다름(content_hash 불일치) — sync_web_data.py 재실행 필요")
        elif index.get("counts") != expected.get("counts"):
            errs.append(f"search-index.json counts 불일치: {index.get('counts')} ≠ {expected.get('counts')}")
        elif index.get("arena_stats") != expected.get("arena_stats"):
            errs.append("search-index.json arena_stats 가 분할 데이터 집계와 다름 — sync_web_data.py 재실행 필요")
        else:
            errs.append("search-index.json 이 생성 결과와 다름 — sync_web_data.py 재실행 필요")
    items = index.get("items") or []
    if len(items) != index.get("counts", {}).get("items"):
        errs.append("search-index.json items 수와 counts.items 불일치")
    required = {"id", "name", "domain", "category", "arenas", "verdict", "score", "assessed_at"}
    for record in items:
        missing = sorted(required - set(record))
        if missing:
            errs.append(f"search-index.json {record.get('id', '?')}: 필수 키 누락 {missing}")
    return errs


# ------------------------------------------------------------------------- 음성 테스트

def negative_tests(schema, good_item):
    """고의로 망가뜨린 데이터를 스키마가 실제로 잡는지 확인."""
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    cases = []

    broken = copy.deepcopy(good_item)
    broken.pop("sources")
    cases.append(("필수 필드 sources 제거", broken))

    broken = copy.deepcopy(good_item)
    broken.pop("domain")
    cases.append(("필수 필드 domain 제거", broken))

    broken = copy.deepcopy(good_item)
    broken["category"] = "Productivity"
    cases.append(("category 대문자(대분류 id 규칙 위반)", broken))

    broken = copy.deepcopy(good_item)
    broken["domain"] = "..."
    cases.append(("domain 규칙 위반", broken))

    broken = copy.deepcopy(good_item)
    broken["keywords"] = "검색"
    cases.append(("keywords 배열 대신 문자열", broken))

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
    broken.pop("maintenance_status")
    cases.append(("필수 필드 maintenance_status 제거", broken))

    broken = copy.deepcopy(good_item)
    broken["maintenance_status"] = "in_progress"
    cases.append(("maintenance_status 허용되지 않은 값", broken))

    broken = copy.deepcopy(good_item)
    broken["tiers"][0]["hard_filters"]["stale_over_12m"]["status"] = "exempted"
    cases.append(("하드필터 status 허용되지 않은 값", broken))

    broken = copy.deepcopy(good_item)
    broken["tiers"][0]["hard_filters"]["gacha_random_items"]["impact"] = "sometimes"
    cases.append(("impact 허용되지 않은 값", broken))

    broken = copy.deepcopy(good_item)
    broken["monetization"]["free_play"] = {"value": "free", "evidence_grade": "A", "note": "x"}
    cases.append(("free_play.value 허용되지 않은 값", broken))

    return [(label, not validator.is_valid(instance)) for label, instance in cases]


def catalog_negative_tests(catalog, ctx, items_by_arena, contract, index):
    """카탈로그·의미 규칙·인덱스가 고의 오류를 잡는지."""
    results = []
    good_item = next(iter(items_by_arena.values()))[1][0]

    broken = copy.deepcopy(catalog)
    broken["categories"][0]["domain"] = "nope"
    results.append(("카탈로그: 없는 도메인을 가리키는 대분류", bool(catalog_errors(broken, DATA_DIR))))

    broken = copy.deepcopy(catalog)
    broken["arenas"][0]["data_file"] = "app/ghost.json"
    results.append(("카탈로그: 존재하지 않는 data_file", bool(catalog_errors(broken, DATA_DIR))))

    broken = copy.deepcopy(catalog)
    broken["arenas"][0]["category"] = "rpg"
    results.append(("카탈로그: 비교군 도메인과 대분류 도메인 불일치", bool(catalog_errors(broken, DATA_DIR))))

    broken = copy.deepcopy(catalog)
    broken["filter_packs"]["game"]["filters"].append("no_such_filter")
    results.append(("카탈로그: 없는 필터를 넣은 팩", bool(catalog_errors(broken, DATA_DIR))))

    bad_item = copy.deepcopy(good_item)
    bad_item["domain"] = "game" if good_item["domain"] == "app" else "app"
    errs, _ = semantic_errors(bad_item, ctx, good_item["arenas"][0])
    results.append(("의미 규칙: 아이템 domain 이 비교군 도메인과 다름", bool(errs)))

    bad_item = copy.deepcopy(good_item)
    bad_item["arenas"] = ["mobile-gacha-rpg"]
    bad_item["arena_notes"] = {"mobile-gacha-rpg": "x"}
    errs, _ = semantic_errors(bad_item, ctx, good_item["arenas"][0])
    results.append(("의미 규칙: 파일과 arenas 가 어긋남", bool(errs)))

    bad_index = copy.deepcopy(index)
    bad_index["items"][0]["score"] = 12.3
    results.append(("인덱스: 데이터와 다른 점수", bool(index_errors(bad_index, index))))

    bad_index = copy.deepcopy(index)
    bad_index["items"][0].pop("domain")
    results.append(("인덱스: 필수 키 누락", bool(index_errors(bad_index, index))))

    return results


def exemption_rule_tests(good_item, ctx):
    """완결작 면제 규칙의 양성/음성 테스트."""
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

    raw_fail = make(tier_status="fail")
    tier = raw_fail["tiers"][0]
    verdict, why = compute_verdict(raw_fail, tier)
    results.append(("완결작 + 기록된 fail → 면제되어 추천(80.15)",
                    verdict == "recommend", f"{verdict} ({why})"))
    errs, _ = semantic_errors(make(tier_status="fail", note="사유"), ctx, good_item["arenas"][0])
    results.append(("완결작 데이터는 exempt 로 기록(완결작 + fail 기록은 의미 검사도 차단)",
                    bool(errs), "; ".join(errs[:1]) or "차단되지 않음"))

    stored = make(tier_status="exempt", note="완결 선언으로 면제.")
    errs, _ = semantic_errors(stored, ctx, good_item["arenas"][0])
    v2, why2 = compute_verdict(stored, stored["tiers"][0])
    results.append(("면제 기록 데이터 의미 검사 통과 + 추천",
                    not errs and v2 == "recommend", f"errs={errs[:1]} / {v2} ({why2})"))

    for status in ("abandoned", "stale_unknown"):
        item = make(status=status, tier_status="fail")
        verdict, why = compute_verdict(item, item["tiers"][0])
        results.append((f"{status} 는 stale_over_12m 으로 거름",
                        verdict == "avoid" and "stale_over_12m" in why, f"{verdict} ({why})"))

    compat = make(tier_status="exempt", compat="yes", note="완결 선언, OS 호환성 이슈 있음.")
    verdict, why = compute_verdict(compat, compat["tiers"][0])
    results.append(("compat_risk=yes → 조건부 경고",
                    verdict == "conditional" and why.startswith("compat_risk"), f"{verdict} ({why})"))

    wrong_key = make(tier_status="exempt", note="완결 선언.")
    wrong_key["tiers"][0]["hard_filters"]["forced_ads"]["status"] = "exempt"
    errs, _ = semantic_errors(wrong_key, ctx, good_item["arenas"][0])
    results.append(("stale 외 필터의 exempt → 의미 검사 차단", bool(errs), "; ".join(errs[:1]) or "차단되지 않음"))

    active = make(status="active", tier_status="exempt", note="x")
    errs, _ = semantic_errors(active, ctx, good_item["arenas"][0])
    results.append(("active + 12개월 공백 → 의미 검사 차단", bool(errs), "; ".join(errs[:1]) or "차단되지 않음"))

    not_complete = make(status="abandoned", tier_status="exempt", note="x")
    verdict, why = compute_verdict(not_complete, not_complete["tiers"][0])
    results.append(("완결작 아닌데 exempt 기록 → fail 로 계산해 거름",
                    verdict == "avoid", f"{verdict} ({why})"))

    return results


def impact_rule_tests(base_item, ctx, arena_id):
    """확률형·P2W 3단계 강도(impact)와 strict_monetization 토글의 양성/음성 테스트."""
    results = []

    def make(impact, free_value="sufficient", free=True, key="gacha_random_items"):
        it = copy.deepcopy(base_item)  # Balatro — 다른 플래그가 모두 no 인 깨끗한 틀
        it["flags"]["gacha_random_items"]["value"] = "yes"
        it["flags"]["gacha_random_items"]["note"] = "테스트용 확률형 상품."
        it["tiers"][0]["hard_filters"][key] = {
            "status": "fail", "evidence_grade": "A", "note": "테스트용 확률형 상품.", "impact": impact,
        }
        if free:
            it["monetization"]["free_play"] = {
                "value": free_value, "evidence_grade": "A", "source_ids": [], "note": "테스트용 무과금 근거.",
            }
        else:
            it["monetization"].pop("free_play", None)
        return it

    def freeze(item):
        verdict, _why = compute_verdict(item, item["tiers"][0])
        item["tiers"][0]["verdict"] = verdict
        item["verdict"]["overall"] = verdict
        return verdict

    optional = make("optional")
    verdict_optional = freeze(optional)
    results.append(("impact optional → 기본 모드에서 거름 아님(추천)",
                    verdict_optional == "recommend", verdict_optional))
    errs, _ = semantic_errors(optional, ctx, arena_id)
    results.append(("impact optional + free_play sufficient → 의미 검사 통과",
                    not errs, "; ".join(errs[:2]) or "통과"))

    strict_verdict, strict_why = compute_verdict(optional, optional["tiers"][0], strict_monetization=True)
    results.append(("같은 데이터 + strict_monetization=true → 거름",
                    strict_verdict == "avoid", f"{strict_verdict} ({strict_why})"))

    core = make("core", "constrained")
    verdict_core = freeze(core)
    results.append(("impact core → 기본 모드에서 거름",
                    verdict_core == "avoid", verdict_core))
    core_strict, _ = compute_verdict(core, core["tiers"][0], strict_monetization=True)
    results.append(("impact core + strict_monetization=true → 거름 유지",
                    core_strict == "avoid", core_strict))

    no_free = make("optional", free=False)
    errs, _ = semantic_errors(no_free, ctx, arena_id)
    results.append(("impact optional 인데 free_play 없음 → 의미 검사 차단",
                    any("free_play" in e for e in errs), "; ".join(errs[:1]) or "차단되지 않음"))

    bad_free = make("optional", "constrained")
    errs, _ = semantic_errors(bad_free, ctx, arena_id)
    results.append(("impact optional + free_play constrained → 차단",
                    any("free_play" in e for e in errs), "; ".join(errs[:1]) or "차단되지 않음"))

    none_fail = make("none")
    errs, _ = semantic_errors(none_fail, ctx, arena_id)
    results.append(("impact none + status fail → 차단",
                    any("impact 'none'" in e for e in errs), "; ".join(errs[:1]) or "차단되지 않음"))

    wrong_key = make("optional")
    wrong_key["tiers"][0]["hard_filters"]["forced_ads"]["impact"] = "optional"
    errs, _ = semantic_errors(wrong_key, ctx, arena_id)
    results.append(("gacha·p2w 가 아닌 필터의 impact → 차단",
                    any("impact 는" in e for e in errs), "; ".join(errs[:1]) or "차단되지 않음"))

    core_conflict = make("core", "sufficient")
    errs, _ = semantic_errors(core_conflict, ctx, arena_id)
    results.append(("impact core + free_play sufficient → 모순 차단",
                    any("모순" in e for e in errs), "; ".join(errs[:1]) or "차단되지 않음"))

    return results


ICON_PATTERN = re.compile(r"^assets/icons/[a-z0-9][a-z0-9-]*\.(png|jpg|jpeg|webp)$")


def image_kind(data):
    """파일 앞부분만 보고 실제 이미지인지(그리고 형식이 무엇인지) 판별한다."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def icon_errors(items_by_arena, web_dir=None):
    """아이콘 경로 규칙 · 파일 존재 · 실제 이미지 여부 · 중복 · 미사용 파일 검사."""
    web_dir = web_dir or WEB_DIR
    errs, warns = [], []
    used = {}
    for _arena_id, (_path, items) in items_by_arena.items():
        for item in items:
            icon = item.get("icon")
            if not icon:
                warns.append(f"{item['id']}: icon 없음 — 카드·상세에서 이니셜 배지로 대체된다")
                continue
            if not isinstance(icon, str) or not ICON_PATTERN.match(icon):
                errs.append(f"{item['id']}: icon 경로 규칙 위반 {icon!r} (assets/icons/{item['id']}.webp 형식)")
                continue
            if icon in used:
                errs.append(f"{item['id']}: icon 경로가 {used[icon]} 와 중복 ({icon})")
            used[icon] = item["id"]
            path = web_dir / icon
            if not path.exists():
                errs.append(f"{item['id']}: 아이콘 파일 없음 web/{icon} — python3 projects/pharos/scripts/fetch_icons.py")
                continue
            data = path.read_bytes()
            kind = image_kind(data)
            if kind is None:
                errs.append(f"{item['id']}: 아이콘이 실제 이미지 파일이 아님 web/{icon}")
            elif path.suffix.lower() == ".webp" and kind != "webp":
                errs.append(f"{item['id']}: 확장자는 .webp 인데 실제 형식은 {kind} web/{icon}")
            elif len(data) < 512:
                errs.append(f"{item['id']}: 아이콘 파일이 너무 작음({len(data)}B) web/{icon}")
    icon_dir = web_dir / "assets" / "icons"
    if icon_dir.exists():
        for path in sorted(icon_dir.iterdir()):
            rel = f"assets/icons/{path.name}"
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and rel not in used:
                warns.append(f"참조되지 않는 아이콘 파일: web/{rel}")
    return errs, warns


def icon_negative_tests(items_by_arena):
    """아이콘 검사기가 고의 오류(없는 파일·규칙 위반·이미지 아닌 파일)를 잡는지 확인한다."""
    results = []

    def mutate(**changes):
        bad = copy.deepcopy(items_by_arena)
        first_key = next(iter(bad))
        item = bad[first_key][1][0]
        item["icon"] = changes.get("icon", item.get("icon"))
        return bad

    errs, _ = icon_errors(mutate(icon="assets/icons/no-such-item.webp"))
    results.append(("아이콘: 없는 파일 경로 → 차단", any("파일 없음" in e for e in errs), "; ".join(errs[:1]) or "차단되지 않음"))

    errs, _ = icon_errors(mutate(icon="icons/balatro.webp"))
    results.append(("아이콘: 경로 규칙 위반(assets/icons/ 아님) → 차단", any("경로 규칙" in e for e in errs), "; ".join(errs[:1]) or "차단되지 않음"))

    errs, _ = icon_errors(mutate(icon="assets/icons/../schema/item.schema.json"))
    results.append(("아이콘: 이미지가 아닌 파일 → 차단", any("경로 규칙" in e or "이미지" in e for e in errs), "; ".join(errs[:1]) or "차단되지 않음"))

    errs, _ = icon_errors(mutate(icon=None))
    results.append(("아이콘: 경로 없음 → 오류가 아니라 경고로 남김", not errs, "; ".join(errs[:1]) or "경고 처리"))

    return results


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def web_sync_errors(catalog, items_by_arena):
    """웹 배포 사본이 원본과 같은지, 웹 JS 가 웹 폴더 밖을 참조하지 않는지."""
    errs = []
    pairs = [
        ("스키마", SCHEMA_PATH, WEB_SCHEMA_PATH),
        ("카탈로그", CATALOG_PATH, WEB_DATA_DIR / "catalog.json"),
        ("검색 인덱스", INDEX_PATH, WEB_DATA_DIR / "search-index.json"),
    ]
    for arena_id, (path, _items) in items_by_arena.items():
        pairs.append((f"비교군 {arena_id}", path, WEB_DATA_DIR / path.relative_to(DATA_DIR)))
    for label, src, dst in pairs:
        rel = dst.relative_to(ROOT)
        if not dst.exists():
            errs.append(f"{label} 사본 없음: {rel} (python3 projects/pharos/scripts/sync_web_data.py)")
        elif sha256(src) != sha256(dst):
            errs.append(f"{label} 사본이 원본과 다름: {rel} (python3 projects/pharos/scripts/sync_web_data.py)")

    legacy = WEB_DATA_DIR / "items.json"
    if legacy.exists():
        errs.append("구 통합 데이터 사본(web/data/items.json)이 남아 있음 — 분할 파일로 대체됨")

    scripts = sorted(WEB_JS_DIR.glob("*.js"))
    if not scripts:
        errs.append("web/js/ 에 스크립트가 없음")
    joined = "\n".join(p.read_text(encoding="utf-8") for p in scripts)
    for needle in ("./data/catalog.json", "./data/search-index.json", "./schema/item.schema.json"):
        if needle not in joined:
            errs.append(f"웹 JS 에 배포 기준 상대경로 {needle} 가 없음")
    if "../data/" in joined or "../schema/" in joined:
        errs.append("웹 JS 에 웹 폴더 밖을 가리키는 ../data/ 또는 ../schema/ 참조가 남아 있음")
    return errs


# ------------------------------------------------------------------------------- main

def main():
    schema = load(SCHEMA_PATH)
    catalog = load(CATALOG_PATH)
    contract = (schema.get("x-pharos") or {}).get("client") or {}
    version = (schema.get("x-pharos") or {}).get("schema_version", "?")

    print("=" * 78)
    print(f"Pharos v{version} 검증 — 4단 계층(도메인→대분류→비교군→항목) · 분할 데이터")
    print(f"schema : {SCHEMA_PATH.relative_to(ROOT.parent.parent)}")
    print(f"catalog: {CATALOG_PATH.relative_to(ROOT.parent.parent)}")
    print("=" * 78)

    # 0) 스키마 자체
    try:
        Draft202012Validator.check_schema(schema)
        print("[0] 스키마 자체 검사: PASS (Draft 2020-12)")
    except Exception as exc:  # noqa: BLE001
        print(f"[0] 스키마 자체 검사: FAIL — {exc}")
        return 1

    # 1) 계산 계약 메타
    meta_errors = []
    if contract.get("catalog", {}).get("file") != "data/catalog.json":
        meta_errors.append("x-pharos.client.catalog.file 이 data/catalog.json 이 아님")
    if contract.get("catalog", {}).get("search_index") != "data/search-index.json":
        meta_errors.append("x-pharos.client.catalog.search_index 가 data/search-index.json 이 아님")
    if list(contract.get("navigation", {}).get("levels") or []) != ["domain", "category", "arena", "item"]:
        meta_errors.append("x-pharos.client.navigation.levels 가 4단 계층이 아님")
    if (contract.get("freshness") or {}).get("review_after_days") != 180:
        meta_errors.append("x-pharos.client.freshness.review_after_days 가 180 이 아님")
    statuses_meta = contract.get("maintenance_statuses") or []
    if {s.get("key") for s in statuses_meta} != MAINTENANCE_STATUSES:
        meta_errors.append(f"maintenance_statuses 메타가 열거형과 다름: {[s.get('key') for s in statuses_meta]}")
    exemption = contract.get("stale_exemption") or {}
    if exemption.get("exempt_value") != "feature_complete" or exemption.get("recorded_status") != "exempt":
        meta_errors.append("stale_exemption 메타(feature_complete → exempt)가 없음")
    if contract.get("hard_filters") and {f["key"] for f in contract["hard_filters"]} != set(FILTER_TO_FLAG):
        meta_errors.append("x-pharos.client.hard_filters 키 집합이 9종과 다름")
    if "arenas" in contract:
        meta_errors.append("x-pharos.client.arenas 가 남아 있음 — catalog.json 으로 옮겨야 함")
    impact_meta = contract.get("monetization_impact") or {}
    if set(impact_meta.get("keys") or []) != MONETIZATION_IMPACT_KEYS:
        meta_errors.append("monetization_impact.keys 가 gacha_random_items·p2w 와 다름")
    contract_weights = {a.get("key"): a.get("default_weight") for a in contract.get("axes") or []}
    for key, weight in AXES:
        try:
            same = abs(float(contract_weights.get(key)) - weight) < 1e-9
        except (TypeError, ValueError):
            same = False
        if not same:
            meta_errors.append(f"axes[{key}].default_weight 가 v0.5.0 기본 배분({weight})과 다름: {contract_weights.get(key)!r}")
    sample_scale = contract.get("sample_scale") or {}
    if sample_scale.get("axis") != "user_rating" or not sample_scale.get("thin_recent_rule") or not sample_scale.get("risky_terms_exception"):
        meta_errors.append("sample_scale(사용자 축 표본 규모 검증) 계약이 없음")
    if {level.get("key") for level in impact_meta.get("levels") or []} != IMPACT_VALUES:
        meta_errors.append("monetization_impact.levels 가 none·optional·core 와 다름")
    toggle = impact_meta.get("strict_toggle") or {}
    if toggle.get("key") != "strict_monetization" or toggle.get("default") is not False:
        meta_errors.append("monetization_impact.strict_toggle(strict_monetization, 기본 OFF)가 없음")
    if meta_errors:
        print(f"[1] 계산 계약 메타 검사: FAIL — {'; '.join(meta_errors)}")
        return 1
    print("[1] 계산 계약 메타 검사: PASS — catalog 참조·4단 탐색·신선도 180일·수명 단계 4종")

    # 2) 카탈로그
    errors = catalog_errors(catalog, DATA_DIR)
    if errors:
        print(f"[2] 카탈로그 검사: FAIL — {len(errors)}건")
        for err in errors:
            print(f"  × {err}")
        return 1
    domains = [d["id"] for d in catalog["domains"]]
    categories = [c["id"] for c in catalog["categories"]]
    arenas_meta = catalog["arenas"]
    print(f"[2] 카탈로그 검사: PASS — 도메인 {len(domains)}개({', '.join(domains)}) · "
          f"대분류 {len(categories)}개 · 비교군 {len(arenas_meta)}개")

    ctx = {
        "arenas": {a["id"]: a for a in arenas_meta},
        "domains": set(domains),
        "categories": set(categories),
    }
    items_by_arena = load_items_by_arena(catalog, DATA_DIR)
    if set(items_by_arena) != set(ctx["arenas"]):
        print(f"[3] 분할 데이터 로드: FAIL — 파일이 없는 비교군 {sorted(set(ctx['arenas']) - set(items_by_arena))}")
        return 1

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    total = sum(len(items) for _p, items in items_by_arena.values())
    print(f"\n[3] 분할 데이터 {len(items_by_arena)}개 파일 · 아이템 {total}건")

    seen_ids = {}
    schema_failures = 0
    semantic_failures = 0
    all_items = []
    for arena in arenas_meta:
        path, items = items_by_arena[arena["id"]]
        rel = path.relative_to(ROOT.parent.parent)
        print(f"  ▸ {arena['id']} ({arena['domain']} / {arena['category']}) — {rel} · {len(items)}건")
        if not items:
            print("      × 비어 있는 비교군")
            semantic_failures += 1
        for item in items:
            all_items.append(item)
            if item["id"] in seen_ids:
                print(f"      × 아이템 id 중복: {item['id']} ({seen_ids[item['id']]} 와 겹침)")
                semantic_failures += 1
            seen_ids[item["id"]] = arena["id"]
            errors = sorted(validator.iter_errors(item), key=lambda e: list(e.path))
            if errors:
                schema_failures += 1
                print(f"      × {item.get('id', '?')}: 스키마 FAIL ({len(errors)}건)")
                for err in errors:
                    where = "/".join(str(p) for p in err.path) or "(root)"
                    print(f"          · {where}: {err.message}")
                continue
            errs, warns = semantic_errors(item, ctx, arena["id"])
            status = "PASS" if not errs else "FAIL"
            print(f"      - {item['id']}: {status} (domain={item['domain']}, category={item['category']}, "
                  f"maintenance_status={item['maintenance_status']})")
            for w in warns:
                print(f"          ! 경고: {w}")
            for e in errs:
                print(f"          × {e}")
            semantic_failures += 1 if errs else 0
            for tier in item["tiers"]:
                score = weighted_score(item, tier)
                computed, why = compute_verdict(item, tier)
                print(f"          · {tier['tier_id']:<14} score={str(score):<6} 판정={tier['verdict']:<11} "
                      f"재계산={computed:<11} stale={filter_status(item, tier, 'stale_over_12m'):<7} ({why})")
    if schema_failures:
        print("  → 스키마 검증 실패")
        return 1
    if semantic_failures:
        print("  → 의미 규칙 위반 있음")
        return 1

    # 3-1) 계층 구성
    print("\n[4] 계층 구성 (도메인 → 대분류 → 비교군 → 항목)")
    for dom in catalog["domains"]:
        cats = [c for c in catalog["categories"] if c["domain"] == dom["id"]]
        print(f"  ▸ {dom['label']}({dom['id']}) — 대분류 {len(cats)} · 팩 {dom['filter_pack']}")
        for cat in cats:
            members = [a for a in arenas_meta if a["category"] == cat["id"]]
            print(f"      - {cat['label']}({cat['id']})")
            for arena in members:
                _p, items = items_by_arena[arena["id"]]
                print(f"          · {arena['label']}({arena['id']}) — {len(items)}건: "
                      f"{', '.join(i['id'] for i in items)}")

    # 4) 인덱스 생성·신선도
    expected_index = build_search_index(catalog, items_by_arena, contract)
    print(f"\n[5] 경량 인덱스 검사 — {INDEX_PATH.relative_to(ROOT.parent.parent)}")
    if not INDEX_PATH.exists():
        print("  × search-index.json 없음 — python3 projects/pharos/scripts/sync_web_data.py 실행")
        return 1
    index = load(INDEX_PATH)
    idx_errs = index_errors(index, expected_index)
    for err in idx_errs:
        print(f"  × {err}")
    if idx_errs:
        return 1
    print(f"  - 아이템 {index['counts']['items']}건 · 비교군 {index['counts']['arenas']}개 · "
          f"gap_report {len(index['gap_report']['items'])}건 ({', '.join(index['gap_report']['items'])})")
    print("  - 분할 데이터에서 다시 생성한 결과와 일치(content_hash 동일)")

    # 5) 음성 테스트
    print("\n[6] 음성 테스트 (일부러 깨뜨린 데이터를 검증기가 잡는지)")
    neg = negative_tests(schema, all_items[0])
    neg_cat = catalog_negative_tests(catalog, ctx, items_by_arena, contract, index)
    for label, caught in neg + neg_cat:
        print(f"  - {label}: {'차단됨 PASS' if caught else '통과됨 FAIL'}")
    if not all(caught for _, caught in neg + neg_cat):
        return 1

    # 6) 완결작 면제 규칙
    print("\n[7] 완결작 면제 규칙 테스트 (maintenance_status ↔ stale_over_12m)")
    inscryption = next((item for item in all_items if item.get("maintenance_status") == "feature_complete"), None)
    if inscryption is None:
        print("  → feature_complete 아이템이 없어 규칙을 확인할 수 없음")
        return 1
    rules = exemption_rule_tests(inscryption, ctx)
    for label, ok, detail in rules:
        print(f"  - {label}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" ← {detail}"))
    if not all(ok for _, ok, _ in rules):
        return 1

    # 6-1) 확률형·P2W 3단계 강도
    print("\n[7-1] 확률형·P2W 3단계 강도(impact)·strict_monetization 테스트")
    base_item = next((item for item in all_items if item["id"] == "balatro"), all_items[0])
    impact_rules = impact_rule_tests(base_item, ctx, base_item["arenas"][0])
    for label, ok, detail in impact_rules:
        print(f"  - {label}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" ← {detail}"))
    if not all(ok for _, ok, _ in impact_rules):
        return 1

    # 7) 웹 사본
    print("\n[8] 정적 배포 준비(web/ 단독 폴더)")
    web_errs = web_sync_errors(catalog, items_by_arena)
    for err in web_errs:
        print(f"  × {err}")
    if web_errs:
        return 1
    print("  - 스키마·카탈로그·검색 인덱스·비교군 데이터 사본이 원본과 바이트 단위로 같음")
    print("  - 웹 JS 가 ./data/catalog.json · ./data/search-index.json · ./schema/item.schema.json 을 상대경로로 참조")
    print("  - web/ 폴더만으로 데이터·스키마·계산 계약이 모두 해결됨")

    # 8-1) 아이콘 파일
    print("\n[9] 아이콘 검사(web/assets/icons/)")
    icon_errs, icon_warns = icon_errors(items_by_arena)
    for warn in icon_warns:
        print(f"  ! 경고: {warn}")
    for err in icon_errs:
        print(f"  × {err}")
    if icon_errs:
        return 1
    with_icon = sum(1 for item in all_items if item.get("icon"))
    print(f"  - 아이템 {with_icon}/{len(all_items)}건이 icon 경로를 가짐 · 모든 파일 존재 · 실제 이미지 확인")
    if not all(index_item.get("icon") for index_item in index.get("items") or []):
        print("  × search-index.json 에 icon 이 비어 있는 항목이 있음")
        return 1
    print("  - search-index.json 에도 icon 이 실려 홈 검색·갭 리포트에서 바로 쓸 수 있음")
    print("\n[9-1] 아이콘 검사 음성 테스트")
    icon_neg = icon_negative_tests(items_by_arena)
    for label, caught, detail in icon_neg:
        print(f"  - {label}: {'차단됨 PASS' if caught else '통과됨 FAIL'}" + ("" if caught else f" ← {detail}"))
    if not all(caught for _, caught, _ in icon_neg):
        return 1

    print("\n" + "=" * 78)
    print(f"결과: PASS — 아이템 {total}건 스키마 100% 충족 · 의미 규칙 위반 0 · "
          f"계층 {len(domains)}/{len(categories)}/{len(arenas_meta)} 정상 · 판정 재계산 일치 · "
          f"인덱스 최신 · 음성 테스트 {sum(1 for _, c in neg + neg_cat if c)}/{len(neg) + len(neg_cat)} 차단 · "
          f"완결작 면제 {sum(1 for _, ok, _ in rules if ok)}/{len(rules)} 통과 · "
          f"강도 3단계 {sum(1 for _, ok, _ in impact_rules if ok)}/{len(impact_rules)} 통과 · "
          f"아이콘 {with_icon}/{len(all_items)}건 · web/ 사본 일치")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
