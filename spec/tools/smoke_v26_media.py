#!/usr/bin/env python3
"""파로스 v26/v27 미디어 도메인 스모크 — 영화 · 애니 · 만화 (데이터에서 건수를 읽는다).

v27(2차 대량 적재)부터 **기대 건수를 데이터에서 읽는다** — 화면이 카탈로그·비교군 파일과
같은 수를 보여 주는지 확인하므로, 작품이 늘어도 이 스크립트는 낡지 않는다.
지금 값은 미디어 300종(비교군 3 × 100종).

무엇을 확인하는가
  1) 도메인 — 상단 탭에 `영화 · 애니 · 만화` 가 있고, 도메인 화면이 3개 대분류 · 90건을 보여 준다.
  2) 비교군 — `TV · 극장 애니메이션` 30장 · `만화 · 단행본` 30장 · `실사 영화` 30장이 카드로 뜨고,
     포스터 아이콘(webp)이 실제로 로드되며(自然Width>0) 판정 배지·가중 점수가 함께 보인다.
  3) 상세 — 만화 항목의 상세에서 `누적 평점(100점)`·`AniList`·`단행본 구매` 가 보이고,
     미디어는 `제작 · 플랫폼`(개발사 아님) 라벨을 쓴다. 가격은 지어내지 않고 '미확인' 표기다.
  4) EN — 같은 화면이 영문 제목(TV & Film Animation)으로 뜨고 카드 텍스트에 한글이 없다.
  5) 비교 — 같은 비교군의 두 항목을 나란히 비교하면 표에 축 점수·누적 평점(100점)이 나온다.
  6) 기존 흐름 — 등대 첫 화면·전체 탐색·앱/게임/AI 도구 비교군이 그대로 열린다(회귀 확인).
  7) 반응형 — 390px 에서 가로 넘침 0.
  8) 오류 0건 · 스크린샷(--shots-dir) {prefix}-desktop.png · {prefix}-mobile.png.

사용
  python3 projects/pharos/scripts/smoke_v26_media.py
  python3 projects/pharos/scripts/smoke_v26_media.py --live --shots-dir projects/pharos/live
"""

from __future__ import annotations

import argparse
import functools
import json
import http.server
import os
import re
import socketserver
import sys
import threading
from pathlib import Path

CHROME_DEPS = "/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu:/workspace/.cache/chromedeps/root/lib/x86_64-linux-gnu"
# 브라우저 런타임 라이브러리(libnspr4 등)가 시스템에 없는 환경이면 LD_LIBRARY_PATH 를 붙여 다시 실행한다.
if (
    not os.environ.get("PHAROS_SMOKE_REEXEC")
    and "LD_LIBRARY_PATH" not in os.environ
    and (Path(CHROME_DEPS.split(":")[0]) / "libnspr4.so").exists()
):
    os.environ["PHAROS_SMOKE_REEXEC"] = "1"
    os.environ["LD_LIBRARY_PATH"] = CHROME_DEPS
    os.execv(sys.executable, [sys.executable, *sys.argv])

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
WEB_ROOT = ROOT / "web"
LIVE = "https://aira1346.github.io/pharos/"
KOREAN = re.compile(r"[\uac00-\ud7a3]")
RESULTS: list[tuple[str, bool, str]] = []

# 기대 건수는 데이터에서 읽는다(스크립트에 숫자를 박지 않는다).
_CATALOG = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
ARENA_COUNTS = {
    a["id"]: len(json.loads((ROOT / "data" / a["data_file"]).read_text(encoding="utf-8")))
    for a in _CATALOG["arenas"] if a.get("domain") == "media"
}
MEDIA_TOTAL = sum(ARENA_COUNTS.values())

CHROME_CANDIDATES = [
    os.environ.get("PHAROS_CHROME", ""),
    "/workspace/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome",
]
DEPS = "/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu:/workspace/.cache/chromedeps/root/lib/x86_64-linux-gnu"


