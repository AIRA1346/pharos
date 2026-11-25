#!/usr/bin/env python3
"""파로스 아이템 29종의 공식 아이콘을 내려받아 web/assets/icons/ 에 정규화 저장한다.

원칙
  · 외부 URL 핫링크·만료를 피하려고 파일을 직접 내려받아 저장한다(오프라인 배포).
  · 출처는 공식 스토어 아트워크를 우선한다 — Apple App Store(iTunes Search/Lookup API)의
    artworkUrl512, 없으면 개발사·퍼블리셔 공식 사이트의 apple-touch-icon·파비콘,
    PC 전용작은 공식 브랜드 아바타(개발사 공식 채널)나 공식 커버 아트를 정사각으로 자른다.
  · 모든 파일은 192×192(카드 44~48px · 상세 52~56px · 비교표 32px의 3~4배 밀도)로
    정규화하고 WebP(q=90)로 저장한다(PNG 대비 1/4 크기, 알파 보존).
  · 출처 URL과 확보 방법은 web/assets/icons/manifest.json 에 남긴다(추적·정정용).

사용:
  python3 projects/pharos/scripts/fetch_icons.py            # 29종 전부 다시 받기
  python3 projects/pharos/scripts/fetch_icons.py --check    # 파일·manifest 상태만 점검
"""

