#!/usr/bin/env python3
"""사전 백필용 사실 보강 — Steam 언어·상점 분류·공식 사이트를 지금 다시 확인해 캐시한다.

이미 적재된 항목은 bulk_ingest 가 언어·분류를 저장하지 않았으므로, 사전(encyclopedia)을
채우기 전에 **대표작의 Steam appid** 로 appdetails 를 한 번씩 받아
  - supported_languages (한국어 지원 여부)
  - categories (Single-player / Co-op / PvP …)
  - website (공식 홈페이지)
만 뽑아 `drafts/encyclopedia-2026-11-28/steam_enrich.json` 에 남긴다.
수치를 추정하지 않고 스토어 표기를 그대로 쓴다.

사용: python3 projects/pharos/scripts/enrich_encyclopedia_facts.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "drafts" / "encyclopedia-2026-11-28" / "steam_enrich.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; PharosEncyclopedia/1.0)"}
STEAM_URL = re.compile(r"store\.steampowered\.com/app/(\d+)")


def fetch(app_id: int) -> dict:
    url = (f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=kr&l=english"
           f"&filters=basic,categories,genres")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    data = ((payload or {}).get(str(app_id)) or {}).get("data") or {}
    langs = [re.sub(r"<[^>]+>", "", part).strip()
             for part in (data.get("supported_languages") or "").split(",")]
    cats = [c.get("description") for c in data.get("categories") or []]
    return {"app_id": app_id, "languages": [x for x in langs if x], "categories": cats,
            "website": data.get("website"), "name": data.get("name")}


def main() -> int:
    lh = json.loads((DATA / "lighthouse-quests.json").read_text(encoding="utf-8"))
    wanted = [g["game_id"] for g in lh["games"]]
    items = {}
    for path in sorted(DATA.glob("*/*.json")):
        for row in json.loads(path.read_text(encoding="utf-8")):
            items[row["id"]] = row
    targets = {}
    for iid in wanted:
        item = items.get(iid)
        if not item:
            print(f"! {iid}: 데이터 없음")
            continue
        app_id = None
        for src in item.get("sources") or []:
            m = STEAM_URL.search(src.get("url") or "")
            if m:
                app_id = int(m.group(1))
                break
        if app_id:
            targets[iid] = app_id
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    print(f"대상 {len(targets)}종 · 이미 캐시 {len(out)}종")
    for iid, app_id in targets.items():
        if iid in out and out[iid].get("languages"):
            continue
        try:
            out[iid] = fetch(app_id)
            ko = "지원" if any("Korean" in x for x in out[iid]["languages"]) else "미지원"
            print(f"  ✓ {iid} ({app_id}) — 한국어 {ko} · 분류 {len(out[iid]['categories'])}")
        except Exception as exc:  # noqa: BLE001
            print(f"  × {iid} ({app_id}) — {exc}")
        time.sleep(1.1)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"저장: {OUT.relative_to(ROOT.parent.parent)} · {len(out)}종")
    return 0


if __name__ == "__main__":
    sys.exit(main())