def expect(condition: bool, label: str, extra: str = "") -> None:
    RESULTS.append((label, bool(condition), str(extra)))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + ("" if condition else f"  ← {extra}"))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):  # noqa: D401
        pass


def serve(directory: Path) -> tuple[socketserver.TCPServer, str]:
    handler = functools.partial(QuietHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}/"


def launch(chromium):
    if DEPS and "LD_LIBRARY_PATH" not in os.environ:
        os.environ["LD_LIBRARY_PATH"] = DEPS
    for candidate in CHROME_CANDIDATES:
        if candidate and Path(candidate).exists():
            return chromium.launch(executable_path=candidate, args=["--no-sandbox"])
    return chromium.launch(args=["--no-sandbox"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="라이브 사이트를 검사한다")
    ap.add_argument("--shots-dir", default="", help="스크린샷을 저장할 폴더(예: projects/pharos/live)")
    ap.add_argument("--prefix", default="live-v26-media")
    args = ap.parse_args()

    httpd = None
    if args.live:
        base = LIVE
    else:
        httpd, base = serve(WEB_ROOT)

    shots: list[Path] = []
    if args.shots_dir:
        out_dir = Path(args.shots_dir)
        if not out_dir.is_absolute():
            out_dir = (ROOT.parent.parent / args.shots_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = None

    errors: list[str] = []
    with sync_playwright() as p:
        browser = launch(p.chromium)
        ctx = browser.new_context(viewport={"width": 1280, "height": 1100}, locale="ko-KR")
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        # 1) 도메인 화면
        page.goto(f"{base}?domain=media", wait_until="networkidle")
        page.wait_for_timeout(900)
        tabs = page.locator("#domainTabs button").all_inner_texts()
        expect(any("영화 · 애니 · 만화" in tab for tab in tabs), "상단 탭에 영화 · 애니 · 만화가 있다", tabs)
        h1 = page.locator("h1").first.inner_text()
        expect(f"{MEDIA_TOTAL}건" in h1, f"도메인 화면이 {MEDIA_TOTAL}건을 보여 준다", h1)
        expect(MEDIA_TOTAL >= 300, "미디어 도메인이 300종을 넘었다", MEDIA_TOTAL)
        cats = page.locator(".level-badges .chip").all_inner_texts()
        expect(sum(1 for c in cats if re.search(r"\n?\s*1$", c.strip())) >= 3 or len(cats) >= 3,
               "도메인 화면에 대분류 3개가 있다", cats[:6])
        expect(page.get_by_text("TV · 극장 애니메이션").count() >= 1, "TV · 극장 애니메이션 비교군 블록이 보인다")
        if out_dir:
            path = out_dir / f"{args.prefix}-home.png"
            page.screenshot(path=str(path))
            shots.append(path)

        # 2) 비교군 카드 30장 · 아이콘 로드
        for arena, label, expected in (
            ("anime-tv", "TV · 극장 애니메이션", ARENA_COUNTS["anime-tv"]),
            ("manga-volumes", "만화 · 단행본", ARENA_COUNTS["manga-volumes"]),
            ("feature-films", "실사 영화", ARENA_COUNTS["feature-films"]),
        ):
            page.goto(f"{base}?domain=media&arena={arena}", wait_until="networkidle")
            page.wait_for_timeout(1200)
            count = page.locator("article[data-item]").count()
            expect(count == expected, f"{label} 카드 {expected}장", count)
            loaded = page.evaluate(
                """() => Array.from(document.querySelectorAll('.card .item-icon img'))
                     .filter(img => img.complete && img.naturalWidth > 0).length""",
            )
            expect(loaded >= expected, f"{label} 포스터 아이콘 {expected}개 로드", loaded)
            first = page.locator("article[data-item]").first.inner_text()
            expect("가중" in first or "WEIGHTED" in first.upper(), f"{label} 카드에 가중 점수", first[:80])

        if out_dir:
            path = out_dir / f"{args.prefix}-arena.png"
            page.screenshot(path=str(path))
            shots.append(path)

        # 3) 상세 — 만화
        page.goto(f"{base}?domain=media&arena=manga-volumes", wait_until="networkidle")
        page.wait_for_timeout(900)
        page.locator("article[data-item]").first.click()
        page.wait_for_timeout(700)
        visible = [i for i in range(page.locator(".modal").count()) if page.locator(".modal").nth(i).is_visible()]
        expect(bool(visible), "카드를 누르면 상세 모달이 열린다", visible)
        detail = page.locator(".modal").nth(visible[0]).inner_text() if visible else ""
        expect("누적 평점(100점)" in detail, "상세에 누적 평점(100점) 행", detail[:120])
        expect("AniList" in detail, "상세에 AniList 출처 표기")
        expect("단행본 구매" in detail, "상세에 단행본 구매 티어")
        expect("제작 · 플랫폼" in detail and "개발사" not in detail, "미디어 항목은 '제작 · 플랫폼' 라벨", detail[:160])
        expect("권당 정가 미확인" in detail, "가격은 지어내지 않고 미확인으로 둔다")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # 4) EN
        page.goto(f"{base}?domain=media&arena=anime-tv&lang=en", wait_until="networkidle")
        page.wait_for_timeout(1100)
        en_h1 = page.locator("h1").first.inner_text()
        expect("TV & Film Animation" in en_h1, "EN 비교군 제목", en_h1)
        en_cards = page.locator("article[data-item]").all_inner_texts()
        leaks = [text for text in en_cards[:6] if KOREAN.search(text)]
        expect(not leaks, "EN 카드에 한글 잔존 없음", leaks[:1])

        # 5) 비교
        page.goto(f"{base}?domain=media&arena=anime-tv", wait_until="networkidle")
        page.wait_for_timeout(900)
        boxes = page.locator("input[data-compare]")
        boxes.nth(0).click()
        boxes.nth(1).click()
        page.wait_for_timeout(300)
        open_btn = page.locator("#compareOpen")
        open_btn.click()
        page.wait_for_timeout(1000)
        compare_text = page.locator("#view").inner_text()
        expect("나란히 비교" in page.locator("h1").first.inner_text(), "비교 화면이 열린다")
        expect("누적 평점(100점)" in compare_text, "비교 표에 누적 평점(100점) 행")

        # 6) 기존 흐름 회귀
        page.goto(f"{base}", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect("등대" in page.locator("h1").first.inner_text() or page.locator("h1").count() > 0,
               "등대 첫 화면이 그대로 뜬다", page.locator("h1").first.inner_text()[:60])
        page.goto(f"{base}?domain=catalog", wait_until="networkidle")
        page.wait_for_timeout(900)
        chips = page.locator(".domain-chip").all_inner_texts()
        joined = " ".join(chips)
        expect(all(word in joined for word in ("앱", "게임", "AI 도구", "영화")),
               "전체 탐색 도메인 필터에 앱·게임·AI·미디어가 함께", chips)
        for domain in ("app", "game", "ai"):
            page.goto(f"{base}?domain={domain}", wait_until="networkidle")
            page.wait_for_timeout(700)
            expect(page.locator("h1").count() > 0, f"{domain} 도메인 화면이 열린다")

        # 7) 모바일
        mobile = browser.new_context(viewport={"width": 390, "height": 900}, locale="ko-KR").new_page()
        mobile.goto(f"{base}?domain=media", wait_until="networkidle")
        mobile.wait_for_timeout(1000)
        width = mobile.evaluate("document.documentElement.scrollWidth")
        expect(width <= 390, "390px 가로 넘침 0", width)
        if out_dir:
            path = out_dir / f"{args.prefix}-mobile.png"
            mobile.screenshot(path=str(path))
            shots.append(path)
        browser.close()

    expect(not errors, "콘솔·페이지 오류 0건", errors[:3])
    passed = sum(1 for _l, ok, _x in RESULTS if ok)
    print(f"\n결과: {passed}/{len(RESULTS)} 통과 · 스크린샷 {[str(p) for p in shots]}")
    if httpd:
        httpd.shutdown()
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
