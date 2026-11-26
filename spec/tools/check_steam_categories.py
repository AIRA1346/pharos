#!/usr/bin/env python3
"""2단계 근거 수집 — stale_over_12m 으로 거름인 게임의 Steam 상점 분류(categories)를 확인한다.

`Single-player` 만 있고 멀티플레이·협동·PvP 분류가 없는 항목은 "오프라인 싱글플레이 전용"의
객관 근거(등급 A)가 된다. 결과는 JSON 으로 남기고 patch_feature_complete.py 의 판단 근거로 쓴다.

python3 projects/pharos/drafts/bulk5-2026-11-26/check_steam_categories.py
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent / "steam-categories.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
ONLINE = {"Multiplayer", "Online PvP", "Online Co-op", "Co-op", "PvP", "MMO", "Cross-Platform Multiplayer",
          "Shared/Split Screen Co-op", "LAN Co-op", "LAN PvP"}


def app_id(item: dict) -> int | None:
    for src in item.get("sources") or []:
        m = re.search(r"store\.steampowered\.com/app/(\d+)", src.get("url") or "")
        if m:
            return int(m.group(1))
    return None


def main() -> int:
    rows = {}
    if OUT.exists():
        rows = json.loads(OUT.read_text(encoding="utf-8"))
    todo = []
    for path in sorted(DATA.glob("game/*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            stale = (item.get("flags") or {}).get("stale_over_12m") or {}
            if stale.get("value") != "yes":
                continue
            aid = app_id(item)
            if not aid or str(aid) in rows:
                continue
            todo.append((item["id"], aid))
    print(f"대상 {len(todo)}건 (이미 확인 {len(rows)}건)")
    for n, (iid, aid) in enumerate(todo, 1):
        url = f"https://store.steampowered.com/api/appdetails?appids={aid}&cc=us&l=english&filters=basic,categories"
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()
            data = (json.loads(raw).get(str(aid)) or {}).get("data") or {}
            cats = [c.get("description") for c in data.get("categories") or []]
            rows[str(aid)] = {"id": iid, "app_id": aid, "name": data.get("name"), "categories": cats}
            flags = [c for c in cats if c in ONLINE]
            print(f"  {iid:<34} {'SP' if 'Single-player' in cats else '--'} · 멀티 {flags}")
        except Exception as exc:  # noqa: BLE001
            print(f"  × {iid}: {type(exc).__name__}: {exc}")
        if n % 20 == 0:
            OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        time.sleep(1.0)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sp = [r["id"] for r in rows.values() if "Single-player" in r["categories"] and not (set(r["categories"]) & ONLINE)]
    print(f"\n확인 {len(rows)}건 · 싱글플레이 전용 {len(sp)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
