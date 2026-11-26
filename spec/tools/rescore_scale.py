#!/usr/bin/env python3
"""v0.6.0 표본 규모 보정(scale_adjustment)을 기존 데이터 전체에 다시 적용한다.

기준표 2.1절의 규칙(scripts/scale_rules.py)을 1,467종 전부에 적용해
  · axes.user_rating.score / signal / scale_adjustment
  · score_notes.user_rating (KO) 과 data/en.json 의 같은 자리(EN)
  · axes.user_rating.summary 의 보정 문구
  · tiers[].verdict, verdict.overall, verdict.signals
을 다시 계산한다. 판정은 schema/validate.py 의 compute_verdict 를 그대로 불러 쓴다(이중 구현 금지).
대표 티어(tier_of_record)는 사람이 고른 값을 유지하고, 그 티어로 overall 만 다시 계산한다.

몇몇 검증 완료 항목은 verdict.reasons 문장 안에 축 점수·사용자 점수를 직접 적어 두었다.
그 문장은 REASON_PATCHES 에 새 수치로 다시 써 둔다(숫자를 손으로 고치지 않고 계산값을 넣는다).

사용
  python3 projects/pharos/scripts/rescore_scale.py            # 미리보기(분포·판정 변화·대표 사례)
  python3 projects/pharos/scripts/rescore_scale.py --apply    # data/*.json · data/en.json 기록
  python3 projects/pharos/scripts/rescore_scale.py --apply --json out.json   # 변화표 저장
"""

from __future__ import annotations

import argparse
import collections
import copy
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
sys.path.insert(0, str(ROOT / "schema"))
sys.path.insert(0, str(ROOT / "scripts"))

import scale_rules as rules                          # noqa: E402
import validate as vlib                              # noqa: E402

DATA = ROOT / "data"
EN_PATH = DATA / "en.json"
KO_MARK = "v0.6.0 표본 규모 보정:"
EN_MARK = "v0.6.0 Sample-scale adjustment:"
KO_SUMMARY_RE = re.compile(r"\s*v0\.6\.0 표본 규모 보정[^.]*\.")
EN_SUMMARY_RE = re.compile(r"\s*v0\.6\.0 sample-scale adjustment[^.]*\.")

# 축 점수·사용자 점수를 문장에 박아 둔 항목 — 계산값으로 다시 쓴다. {u}=사용자, {w}=가중 점수
REASON_PATCHES: dict[str, dict[str, dict[int, str]]] = {
    "black-desert": {
        "ko": {2: ("v0.6.0 표본 규모 보정으로 Steam 9.5만 건 규모가 반영돼 사용자 72→{u}, "
                   "축 점수 {w} — 추천 문턱(80)을 넘어 추천 판정으로 바뀌었다"
                   "(객관 78·AI 96은 그대로, 최근 30일 65% 하락은 사실로 남는다).")},
        "en": {2: ("With the v0.6.0 sample-scale adjustment the Steam sample of about 95,000 ratings is reflected: "
                   "user 72→{u}, axis score {w} — above the recommendation threshold (80), so it is now recommended "
                   "(objective 78 and AI 96 unchanged; the recent 30-day drop to 65% remains a fact).")},
    },
    "overwatch-2": {
        "ko": {2: "스팀 리뷰는 41%로 낮지만 항의성 평가가 섞여 있어 {u}(🟡)로 보정했다(원 환산 41점, v0.6.0 규모 보정 포함)."},
        "en": {2: ("The Steam rating is 41%, but with heavy protest voting it was adjusted to {u} (🟡) "
                   "(41 as scored, including the v0.6.0 sample-scale adjustment).")},
    },
    "bloons-td-6": {
        "ko": {0: "광고·구독·P2W가 없고 1회 구매로 전편을 즐길 수 있어 축 점수가 {w}로 높다."},
        "en": {0: ("There are no advertisements, subscriptions, or P2W, and you can enjoy the entire game with a "
                   "one-time purchase, so the axis score is high at {w}.")},
    },
    "clash-of-clans": {
        "ko": {1: "축 점수는 {w}(사용자 {u}·객관 60·AI 86). 🟡 신호가 객관 하나뿐이라 80 이상에서 추천 판정이다."},
        "en": {1: "The axis score was {w} (user {u}, objective 60, AI 86). 🟡 Since there is only one objective signal, a score of 80 or higher is recommended."},
    },
    "arknights": {
        "ko": {0: "축 점수 {w}(사용자 {u}·객관 68·AI 88)로 80 이상이고 🟡 신호가 1개뿐이라 추천 판정이다."},
        "en": {0: "The axis score is {w} (user {u}, objective 68, AI 88), which is over 80 and there is only one 🟡 signal, so it is a recommended decision."},
    },
    "goddess-of-victory-nikke": {
        "ko": {1: ("축 점수는 {w}(사용자 {u}·객관 68·AI 92) — 스토리·더빙·연출·OST의 본질 완성도가 높고, "
                   "광고·구독 없이 업데이트가 이어지는 점이 객관 축에 반영됐다.")},
        "en": {1: ("The axis score was {w} (user {u}, objective 68, AI 92) — the essential completeness of the story, "
                   "dubbing, directing, and OST was high, and continuous updates without ads or subscriptions were "
                   "reflected in the objective axis.")},
    },
    "blue-archive": {
        "ko": {0: "축 점수 {w}(사용자 {u}·객관 62·AI 84)로 🟡 신호 1개, 80점 미만이라 조건부다."},
        "en": {0: "With an axis score of {w} (user {u}, objective 62, AI 84), there is 1 🟡 signal, and it is conditional because it is less than 80 points."},
    },
    "honkai-star-rail": {
        "ko": {0: "축 점수 {w}(사용자 {u}·객관 58·AI 84)로 품질 신호는 높지만 기본 활성 필터에서 거름이다."},
        "en": {0: "The quality signal is high with an axis score of {w} (user {u}, objective 58, AI 84), but it is filtered by the default active filter."},
    },
    "notion": {
        "ko": {2: ("최근 3자 표본(100건씩)은 낮지만 누적 4.6~4.8★(약 50만)과 반씩 섞어 사용자 {u}로 본다"
                   "(v0.6.0 규모 보정 포함). AI 노출·모바일 속도·유실 불만은 사실로 남는다.")},
        "en": {2: ("The recent third-party sample (100 each) is low, but mixed half with the cumulative 4.6~4.8★ "
                   "(about 500,000) the user axis is {u} (including the v0.6.0 sample-scale adjustment). "
                   "Complaints about AI exposure, mobile speed and lost content remain true.")},
    },
}