import argparse
import io
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]  # projects/pharos
OUT_DIR = ROOT / "web" / "assets" / "icons"
MANIFEST = OUT_DIR / "manifest.json"
SIZE = 192
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# kind="itunes": App Store 아트워크(bundleId 우선, 실패 시 term 검색).
# kind="url"   : 공식 사이트·공식 채널의 이미지. crop 은 원본 픽셀 좌표(좌,상,우,하).
SOURCES = [
    # ── 앱: 생산성 · 지식관리 ────────────────────────────────────────────────
    {"id": "obsidian", "kind": "itunes", "bundle": "md.obsidian", "term": "Obsidian", "countries": ["kr", "us"]},
    {"id": "evernote", "kind": "itunes", "bundle": "com.evernote.iPhone.Evernote", "term": "Evernote", "countries": ["kr", "us"]},
    {"id": "notion", "kind": "itunes", "bundle": "notion.id", "term": "Notion", "countries": ["kr", "us"]},
    {"id": "joplin", "kind": "itunes", "bundle": "net.cozic.joplin", "term": "Joplin", "countries": ["kr", "us"]},
    {"id": "simplenote", "kind": "itunes", "bundle": "com.codality.NotationalFlow", "term": "Simplenote", "countries": ["kr", "us"]},
    # ── 게임: 덱빌딩 ─────────────────────────────────────────────────────────
    {"id": "balatro", "kind": "itunes", "bundle": "com.playstack.balatropremium", "term": "Balatro", "countries": ["kr", "us"]},
    {"id": "slay-the-spire", "kind": "itunes", "bundle": "com.humblebundle.slaythespire", "term": "Slay the Spire", "countries": ["kr", "us"]},
    {
        "id": "inscryption", "kind": "itunes", "bundle": "com.devolver.inscryption", "term": "Inscryption",
        "entity": "macSoftware", "countries": ["us"],
        "note": "PC 전용작 — Devolver Digital 의 Mac App Store 공식 앱 아이콘",
    },
    {"id": "night-of-the-full-moon", "kind": "itunes", "bundle": "com.yomob.yyzy", "term": "Night of the Full Moon", "countries": ["kr", "us"]},
    # ── 게임: 액션 로그라이크 ────────────────────────────────────────────────
    {
        "id": "hades", "kind": "url",
        "url": "https://images.ctfassets.net/5owu3y35gz1g/221gU3J0H5urRoHsNbYDpf/0b197a0eabe1070d7cb4bd48747ec1af/Hades_Cover_Website.png",
        "crop": [140, 0, 440, 300],
        "provider": "Supergiant Games 공식 사이트(game art)",
        "note": "모바일 스토어 앱 아이콘이 없는 PC·콘솔 작 — Supergiant 공식 커버 아트에서 자바르 그림 얼굴 부분을 정사각으로 잘라 사용",
    },
    {"id": "vampire-survivors", "kind": "itunes", "bundle": "com.poncle.VampireSurvivors", "term": "Vampire Survivors", "countries": ["kr", "us"]},
    {"id": "dead-cells", "kind": "itunes", "bundle": "com.playdigious.deadcells", "term": "Dead Cells", "countries": ["kr", "us"]},
    {"id": "archero", "kind": "itunes", "bundle": "com.habby.archero", "term": "Archero", "countries": ["kr", "us"]},
    # ── 게임: 모바일 수집형 RPG ──────────────────────────────────────────────
    {"id": "hero-wars-alliance", "kind": "itunes", "bundle": "com.nexters.titanhunters", "term": "Hero Wars", "countries": ["kr", "us"]},
    {"id": "limbus-company", "kind": "itunes", "bundle": "com.ProjectMoon.LimbusCompany", "term": "Limbus Company", "countries": ["kr", "us"]},
    {"id": "genshin-impact", "kind": "itunes", "bundle": "com.miHoYo.GenshinImpact", "term": "Genshin Impact", "countries": ["kr", "us"]},
    {"id": "goddess-of-victory-nikke", "kind": "itunes", "bundle": "com.proximabeta.nikke", "term": "NIKKE", "countries": ["kr", "us"]},
    {"id": "blue-archive", "kind": "itunes", "bundle": "com.nexon.bluearchive", "term": "Blue Archive", "countries": ["kr", "us"]},
    {"id": "honkai-star-rail", "kind": "itunes", "bundle": "com.HoYoverse.hkrpgoversea", "term": "Honkai Star Rail", "countries": ["kr", "us"]},
    # ── 게임: PC MMORPG ─────────────────────────────────────────────────────
    {
        "id": "final-fantasy-xiv", "kind": "url",
        "url": "https://lds-img.finalfantasyxiv.com/promo/h/0/U2uGfVX4GdZgU1jASO0m9h_xLg.png",
        "provider": "FINAL FANTASY XIV 공식 사이트(north america) apple-touch-icon",
        "note": "PC·콘솔 전용 — 스퀘어에닉스 공식 사이트의 유성 문장 아이콘",
    },
    {
        "id": "guild-wars-2", "kind": "url",
        "url": "https://yt3.googleusercontent.com/C63T2V9ucG1G7W9dT9bjlHtc5HlwMIasb0KLPzdj17dS0hsVw8HWId_gX7G8gELglgoNufrgiw=s900-c-k-c0x00ffffff-no-rj",
        "provider": "Guild Wars 2 공식 유튜브 채널 아바타(ArenaNet)",
        "note": "PC 전용 — 공식 사이트 파비콘은 16px 뿐이라 공식 채널의 900px 'GW' 마크 사용",
    },
    {
        "id": "lost-ark", "kind": "url",
        "url": "https://d3irh93dd5ckql.cloudfront.net/statics/2026-11-25/images/apple-touch-icon.png",
        "provider": "Lost Ark 공식 사이트 apple-touch-icon",
        "note": "PC 전용 — 공식 사이트 190px 엠블럼",
    },
    {
        "id": "black-desert", "kind": "url",
        "url": "https://static.pearlcdn.com/asset/portal/bdo_naeu/contents/img/common/favicon256_bdo.ico",
        "provider": "Black Desert 공식 사이트 favicon(256px, Pearl Abyss)",
        "note": "PC 전용 — 공식 사이트의 256px 아이콘(ICO→PNG 변환)",
    },
    # ── 게임: 모바일 전략 · 디펜스 ───────────────────────────────────────────
    {"id": "bloons-td-6", "kind": "itunes", "bundle": "com.ninjakiwi.bloonstd6", "term": "Bloons TD 6", "countries": ["kr", "us"]},
    {"id": "kingdom-rush-vengeance", "kind": "itunes", "bundle": "com.ironhidegames.kingdomrush4", "term": "Kingdom Rush Vengeance", "countries": ["kr", "us"]},
    {"id": "clash-royale", "kind": "itunes", "bundle": "com.supercell.scroll", "term": "Clash Royale", "countries": ["kr", "us"]},
    {"id": "plants-vs-zombies-2", "kind": "itunes", "bundle": "com.popcap.ios.PvZ2", "term": "Plants vs Zombies 2", "countries": ["kr", "us"]},
    {"id": "clash-of-clans", "kind": "itunes", "bundle": "com.supercell.magic", "term": "Clash of Clans", "countries": ["kr", "us"]},
    {"id": "arknights", "kind": "itunes", "bundle": "com.YoStarKR.Arknights", "term": "명일방주", "countries": ["kr", "us", "jp"]},
]


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as res:
        return res.read()


