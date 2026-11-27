#!/usr/bin/env python3
"""등대(Lighthouse) 퀘스트 데이터 빌더 — 명작 50~70종, 상징 목표 100개 이상.

원본은 `drafts/lighthouse/games-*.json`(게임 10종씩 나눈 편집 파일)이다.
이 스크립트가 한 파일로 합쳐 `data/lighthouse-quests.json` 을 만들고,
정적 배포 사본 `web/data/lighthouse-quests.json` 에 그대로 복사한다.

v2 규칙 — 난이도는 게임이 아니라 **퀘스트마다** 붙는다. 같은 게임이 같은 단계에
서로 다른 난이도의 목표를 가질 수 있고(지오메트리 대시 4단계 vs Clubstep),
목표가 곧 추첨 단위다.

검사하는 것
  · 게임 50~70종 · 퀘스트 100개 이상 · 게임마다 1~4개
  · 모든 game_id 가 search-index.json(game 도메인)에 존재
  · 무료 게임 10종 이상 · 플랫폼 값은 pc/mobile 만
  · 퀘스트마다 tier(1~3)·difficulty(chill/normal/hardcore), 게임 안에서 (tier, difficulty) 유일
  · 플랫폼(PC·모바일) × 가격(전체·무료) × 단계(1~3) × 난이도(전체·세 단계) 모든 조합에 후보 2개 이상
  · KO/EN 필수 필드가 비어 있지 않고, EN 필드에 한글이 남지 않음

사용:
  python3 projects/pharos/scripts/build_lighthouse.py
  python3 projects/pharos/scripts/build_lighthouse.py --check   # 쓰지 않고 검사만
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
DRAFT_DIR = ROOT / "drafts" / "lighthouse"
OUT = ROOT / "data" / "lighthouse-quests.json"
WEB_OUT = ROOT / "web" / "data" / "lighthouse-quests.json"
INDEX = ROOT / "web" / "data" / "search-index.json"
KOREAN = re.compile(r"[\uac00-\ud7a3]")
TIERS = (1, 2, 3)
PLATFORMS = {"pc", "mobile"}
DIFFICULTIES = ("chill", "normal", "hardcore")
DIFFICULTY_LABELS = {"chill": "편안", "normal": "보통", "hardcore": "매운맛"}
FILTER_PLATFORMS = ("all", "pc", "mobile")
FILTER_PRICES = ("all", "free")
MIN_GAMES, MAX_GAMES = 50, 70
MIN_QUESTS, MIN_FREE_GAMES = 100, 10
MIN_PER_COMBO = 2
QUEST_FIELDS = ("title_ko", "title_en", "desc_ko", "desc_en", "tip_ko", "tip_en", "est_time_ko", "est_time_en")

META = {
    "schema_version": "2.0.0",
    "title_ko": "🚨 등대 — 명작 {games}종, 상징 목표 {quests}개",
    "title_en": "🚨 Lighthouse — {games} masterworks, {quests} iconic goals",
    "note_ko": "등대는 플랫폼·가격·시간·난이도를 한 단계씩 고르면, 파로스가 고른 명작 하나와 그 안의 상징적인 목표를 비춰 준다. 목표마다 난이도가 다르고, 한 번 받은 목표는 완료하거나 건너뛰기 전까지 그대로 유지된다.",
    "note_en": "Pick platform, price, length and difficulty one step at a time, and the Lighthouse shines on one hand-picked game with an iconic goal inside it. Each goal carries its own difficulty, and a drawn goal stays fixed until you complete it or skip it.",
    "tiers": [
        {
            "tier": 1,
            "label_ko": "1단계 · 짧게",
            "label_en": "Tier 1 · Short",
            "window_ko": "1~5시간",
            "window_en": "1–5 hours",
            "hint_ko": "한 번의 결전·한 판의 증명",
            "hint_en": "One decisive fight, one run, one proof",
        },
        {
            "tier": 2,
            "label_ko": "2단계 · 제대로",
            "label_en": "Tier 2 · Proper",
            "window_ko": "엔딩까지 · 며칠",
            "window_en": "To the ending · days",
            "hint_ko": "일주일, 하나의 완주",
            "hint_en": "A week, one full run",
        },
        {
            "tier": 3,
            "label_ko": "3단계 · 길게",
            "label_en": "Tier 3 · Long",
            "window_ko": "수십 시간",
            "window_en": "Dozens of hours",
            "hint_ko": "수십 시간, 인생에 남는 한 컷",
            "hint_en": "Dozens of hours, one scene you keep",
        },
    ],
}


def load_games() -> list[dict]:
    games: list[dict] = []
    for path in sorted(glob.glob(str(DRAFT_DIR / "games-*.json"))):
        games.extend(json.loads(Path(path).read_text(encoding="utf-8")))
    return games


def quest_pool(games: list[dict]):
    """(게임, 퀘스트) 쌍을 평평하게 편다 — 추첨·필터의 단위는 게임이 아니라 퀘스트다."""
    for game in games:
        for quest in game.get("quests") or []:
            yield game, quest


def combo_count(games: list[dict], platform: str, price: str, tier: str, difficulty: str) -> int:
    n = 0
    for game, quest in quest_pool(games):
        if price == "free" and not game.get("free_to_play"):
            continue
        if platform != "all" and platform not in (game.get("platforms") or []):
            continue
        if tier != "all" and quest.get("tier") != int(tier):
            continue
        if difficulty != "all" and quest.get("difficulty") != difficulty:
            continue
        n += 1
    return n


def validate(games: list[dict]) -> list[str]:
    errs: list[str] = []
    index = {row["id"]: row for row in json.loads(INDEX.read_text(encoding="utf-8"))["items"]}
    seen = set()
    free = 0
    quests_total = 0
    by_difficulty = {d: 0 for d in DIFFICULTIES}
    by_tier = {t: 0 for t in TIERS}
    if not MIN_GAMES <= len(games) <= MAX_GAMES:
        errs.append(f"게임 {len(games)}종 — {MIN_GAMES}~{MAX_GAMES}종이어야 함")
    for game in games:
        gid = game.get("game_id")
        rec = index.get(gid)
        if not rec:
            errs.append(f"{gid}: search-index.json 에 없음")
            continue
        if rec.get("domain") != "game":
            errs.append(f"{gid}: game 도메인이 아님({rec.get('domain')})")
        if gid in seen:
            errs.append(f"{gid}: game_id 중복")
        seen.add(gid)
        if not isinstance(game.get("free_to_play"), bool):
            errs.append(f"{gid}: free_to_play 가 bool 이 아님")
        if game.get("free_to_play"):
            free += 1
        platforms = game.get("platforms") or []
        if not platforms or set(platforms) - PLATFORMS:
            errs.append(f"{gid}: platforms 값 오류 {platforms}")
        quests = game.get("quests") or []
        if not 1 <= len(quests) <= 6:
            errs.append(f"{gid}: 퀘스트 {len(quests)}개 — 게임마다 1~6개여야 함")
        seen_keys = set()
        for quest in quests:
            key = (quest.get("tier"), quest.get("difficulty"))
            if quest.get("tier") not in TIERS:
                errs.append(f"{gid}: tier 는 1·2·3 중 하나여야 함({quest.get('tier')})")
            if quest.get("difficulty") not in DIFFICULTIES:
                errs.append(f"{gid}: difficulty 는 chill/normal/hardcore 중 하나여야 함({quest.get('difficulty')})")
            if key in seen_keys:
                errs.append(f"{gid}: (tier {key[0]}, {key[1]}) 목표가 중복")
            seen_keys.add(key)
            quests_total += 1
            by_difficulty[quest.get("difficulty")] = by_difficulty.get(quest.get("difficulty"), 0) + 1
            by_tier[quest.get("tier")] = by_tier.get(quest.get("tier"), 0) + 1
            for field in QUEST_FIELDS:
                value = quest.get(field)
                if not isinstance(value, str) or not value.strip():
                    errs.append(f"{gid} tier {quest.get('tier')} {quest.get('difficulty')}: {field} 비어 있음")
                    continue
                if field.endswith("_en") and KOREAN.search(value):
                    errs.append(f"{gid} tier {quest.get('tier')} {quest.get('difficulty')}: {field} 에 한글 — {value[:40]}")
            if len(quest.get("title_ko", "")) > 70:
                errs.append(f"{gid} tier {quest.get('tier')} {quest.get('difficulty')}: title_ko 70자 초과")
            if len(quest.get("title_en", "")) > 90:
                errs.append(f"{gid} tier {quest.get('tier')} {quest.get('difficulty')}: title_en 90자 초과")
    if quests_total < MIN_QUESTS:
        errs.append(f"퀘스트 {quests_total}개 — {MIN_QUESTS}개 이상이어야 함")
    if free < MIN_FREE_GAMES:
        errs.append(f"무료 게임 {free}종 — {MIN_FREE_GAMES}종 이상이어야 함")
    for platform in FILTER_PLATFORMS:
        for price in FILTER_PRICES:
            for tier in ("all",) + TIERS:
                for difficulty in ("all",) + DIFFICULTIES:
                    n = combo_count(games, platform, price, str(tier), difficulty)
                    if n < MIN_PER_COMBO:
                        errs.append(
                            f"후보 {n}개 조합: 플랫폼={platform} 가격={price} 단계={tier} 난이도={difficulty}"
                        )
    for difficulty in DIFFICULTIES:
        if by_difficulty[difficulty] < 8:
            errs.append(f"{DIFFICULTY_LABELS[difficulty]} 목표 {by_difficulty[difficulty]}개 — 8개 이상이어야 함")
    return errs


def build(games: list[dict]) -> dict:
    quests_total = sum(len(game["quests"]) for game in games)
    order = {tier: i for i, tier in enumerate(TIERS)}
    diff_order = {d: i for i, d in enumerate(DIFFICULTIES)}
    counts = {
        "games": len(games),
        "quests": quests_total,
        "free_to_play": sum(1 for game in games if game["free_to_play"]),
        "premium": sum(1 for game in games if not game["free_to_play"]),
        "by_difficulty": {
            d: sum(1 for _g, q in quest_pool(games) if q["difficulty"] == d) for d in DIFFICULTIES
        },
        "by_tier": {str(t): sum(1 for _g, q in quest_pool(games) if q["tier"] == t) for t in TIERS},
    }
    meta = dict(META)
    meta["title_ko"] = META["title_ko"].format(**counts)
    meta["title_en"] = META["title_en"].format(**counts)
    payload = {
        **meta,
        "counts": counts,
        "games": [
            {
                "game_id": game["game_id"],
                "free_to_play": game["free_to_play"],
                "platforms": game["platforms"],
                "quests": sorted(
                    game["quests"], key=lambda q: (order[q["tier"]], diff_order[q["difficulty"]])
                ),
            }
            for game in games
        ],
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="파일을 쓰지 않고 최신 여부만 확인")
    args = parser.parse_args()

    games = load_games()
    errs = validate(games)
    if errs:
        print(f"등대 데이터 검사: FAIL — {len(errs)}건")
        for err in errs:
            print(f"  × {err}")
        return 1
    payload = build(games)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    counts = payload["counts"]
    print(f"등대 데이터 검사: PASS — 게임 {counts['games']}종(무료 {counts['free_to_play']}) · "
          f"퀘스트 {counts['quests']}개 · 난이도 {counts['by_difficulty']}")
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
        web = WEB_OUT.read_text(encoding="utf-8") if WEB_OUT.exists() else None
        if current != text or web != text:
            print("  × data/lighthouse-quests.json 또는 웹 사본이 원본과 다름 — 빌드 필요")
            return 1
        print("  - data·web 사본이 편집 원본과 일치")
        return 0
    OUT.write_text(text, encoding="utf-8")
    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    WEB_OUT.write_text(text, encoding="utf-8")
    print(f"  → {OUT.relative_to(ROOT.parent.parent)}")
    print(f"  → {WEB_OUT.relative_to(ROOT.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
