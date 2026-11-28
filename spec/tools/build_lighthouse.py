#!/usr/bin/env python3
"""등대(Lighthouse) 퀘스트 데이터 빌더 v3 — 4분야(게임·애니·영화·만화) + 전체 랜덤.

원본은 `drafts/lighthouse/` 의 편집 파일이다.
  · games-*.json      게임 10종씩 (`game_id` · `free_to_play` · `platforms` · `quests`)
  · media-anime.json  애니 25종 (`item_id` · `category: anime` · `quests`)
  · media-movie.json  영화 25종 (category: movie)
  · media-manga.json  만화 25종 (category: manga)

이 스크립트가 한 파일로 합쳐 `data/lighthouse-quests.json` 을 만들고,
정적 배포 사본 `web/data/lighthouse-quests.json` 에 그대로 복사한다.

v3 규칙
  · 추첨 단위는 게임이 아니라 **퀘스트**다(같은 작품이 같은 단계에 다른 난이도의 목표를 가질 수 있다).
  · 분야마다 흐름이 다르다 — 게임은 플랫폼·가격을 묻고, 애니·영화·만화·전체 랜덤은 묻지 않는다.
  · 단계(tier) 문구는 분야마다 다르다(게임 1~5시간 / 애니 한 편·한 시즌 / 영화 한 편·트릴로지 / 만화 1~5권·완독).

검사하는 것
  · 게임 50~70종 · 퀘스트 100개 이상 · 무료 게임 10종 이상
  · 애니·영화·만화 각 25종 · 분야별 퀘스트 40개 이상
  · 모든 id 가 search-index.json 의 실제 카탈로그 항목과 일치(게임=game, 미디어=media/카테고리 일치)
  · 퀘스트마다 tier(1~3)·difficulty(chill/normal/hardcore), 작품 안에서 (tier, difficulty) 유일
  · 게임: 플랫폼(PC·모바일) × 가격(전체·무료) × 단계 × 난이도 모든 조합에 후보 2개 이상
  · 미디어·전체 랜덤: 단계 × 난이도 모든 조합에 후보 2개 이상
  · KO/EN 필수 필드가 비어 있지 않고, EN 필드에 한글이 남지 않음
  · counts 가 실제 집계와 일치

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
MEDIA_CATEGORIES = ("anime", "movie", "manga")
MEDIA_FILES = {"anime": "media-anime.json", "movie": "media-movie.json", "manga": "media-manga.json"}
MEDIA_MIN_ITEMS, MEDIA_MAX_ITEMS = 20, 40
MEDIA_MIN_QUESTS = 40
QUEST_FIELDS = ("title_ko", "title_en", "desc_ko", "desc_en", "tip_ko", "tip_en", "est_time_ko", "est_time_en")

CATEGORIES = [
    {
        "id": "game",
        "label_ko": "🎮 게임",
        "label_en": "🎮 Games",
        "badge_ko": "🎮 게임",
        "badge_en": "🎮 Game",
        "sub_ko": "플랫폼·가격·시간·난이도",
        "sub_en": "Platform, price, length, difficulty",
        "hint_ko": "PC·모바일, 무료 포함 여부까지 묻습니다",
        "hint_en": "PC or mobile, free or paid — you choose",
        "has_platform": True,
    },
    {
        "id": "anime",
        "label_ko": "📺 애니",
        "label_en": "📺 Anime",
        "badge_ko": "📺 애니",
        "badge_en": "📺 Anime",
        "sub_ko": "한 편 · 한 시즌 · 정주행",
        "sub_en": "A film, a season, a full run",
        "hint_ko": "극장판 한 편부터 장편 정주행까지",
        "hint_en": "From one film to a hundred-episode run",
        "has_platform": False,
    },
    {
        "id": "movie",
        "label_ko": "🎬 영화",
        "label_en": "🎬 Movies",
        "badge_ko": "🎬 영화",
        "badge_en": "🎬 Movie",
        "sub_ko": "한 편 · 두 편 · 마라톤",
        "sub_en": "One film, two films, a marathon",
        "hint_ko": "오늘 한 편부터 트릴로지 마라톤까지",
        "hint_en": "One film tonight to a full trilogy day",
        "has_platform": False,
    },
    {
        "id": "manga",
        "label_ko": "📖 만화",
        "label_en": "📖 Manga",
        "badge_ko": "📖 만화",
        "badge_en": "📖 Manga",
        "sub_ko": "단편 · 한 아크 · 완독",
        "sub_en": "A short run, one arc, a full read",
        "hint_ko": "1~5권부터 30권 완독까지",
        "hint_en": "From five volumes to a thirty-volume read",
        "has_platform": False,
    },
    {
        "id": "all",
        "label_ko": "🎲 상관없이",
        "label_en": "🎲 Surprise me",
        "badge_ko": "🎲 전체",
        "badge_en": "🎲 Any",
        "sub_ko": "전체 랜덤",
        "sub_en": "All four, one draw",
        "hint_ko": "게임·애니·영화·만화에서 한 목표",
        "hint_en": "One goal from all four fields",
        "has_platform": False,
    },
]

TIER_META = {
    "game": [
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
    "anime": [
        {
            "tier": 1,
            "label_ko": "1단계 · 한 편",
            "label_en": "Tier 1 · One film",
            "window_ko": "극장판 한 편 · 1~3시간",
            "window_en": "One film · 1–3 hours",
            "hint_ko": "오늘 밤 한 편의 여운",
            "hint_en": "One film, one evening",
        },
        {
            "tier": 2,
            "label_ko": "2단계 · 한 시즌",
            "label_en": "Tier 2 · One season",
            "window_ko": "12~26화 · 며칠",
            "window_en": "12–26 episodes · days",
            "hint_ko": "한 주, 한 작품 완주",
            "hint_en": "A week, one season",
        },
        {
            "tier": 3,
            "label_ko": "3단계 · 정주행",
            "label_en": "Tier 3 · Binge",
            "window_ko": "50화 이상 · 수십 시간",
            "window_en": "50+ episodes · dozens of hours",
            "hint_ko": "수십 시간, 통째로 건너가기",
            "hint_en": "Dozens of hours, all at once",
        },
    ],
    "movie": [
        {
            "tier": 1,
            "label_ko": "1단계 · 한 편",
            "label_en": "Tier 1 · One film",
            "window_ko": "2시간 안팎 · 한 번",
            "window_en": "About two hours · one sitting",
            "hint_ko": "오늘 밤, 한 편",
            "hint_en": "Tonight, one film",
        },
        {
            "tier": 2,
            "label_ko": "2단계 · 두 편",
            "label_en": "Tier 2 · Two films",
            "window_ko": "4~6시간 · 주말",
            "window_en": "4–6 hours · a weekend",
            "hint_ko": "주말 하나, 두 편의 대화",
            "hint_en": "One weekend, two films in conversation",
        },
        {
            "tier": 3,
            "label_ko": "3단계 · 마라톤",
            "label_en": "Tier 3 · Marathon",
            "window_ko": "세 편 이상 · 7시간+",
            "window_en": "Three films or more · 7+ hours",
            "hint_ko": "하루를 통째로, 세계 하나",
            "hint_en": "A whole day inside one world",
        },
    ],
    "manga": [
        {
            "tier": 1,
            "label_ko": "1단계 · 단편",
            "label_en": "Tier 1 · Short run",
            "window_ko": "1~5권 · 2~4시간",
            "window_en": "1–5 volumes · 2–4 hours",
            "hint_ko": "한자리에서 끝나는 한 권의 충격",
            "hint_en": "One sitting, one volume's shock",
        },
        {
            "tier": 2,
            "label_ko": "2단계 · 한 아크",
            "label_en": "Tier 2 · One arc",
            "window_ko": "10~20권 · 일주일",
            "window_en": "10–20 volumes · a week",
            "hint_ko": "일주일, 한 아크 완독",
            "hint_en": "A week, one arc",
        },
        {
            "tier": 3,
            "label_ko": "3단계 · 완독",
            "label_en": "Tier 3 · Full read",
            "window_ko": "30권 이상 · 수십 시간",
            "window_en": "30+ volumes · dozens of hours",
            "hint_ko": "서가 하나를 통째로",
            "hint_en": "A whole shelf, read through",
        },
    ],
    "all": [
        {
            "tier": 1,
            "label_ko": "1단계 · 가볍게",
            "label_en": "Tier 1 · Light",
            "window_ko": "한 편 · 한 판 · 몇 시간",
            "window_en": "One film, one run · hours",
            "hint_ko": "오늘 안에 끝내는 한 가지",
            "hint_en": "Something finished tonight",
        },
        {
            "tier": 2,
            "label_ko": "2단계 · 제대로",
            "label_en": "Tier 2 · Proper",
            "window_ko": "며칠 · 한 작품",
            "window_en": "Days · one work",
            "hint_ko": "한 주, 하나의 완주",
            "hint_en": "A week, one full run",
        },
        {
            "tier": 3,
            "label_ko": "3단계 · 길게",
            "label_en": "Tier 3 · Long",
            "window_ko": "수십 시간 · 정주행",
            "window_en": "Dozens of hours · binge",
            "hint_ko": "인생에 남는 한 컷",
            "hint_en": "One scene you keep",
        },
    ],
}

META = {
    "schema_version": "3.0.0",
    "title_ko": "🚨 등대 — 명작 {items}종, 상징 목표 {quests}개",
    "title_en": "🚨 Lighthouse — {items} masterworks, {quests} iconic goals",
    "note_ko": "등대는 분야와 시간·난이도를 한 단계씩 고르면, 파로스가 고른 명작 하나와 그 안의 상징적인 목표를 비춰 준다. 게임은 플랫폼과 가격까지 묻고, 애니·영화·만화는 분량만 고르면 된다. 한 번 받은 목표는 완료하거나 건너뛰기 전까지 그대로 유지된다.",
    "note_en": "Pick a field, a length and a weight one step at a time, and the Lighthouse shines on one hand-picked work with an iconic goal inside it. Games also ask platform and price; anime, movies and manga ask only how much you want. A drawn goal stays fixed until you complete it or skip it.",
}


def load_games() -> list[dict]:
    games: list[dict] = []
    for path in sorted(glob.glob(str(DRAFT_DIR / "games-*.json"))):
        games.extend(json.loads(Path(path).read_text(encoding="utf-8")))
    return games


def load_media() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for category, name in MEDIA_FILES.items():
        path = DRAFT_DIR / name
        if not path.exists():
            raise SystemExit(f"미디어 편집 파일 없음: {path}")
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            row["category"] = category
        out[category] = rows
    return out


def all_entries(games: list[dict], media: dict[str, list[dict]]) -> list[dict]:
    """추첨 단위는 작품이 아니라 퀘스트 — 모든 분야의 항목을 같은 모양으로 편다."""
    entries = []
    for game in games:
        entries.append(
            {
                "id": game["game_id"],
                "category": "game",
                "free_to_play": game["free_to_play"],
                "platforms": game["platforms"],
                "quests": game["quests"],
            }
        )
    for category in MEDIA_CATEGORIES:
        for row in media.get(category, []):
            entries.append(
                {"id": row["item_id"], "category": category, "free_to_play": None, "platforms": [], "quests": row["quests"]}
            )
    return entries


def quest_pool(entries: list[dict], category: str = "all"):
    for entry in entries:
        if category != "all" and entry["category"] != category:
            continue
        for quest in entry.get("quests") or []:
            yield entry, quest


def combo_count(entries: list[dict], category: str, platform: str, price: str, tier, difficulty) -> int:
    n = 0
    for entry, quest in quest_pool(entries, category):
        if category == "game":
            if price == "free" and not entry.get("free_to_play"):
                continue
            if platform != "all" and platform not in (entry.get("platforms") or []):
                continue
        if tier != "all" and quest.get("tier") != int(tier):
            continue
        if difficulty != "all" and quest.get("difficulty") != difficulty:
            continue
        n += 1
    return n


def _check_quests(entry: dict, label: str, errs: list[str]) -> list[dict]:
    quests = entry.get("quests") or []
    if not 1 <= len(quests) <= 6:
        errs.append(f"{label}: 퀘스트 {len(quests)}개 — 작품마다 1~6개여야 함")
    seen_keys = set()
    for quest in quests:
        key = (quest.get("tier"), quest.get("difficulty"))
        if quest.get("tier") not in TIERS:
            errs.append(f"{label}: tier 는 1·2·3 중 하나여야 함({quest.get('tier')})")
        if quest.get("difficulty") not in DIFFICULTIES:
            errs.append(f"{label}: difficulty 는 chill/normal/hardcore 중 하나여야 함({quest.get('difficulty')})")
        if key in seen_keys:
            errs.append(f"{label}: (tier {key[0]}, {key[1]}) 목표가 중복")
        seen_keys.add(key)
        for field in QUEST_FIELDS:
            value = quest.get(field)
            if not isinstance(value, str) or not value.strip():
                errs.append(f"{label} tier {quest.get('tier')} {quest.get('difficulty')}: {field} 비어 있음")
                continue
            if field.endswith("_en") and KOREAN.search(value):
                errs.append(f"{label} tier {quest.get('tier')} {quest.get('difficulty')}: {field} 에 한글 — {value[:40]}")
        if len(quest.get("title_ko", "")) > 70:
            errs.append(f"{label} tier {quest.get('tier')} {quest.get('difficulty')}: title_ko 70자 초과")
        if len(quest.get("title_en", "")) > 90:
            errs.append(f"{label} tier {quest.get('tier')} {quest.get('difficulty')}: title_en 90자 초과")
    return quests


def validate(games: list[dict], media: dict[str, list[dict]]) -> list[str]:
    errs: list[str] = []
    index_rows = json.loads(INDEX.read_text(encoding="utf-8"))["items"]
    index = {row["id"]: row for row in index_rows}
    domain_cats: dict[str, set[str]] = {}
    for row in index_rows:
        domain_cats.setdefault(row.get("domain"), set()).add(row.get("category"))
    seen = set()
    free = 0
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
            errs.append(f"{gid}: id 중복")
        seen.add(gid)
        if not isinstance(game.get("free_to_play"), bool):
            errs.append(f"{gid}: free_to_play 가 bool 이 아님")
        if game.get("free_to_play"):
            free += 1
        platforms = game.get("platforms") or []
        if not platforms or set(platforms) - PLATFORMS:
            errs.append(f"{gid}: platforms 값 오류 {platforms}")
        _check_quests(game, gid, errs)

    for category in MEDIA_CATEGORIES:
        rows = media.get(category) or []
        if not MEDIA_MIN_ITEMS <= len(rows) <= MEDIA_MAX_ITEMS:
            errs.append(f"{category} {len(rows)}종 — {MEDIA_MIN_ITEMS}~{MEDIA_MAX_ITEMS}종이어야 함")
        quests_total = 0
        for row in rows:
            iid = row.get("item_id")
            rec = index.get(iid)
            if not rec:
                errs.append(f"{category}/{iid}: search-index.json 에 없음")
                continue
            if rec.get("domain") != category:
                errs.append(f"{category}/{iid}: {category} 도메인이 아님({rec.get('domain')})")
            elif rec.get("category") not in domain_cats.get(category, set()):
                errs.append(f"{category}/{iid}: 대분류 {rec.get('category')} 가 {category} 도메인 소속이 아님")
            if iid in seen:
                errs.append(f"{category}/{iid}: id 중복")
            seen.add(iid)
            quests_total += len(_check_quests(row, f"{category}/{iid}", errs))
        if quests_total < MEDIA_MIN_QUESTS:
            errs.append(f"{category} 퀘스트 {quests_total}개 — {MEDIA_MIN_QUESTS}개 이상이어야 함")

    entries = all_entries(games, media)

    # 게임: 플랫폼 × 가격 × 단계 × 난이도
    for platform in FILTER_PLATFORMS:
        for price in FILTER_PRICES:
            for tier in ("all",) + TIERS:
                for difficulty in ("all",) + DIFFICULTIES:
                    n = combo_count(entries, "game", platform, price, str(tier), difficulty)
                    if n < MIN_PER_COMBO:
                        errs.append(f"게임 후보 {n}개 조합: 플랫폼={platform} 가격={price} 단계={tier} 난이도={difficulty}")

    # 미디어 각 분야 + 전체 랜덤: 단계 × 난이도
    for category in MEDIA_CATEGORIES + ("all",):
        for tier in TIERS:
            for difficulty in DIFFICULTIES:
                n = combo_count(entries, category, "all", "all", tier, difficulty)
                if n < MIN_PER_COMBO:
                    errs.append(f"{category} 후보 {n}개 조합: 단계={tier} 난이도={difficulty}")

    for category in ("game",) + MEDIA_CATEGORIES:
        for difficulty in DIFFICULTIES:
            n = sum(1 for _e, q in quest_pool(entries, category) if q["difficulty"] == difficulty)
            if n < 8:
                errs.append(f"{category} {DIFFICULTY_LABELS[difficulty]} 목표 {n}개 — 8개 이상이어야 함")
    return errs


def build(games: list[dict], media: dict[str, list[dict]]) -> dict:
    entries = all_entries(games, media)
    order = {tier: i for i, tier in enumerate(TIERS)}
    diff_order = {d: i for i, d in enumerate(DIFFICULTIES)}

    def sort_quests(quests: list[dict]) -> list[dict]:
        return sorted(quests, key=lambda q: (order[q["tier"]], diff_order[q["difficulty"]]))

    quests_total = sum(len(e["quests"]) for e in entries)
    by_category = {}
    for category in ("game",) + MEDIA_CATEGORIES:
        rows = [e for e in entries if e["category"] == category]
        by_category[category] = {
            "items": len(rows),
            "quests": sum(len(e["quests"]) for e in rows),
        }
    counts = {
        "items": len(entries),
        "games": len(games),
        "quests": quests_total,
        "free_to_play": sum(1 for g in games if g["free_to_play"]),
        "premium": sum(1 for g in games if not g["free_to_play"]),
        "by_category": by_category,
        "by_difficulty": {d: sum(1 for _e, q in quest_pool(entries) if q["difficulty"] == d) for d in DIFFICULTIES},
        "by_tier": {str(t): sum(1 for _e, q in quest_pool(entries) if q["tier"] == t) for t in TIERS},
    }
    meta = dict(META)
    meta["title_ko"] = META["title_ko"].format(**counts)
    meta["title_en"] = META["title_en"].format(**counts)
    return {
        **meta,
        "categories": CATEGORIES,
        "tiers": TIER_META,
        "counts": counts,
        "games": [
            {
                "game_id": game["game_id"],
                "free_to_play": game["free_to_play"],
                "platforms": game["platforms"],
                "quests": sort_quests(game["quests"]),
            }
            for game in games
        ],
        "media": {
            category: [
                {"item_id": row["item_id"], "category": category, "quests": sort_quests(row["quests"])}
                for row in media.get(category, [])
            ]
            for category in MEDIA_CATEGORIES
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="파일을 쓰지 않고 최신 여부만 확인")
    args = parser.parse_args()

    games = load_games()
    media = load_media()
    errs = validate(games, media)
    counts = {
        "games": len(games),
        "quests": sum(len(g["quests"]) for g in games) + sum(len(r["quests"]) for c in media for r in media[c]),
    }
    if errs:
        print(f"등대 데이터 검사: FAIL — {len(errs)}건")
        for err in errs[:40]:
            print(f"  × {err}")
        if len(errs) > 40:
            print(f"  … 외 {len(errs) - 40}건")
        return 1
    payload = build(games, media)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    c = payload["counts"]
    print(
        f"등대 데이터 검사: PASS — 작품 {c['items']}종 · 목표 {c['quests']}개 · "
        f"분야 {({k: v['quests'] for k, v in c['by_category'].items()})} · 난이도 {c['by_difficulty']}"
    )
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
