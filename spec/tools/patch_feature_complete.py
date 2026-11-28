#!/usr/bin/env python3
"""2단계 — 완결형 싱글플레이 패키지 게임의 `stale_over_12m` 거름 해소.

대상 선정(근거 우선)
  · `review_tier=auto_fact` · 하드 필터에서 **오직 `stale_over_12m` 하나만** fail 인 게임
  · Steam 상점 분류가 **Single-player 단독**(멀티플레이·협동·PvP 분류 없음) — `steam-categories.json`(등급 A)
  · 예외(등급 B): 온라인 협동이 선택 모드일 뿐 본편이 오프라인 싱글 캠페인인 완결작 — C U R A T E D

하는 일
  1) `maintenance_status = feature_complete` + `maintenance_note`(판단 근거·등급) 기록
  2) `stale_over_12m` 티어 기록을 `exempt` 로 바꾸고 사유를 남긴다(원자료 flags 는 사실 그대로)
  3) `auto_collect.finalize_item` 으로 티어·대표 판정을 계산 규칙대로 다시 맞춘다
  4) 판정 문장(one_liner·reasons·condition_notes)과 영문 오버레이(data/en.json)를 새 판정에 맞춘다
  5) `data/{domain}/{arena}.json` 에 다시 쓴다

실행
  python3 projects/pharos/drafts/bulk5-2026-11-26/patch_feature_complete.py --check
  python3 projects/pharos/drafts/bulk5-2026-11-26/patch_feature_complete.py --write
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "schema"))

import auto_collect as ac  # noqa: E402
import validate as vlib  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = ROOT / "data"
EN_PATH = DATA / "en.json"

ONLINE_CATS = {"Multiplayer", "Online PvP", "Online Co-op", "Co-op", "PvP", "MMO",
               "Cross-Platform Multiplayer", "Shared/Split Screen Co-op", "LAN Co-op", "LAN PvP"}
# 온라인 협동이 선택 모드이고 본편이 오프라인 싱글 캠페인인 완결작 — 예외로 인정(등급 B)
CURATED = {
    # 8차 배치 — 본편이 끝난 1회 구매작이고 온라인은 선택 모드(등급 B). 출시 후 추가 콘텐츠가 끝나
    # 12개월 넘게 새 소식이 없는 것은 방치가 아니라 완결로 본다.
    "half-life": "1998년작 1인칭 슈터로 본편 캠페인이 완결됐고, 데스매치 등 온라인 모드는 본편과 별개의 선택 모드다",
    "far-cry-3": "본편 캠페인이 완결된 1회 구매작이고 협동은 별도 모드로만 붙는다",
    "battletech": "2018년작 턴제 전술 게임으로 본편 캠페인과 DLC가 완결됐고 PvP는 선택 모드다",
    "nioh-complete-edition": "본편과 DLC가 모두 포함된 완결판이고 협동·PvP는 선택 모드다",
    "salt-and-sacrifice": "본편 캠페인이 완결된 1회 구매작이고 협동·PvP는 선택 모드다",
    "streets-of-rogue": "본편이 완결된 1인 플레이 로그라이크이고 협동·PvP는 선택 모드다",
    "the-casting-of-frank-stone": "한 편으로 끝나는 내러티브 호러이고 협동은 선택 모드다",
    "beyond-two-souls": "한 편으로 끝나는 내러티브 작품이고 협동은 선택 모드다",
    "dirt-5": "커리어가 완결된 1회 구매 레이싱 게임이고 온라인 대전은 선택 모드다",
    "need-for-speed-unbound": "스토리 커리어와 차량 콘텐츠가 완결됐고 온라인은 선택 모드다",
    "tekken-7": "본편과 시즌 패스 DLC로 로스터가 완결된 1회 구매 격투 게임이고, 온라인 대전은 서비스 중인 선택 모드다",
    "dark-souls-iii": "본편과 DLC(Ashes of Ariandel·The Ringed City)로 완결됐고, 온라인 협동·침입은 선택 모드라 "
                      "오프라인에서도 싱글 캠페인을 끝까지 진행할 수 있다",
    "dark-souls-2-sotfs": "Scholar of the First Sin로 본편·DLC가 완결됐고, 온라인 협동은 선택 모드다",
}
KIND_KO = {
    "sp_only": "Steam 상점 분류가 Single-player 단독",
    "sp_curated": "본편이 오프라인 싱글 캠페인, 온라인 협동은 선택",
}
KIND_EN = {
    "sp_only": "Steam store lists Single-player only; no multiplayer, co-op or PvP categories, and the main game is "
               "a finished one-time purchase",
    "sp_curated": "the main game is an offline single-player campaign complete in its own right, with online co-op "
                  "only as an optional mode",
}
BASIS_EN = {
    "dark-souls-iii": "the base game and its DLC (Ashes of Ariandel, The Ringed City) are finished, and online co-op "
                      "or invasion is optional, so the campaign can be played offline to the end",
    "dark-souls-2-sotfs": "Scholar of the First Sin completes the base game and DLC, and online co-op is optional",
}


def load_categories() -> dict[str, dict]:
    path = HERE / "steam-categories.json"
    if not path.exists():
        raise SystemExit("steam-categories.json 이 없다 — check_steam_categories.py 를 먼저 실행한다.")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {row["id"]: row for row in raw.values()}


def stale_blocked(item: dict) -> bool:
    fails = set()
    for tier in item.get("tiers") or []:
        for key, rec in (tier.get("hard_filters") or {}).items():
            if rec.get("status") == "fail":
                fails.add(key)
    return fails == {"stale_over_12m"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    cats = load_categories()
    bundle = json.loads(EN_PATH.read_text(encoding="utf-8"))
    changed, skipped = [], []
    for path in sorted(DATA.glob("game/*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        touched = False
        for item in rows:
            iid = item["id"]
            cat = cats.get(iid)
            if item.get("review_tier") != "auto_fact" or not stale_blocked(item):
                continue
            if item.get("maintenance_status") == "feature_complete":
                continue
            sp_only = bool(cat) and "Single-player" in cat["categories"] and not (set(cat["categories"]) & ONLINE_CATS)
            if iid in CURATED:
                kind = "sp_curated"
                basis = CURATED[iid]
            elif sp_only:
                kind = "sp_only"
                basis = "본편이 완결된 1회 구매 패키지이며 온라인 모드가 없다"
            else:
                skipped.append((iid, "싱글플레이 전용 근거 없음" if cat else "Steam 분류 미확인"))
                continue
            if any("얼리 액세스" in json.dumps(t, ensure_ascii=False) for t in item["tiers"]):
                skipped.append((iid, "얼리 액세스 표기"))
                continue

            stale = (item.get("flags") or {}).get("stale_over_12m") or {}
            m = re.search(r"(\d{4}-\d{2}-\d{2})", stale.get("note") or "")
            last = m.group(1) if m else "미상"
            days = ac.days_since(last) if m else None
            before = item["verdict"]["overall"]
            grade = "A" if kind == "sp_only" else "B"

            item["maintenance_status"] = "feature_complete"
            item["maintenance_note"] = (
                f"완결형 싱글플레이 패키지 — {KIND_KO[kind]}({basis}). "
                f"마지막 업데이트 {last}{f'({days}일 전)' if days else ''} 이후 추가 콘텐츠가 없으나 "
                "구독·서버 없이 본편이 완결된 1회 구매작이라 완료로 판단한다"
                f"(근거 등급 {grade})."
            )
            for tier in item["tiers"]:
                hf = tier["hard_filters"].get("stale_over_12m") or {}
                if hf.get("status") == "fail":
                    hf["status"] = "exempt"
                    hf["note"] = (
                        f"{last} 이후 12개월 넘게 새 공지·릴리스가 없는 것은 사실이나, "
                        "완결형 싱글플레이 패키지(maintenance_status=feature_complete)로 면제한다."
                    )
            item = ac.finalize_item(item)
            overall = item["verdict"]["overall"]
            tier = next(t for t in item["tiers"] if t["tier_id"] == item["verdict"]["tier_of_record"])
            score = vlib.weighted_score(item, tier)
            label = {"recommend": "추천", "conditional": "조건부", "avoid": "거름"}[overall]

            item["verdict"]["one_liner"] = (
                f"{label} — {tier.get('price', {}).get('display') or '가격 미표기'} · "
                f"마지막 업데이트 {last}. 완결작 면제 적용, 자동 수집 1차 판정."
            )
            reasons = [r for r in item["verdict"].get("reasons") or [] if "1차 판정" not in r]
            reasons.append(
                "완결형 싱글플레이 패키지로 maintenance_status=feature_complete — 12개월 공백은 판정에서 면제"
                f"(근거 등급 {grade})."
            )
            item["verdict"]["reasons"] = reasons
            notes = [n for n in item["verdict"].get("condition_notes") or []
                     if "심층 검수에서 maintenance_status" not in n]
            notes.append(
                f"완결작 면제는 {'Steam 상점 분류(Single-player 단독)' if grade == 'A' else '공개 정보(온라인은 선택 모드)'}"
                f"에 근거한 자동 판단(등급 {grade})이다. 서버가 닫히거나 치명적 버그가 방치되면 재검토한다."
            )
            item["verdict"]["condition_notes"] = notes

            en = (bundle.get("items") or {}).get(iid)
            if en:
                en["maintenance_note"] = (
                    f"Finished single-player package — {KIND_EN[kind]}"
                    + (f" ({BASIS_EN[iid]})" if iid in BASIS_EN else "") + ". "
                    f"No content has been added since the last update on {last}, but the game is a one-time "
                    f"purchase complete without a subscription or server, so it is treated as finished "
                    f"(evidence grade {grade})."
                )
                en_tier = next((t for t in en.get("tiers") or []
                                if t.get("tier_id") == item["verdict"]["tier_of_record"]), None)
                en_price = ((en_tier or {}).get("price") or {}).get("display") or "price not listed"
                en["verdict"]["one_liner"] = (
                    f"{ {'recommend': 'Recommended', 'conditional': 'Conditional', 'avoid': 'Filtered out'}[overall] } — "
                    f"{en_price} · last update {last}. "
                    "Feature-complete exemption applied; first-pass auto assessment."
                )
                en_reasons = [r for r in en["verdict"].get("reasons") or [] if "First-pass verdict" not in r]
                en_reasons.append(
                    "Finished single-player package, maintenance_status=feature_complete — the 12-month gap is "
                    f"exempted from the verdict (evidence grade {grade})."
                )
                en["verdict"]["reasons"] = en_reasons
                en_notes = [n for n in en["verdict"].get("condition_notes") or []
                            if "the deep review confirms maintenance_status" not in n]
                en_notes.append(
                    "The feature-complete exemption is an automated judgement from "
                    f"{'the Steam store category (Single-player only)' if grade == 'A' else 'public information (online is optional)'} "
                    f"(grade {grade}). It is revisited if servers close or critical bugs are left unfixed."
                )
                en["verdict"]["condition_notes"] = en_notes
                for t in en.get("tiers") or []:
                    hf = (t.get("hard_filters") or {}).get("stale_over_12m")
                    if hf:
                        hf["note"] = (
                            f"No new announcement or release for over 12 months since {last} is a fact, "
                            "but it is exempted as a finished single-player package "
                            "(maintenance_status=feature_complete)."
                        )

            changed.append((iid, path.name, before, overall, score, kind))
            touched = True
        if touched and args.write:
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    if args.write:
        EN_PATH.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{'변경' if args.write else '검사'} {len(changed)}건 · 건너뜀 {len(skipped)}건")
    for iid, fname, before, after, score, kind in sorted(changed, key=lambda r: r[4] or 0, reverse=True):
        print(f"  {iid:<36} {fname:<28} {before:>11} → {after:<11} {score:<6} {kind}")
    print(f"\n건너뜀 {len(skipped)}건")
    for iid, why in skipped:
        print(f"  ↷ {iid}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
