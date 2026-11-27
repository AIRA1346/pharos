#!/usr/bin/env python3
"""EN 오버레이 누출 검사 — 병합 후에도 한글이 남는 표시 문자열을 찾는다.

`data/en.json` 은 오버레이(부분 번역)라서, 항목의 어떤 필드를 덮지 않았는지 사람이 놓치기 쉽다.
`web/js/data.js` 의 merge 규칙과 같게 병합한 뒤 **화면에 나가는 문자열**에 한글이 남아 있으면 경로별로 모아 보여준다.
검색 전용 별칭·키워드는 제외한다(영문 화면에서도 검색어로 쓰인다).

사용: python3 projects/pharos/scripts/check_en_leaks.py [--all]
  --all 을 주면 verified 항목까지 검사한다(auto_fact 기본).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
DATA = ROOT / "data"
KOREAN = re.compile(r"[\uac00-\ud7a3]")
SKIP_SUFFIX = ("keywords", "aliases")


def merge(base, overlay):
    if overlay is None:
        return base
    if isinstance(overlay, list):
        return overlay
    if not isinstance(overlay, dict):
        return overlay
    out = dict(base) if isinstance(base, dict) else {}
    for key, value in overlay.items():
        if key == "price_display":
            out["price"] = {**(out.get("price") or {}), "display": value}
            continue
        out[key] = merge(out.get(key), value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="verified 항목까지 검사")
    args = parser.parse_args()
    bundle = json.loads((DATA / "en.json").read_text(encoding="utf-8"))
    leaks: dict[str, set[str]] = {}
    checked = 0
    for path in sorted(DATA.glob("*/*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            tier = item.get("review_tier", "verified")
            if not args.all and tier != "auto_fact":
                continue
            checked += 1
            merged = merge(item, bundle.get("items", {}).get(item["id"], {}))

            def walk(node, path_key=""):
                if isinstance(node, dict):
                    for key, value in node.items():
                        walk(value, f"{path_key}.{key}" if path_key else key)
                elif isinstance(node, list):
                    for index, value in enumerate(node):
                        walk(value, f"{path_key}[{index}]")
                elif isinstance(node, str) and KOREAN.search(node):
                    if path_key.split("[")[0].endswith(SKIP_SUFFIX):
                        return
                    leaks.setdefault(path_key, set()).add(node[:50])

            walk(merged)
    for key, values in sorted(leaks.items()):
        print(f"{key:38} {len(values):3}  {sorted(values)[:2]}")
    print(f"\n검사 {checked}건 · 한글 남은 경로 {len(leaks)}개")

    # 등대(Lighthouse) 퀘스트 — 오버레이가 아니라 파일 안에 EN 필드를 따로 둔다.
    lh_path = DATA / "lighthouse-quests.json"
    lh_leaks = 0
    if lh_path.exists():
        lh = json.loads(lh_path.read_text(encoding="utf-8"))
        rows = []
        for field in ("title_en", "note_en"):
            if KOREAN.search(str(lh.get(field) or "")):
                rows.append((f"lighthouse.{field}", lh.get(field)))
        for row in lh.get("categories") or []:
            for field in ("label_en", "badge_en", "sub_en", "hint_en"):
                if KOREAN.search(str(row.get(field) or "")):
                    rows.append((f"lighthouse.categories[{row.get('id')}].{field}", row.get(field)))
        for category, tier_rows in (lh.get("tiers") or {}).items():
            for row in tier_rows:
                for field in ("label_en", "window_en", "hint_en"):
                    if KOREAN.search(str(row.get(field) or "")):
                        rows.append((f"lighthouse.tiers[{category}][{row.get('tier')}].{field}", row.get(field)))
        quests = 0
        entries = [(g.get("game_id"), g.get("quests") or []) for g in lh.get("games") or []]
        for category, media_rows in (lh.get("media") or {}).items():
            entries.extend((f"{category}/{row.get('item_id')}", row.get("quests") or []) for row in media_rows)
        for label, quests_of in entries:
            for quest in quests_of:
                quests += 1
                for field in ("title_en", "desc_en", "tip_en", "est_time_en"):
                    value = quest.get(field)
                    if KOREAN.search(str(value or "")):
                        rows.append((f"lighthouse.{label}.t{quest.get('tier')}.{field}", value))
        lh_leaks = len(rows)
        for key, value in rows[:10]:
            print(f"{key:52} {str(value)[:40]}")
        print(f"등대 퀘스트 검사 {quests}개 · EN 필드 한글 잔존 {lh_leaks}건")
    return 0 if not leaks and not lh_leaks else 1


if __name__ == "__main__":
    raise SystemExit(main())
