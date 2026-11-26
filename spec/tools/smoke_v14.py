#!/usr/bin/env python3
"""파로스 v14 3차 대량 적재(500종+) 스모크 검증 — 건수는 카탈로그·인덱스에서 계산해 낡지 않는다.

무엇을 확인하는가 (2분 이내)
  1) 데이터 계약: 데이터 칩 = 스키마 v0.4.0 · 총 건수 · 비교군 수, 홈 장르 블록 = featured
  2) 이번 배치의 신규 11개 비교군 — 카드 수·`자동 수집` 배지·192px 아이콘 로드
  3) `자동 수집` 상세 안내(auto_fact) / 검증 완료 항목에는 없음
  4) KO/EN 전환: 신규 비교군·상세에서 한글 잔존 0건, 배지는 Auto-collected
  5) 콘솔 오류·페이지 예외·HTTP 4xx/5xx 0건, 390px 가로 넘침 0
  6) 스크린샷: --shots-dir 에 home·arena 2장 (기본 이름 live-v14-bulk3-*.png)

사용
  python3 projects/pharos/scripts/smoke_v14.py
  python3 projects/pharos/scripts/smoke_v14.py --live --shots-dir projects/pharos/live
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import re
import socketserver
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
WEB_ROOT = ROOT / "web"
LIVE = "https://aira1346.github.io/pharos/"
KOREAN = re.compile(r"[\uac00-\ud7a3]")
RESULTS: list[tuple[str, bool, str]] = []

# 이번 배치(v14)에서 새로 들어온 비교군 — 건수는 데이터에서 계산한다.
NEW_ARENAS = [
    "horror-thriller", "story-narrative-vn", "sim-tycoon-casual", "card-board-digital",
    "mobile-action-arcade", "maps-navigation-travel", "photo-camera-filter",
    "finance-budget-crypto", "remote-desktop-network", "reading-ebooks-news", "ai-audio-video",
]
# 기존 비교군 보강분(전수는 26개 — 화면 확인은 대표 8개)
ENRICHED = ["fps-shooters", "survival-crafting", "co-op-party", "city-builder-management",
            "soulslike", "open-world-rpg", "web-browsers", "messaging-team"]
ARENA_SHOT = "horror-thriller"
MODAL_SHOT_ITEM = "resident-evil-4"


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
    def log_message(self, *args, **kwargs):
        return


def serve(root: Path):
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
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
    stats = index["arena_stats"]
    featured = [a for a in catalog["home"]["featured_arenas"] if a in stats]
    auto_ids = {row["id"] for row in items if row.get("review_tier") == "auto_fact"}
    verified_ids = {row["id"] for row in items if row.get("review_tier", "verified") == "verified"}
    counts = {arena_id: stats[arena_id]["count"] for arena_id in NEW_ARENAS + ENRICHED if arena_id in stats}
    batch_ids = [row["id"] for row in items if set(row["arenas"]) & set(NEW_ARENAS)]

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

        # 1) 홈 — 총 건수·비교군·featured 블록
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(800)
        chip = page.inner_text("#datasetChip")
        expect(f"{total}건" in chip and f"비교군 {arenas}" in chip and "v0.4.0" in chip,
               f"홈 데이터 칩 = v0.4.0 · {total}건 · 비교군 {arenas}", chip)
        expect(total >= 500, f"총 {total}종(500종 돌파)", str(total))
        blocks = page.eval_on_selector_all("#genreList .genre-block", "els => els.map(e => e.dataset.arena)")
        expect(len(blocks) == len(featured), f"홈 장르 블록 {len(featured)}개", str(len(blocks)))
        missing_blocks = [a for a in NEW_ARENAS + ENRICHED if a not in blocks]
        expect(not missing_blocks, "홈에 이번 배치 19개 비교군 노출", str(missing_blocks))
        hero_meta = page.inner_text(".hero-meta")
        expect(f"{total}" in hero_meta, f"히어로에 {total}건 표시", hero_meta.replace("\n", " | ")[:120])
        if shots:
            page.screenshot(path=str(shots / "live-v14-bulk3-home.png"))

        # 2) 신규·보강 비교군 — 카드 수·배지·아이콘
        for arena_id, count in counts.items():
            page.goto(f"{base}?arena={arena_id}", wait_until="networkidle")
            page.wait_for_timeout(450)
            rows = cards(page)
            expect(len(rows) == count, f"{arena_id} = {count}건", str([c["id"] for c in rows]))
            picks = len([c for c in rows if c["verdict"] != "avoid"])
            icons = page.eval_on_selector_all(
                "#grid .card .item-icon img", "els => els.map(e => e.complete && e.naturalWidth === 192)")
            expect(len(icons) == picks and all(icons), f"{arena_id} 아이콘 192px 로드 {picks}건", str(icons))

        # 3) 이번 배치 항목에만 자동 수집 배지가 붙는지
        page.goto(f"{base}?arena={ARENA_SHOT}", wait_until="networkidle")
        page.wait_for_timeout(450)
        badges = page.eval_on_selector_all("#grid .card .chip--auto, #avoidGrid .card .chip--auto", "els => els.length")
        expect(badges == counts[ARENA_SHOT], f"{ARENA_SHOT} 자동 수집 배지 {counts[ARENA_SHOT]}개", str(badges))

        # 4) 상세 모달 — auto_fact 안내 / verified 는 없음
        page.goto(f"{base}?arena={ARENA_SHOT}", wait_until="networkidle")
        page.wait_for_timeout(450)
        page.click(f'#grid .card[data-id="{MODAL_SHOT_ITEM}"], #avoidGrid .card[data-id="{MODAL_SHOT_ITEM}"]')
        page.wait_for_timeout(700)
        modal = page.inner_text("#modal")
        expect("자동 수집" in modal and "순차 검수" in modal, "자동 수집 상세에 1차 판정 안내",
               modal[:140].replace("\n", " | "))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        page.goto(f"{base}?arena=pkm-notes", wait_until="networkidle")
        page.wait_for_timeout(450)
        page.click('#grid .card[data-id="obsidian"]')
        page.wait_for_timeout(700)
        vmodal = page.inner_text("#modal")
        expect("순차 검수" not in vmodal, "검증 완료 항목에는 자동 수집 안내 없음", vmodal[:120].replace("\n", " | "))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # 5) EN 모드 — 신규 비교군 한글 0 + 배지 영문
        en = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US").new_page()
        en.goto(f"{base}?lang=en&arena={ARENA_SHOT}", wait_until="networkidle")
        en.wait_for_timeout(700)
        expect(en.evaluate("document.documentElement.lang") == "en", "EN 언어 전환", "")
        expect(not korean_left(en), f"EN {ARENA_SHOT} 한글 잔존 0건", str(korean_left(en)[:4]))
        expect("Auto-collected" in en.inner_text("#grid"), "EN 자동 수집 배지 = Auto-collected",
               en.inner_text("#grid")[:100].replace("\n", " | "))
        en.click(f'#grid .card[data-id="{MODAL_SHOT_ITEM}"], #avoidGrid .card[data-id="{MODAL_SHOT_ITEM}"]')
        en.wait_for_timeout(700)
        en_modal = en.inner_text("#modalBody")
        en_modal_kr = [line for line in en_modal.split("\n") if KOREAN.search(line)]
        expect(not en_modal_kr, "EN auto_fact 상세 모달 한글 잔존 0건", str(en_modal_kr[:3]))
        en.keyboard.press("Escape")
        en.wait_for_timeout(200)
        for arena_id in ("maps-navigation-travel", "photo-camera-filter", "finance-budget-crypto",
                         "reading-ebooks-news", "ai-audio-video", "card-board-digital",
                         "mobile-action-arcade"):
            en.goto(f"{base}?lang=en&arena={arena_id}", wait_until="networkidle")
            en.wait_for_timeout(500)
            expect(not korean_left(en), f"EN {arena_id} 한글 잔존 0건", str(korean_left(en)[:4]))
        en.goto(f"{base}?lang=en&arena=streaming-video", wait_until="networkidle")
        en.wait_for_timeout(500)
        expect(not korean_left(en), "EN streaming-video 한글 잔존 0건", str(korean_left(en)[:4]))
        en.close()

        # 6) 390px
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR").new_page()
        for arena_id in (ARENA_SHOT, "maps-navigation-travel", "card-board-digital",
                         "reading-ebooks-news", "ai-audio-video"):
            mobile.goto(f"{base}?arena={arena_id}", wait_until="networkidle")
            mobile.wait_for_timeout(500)
            expect(overflow(mobile) == 0, f"390px {arena_id} 가로 넘침 0", str(overflow(mobile)))
        mobile.close()

        # 7) 비교군 스크린샷
        page.goto(f"{base}?arena={ARENA_SHOT}", wait_until="networkidle")
        page.wait_for_timeout(700)
        if shots:
            page.screenshot(path=str(shots / "live-v14-bulk3-arena.png"))

        expect(not errors, "콘솔 오류·페이지 예외 0건", "; ".join(errors[:3]))
        expect(not bad_http, "HTTP 4xx/5xx 0건", "; ".join(bad_http[:3]))
        browser.close()
    if httpd:
        httpd.shutdown()

    passed = sum(1 for _l, ok, _e in RESULTS if ok)
    print("=" * 70)
    print(f"결과: {passed}/{len(RESULTS)} PASS · 총 {total}종 · auto_fact {len(auto_ids)}종 / verified {len(verified_ids)}종 "
          f"· 이번 배치 {len(batch_ids)}종")
    print("=" * 70)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
