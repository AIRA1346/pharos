#!/usr/bin/env python3
"""v39 11차 대량 적재(4,437종) 라이브 스크린샷.

`live/live-v39-batch11-recommend.png`   — 추천 모드 첫 화면(4,437종 · 101비교군)
`live/live-v39-batch11-encyclopedia.png` — 도감에서 연 《사자에상》 상세(새로 쓴 사전 17종 중 하나)

사용
  python3 spec/tools/shot_v39_batch11.py
  python3 spec/tools/shot_v39_batch11.py --base http://localhost:8000/
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
DETAIL_ITEM = "sazae-san"
DETAIL_DOMAIN = "manga"


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
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(f"{base}?mode=recommend&domain=catalog&lang=ko", wait_until="networkidle")
        page.wait_for_timeout(1800)
        body = page.inner_text("body")
        hit = f"{total:,}" in body or str(total) in body
        print(f"추천 모드: 카탈로그 {total:,}종 표기 {'확인' if hit else '못 찾음'}", domains)
        path = out / "live-v39-batch11-recommend.png"
        page.screenshot(path=str(path))
        print("saved", path)

        page.goto(f"{base}?mode=encyclopedia&domain={DETAIL_DOMAIN}&item={DETAIL_ITEM}&lang=ko",
                  wait_until="networkidle")
        page.wait_for_timeout(1800)
        modals = [i for i in range(page.locator(".modal").count()) if page.locator(".modal").nth(i).is_visible()]
        detail = page.locator(".modal").nth(modals[0]).inner_text() if modals else page.inner_text("body")
        print("상세 모달:", "열림" if modals else "안 열림", "| 사전 섹션:", "📖" in detail,
              "| 제목:", detail[:40].replace("\n", " "))
        path = out / "live-v39-batch11-encyclopedia.png"
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
