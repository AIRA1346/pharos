#!/usr/bin/env python3
"""v0.6.0 표본 규모 보정(scale_adjustment) — 기준표 2.1절의 순수 함수 모음.

기준표가 정한 세 가지를 그대로 코드로 옮긴다.

1) 하드 필터 우선 — 이 모듈은 점수만 만진다. 강제 광고·핵심 P2W·서비스 종료 같은
   거름 조건은 판정 단계(validate.compute_verdict)에서 그대로 먼저 걸린다.
2) 평점 연동 게이트 — 기본 평점이 70점 이상이면 보정 100%, 60~70점은 비례 축소,
   60점 미만은 0%. "욕먹지만 유명한 앱"을 표본 규모로 미화하지 않는다.
3) 연속 로그 보정 — 누적 표본 수의 로그값에 대해 구간별 선형 보간.
     <100건  -6.0 | 100건 -5.0 | 1천 -2.0 | 1만 0 | 10만 +3.0 | 100만 +5.5 | 1천만+ +7.5
   최종 사용자 점수는 0.0~100.0 으로 클램프한다.

표본 수는 `review_snapshot.platforms[].cumulative.count` 중 최댓값을 쓴다. 평점 표본이
아예 없고 GitHub stars 만 있는 도구는 별 수를 대리 표본으로 쓰되 `sample_source` 에
`github_stars` 로 남겨 리뷰 수와 구분한다.

`python3 projects/pharos/scripts/scale_rules.py <표본수>` 로 계산을 바로 확인할 수 있다.
"""

from __future__ import annotations

import math
import sys

RULE_VERSION = "v0.6.0"
FIELD = "axes.user_rating.scale_adjustment"
NOTE_FIELD = "score_notes.user_rating"

# (표본 수, 보정치) — 로그 구간 선형 보간의 기준점. 첫 점 미만은 첫 점 값을 그대로 쓴다.
ANCHORS: list[tuple[float, float]] = [
    (100, -5.0),
    (1_000, -2.0),
    (10_000, 0.0),
    (100_000, 3.0),
    (1_000_000, 5.5),
    (10_000_000, 7.5),
]
TINY_COUNT = 100          # 100건 미만은 -6.0 고정
TINY_DELTA = -6.0
GATE_FULL = 70.0          # 이 이상이면 보정 100%
GATE_ZERO = 60.0          # 이 미만이면 보정 0%
SCORE_MIN, SCORE_MAX = 0.0, 100.0


def log_delta(count: int | None) -> float:
    """누적 표본 수 → 로그 보정치(게이트 적용 전). 표본을 모르면 0(보정 없음)."""
    if count is None or count <= 0:
        return 0.0
    if count < TINY_COUNT:
        return TINY_DELTA
    x = math.log10(count)
    if x >= math.log10(ANCHORS[-1][0]):
        return ANCHORS[-1][1]
    for (x0, y0), (x1, y1) in zip(ANCHORS, ANCHORS[1:]):
        lx0, lx1 = math.log10(x0), math.log10(x1)
        if lx0 <= x <= lx1:
            return round(y0 + (y1 - y0) * (x - lx0) / (lx1 - lx0), 4)
    return 0.0


def rating_gate(base_score: float | None) -> float:
    """기본 평점 → 게이트 배율. 70 이상 1.0, 60~70 비례, 60 미만 0."""
    if base_score is None:
        return 0.0
    if base_score >= GATE_FULL:
        return 1.0
    if base_score >= GATE_ZERO:
        return round((base_score - GATE_ZERO) / (GATE_FULL - GATE_ZERO), 4)
    return 0.0


def sample_count_of(item: dict) -> tuple[int | None, str | None]:
    """항목의 누적 표본 수와 그 출처. 리뷰 수 우선, 없으면 GitHub stars(대리 지표)."""
    rows = (item.get("review_snapshot") or {}).get("platforms") or []
    counts = [
        row["cumulative"]["count"]
        for row in rows
        if isinstance((row.get("cumulative") or {}).get("count"), int)
        and row["cumulative"]["count"] > 0
    ]
    if counts:
        return max(counts), "reviews"
    stars = [
        row["cumulative"]["value"]
        for row in rows
        if (row.get("cumulative") or {}).get("metric") == "score"
        and "stars" in str((row["cumulative"] or {}).get("window") or "").lower()
        and isinstance((row["cumulative"] or {}).get("value"), (int, float))
        and row["cumulative"]["value"] > 0
    ]
    if stars:
        return int(max(stars)), "github_stars"
    return None, None


