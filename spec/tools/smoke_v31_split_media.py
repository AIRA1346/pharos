#!/usr/bin/env python3
"""파로스 v31 — 영화·애니·만화 도메인 분리 스모크.

통합 미디어(media) 도메인을 영화(movie)·애니(anime)·만화(manga) 3개 도메인으로 나누고,
도메인마다 대분류 2개·장르별 비교군 7개로 재편한 결과를 화면과 데이터 양쪽에서 확인한다.

무엇을 확인하는가
  1) 데이터 — 도메인 6개, 작품 3도메인 각 175종·비교군 7개·대분류 2개, 총 2,072종.
  2) 상단 탭 — 등대·전체 탐색·앱·게임·AI 도구·영화·애니·만화 8개가 순서대로, 1280px 에서 잘리지 않는다.
  3) 도메인 화면 — 영화/애니/만화 각각 175건·장르 블록 7개·대분류 칩 2개.
  4) 비교군 — 21개 비교군의 카드 수가 데이터와 같고, 아이콘·판정 배지·가중 점수가 보인다.
  5) 상세 — 작품 항목은 '제작 · 플랫폼' 라벨, 애니는 AniList·누적 평점(100점), 영화는 Letterboxd.
  6) EN — 영화 도메인·비교군 이름이 영문으로 뜨고 카드에 한글이 없다.
  7) 비교 — 같은 비교군의 두 항목을 나란히 비교.
  8) 반응형 — 390px 가로 넘침 0, 탭 8개가 4×2 격자 안에 모두 보인다.
  9) 오류 0건 · 스크린샷(--shots-dir) {prefix}-desktop.png · {prefix}-mobile.png.

사용
  python3 projects/pharos/scripts/smoke_v31_split_media.py
  python3 projects/pharos/scripts/smoke_v31_split_media.py --live --shots-dir projects/pharos/live
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

CATALOG = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
WORKS = ("movie", "anime", "manga")
ARENA_COUNT = {
    a["id"]: len(json.loads((ROOT / "data" / a["data_file"]).read_text(encoding="utf-8")))
    for a in CATALOG["arenas"]
}
WORK_TOTAL = sum(ARENA_COUNT[a["id"]] for a in CATALOG["arenas"] if a["domain"] in WORKS)

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="라이브 사이트를 검사한다")
    ap.add_argument("--shots-dir", default="", help="스크린샷을 저장할 폴더(예: projects/pharos/live)")
    ap.add_argument("--prefix", default="live-v31-split")
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

    # ---------------------------------------------------------------- 1) 데이터 계약
    domain_ids = [d["id"] for d in CATALOG["domains"]]
    expect(domain_ids == ["app", "game", "ai", "movie", "anime", "manga"],
           "데이터: 도메인 6개 = 앱·게임·AI 도구·영화·애니·만화", domain_ids)
    DOMAIN_TOTALS: dict[str, int] = {}
    for domain in WORKS:
        arenas = [a for a in CATALOG["arenas"] if a["domain"] == domain]
        cats = [c for c in CATALOG["categories"] if c["domain"] == domain]
        expect(len(arenas) == 7 and len(cats) == 2,
               f"데이터: {domain} 대분류 2 · 비교군 7", f"{len(cats)}대분류/{len(arenas)}비교군")
        total = sum(ARENA_COUNT[a["id"]] for a in arenas)
        # v32 부터 작품은 계속 늘어난다 — 고정 수치 대신 비교군 합계와 도메인 합계가 같은지만 본다.
        expect(total >= 175, f"데이터: {domain} 175종 이상", total)
        DOMAIN_TOTALS[domain] = total
    expect(WORK_TOTAL == sum(DOMAIN_TOTALS.values()) and WORK_TOTAL >= 525,
           "데이터: 작품 3도메인 합계 = 도메인 합", (WORK_TOTAL, DOMAIN_TOTALS))

    errors: list[str] = []
    with sync_playwright() as p:
        browser = launch(p.chromium)
        ctx = browser.new_context(viewport={"width": 1280, "height": 1100}, locale="ko-KR")
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

        # ------------------------------------------------------------ 2) 상단 탭
        page.goto(f"{base}?domain=catalog", wait_until="networkidle")
        page.wait_for_timeout(900)
        tabs = page.locator("#domainTabs button").all_inner_texts()
        expect(tabs[:2] == ["🚨 등대", "🧭 전체 탐색"], "상단 탭 앞 두 개 = 등대·전체 탐색", tabs[:2])
        expect([t.strip() for t in tabs[2:]] == ["앱", "게임", "AI 도구", "영화", "애니", "만화"],
               "상단 탭 = 앱·게임·AI 도구·영화·애니·만화", tabs[2:])
        expect("영화 · 애니 · 만화" not in " ".join(tabs), "통합 미디어 탭이 남아 있지 않다", tabs)
        boxes = page.evaluate(
            """() => Array.from(document.querySelectorAll('#domainTabs button')).map(b => {
                 const r = b.getBoundingClientRect();
                 return {text: b.textContent.trim(), left: r.left, right: r.right, top: r.top, w: r.width};
               })""",
        )
        expect(all(b["left"] >= 0 and b["right"] <= 1280 + 1 and b["w"] > 0 for b in boxes),
               "1280px 에서 탭 8개가 모두 화면 안에 있다", [(b["text"], round(b["left"]), round(b["right"])) for b in boxes])
        expect(page.evaluate("document.documentElement.scrollWidth") <= 1280,
               "1280px 가로 넘침 0", page.evaluate("document.documentElement.scrollWidth"))

        # ------------------------------------------------------------ 3) 도메인 화면
        for domain, label in (("movie", "영화"), ("anime", "애니"), ("manga", "만화")):
            page.goto(f"{base}?domain={domain}", wait_until="networkidle")
            page.wait_for_timeout(1100)
            h1 = page.locator("h1").first.inner_text()
            expect(f"{label}" in h1 and str(DOMAIN_TOTALS[domain]) in h1,
                   f"{label} 도메인 화면이 {DOMAIN_TOTALS[domain]}건", h1)
            cat_chips = page.locator(".level-badges .chip--link").all_inner_texts()
            expect(len(cat_chips) == 2, f"{label} 도메인에 대분류 칩 2개", cat_chips)
            blocks = page.locator(".genre-block").count()
            expect(blocks == 7, f"{label} 도메인에 장르 비교군 블록 7개", blocks)
            expect(page.evaluate("document.documentElement.scrollWidth") <= 1280,
                   f"{label} 도메인 1280px 가로 넘침 0", page.evaluate("document.documentElement.scrollWidth"))

        if out_dir:
            page.goto(f"{base}?domain=anime", wait_until="networkidle")
            page.wait_for_timeout(1200)
            path = out_dir / f"{args.prefix}-desktop.png"
            page.screenshot(path=str(path))
            shots.append(path)

        # ------------------------------------------------------------ 4) 비교군 카드
        for domain in WORKS:
            for arena in [a for a in CATALOG["arenas"] if a["domain"] == domain]:
                page.goto(f"{base}?domain={domain}&arena={arena['id']}", wait_until="networkidle")
                page.wait_for_timeout(900)
                count = page.locator("article[data-item]").count()
                expect(count == ARENA_COUNT[arena["id"]],
                       f"비교군 {arena['id']} 카드 {ARENA_COUNT[arena['id']]}장", count)
        for domain, arena_id in (("movie", "movie-sf-fantasy"), ("anime", "anime-films"), ("manga", "manga-action")):
            page.goto(f"{base}?domain={domain}&arena={arena_id}", wait_until="networkidle")
            page.wait_for_timeout(1100)
            loaded = page.evaluate(
                """() => Array.from(document.querySelectorAll('.card .item-icon img'))
                     .filter(img => img.complete && img.naturalWidth > 0).length""",
            )
            expect(loaded >= min(ARENA_COUNT[arena_id], 10), f"{arena_id} 아이콘 로드", loaded)
            first = page.locator("article[data-item]").first.inner_text()
            expect("가중" in first or "WEIGHTED" in first.upper(), f"{arena_id} 카드에 가중 점수", first[:80])

        # ------------------------------------------------------------ 5) 상세
        page.goto(f"{base}?domain=anime&arena=anime-action", wait_until="networkidle")
        page.wait_for_timeout(1000)
        page.locator("article[data-item]").first.click()
        page.wait_for_timeout(800)
        visible = [i for i in range(page.locator(".modal").count()) if page.locator(".modal").nth(i).is_visible()]
        detail = page.locator(".modal").nth(visible[0]).inner_text() if visible else ""
        expect(bool(visible), "애니 카드를 누르면 상세 모달이 열린다", visible)
        expect("제작 · 플랫폼" in detail and "개발사" not in detail, "작품 항목은 '제작 · 플랫폼' 라벨", detail[:160])
        expect("누적 평점(100점)" in detail and "AniList" in detail, "애니 상세에 AniList·누적 평점(100점)", detail[:200])
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        page.goto(f"{base}?domain=movie&arena=movie-drama", wait_until="networkidle")
        page.wait_for_timeout(1000)
        page.locator("article[data-item]").first.click()
        page.wait_for_timeout(800)
        visible = [i for i in range(page.locator(".modal").count()) if page.locator(".modal").nth(i).is_visible()]
        detail = page.locator(".modal").nth(visible[0]).inner_text() if visible else ""
        expect("Letterboxd" in detail, "영화 상세에 Letterboxd 출처", detail[:200])
        expect("제작 · 플랫폼" in detail, "영화 상세도 '제작 · 플랫폼' 라벨", detail[:120])
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ------------------------------------------------------------ 6) EN
        page.goto(f"{base}?domain=movie&lang=en", wait_until="networkidle")
        page.wait_for_timeout(1200)
        en_h1 = page.locator("h1").first.inner_text()
        expect("Film" in en_h1, "EN 영화 도메인 제목", en_h1)
        en_blocks = page.locator(".genre-block .genre-name").all_inner_texts()
        expect(all(not KOREAN.search(name) for name in en_blocks) and len(en_blocks) == 7,
               "EN 장르 비교군 7개 이름이 영문", en_blocks)
        page.goto(f"{base}?domain=anime&arena=anime-films&lang=en", wait_until="networkidle")
        page.wait_for_timeout(1100)
        expect("Anime Films" in page.locator("h1").first.inner_text(), "EN 비교군 제목 = Anime Films",
               page.locator("h1").first.inner_text())
        en_cards = page.locator("article[data-item]").all_inner_texts()
        leaks = [text for text in en_cards[:6] if KOREAN.search(text)]
        expect(not leaks, "EN 카드에 한글 잔존 없음", leaks[:1])

        # ------------------------------------------------------------ 7) 비교
        page.goto(f"{base}?domain=manga&arena=manga-action", wait_until="networkidle")
        page.wait_for_timeout(1000)
        boxes = page.locator("input[data-compare]")
        boxes.nth(0).click()
        boxes.nth(1).click()
        page.wait_for_timeout(300)
        page.locator("#compareOpen").click()
        page.wait_for_timeout(1000)
        expect("나란히 비교" in page.locator("h1").first.inner_text(), "비교 화면이 열린다",
               page.locator("h1").first.inner_text())
        expect("누적 평점(100점)" in page.locator("#view").inner_text(), "만화 비교 표에 누적 평점(100점)")

        # ------------------------------------------------------------ 8) 모바일
        mobile = browser.new_context(viewport={"width": 390, "height": 900}, locale="ko-KR").new_page()
        mobile.goto(f"{base}?domain=movie", wait_until="networkidle")
        mobile.wait_for_timeout(1100)
        width = mobile.evaluate("document.documentElement.scrollWidth")
        expect(width <= 390, "390px 가로 넘침 0", width)
        mboxes = mobile.evaluate(
            """() => Array.from(document.querySelectorAll('#domainTabs button')).map(b => {
                 const r = b.getBoundingClientRect();
                 return {text: b.textContent.trim(), left: r.left, right: r.right, top: r.top};
               })""",
        )
        expect(len(mboxes) == 8 and all(b["left"] >= -1 and b["right"] <= 391 for b in mboxes),
               "390px 에서 탭 8개가 모두 화면 안에 있다", [(b["text"], round(b["left"]), round(b["right"])) for b in mboxes])
        expect(len({round(b["top"]) for b in mboxes}) == 2, "390px 탭이 4×2 두 줄로 접힌다",
               sorted({round(b["top"]) for b in mboxes}))
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
