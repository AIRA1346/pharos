#!/usr/bin/env python3
"""파로스 v26.1 — 구 미디어 URL 호환 스모크 (v31 도메인 분리 뒤).

v31 에서 통합 `media` 도메인이 영화(movie)·애니(anime)·만화(manga)로 나뉘었다.
이 스크립트는 **예전에 공유된 주소가 깨지지 않는지**만 본다.

무엇을 확인하는가
  1) `?domain=media` → 영화 도메인으로 열리고, 주소가 `?domain=movie` 로 정리된다.
  2) `?arena=feature-films` → 영화, `?arena=anime-tv` → 애니, `?arena=manga-volumes` → 만화 도메인.
  3) `?domain=media&category=anime` → 애니 도메인(옛 대분류), `?domain=media&arena=anime-tv` → 애니 도메인.
  4) 구 주소 + `lang=en` 도 영문 도메인 화면으로 열린다.
  5) `?domain=media&item=interstellar` → 영화 도메인의 상세 모달이 열린다.
  6) 새 주소·탭은 그대로 동작하고(영화·애니·만화 탭), 390px 가로 넘침 0.

사용
  python3 projects/pharos/scripts/smoke_v26_media.py
  python3 projects/pharos/scripts/smoke_v26_media.py --live
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
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
CHROME_CANDIDATES = [
    os.environ.get("PHAROS_CHROME", ""),
    "/workspace/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome",
]
DEPS = "/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu:/workspace/.cache/chromedeps/root/lib/x86_64-linux-gnu"


def expect(condition: bool, label: str, extra: str = "") -> None:
    RESULTS.append((label, bool(condition), str(extra)))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + ("" if condition else f"  ← {extra}"))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
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


def domain_counts() -> dict[str, int]:
    """도메인별 종수를 데이터(카탈로그+비교군 파일)에서 계산한다 — 배치가 늘어도 낡지 않게."""
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / "data" / "catalog.json").read_text(encoding="utf-8"))
    counts = {"movie": 0, "anime": 0, "manga": 0}
    for arena in catalog["arenas"]:
        if arena.get("domain") not in counts:
            continue
        rows = json.loads((root / "data" / arena["data_file"]).read_text(encoding="utf-8"))
        counts[arena["domain"]] += len(rows)
    return counts


DOMAIN_COUNT = domain_counts()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="라이브 사이트를 검사한다")
    args = ap.parse_args()

    httpd = None
    if args.live:
        base = LIVE
    else:
        httpd, base = serve(WEB_ROOT)

    errors: list[str] = []
    with sync_playwright() as p:
        browser = launch(p.chromium)
        ctx = browser.new_context(viewport={"width": 1280, "height": 1000}, locale="ko-KR")
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        def open_url(query: str, wait: int = 900):
            page.goto(f"{base}{query}", wait_until="networkidle")
            page.wait_for_timeout(wait)
            return page.url, page.locator("h1").first.inner_text()

        # 1) ?domain=media → 영화
        url, h1 = open_url("?domain=media")
        expect("domain=movie" in url, "구 ?domain=media 주소가 ?domain=movie 로 정리된다", url)
        expect("영화" in h1 and str(DOMAIN_COUNT["movie"]) in h1,
               f"?domain=media 가 영화 도메인({DOMAIN_COUNT['movie']}건)으로 열린다", h1)

        # 2) 구 비교군 주소 3종
        for old, domain, label in (
            ("feature-films", "movie", "영화"),
            ("anime-tv", "anime", "애니"),
            ("manga-volumes", "manga", "만화"),
        ):
            url, h1 = open_url(f"?arena={old}")
            expect(f"domain={domain}" in url, f"구 ?arena={old} 이 {domain} 도메인으로 매핑된다", url)
            expect(label in h1, f"구 ?arena={old} 화면 제목에 {label}", h1)

        # 3) 옛 대분류·비교군이 함께 붙은 주소
        url, h1 = open_url("?domain=media&category=anime")
        expect("domain=anime" in url and "애니" in h1, "옛 대분류 category=anime 이 애니 도메인으로", f"{url} / {h1}")
        url, h1 = open_url("?domain=media&arena=anime-tv")
        expect("domain=anime" in url and "애니" in h1, "옛 arena=anime-tv 가 애니 도메인으로", f"{url} / {h1}")

        # 4) EN
        url, h1 = open_url("?domain=media&arena=anime-tv&lang=en", wait=1200)
        expect("Anime" in h1 and not KOREAN.search(h1), "구 주소 + EN 이 영문 애니 도메인으로 열린다", h1)

        # 5) 구 주소의 항목 딥링크
        page.goto(f"{base}?domain=media&item=interstellar", wait_until="networkidle")
        page.wait_for_timeout(1200)
        visible = [i for i in range(page.locator(".modal").count()) if page.locator(".modal").nth(i).is_visible()]
        detail = page.locator(".modal").nth(visible[0]).inner_text() if visible else ""
        expect(bool(visible) and "인터스텔라" in detail, "구 주소의 항목 딥링크가 영화 상세를 연다", detail[:80])
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # 6) 새 탭·새 주소
        page.goto(f"{base}?domain=catalog", wait_until="networkidle")
        page.wait_for_timeout(900)
        tabs = page.locator("#domainTabs button").all_inner_texts()
        joined = " ".join(tabs)
        expect(all(word in joined for word in ("영화", "애니", "만화")),
               "새 상단 탭에 영화·애니·만화가 각각 있다", tabs)
        expect("영화 · 애니 · 만화" not in joined, "통합 미디어 탭은 사라졌다", tabs)
        for domain in ("movie", "anime", "manga"):
            url, h1 = open_url(f"?domain={domain}")
            expect(f"domain={domain}" in url and str(DOMAIN_COUNT[domain]) in h1,
                   f"새 ?domain={domain} 이 {DOMAIN_COUNT[domain]}건을 보여 준다", h1)

        # 7) 모바일 가로 넘침
        mobile = browser.new_context(viewport={"width": 390, "height": 900}, locale="ko-KR").new_page()
        mobile.goto(f"{base}?domain=media", wait_until="networkidle")
        mobile.wait_for_timeout(1000)
        width = mobile.evaluate("document.documentElement.scrollWidth")
        expect(width <= 390, "390px 가로 넘침 0", width)
        expect("영화" in mobile.locator("h1").first.inner_text(), "모바일에서도 구 주소가 영화 도메인으로", mobile.locator("h1").first.inner_text())
        browser.close()

    expect(not errors, "콘솔·페이지 오류 0건", errors[:3])
    passed = sum(1 for _l, ok, _x in RESULTS if ok)
    print(f"\n결과: {passed}/{len(RESULTS)} 통과")
    if httpd:
        httpd.shutdown()
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
