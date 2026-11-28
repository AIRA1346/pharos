#!/usr/bin/env python3
"""v29 2,000종 돌파 라이브 스크린샷 — 전체 탐색·작품 도메인.

`live/live-v29-2000-home.png`(전체 탐색에서 총 2,072종 확인)과
`live/live-v29-2000-media.png`(v31 이후 — 영화·애니·만화 각 175, 합계 525 확인)를 저장하고,
화면에 보이는 건수 텍스트를 함께 출력한다.

사용
  python3 projects/pharos/scripts/shot_v29_2000.py
  python3 projects/pharos/scripts/shot_v29_2000.py --base http://localhost:8000/
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=LIVE)
    ap.add_argument("--out", default=str(ROOT / "live"))
    args = ap.parse_args()
    base = args.base if args.base.endswith("/") else args.base + "/"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    total = sum(
        len(json.loads((ROOT / "data" / a["data_file"]).read_text(encoding="utf-8")))
        for a in json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))["arenas"]
    )
    works = {
        a["id"]: len(json.loads((ROOT / "data" / a["data_file"]).read_text(encoding="utf-8")))
        for a in json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))["arenas"]
        if a["domain"] in ("movie", "anime", "manga")
    }

    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(f"{base}?domain=catalog&lang=ko", wait_until="networkidle")
        page.wait_for_timeout(1200)
        body = page.inner_text("body")
        hit = f"{total:,}" in body or str(total) in body
        print(f"전체 탐색: 카탈로그 {total}종 표기 {'확인' if hit else '못 찾음'}")
        path = out / "live-v29-2000-home.png"
        page.screenshot(path=str(path))
        print("saved", path)

        page.goto(f"{base}?domain=movie&lang=ko", wait_until="networkidle")
        page.wait_for_timeout(1200)
        body = page.inner_text("body")
        print("작품 도메인:", {k: v for k, v in works.items()},
              "| 영화 175 표기:", "175" in body)
        path = out / "live-v29-2000-media.png"
        page.screenshot(path=str(path))
        print("saved", path)

        browser.close()
    if errors:
        print("콘솔 오류:", errors[:3])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
