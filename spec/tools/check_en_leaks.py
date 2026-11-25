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
    return 0 if not leaks else 1


if __name__ == "__main__":
    raise SystemExit(main())
