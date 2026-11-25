#!/usr/bin/env python3
"""파로스 v12 대량 팩트 적재 스모크 검증 — 배치마다 734개 풀 테스트 대신 핵심만 빠르게.

무엇을 확인하는가 (약 30항목, 1분 이내)
  1) 데이터 계약: 데이터 칩 = 스키마 v0.4.0 · 210건 · 비교군 33, 홈 장르 블록 = featured 33개
  2) 신규 비교군: 게임 5(arpg·soulslike·city-builder·co-op·racing) + 앱 6(messaging·media·video·dev·backup·read-later)
     — 각 비교군 카드 수, 자동 수집 배지, 아이콘 192px 로드
  3) `자동 수집` 배지·안내: auto_fact 카드에 배지가 있고 검증 완료 항목에는 없다. 상세 모달 상단에
     "1차 판정 · 순차 검수 중" 안내가 뜬다(검증 완료 항목에는 뜨지 않는다).
  4) KO/EN 전환: EN 모드에서 신규 비교군·상세에 한글 잔존 0건, 배지는 Auto-collected.
  5) 콘솔 오류·페이지 예외·HTTP 4xx/5xx 0건, 390px 가로 넘침 0.
  6) 스크린샷: --shots-dir 에 home·arena 2장.

사용
  python3 projects/pharos/scripts/smoke_v12.py                    # web/ 로컬 서버로 검증
  python3 projects/pharos/scripts/smoke_v12.py --live             # https://aira1346.github.io/pharos/
  CHROME_PATH=/... LD_LIBRARY_PATH=/... python3 ... --live --shots-dir projects/pharos/live
종료 코드 0 = 전부 통과.
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

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
WEB_ROOT = ROOT / "web"
LIVE = "https://aira1346.github.io/pharos/"
KOREAN = re.compile(r"[\uac00-\ud7a3]")
RESULTS: list[tuple[str, bool, str]] = []

NEW_GAME_ARENAS = {
    "arpg-hack-slash": 8, "soulslike": 8, "city-builder-management": 10,
    "co-op-party": 10, "racing-sim": 8,
}
NEW_APP_ARENAS = {
    "messaging-team": 8, "media-players": 10, "video-editing": 7,
    "dev-terminals-git": 10, "backup-sync": 8, "read-later": 4,
}


def expect(condition: bool, label: str, extra: str = "") -> None:
    RESULTS.append((label, bool(condition), str(extra)))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + ("" if condition else f"  ← {extra}"))


def korean_left(page) -> list[str]:
    return page.evaluate(
        """(pattern) => {
        const re = new RegExp(pattern);
        const out = new Set();
        document.body.innerText.split('\\n').forEach((line) => { if (re.test(line)) out.add(line.trim()); });
        document.querySelectorAll('[aria-label],[title],[placeholder],[alt]').forEach((el) => {
          ['aria-label', 'title', 'placeholder', 'alt'].forEach((attr) => {
            const v = el.getAttribute(attr);
            if (v && re.test(v)) out.add(attr + ': ' + v);
          });
        });
        return [...out];
      }""",
        KOREAN.pattern,
    )


def overflow(page) -> int:
    return page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


def cards(page):
    return page.eval_on_selector_all(
        "#grid .card, #avoidGrid .card",
        "els => els.map(e => ({id: e.dataset.id, verdict: e.dataset.verdict, score: e.dataset.score,"
        " text: e.innerText}))",
    )


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):  # noqa: D401 — 검증 로그만 남긴다
        return


def serve(root: Path):
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="GitHub Pages 라이브 URL 로 검증")
    parser.add_argument("--shots-dir", default="")
    parser.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    args = parser.parse_args()

    httpd = None
    if args.live:
        base = LIVE
    else:
        httpd, base = serve(WEB_ROOT)
    shots = Path(args.shots_dir) if args.shots_dir else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    catalog = json.loads((WEB_ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    index = json.loads((WEB_ROOT / "data" / "search-index.json").read_text(encoding="utf-8"))
    items = index["items"]
    total = index["counts"]["items"]
    arenas = index["counts"]["arenas"]
    featured = [a for a in catalog["home"]["featured_arenas"] if a in index["arena_stats"]]
    auto_ids = {row["id"] for row in items if row.get("review_tier") == "auto_fact"}
    verified_ids = {row["id"] for row in items if row.get("review_tier", "verified") == "verified"}

    with sync_playwright() as p:
        launch = {"executable_path": args.chrome} if args.chrome else {}
        browser = p.chromium.launch(**launch)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="ko-KR")
        page = ctx.new_page()
        errors: list[str] = []
        bad_http: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: errors.append(f"console: {msg.text}") if msg.type == "error" else None)
        page.on("response", lambda res: bad_http.append(f"{res.status} {res.url}") if res.status >= 400 else None)

        # 1) 홈
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(700)
        chip = page.inner_text("#datasetChip")
        expect(f"{total}건" in chip and f"비교군 {arenas}" in chip and "v0.4.0" in chip,
               f"홈 데이터 칩 = v0.4.0 · {total}건 · 비교군 {arenas}", chip)
        expect(total >= 207, f"총 {total}종(200종 이상)", str(total))
        blocks = page.eval_on_selector_all("#genreList .genre-block", "els => els.map(e => e.dataset.arena)")
        expect(len(blocks) == len(featured), f"홈 장르 블록 {len(featured)}개", str(len(blocks)))
        expect(all(a in blocks for a in list(NEW_GAME_ARENAS) + list(NEW_APP_ARENAS)),
               "홈에 신규 11개 비교군 노출", str([a for a in NEW_GAME_ARENAS if a not in blocks]))
        hero_meta = page.inner_text(".hero-meta")
        expect(f"{total}" in hero_meta, f"히어로에 {total}건 표시", hero_meta.replace("\n", " | ")[:120])
        if shots:
            page.screenshot(path=str(shots / "live-v12-bulk100-home.png"))
        home_errors = len(errors)

        # 2) 신규 게임 비교군 — 카드 수·배지·아이콘
        for arena_id, count in {**NEW_GAME_ARENAS, **NEW_APP_ARENAS}.items():
            page.goto(f"{base}?arena={arena_id}", wait_until="networkidle")
            page.wait_for_timeout(500)
            rows = cards(page)
            expect(len(rows) == count, f"{arena_id} = {count}건", str([c['id'] for c in rows]))
            badges = page.eval_on_selector_all(
                "#grid .card .chip--auto, #avoidGrid .card .chip--auto", "els => els.length")
            expect(badges >= count, f"{arena_id} 카드에 자동 수집 배지 {count}개", str(badges))
            picks = len([c for c in rows if c["verdict"] != "avoid"])
            icons = page.eval_on_selector_all(
                "#grid .card .item-icon img", "els => els.map(e => e.complete && e.naturalWidth === 192)")
            expect(len(icons) == picks and all(icons), f"{arena_id} 아이콘 192px 로드 {picks}건", str(icons))

        # 3) 상세 모달 — auto_fact 안내 / verified 는 없음
        page.goto(f"{base}?arena=soulslike", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.click('#grid .card[data-id="elden-ring"]')
        page.wait_for_timeout(600)
        modal = page.inner_text("#modal")
        expect("자동 수집" in modal and "순차 검수" in modal, "자동 수집 상세에 1차 판정 안내",
               modal[:140].replace("\n", " | "))
        expect("Steam 누적" in modal or "Steam" in modal, "상세에 Steam 평가 근거", modal[:100].replace("\n", " | "))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        page.goto(f"{base}?arena=pkm-notes", wait_until="networkidle")
        page.wait_for_timeout(500)
        page.click('#grid .card[data-id="obsidian"]')
        page.wait_for_timeout(600)
        vmodal = page.inner_text("#modal")
        expect("순차 검수" not in vmodal, "검증 완료 항목에는 자동 수집 안내 없음", vmodal[:120].replace("\n", " | "))
        vbadge = page.eval_on_selector_all("#modal .chip--auto", "els => els.length")
        expect(vbadge == 0, "검증 완료 항목에 자동 수집 배지 없음", str(vbadge))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # 4) EN 모드 — 신규 비교군 한글 0 + 배지 영문
        en = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US").new_page()
        en.goto(f"{base}?lang=en&arena=dev-terminals-git", wait_until="networkidle")
        en.wait_for_timeout(700)
        expect(en.evaluate("document.documentElement.lang") == "en", "EN 언어 전환", "")
        expect(not korean_left(en), "EN 개발자 도구 비교군 한글 잔존 0건", str(korean_left(en)[:4]))
        expect("Auto-collected" in en.inner_text("#grid"), "EN 자동 수집 배지 = Auto-collected",
               en.inner_text("#grid")[:100].replace("\n", " | "))
        en.goto(f"{base}?lang=en&arena=messaging-team", wait_until="networkidle")
        en.wait_for_timeout(500)
        en.click('#grid .card[data-id="discord"]')
        en.wait_for_timeout(700)
        en_modal = en.inner_text("#modalBody")
        en_modal_kr = [line for line in en_modal.split("\n") if KOREAN.search(line)]
        expect(not en_modal_kr, "EN auto_fact 상세 모달 한글 잔존 0건", str(en_modal_kr[:3]))
        expect("still being reviewed" in en_modal, "EN 상세에 1차 판정 안내",
               en_modal[:120].replace("\n", " | "))
        en.keyboard.press("Escape")
        en.wait_for_timeout(200)
        for arena_id in ("arpg-hack-slash", "messaging-team", "video-editing"):
            en.goto(f"{base}?lang=en&arena={arena_id}", wait_until="networkidle")
            en.wait_for_timeout(600)
            expect(not korean_left(en), f"EN {arena_id} 한글 잔존 0건", str(korean_left(en)[:4]))
        en.close()

        # 5) 390px
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR").new_page()
        for arena_id in ("arpg-hack-slash", "messaging-team", "backup-sync"):
            mobile.goto(f"{base}?arena={arena_id}", wait_until="networkidle")
            mobile.wait_for_timeout(500)
            expect(overflow(mobile) == 0, f"390px {arena_id} 가로 넘침 0", str(overflow(mobile)))
        mobile.close()

        # 6) 비교군 스크린샷(auto_fact 배지가 보이는 화면)
        page.goto(f"{base}?arena=arpg-hack-slash", wait_until="networkidle")
        page.wait_for_timeout(600)
        if shots:
            page.screenshot(path=str(shots / "live-v12-bulk100-arena.png"))

        expect(not errors, "콘솔 오류·페이지 예외 0건", "; ".join(errors[:3]))
        expect(not bad_http, "HTTP 4xx/5xx 0건", "; ".join(bad_http[:3]))
        browser.close()
    if httpd:
        httpd.shutdown()

    passed = sum(1 for _l, ok, _e in RESULTS if ok)
    print("=" * 70)
    print(f"결과: {passed}/{len(RESULTS)} PASS · auto_fact {len(auto_ids)}종 / verified {len(verified_ids)}종")
    print("=" * 70)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