def itunes_lookup(entry):
    """bundleId 로 정확히 찾고, 없으면 검색 결과에서 이름이 맞는 것을 고른다."""
    for country in entry.get("countries") or ["kr", "us"]:
        params = {"bundleId": entry["bundle"], "country": country}
        url = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(params)
        try:
            results = json.loads(fetch(url)).get("results") or []
        except Exception:  # noqa: BLE001
            results = []
        for res in results:
            if res.get("bundleId") == entry["bundle"] and res.get("artworkUrl512"):
                return res, country
    entity = entry.get("entity", "software")
    for country in entry.get("countries") or ["kr", "us"]:
        params = {"term": entry.get("term") or entry["id"], "country": country, "entity": entity, "limit": 10}
        url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(params)
        try:
            results = json.loads(fetch(url)).get("results") or []
        except Exception:  # noqa: BLE001
            results = []
        for res in results:
            if res.get("bundleId") == entry["bundle"] and res.get("artworkUrl512"):
                return res, country
    return None, None


def square(img, crop=None):
    """정사각 크롭 — crop(원본 픽셀)이 있으면 그 영역, 없으면 가운데 정사각."""
    if crop:
        return img.crop(tuple(crop))
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def normalize(img):
    img = img.convert("RGBA")
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def build_one(entry, retrieved):
    record = {"id": entry["id"]}
    if entry["kind"] == "itunes":
        res, country = itunes_lookup(entry)
        if not res:
            return None, f"{entry['id']}: App Store 에서 bundleId {entry['bundle']} 를 찾지 못함"
        art = res["artworkUrl512"]
        raw = fetch(art)
        title, provider = res.get("trackName"), res.get("sellerName")
        record.update({
            "provider": f"Apple App Store (iTunes {entry.get('entity', 'software')}, {country})",
            "source_url": art,
            "store_name": title,
            "store_seller": provider,
        })
    else:
        raw = fetch(entry["url"])
        record.update({"provider": entry.get("provider", ""), "source_url": entry["url"]})

    img = Image.open(io.BytesIO(raw))
    img.load()
    record["source_size"] = list(img.size)
    img = normalize(square(img, entry.get("crop")))
    out = OUT_DIR / f"{entry['id']}.webp"
    img.save(out, "WEBP", quality=90, method=6)
    record.update({
        "file": f"assets/icons/{out.name}",
        "bytes": out.stat().st_size,
        "note": entry.get("note", ""),
        "retrieved_at": retrieved,
    })
    return record, None


def main():
    parser = argparse.ArgumentParser(description="파로스 공식 아이콘 수집")
    parser.add_argument("--check", action="store_true", help="내려받지 않고 파일·manifest 상태만 점검")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    retrieved = date.today().isoformat()

    if args.check:
        missing = [e["id"] for e in SOURCES if not (OUT_DIR / f"{e['id']}.webp").exists()]
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
        unlisted = [e["id"] for e in SOURCES if e["id"] not in {i["id"] for i in manifest.get("items", [])}]
        print(f"파일 {len(SOURCES) - len(missing)}/{len(SOURCES)} 존재 · manifest {len(manifest.get('items', []))}건")
        for label, rows in (("파일 없음", missing), ("manifest 누락", unlisted)):
            if rows:
                print(f"  × {label}: {', '.join(rows)}")
        return 0 if not missing and not unlisted else 1

    records, failures = [], []
    for entry in SOURCES:
        try:
            record, err = build_one(entry, retrieved)
        except Exception as exc:  # noqa: BLE001
            record, err = None, f"{entry['id']}: {type(exc).__name__} {exc}"
        if record:
            records.append(record)
            print(f"  ✓ {entry['id']:<26} {record['bytes']:>6,}B  ← {record['source_url'][:78]}")
        else:
            failures.append(err)
            print(f"  × {err}")

    if failures:
        print(f"\n결과: FAIL — {len(failures)}종 확보 실패. 기존 파일은 그대로 두었다.")
        return 1

    manifest = {
        "note": (
            "파로스 카드·상세·비교표에 쓰는 공식 아이콘 목록. 각 이미지는 해당 권리자의 "
            "앱 아이콘·브랜드 마크이며, 파로스는 식별 목적으로만 사용한다(상표권은 각 권리자에게). "
            "이 파일은 scripts/fetch_icons.py 가 생성한다 — 손으로 고치지 않는다."
        ),
        "size": [SIZE, SIZE],
        "format": "webp/q90",
        "count": len(records),
        "retrieved_at": retrieved,
        "items": records,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(r["bytes"] for r in records)
    print(f"\n결과: PASS — {len(records)}/{len(SOURCES)}종 · {SIZE}×{SIZE} webp · 합계 {total/1024:.0f}KB")
    print(f"manifest: {MANIFEST.relative_to(ROOT.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
