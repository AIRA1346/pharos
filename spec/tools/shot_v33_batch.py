#!/usr/bin/env python3
"""v33 9차 대량 적재(3,026종) 라이브 스크린샷.

`live/live-v33-batch9-home.png`   — 전체 탐색에서 총 3,026종이 보이는 화면
`live/live-v33-batch9-detail.png` — 이번에 새로 들어와 사전까지 채운 작품(《NHK에 어서오세요!》)의 상세 모달

사용
  python3 projects/pharos/scripts/shot_v33_batch.py
  python3 projects/pharos/scripts/shot_v33_batch.py --base http://localhost:8000/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

CHROME_DEPS = "/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu:/workspace/.cache/chromedeps/root/lib/x86_64-linux-gnu"
if (
    not os.environ.get("PHAROS_SHOT_REEXEC")
    and "LD_LIBRARY_PATH" not in os.environ
    and (Path(CHROME_DEPS.split(":")[0]) / "libnspr4.so").exists()
):
    os.environ["PHAROS_SHOT_REEXEC"] = "1"
    os.environ["LD_LIBRARY_PATH"] = CHROME_DEPS
    os.execv(sys.executable, [sys.executable, *sys.argv])

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LIVE = "https://aira1346.github.io/pharos/"
DETAIL_ITEM = "nhk-ni-youkoso"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--out", default=str(ROOT / "live"))
    args = ap.parse_args()
    base = args.base if args.base.endswith("/") else args.base + "/"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    catalog = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    total = sum(len(json.loads((ROOT / "data" / a["data_file"]).read_text(encoding="utf-8")))
                for a in catalog["arenas"])
    domains: dict[str, int] = {}
    for a in catalog["arenas"]:
        rows = json.loads((ROOT / "data" / a["data_file"]).read_text(encoding="utf-8"))
        domains[a["domain"]] = domains.get(a["domain"], 0) + len(rows)

    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(f"{base}?domain=catalog&lang=ko", wait_until="networkidle")
        page.wait_for_timeout(1500)
        body = page.inner_text("body")
        hit = f"{total:,}" in body or str(total) in body
        print(f"전체 탐색: 카탈로그 {total:,}종 표기 {'확인' if hit else '못 찾음'}", domains)
        path = out / "live-v33-batch9-home.png"
        page.screenshot(path=str(path))
        print("saved", path)

        page.goto(f"{base}?domain=anime&item={DETAIL_ITEM}&lang=ko", wait_until="networkidle")
        page.wait_for_timeout(1600)
        modals = [i for i in range(page.locator(".modal").count()) if page.locator(".modal").nth(i).is_visible()]
        detail = page.locator(".modal").nth(modals[0]).inner_text() if modals else ""
        print("상세 모달:", "열림" if modals else "안 열림", "| 사전 섹션:", "📖" in detail,
              "| 제목:", detail[:40].replace("\n", " "))
        path = out / "live-v33-batch9-detail.png"
        if modals:
            page.locator(".modal").nth(modals[0]).screenshot(path=str(path))
        else:
            page.screenshot(path=str(path))
        print("saved", path)
        browser.close()
    if errors:
        print("콘솔 오류:", errors[:3])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
