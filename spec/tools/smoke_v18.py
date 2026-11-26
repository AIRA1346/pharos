#!/usr/bin/env python3
"""파로스 v18 v0.6.0 표본 규모 보정 스모크 검증 — 건수·점수는 데이터에서 계산해 낡지 않는다.

무엇을 확인하는가 (2분 이내)
  1) 데이터 계약: 데이터 칩 = 스키마 v0.4.0 · 총 1,467건 · 비교군 80, 히어로 건수
  2) 사용자 축 점수가 **규모 보정 반영값**으로 서빙되는지 — 카드 data-score 가 인덱스 값과 같은지
     (대규모 표본 YouTube 87.5 · 중간 Krita 71.7 · 미세 표본 Mathpix 85.5)
  3) 상세 모달의 '산정 메모'에 v0.6.0 규모 보정 근거(표본 수·로그보정·게이트·전후 점수)가 보이는지
  4) 하드 필터 우선 — Clash Royale(표본 4,190만)이 사용자 87.5 인데도 거름 그리드에 남아 있는지
  5) EN 화면: 같은 항목의 한글 잔존 0건 + 'sample-scale adjustment' 문구 표시
  6) 390px 가로 넘침 0 (대규모 표본 항목이 있는 비교군)
  7) 콘솔 오류·페이지 예외·HTTP 4xx/5xx 0건
  8) 스크린샷: home · detail 2장 (--shots-dir)

사용
  python3 projects/pharos/scripts/smoke_v18.py
  python3 projects/pharos/scripts/smoke_v18.py --live --shots-dir projects/pharos/live
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

# 규모 보정이 눈에 보이는 대표 항목 — (비교군, 항목 id, 기대 사용자 점수)
LARGE = ("streaming-video", "youtube", 87.5)        # 표본 1억 7,262만 → +7.50
MID = ("image-editors", "krita", 71.7)              # 표본 6,937 → -0.30
TINY = ("translation-study-notes", "mathpix", 85.5)  # 표본 142 → -4.50
FILTERED = ("mobile-strategy-defense", "clash-royale")  # 표본 4,190만에도 계속 거름
EN_ARENAS = ["streaming-video", "social-community", "translation-study-notes"]
MOBILE_ARENAS = ["streaming-video", "social-community", "mobile-strategy-defense"]


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


def open_detail(page, base: str, arena: str, item_id: str) -> None:
    page.goto(f"{base}?arena={arena}", wait_until="networkidle")
    page.wait_for_timeout(450)
    page.click(f'#grid .card[data-id="{item_id}"], #avoidGrid .card[data-id="{item_id}"]')
    page.wait_for_timeout(700)


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
    items = {row["id"]: row for row in index["items"]}
    total = index["counts"]["items"]
    arenas = index["counts"]["arenas"]
    featured = [a for a in catalog["home"]["featured_arenas"] if a in index["arena_stats"]]
    schema_version = json.loads((WEB_ROOT / "schema" / "item.schema.json").read_text(encoding="utf-8"))["title"].split("v")[-1]

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

        # 1) 홈 — 건수·비교군·featured 블록
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(800)
        chip = page.inner_text("#datasetChip")
        chip_flat = chip.replace(",", "")
        expect(f"{total}건" in chip_flat and f"비교군 {arenas}" in chip_flat and schema_version in chip_flat,
               f"홈 데이터 칩 = 스키마 v{schema_version} · {total}건 · 비교군 {arenas}", chip)
        hero_meta = page.inner_text(".hero-meta").replace(",", "")
        expect(str(total) in hero_meta, f"히어로에 {total}건 표시", hero_meta.replace("\n", " | ")[:120])
        blocks = page.eval_on_selector_all("#genreList .genre-block", "els => els.map(e => e.dataset.arena)")
        expect(len(blocks) == len(featured), f"홈 장르 블록 {len(featured)}개", str(len(blocks)))
        if shots:
            page.screenshot(path=str(shots / "live-v18-scale-home.png"))

        # 2) 규모 보정 반영 점수 — 카드 점수가 인덱스(가중 점수)와 같고, 사용자 축이 보정값인지
        for arena_id, item_id, expected_user in (LARGE, MID, TINY):
            page.goto(f"{base}?arena={arena_id}", wait_until="networkidle")
            page.wait_for_timeout(450)
            rows = [c for c in cards(page) if c["id"] == item_id]
            row = items[item_id]
            expect(bool(rows) and rows[0]["score"] == f"{row['score']:.2f}",
                   f"{item_id} 카드 점수 = 인덱스 {row['score']:.2f}", str(rows[:1]))
            expect(bool(rows) and row["user_rating"] == expected_user,
                   f"{item_id} 사용자 축 = 규모 보정값 {expected_user}", str(row["user_rating"]))

        # 3) 상세 '산정 메모' — 표본 수·로그 보정·게이트·전후 점수가 문장으로 보인다
        open_detail(page, base, LARGE[0], LARGE[1])
        modal = page.inner_text("#modal")
        expect("산정 메모" in modal, "상세에 '산정 메모' 섹션 표시", modal[:120].replace("\n", " | "))
        expect("표본 규모 보정" in modal and "게이트" in modal,
               "대규모 표본 항목 산정 메모에 규모 보정 근거", modal[:200].replace("\n", " | "))
        youtube_note = items[LARGE[1]]
        expect("172,620,041" in modal.replace(",", ",") or "172,620,041" in modal,
               "산정 메모에 표본 수 172,620,041건 표기", modal[:200].replace("\n", " | "))
        if shots:
            page.eval_on_selector(
                "#modalBody",
                """el => { const c = [...el.querySelectorAll('.callout--ok')]
                     .find(n => n.innerText.includes('산정 메모'));
                     if (c) c.scrollIntoView({ block: 'center' }); }""",
            )
            page.wait_for_timeout(450)
            page.screenshot(path=str(shots / "live-v18-scale-detail.png"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)

        open_detail(page, base, TINY[0], TINY[1])
        tiny_modal = page.inner_text("#modal")
        expect("142" in tiny_modal and "-4.5" in tiny_modal.replace("−", "-"),
               "미세 표본 항목 산정 메모에 142건 · -4.5 표기", tiny_modal[:200].replace("\n", " | "))
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)

        # 4) 하드 필터 우선 — 표본이 커도 거름은 거름
        page.goto(f"{base}?arena={FILTERED[0]}", wait_until="networkidle")
        page.wait_for_timeout(450)
        avoid_rows = page.eval_on_selector_all("#avoidGrid .card", "els => els.map(e => e.dataset.id)")
        rows = [c for c in cards(page) if c["id"] == FILTERED[1]]
        expect(FILTERED[1] in avoid_rows, f"{FILTERED[1]} 는 거름 그리드에 있음", str(avoid_rows))
        expect(bool(rows) and rows[0]["verdict"] == "avoid",
               f"{FILTERED[1]} 표본 4,190만·사용자 87.5 여도 판정 = 거름", str(rows[:1]))

        # 5) EN — 한글 0 + 규모 보정 문구
        en = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US").new_page()
        en.goto(f"{base}?lang=en&arena={LARGE[0]}", wait_until="networkidle")
        en.wait_for_timeout(700)
        expect(en.evaluate("document.documentElement.lang") == "en", "EN 언어 전환", "")
        expect(not korean_left(en), f"EN {LARGE[0]} 한글 잔존 0건", str(korean_left(en)[:4]))
        en.click(f'#grid .card[data-id="{LARGE[1]}"], #avoidGrid .card[data-id="{LARGE[1]}"]')
        en.wait_for_timeout(700)
        en_modal = en.inner_text("#modalBody")
        expect("sample-scale adjustment" in en_modal.lower(), "EN 상세에 sample-scale adjustment 문구", en_modal[:200].replace("\n", " | "))
        en.keyboard.press("Escape")
        en.wait_for_timeout(200)
        for arena_id in EN_ARENAS:
            en.goto(f"{base}?lang=en&arena={arena_id}", wait_until="networkidle")
            en.wait_for_timeout(500)
            text = en.inner_text("body")
            expect(not korean_left(en), f"EN {arena_id} 한글 잔존 0건", str(korean_left(en)[:4]))
            expect("undefined" not in text and "null" not in text.lower().split(),
                   f"EN {arena_id} 빈 값 표기 깨짐 없음", "")
        en.close()

        # 6) 390px
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR").new_page()
        for arena_id in MOBILE_ARENAS:
            mobile.goto(f"{base}?arena={arena_id}", wait_until="networkidle")
            mobile.wait_for_timeout(500)
            expect(overflow(mobile) == 0, f"390px {arena_id} 가로 넘침 0", str(overflow(mobile)))
        mobile.close()

        expect(not errors, "콘솔 오류·페이지 예외 0건", "; ".join(errors[:3]))
        expect(not bad_http, "HTTP 4xx/5xx 0건", "; ".join(bad_http[:3]))
        browser.close()
    if httpd:
        httpd.shutdown()

    passed = sum(1 for _l, ok, _e in RESULTS if ok)
    print("=" * 70)
    print(f"결과: {passed}/{len(RESULTS)} PASS · 총 {total}종 · 비교군 {arenas} · v0.6.0 규모 보정")
    print("=" * 70)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