def num(value) -> str:
    """60.0 → '60', 74.9 → '74.9' — 문장에 넣기 좋은 표기."""
    if value is None:
        return "—"
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text


def weight(item) -> float | None:
    tier = next((t for t in item["tiers"] if t["tier_id"] == item["verdict"]["tier_of_record"]), None)
    return vlib.weighted_score(item, tier) if tier else None


def strip_note(text: str | None, mark: str) -> str:
    if not text:
        return ""
    index = text.find(mark)
    return (text[:index] if index >= 0 else text).strip()


def strip_summary(text: str | None, pattern: re.Pattern) -> str:
    if not text:
        return ""
    return pattern.sub("", text).strip()


def rescore_item(item: dict, en_item: dict | None) -> dict:
    """아이템 1건의 사용자 축·판정을 다시 계산한다(제자리 수정)."""
    axis = item["axes"]["user_rating"]
    previous_record = axis.get("scale_adjustment") or {}
    base = previous_record.get("base_score")
    if base is None:
        base = axis.get("score")
    count, source = rules.sample_count_of(item)
    record = rules.adjust(base, count, source)
    record["applied_flag"] = bool(record["applied"])

    before_score, before_signal = axis.get("score"), axis.get("signal")
    axis["scale_adjustment"] = record
    if record["final_score"] is not None:
        axis["score"] = record["final_score"]
        if axis.get("signal_basis") != "review_override":
            axis["signal"] = ("red" if axis["score"] < 50 else "yellow" if axis["score"] < 75 else "green")

    # ── 산정 메모(KO/EN): 기존 문장 뒤에 v0.6.0 보정 근거를 붙인다(다시 돌려도 한 번만).
    notes = item.setdefault("score_notes", {})
    old_note = strip_note(notes.get("user_rating"), KO_MARK)
    if record["base_score"] is not None:
        notes["user_rating"] = (old_note + " " + KO_MARK + " " + rules.reason_ko(record)[len("표본 규모 보정:"):].strip()).strip()
    if en_item is not None:
        en_notes = en_item.setdefault("score_notes", {})
        old_en = strip_note(en_notes.get("user_rating"), EN_MARK)
        if record["base_score"] is not None:
            en_notes["user_rating"] = (old_en + " " + EN_MARK + " " +
                                       rules.reason_en(record)[len("Sample-scale adjustment:"):].strip()).strip()

    # ── 요약 문장: 보정이 점수를 움직였으면 한 줄 덧붙인다.
    if record["applied"] != 0:
        axis["summary"] = (strip_summary(axis.get("summary"), KO_SUMMARY_RE) +
                           f" v0.6.0 표본 규모 보정 {record['applied']:+.2f} → {num(record['final_score'])}.").strip()
        if en_item is not None and (en_item.get("axes") or {}).get("user_rating", {}).get("summary"):
            en_axis = en_item["axes"]["user_rating"]
            en_axis["summary"] = (strip_summary(en_axis.get("summary"), EN_SUMMARY_RE) +
                                  f" v0.6.0 sample-scale adjustment {record['applied']:+.2f} → {num(record['final_score'])}.").strip()
    else:
        axis["summary"] = strip_summary(axis.get("summary"), KO_SUMMARY_RE)
        if en_item is not None and (en_item.get("axes") or {}).get("user_rating", {}).get("summary"):
            en_item["axes"]["user_rating"]["summary"] = strip_summary(
                en_item["axes"]["user_rating"]["summary"], EN_SUMMARY_RE)

    # ── 티어 판정·대표 판정 재계산(검증기와 같은 함수).
    for tier in item["tiers"]:
        tier["verdict"] = vlib.compute_verdict(item, tier)[0]
    record_tier = next(t for t in item["tiers"] if t["tier_id"] == item["verdict"]["tier_of_record"])
    overall, _why = vlib.compute_verdict(item, record_tier)
    item["verdict"]["overall"] = overall
    item["verdict"]["hard_filter_blocked"] = overall == "avoid"
    for key in ("user_rating", "objective", "ai_review"):
        item["verdict"]["signals"][key] = item["axes"][key].get("signal", "unknown")

    # ── 문장에 박힌 축 점수·사용자 점수 다시 쓰기.
    patches = REASON_PATCHES.get(item["id"])
    if patches:
        fields = {"u": num(axis.get("score")), "w": num(weight(item))}
        for index, text in patches.get("ko", {}).items():
            item["verdict"]["reasons"][index] = text.format(**fields)
        if en_item is not None:
            for index, text in patches.get("en", {}).items():
                en_item["verdict"]["reasons"][index] = text.format(**fields)

    return {
        "id": item["id"],
        "review_tier": item.get("review_tier") or "verified",
        "sample_count": count,
        "sample_source": source,
        "before": before_score,
        "after": axis.get("score"),
        "applied": record["applied"],
        "gate": record["gate"],
        "signal_before": before_signal,
        "signal_after": axis.get("signal"),
        "verdict_before": None,     # 호출부에서 채운다
        "verdict_after": overall,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="data/*.json 과 data/en.json 에 기록")
    parser.add_argument("--json", default="", help="변화표를 저장할 경로")
    args = parser.parse_args()

    bundle = json.loads(EN_PATH.read_text(encoding="utf-8"))
    en_items = bundle.get("items", {})

    before_dist = collections.Counter()
    after_dist = collections.Counter()
    rows = []
    files = sorted(glob.glob(str(DATA / "*" / "*.json")))
    for path in files:
        items = json.loads(Path(path).read_text(encoding="utf-8"))
        changed = False
        for index, item in enumerate(items):
            before_dist[item["verdict"]["overall"]] += 1
            original = copy.deepcopy(item)
            row = rescore_item(item, en_items.get(item["id"]))
            row["verdict_before"] = original["verdict"]["overall"]
            after_dist[row["verdict_after"]] += 1
            rows.append(row)
            if item != original:
                changed = True
            if en_items.get(item["id"]) is not None:
                changed = True
        if args.apply and changed:
            Path(path).write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    if args.apply:
        EN_PATH.write_text(json.dumps(bundle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    moved = [r for r in rows if r["before"] != r["after"]]
    flips = [r for r in rows if r["verdict_before"] != r["verdict_after"]]
    print(f"아이템 {len(rows)}건 · 점수 변화 {len(moved)}건(상승 {sum(1 for r in moved if (r['after'] or 0) > (r['before'] or 0))}"
          f" · 하락 {sum(1 for r in moved if (r['after'] or 0) < (r['before'] or 0))}) · 판정 변화 {len(flips)}건")
    print("판정 분포:", dict(before_dist), "→", dict(after_dist))
    print("신호 변화:", collections.Counter((r["signal_before"], r["signal_after"]) for r in rows
                                        if r["signal_before"] != r["signal_after"]))
    print("\n판정이 바뀐 항목:")
    for r in sorted(flips, key=lambda x: x["id"]):
        print(f"  {r['id']:28} {r['verdict_before']:12} → {r['verdict_after']:12} "
              f"(사용자 {num(r['before'])} → {num(r['after'])}, 표본 {rules.fmt_count(r['sample_count'])}, "
              f"보정 {r['applied']:+.2f}, {r['review_tier']})")
    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"\n변화표 저장: {args.json}")
    if not args.apply:
        print("\n(미리보기입니다 — 실제 기록은 --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