def adjust(base_score: float | None, count: int | None, source: str | None = "reviews") -> dict:
    """기본 평점과 표본 수 → 규모 보정 기록(dict). 점수가 없으면 보정하지 않는다."""
    if base_score is None:
        return {
            "rule": RULE_VERSION, "sample_count": count, "sample_source": source,
            "base_score": None, "log_delta": 0.0, "gate": 0.0,
            "applied": 0.0, "final_score": None, "applied_flag": False,
        }
    raw = log_delta(count)
    gate = rating_gate(base_score)
    applied = round(raw * gate, 2)
    final = max(SCORE_MIN, min(SCORE_MAX, round(base_score + applied, 1)))
    applied = round(final - base_score, 2)   # 클램프 결과를 반영해 기록을 점수와 일치시킨다
    return {
        "rule": RULE_VERSION,
        "sample_count": count,
        "sample_source": source if count is not None else None,
        "base_score": base_score,
        "log_delta": raw,
        "gate": gate,
        "applied": applied,
        "final_score": final,
        "applied_flag": applied != 0,
    }


def fmt_count(count: int | None) -> str:
    return "미확인" if count is None else f"{count:,}"


def reason_ko(record: dict) -> str:
    """보정 한 줄(한국어) — 왜 이 값이 나왔는지."""
    if record.get("base_score") is None:
        return "표본 규모 보정: 스토어 평점 표본이 없어 사용자 축을 비워 두어 보정 대상이 아니다."
    count, source = record.get("sample_count"), record.get("sample_source")
    base, final = record["base_score"], record["final_score"]
    raw, gate, applied = record["log_delta"], record["gate"], record["applied"]
    if count is None:
        return "표본 규모 보정: 누적 표본 수를 확인하지 못해 보정하지 않았다(0)."
    label = f"GitHub stars {fmt_count(count)}" if source == "github_stars" else f"누적 표본 {fmt_count(count)}건"
    if gate == 0:
        return (f"표본 규모 보정: {label} → 로그 보정 {raw:+.2f}이지만 기본 평점 {base}가 게이트 하한(60) "
                f"미만이라 적용 0 — 낮은 평점을 표본 규모로 미화하지 않는다(최종 {final}).")
    if applied == 0 and raw == 0:
        return f"표본 규모 보정: {label} — 기준점(1만 건)과 같아 보정 0(최종 {final})."
    if applied == 0:
        return (f"표본 규모 보정: {label} → 로그 보정 {raw:+.2f} × 게이트 {gate:.2f} = 0에 수렴"
                f"(최종 {final}).")
    return (f"표본 규모 보정: {label} → 로그 보정 {raw:+.2f} × 평점 게이트 {gate:.2f} = "
            f"{applied:+.2f} ({base} → {final}).")


def reason_en(record: dict) -> str:
    if record.get("base_score") is None:
        return "Sample-scale adjustment: no store rating sample, so the user axis stays empty."
    count, source = record.get("sample_count"), record.get("sample_source")
    base, final = record["base_score"], record["final_score"]
    raw, gate, applied = record["log_delta"], record["gate"], record["applied"]
    if count is None:
        return "Sample-scale adjustment: the cumulative sample count could not be confirmed, so no adjustment was applied (0)."
    label = f"GitHub stars {fmt_count(count)}" if source == "github_stars" else f"{fmt_count(count)} cumulative ratings"
    if gate == 0:
        return (f"Sample-scale adjustment: {label} → log adjustment {raw:+.2f}, but the base rating {base} is "
                f"below the gate floor (60), so 0 applies — a low rating is not flattered by its sample size "
                f"(final {final}).")
    if applied == 0 and raw == 0:
        return f"Sample-scale adjustment: {label} — equal to the 10,000 baseline, so 0 (final {final})."
    if applied == 0:
        return (f"Sample-scale adjustment: {label} → log adjustment {raw:+.2f} × gate {gate:.2f} ≈ 0 "
                f"(final {final}).")
    return (f"Sample-scale adjustment: {label} → log adjustment {raw:+.2f} × rating gate {gate:.2f} = "
            f"{applied:+.2f} ({base} → {final}).")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 0
    count = int(float(argv[1]))
    for base in (95, 80, 72, 65, 55):
        rec = adjust(base, count)
        print(f"기본 {base:>5} · 표본 {count:>12,} → {reason_ko(rec)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
