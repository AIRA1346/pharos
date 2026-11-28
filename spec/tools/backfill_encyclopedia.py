#!/usr/bin/env python3
"""대표작 사전(encyclopedia) 백필 — 큐레이션 문장 + 수집 사실로 150종 이상을 채운다.

입력
  · drafts/encyclopedia-2026-11-28/curated.py   — 사람이 쓴 개요·핵심 특징·추가 제원·관련작·공식 링크
  · drafts/encyclopedia-2026-11-28/steam_enrich.json — Steam 재확인(언어·상점 분류·공식 사이트)
  · data/{domain}/{arena}.json · data/en.json — 기존 수집 데이터

하는 일
  1) 큐레이션 대상 id 가 실제 카탈로그에 있는지 확인한다.
  2) 기존 데이터에서 확인된 사실(플랫폼·장르·가격·평가·업데이트·출시·Steam 언어/모드)로 제원을 만들고,
     큐레이션 제원을 앞에 붙인다(키 중복은 큐레이션 우선).
  3) 핵심 특징 = 큐레이션 문장 + 사실 문장으로 3~4줄.
  4) related 는 실제 항목 id 만 남기고(없는 id 는 경고 후 제외), relation 5종만 쓴다.
  5) data/{domain}/{arena}.json 의 항목과 data/en.json 의 오버레이에 같은 구조로 쓴다.
  6) search-index.json 재생성과 검증은 하지 않는다 — 뒤이어 scripts/sync_web_data.py 가 한다.

사용
  python3 projects/pharos/scripts/backfill_encyclopedia.py --dry-run
  python3 projects/pharos/scripts/backfill_encyclopedia.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import encyclopedia as enc  # noqa: E402

DATA = ROOT / "data"
# v31 — 작품 도메인(영화·애니·만화). 미디어 제원·제작진 라벨을 쓰는 세 도메인이다.
WORK_DOMAINS = {"movie", "anime", "manga"}
EN_PATH = DATA / "en.json"
CURATED_DIR = ROOT / "drafts" / "encyclopedia-2026-11-28"
STEAM_ENRICH = CURATED_DIR / "steam_enrich.json"

KIND_KO = {"free": "무료", "freemium": "무료 + 유료", "demo": "체험판", "one_time": "1회 구매",
           "subscription": "구독", "license": "라이선스", "consumable": "소모품 과금"}
KIND_EN = {"free": "Free", "freemium": "Free + paid tiers", "demo": "Demo", "one_time": "One-time purchase",
           "subscription": "Subscription", "license": "License", "consumable": "Consumable purchases"}


def load_curated() -> dict:
    path = CURATED_DIR / "curated.py"
    sys.path.insert(0, str(CURATED_DIR))
    spec = importlib.util.spec_from_file_location("curated_enc", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ENTRIES


def load_items() -> dict:
    items = {}
    for path in sorted(DATA.glob("*/*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            items[row["id"]] = (row, path)
    return items


def rating_text(item: dict, lang: str) -> str:
    parts = []
    for row in item.get("review_snapshot", {}).get("platforms") or []:
        metric = row.get("cumulative") or {}
        value, count = metric.get("value"), metric.get("count")
        if not value or not count:
            continue
        platform = {"steam": "Steam", "ios": "App Store", "android": "Google Play",
                    "anilist": "AniList", "letterboxd": "Letterboxd"}.get(row.get("platform"), row.get("platform"))
        if metric.get("scale") == "percent":
            parts.append(f"{platform} {value}% 긍정({count:,}건)" if lang == "ko"
                         else f"{value}% positive on {platform} ({count:,})")
        elif metric.get("scale") == "stars5":
            parts.append(f"{platform} {value}★({count:,}건)" if lang == "ko"
                         else f"{value}★ on {platform} ({count:,})")
        else:
            parts.append(f"{platform} {value}/100({count:,}건)" if lang == "ko"
                         else f"{value}/100 on {platform} ({count:,})")
    return " · ".join(parts)


MEDIA_STATUS_KO = {"feature_complete": "완결", "active": "연재·방영 중",
                   "stale_unknown": "휴재·중단", "abandoned": "중단"}
MEDIA_STATUS_EN = {"feature_complete": "complete", "active": "still running",
                 "stale_unknown": "on hiatus", "abandoned": "discontinued"}
MEDIA_FORMAT_EN = {"TV": "TV", "OVA": "OVA", "ONA": "ONA", "극장판": "Film", "특별편": "Special"}


def media_format(item: dict, en_entry: dict | None) -> tuple[str, str] | None:
    """arena_notes 의 형식 구간('TV 25화 (2013)' · '만화 224화·29권' · '영화 148분')을 읽어 KO/EN 분량 문구를 만든다.

    한국어는 수집 때 저장한 한국어 표기, 영어는 영문 번역본(arena_notes)의 해당 구간만 옮긴다(없으면 만든다).
    """
    note = next(iter((item.get("arena_notes") or {}).values()), "")
    en_note = next(iter(((en_entry or {}).get("arena_notes") or {}).values()), "")
    m = re.search(r"(TV|OVA|ONA|극장판|특별편)\s*(\d+)화\s*\(([^)]*)\)", note)
    if m:
        fmt, eps, span = m.group(1), m.group(2), m.group(3)
        return (f"{fmt} {eps}화 ({span})",
                f"{MEDIA_FORMAT_EN[fmt]}, {eps} episodes ({span})")
    m = re.search(r"만화\s*(\d+)화(?:\s*·\s*(\d+)권)?", note)
    if m:
        chapters, volumes = m.group(1), m.group(2)
        ko = f"만화 {chapters}화" + (f"·{volumes}권" if volumes else "")
        en = f"{chapters} chapters" + (f" in {volumes} volumes" if volumes else "")
        return ko, en
    m = re.search(r"영화\s*(\d+)분", note)
    if m:
        return f"영화 {m.group(1)}분", f"{m.group(1)} min"
    return None


def media_facts(item: dict, en_entry: dict | None = None) -> list[dict]:
    """미디어 제원 — 제작·분량·방영/출간·장르·감상 경로. 수집한 값만 쓴다."""
    rows = []
    if item.get("developer"):
        rows.append(enc.fact("제작", "Created by", item["developer"],
                             (en_entry or {}).get("developer") or item["developer"]))
    fmt = media_format(item, en_entry)
    if fmt:
        rows.append(enc.fact("분량", "Format", fmt[0], fmt[1]))
    if item.get("release_date"):
        status_ko = MEDIA_STATUS_KO.get(item.get("maintenance_status"), "")
        status_en = MEDIA_STATUS_EN.get(item.get("maintenance_status"), "")
        rows.append(enc.fact("방영·출간", "Release",
                             item["release_date"] + (f" · {status_ko}" if status_ko else ""),
                             item["release_date"] + (f" · {status_en}" if status_en else "")))
    if item.get("genres"):
        genres_ko = " · ".join(item["genres"][:3])
        genres_en = " · ".join(((en_entry or {}).get("genres") or [])[:3]) or genres_ko
        rows.append(enc.fact("장르", "Genres", genres_ko, genres_en))
    if item.get("platforms"):
        rows.append(enc.fact("감상 경로", "Where it runs",
                             " · ".join(enc.PLATFORM_KO.get(p, p) for p in item["platforms"]),
                             " · ".join(enc.PLATFORM_EN.get(p, p) for p in item["platforms"])))
    return rows


def auto_facts(item: dict, enrich: dict | None, tier: dict | None, en_price: str | None = None,
               en_entry: dict | None = None) -> list[dict]:
    if item.get("domain") in WORK_DOMAINS:
        rows = media_facts(item, en_entry)
        if tier:
            kind_ko = KIND_KO.get(tier.get("kind"), tier.get("kind") or "")
            kind_en = KIND_EN.get(tier.get("kind"), tier.get("kind") or "")
            display_ko = (tier.get("price") or {}).get("display") or ""
            display_en = en_price or display_ko
            rows.append(enc.fact("가격", "Price", f"{display_ko}{f' ({kind_ko})' if kind_ko else ''}".strip(),
                                 f"{display_en}{f' ({kind_en})' if kind_en else ''}".strip()))
        rating_ko, rating_en = rating_text(item, "ko"), rating_text(item, "en")
        if rating_ko:
            rows.append(enc.fact("평가", "Rating", rating_ko, rating_en))
        return rows
    rows = []
    platforms = item.get("platforms") or []
    if platforms:
        rows.append(enc.fact("플랫폼", "Platforms",
                             " · ".join(enc.PLATFORM_KO.get(p, p) for p in platforms),
                             " · ".join(enc.PLATFORM_EN.get(p, p) for p in platforms)))
    if enrich:
        langs = enrich.get("languages") or []
        if langs:
            korean = any("Korean" in x for x in langs)
            rows.append(enc.fact("한국어", "Korean", "지원" if korean else "미지원",
                                 "Supported" if korean else "Not supported",
                                 f"Steam 표시 언어 {len(langs)}개 중" if korean else "Steam 표시 언어 목록",
                                 f"one of {len(langs)} languages on Steam" if korean else "Steam language list"))
        cats = enrich.get("categories") or []
        modes = [c for c in cats if c in ("Single-player", "Multi-player", "Online PvP", "PvP", "Online Co-op",
                                          "Co-op", "Shared/Split Screen Co-op", "Shared/Split Screen", "MMO",
                                          "Cross-Platform Multiplayer")]
        if modes:
            rows.append(enc.fact("모드", "Modes", " · ".join(modes), " · ".join(modes),
                                 "Steam 상점 분류", "Steam store categories"))
    if tier:
        kind_ko = KIND_KO.get(tier.get("kind"), tier.get("kind") or "")
        kind_en = KIND_EN.get(tier.get("kind"), tier.get("kind") or "")
        display_ko = (tier.get("price") or {}).get("display") or ""
        display_en = en_price or display_ko
        rows.append(enc.fact("가격", "Price", f"{display_ko}{f' ({kind_ko})' if kind_ko else ''}".strip(),
                             f"{display_en}{f' ({kind_en})' if kind_en else ''}".strip()))
    rating_ko, rating_en = rating_text(item, "ko"), rating_text(item, "en")
    if rating_ko:
        rows.append(enc.fact("평가", "Rating", rating_ko, rating_en))
    release = item.get("release_date")
    if release and item.get("domain") not in WORK_DOMAINS:
        rows.append(enc.fact("출시", "Released", release, release))
    latest = (item.get("update_profile") or {}).get("latest_update")
    if latest and item.get("domain") not in WORK_DOMAINS:
        rows.append(enc.fact("최근 업데이트", "Latest update", latest, latest,
                             "수집 시점 스토어·저장소 표기", "As listed when collected"))
    return rows


def auto_highlights(item: dict, enrich: dict | None, tier: dict | None,
                    en_price: str | None = None) -> tuple[list[str], list[str]]:
    ko, en = [], []
    if enrich and enrich.get("languages"):
        korean = any("Korean" in x for x in enrich["languages"])
        if korean:
            ko.append("한국어를 공식 지원한다 — Steam 표시 언어 목록 기준.")
            en.append("Korean is officially supported, per Steam's language list.")
    if tier:
        display = (tier.get("price") or {}).get("display") or ""
        kind_ko = KIND_KO.get(tier.get("kind"), "")
        kind_en = KIND_EN.get(tier.get("kind"), "")
        if display:
            ko.append(f"가격은 {display}{f' ({kind_ko})' if kind_ko else ''}.")
            en.append(f"Price: {en_price or display}{f' ({kind_en})' if kind_en else ''}.")
    rating_ko, rating_en = rating_text(item, "ko"), rating_text(item, "en")
    if rating_ko:
        ko.append(f"공개 평가 {rating_ko}.")
        en.append(f"Public ratings: {rating_en}.")
    latest = (item.get("update_profile") or {}).get("latest_update")
    if latest and item.get("domain") not in WORK_DOMAINS and len(ko) < 4:
        ko.append(f"최근 업데이트 {latest}.")
        en.append(f"Latest update {latest}.")
    return ko, en


def build(item: dict, curated: dict, enrich: dict | None, en_entry: dict | None = None) -> tuple[dict, dict, list[str]]:
    warns = []
    tier = next((t for t in item.get("tiers") or [] if t.get("tier_id") == item["verdict"]["tier_of_record"]),
                (item.get("tiers") or [None])[0])
    en_price = None
    for row in (en_entry or {}).get("tiers") or []:
        if isinstance(row, dict) and tier and row.get("tier_id") == tier.get("tier_id"):
            en_price = ((row.get("price") or {}).get("display")) or None
            break
    facts = []
    for row in curated.get("facts") or []:
        facts.append(enc.fact(*row))
    facts.extend(auto_facts(item, enrich, tier, en_price, en_entry))
    facts = [f for f in facts if f]

    highlights_ko = list(curated.get("highlights_ko") or [])
    highlights_en = list(curated.get("highlights_en") or [])
    auto_ko, auto_en = auto_highlights(item, enrich, tier, en_price)
    for a, b in zip(auto_ko, auto_en):
        if len(highlights_ko) >= 3:
            break
        highlights_ko.append(a)
        highlights_en.append(b)
    if len(highlights_ko) > 4:
        highlights_ko, highlights_en = highlights_ko[:4], highlights_en[:4]

    if item.get("domain") in WORK_DOMAINS:
        credit = item.get("developer") or ""
        if not credit:
            warns.append(f"{item['id']}: 제작진 표기 없음")
    summary_ko = curated["about_ko"].strip()
    summary_en = curated["about_en"].strip()

    related = []
    for row in curated.get("related") or []:
        rid, relation = row[0], row[1]
        note_ko = row[2] if len(row) > 2 else None
        note_en = row[3] if len(row) > 3 else None
        if rid not in ITEM_IDS:
            warns.append(f"{item['id']}: related id 없음 → {rid}")
            continue
        related.append({"id": rid, "relation": relation, "note_ko": note_ko, "note_en": note_en})
    links = []
    for row in curated.get("links") or []:
        links.append(enc.link(*row))
    if enrich and enrich.get("website"):
        links.append(enc.link("공식 사이트", "Official site", enrich["website"]))
    seen_urls = set()
    links = [l for l in links if not (l["url"] in seen_urls or seen_urls.add(l["url"]))]

    enc_ko, enc_en = enc.compose(summary_ko=summary_ko, summary_en=summary_en, facts=facts,
                                 highlights_ko=highlights_ko, highlights_en=highlights_en,
                                 related=related, official_links=links)
    return enc_ko, enc_en, warns


ITEM_IDS: set[str] = set()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    global ITEM_IDS
    items = load_items()
    ITEM_IDS = set(items)
    curated_all = load_curated()
    enrich = json.loads(STEAM_ENRICH.read_text(encoding="utf-8")) if STEAM_ENRICH.exists() else {}
    bundle = json.loads(EN_PATH.read_text(encoding="utf-8"))
    en_items = bundle.setdefault("items", {})

    missing = sorted(set(curated_all) - set(items))
    if missing:
        print(f"! 카탈로그에 없는 큐레이션 id {len(missing)}건: {missing}")

    by_domain, wrote = {}, 0
    touched_files = set()
    all_warns = []
    for iid, curated in curated_all.items():
        if iid not in items:
            continue
        item, path = items[iid]
        try:
            enc_ko, enc_en, warns = build(item, curated, enrich.get(iid), en_items.get(iid))
        except ValueError as exc:
            print(f"× {iid}: {exc}")
            continue
        all_warns.extend(warns)
        item["encyclopedia"] = enc_ko
        en_items.setdefault(iid, {})["encyclopedia"] = enc_en
        by_domain[item["domain"]] = by_domain.get(item["domain"], 0) + 1
        wrote += 1
        touched_files.add(path)

    print(f"사전 백필 {wrote}건 · {by_domain}")
    if all_warns:
        print(f"! 경고 {len(all_warns)}건")
        for w in all_warns[:20]:
            print(f"  - {w}")
    if args.dry_run:
        print("(dry-run — 파일을 쓰지 않았다)")
        return 0

    for path in sorted(touched_files):
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            if row["id"] in curated_all and row["id"] in items:
                row["encyclopedia"] = items[row["id"]][0]["encyclopedia"]
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EN_PATH.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"기록: 데이터 {len(touched_files)}파일 · en.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
