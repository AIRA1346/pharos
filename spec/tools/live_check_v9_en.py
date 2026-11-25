#!/usr/bin/env python3
"""파로스 라이브 KO/EN 검증 (v9) — GitHub Pages 실제 배포본을 브라우저로 연다.

확인 항목
  1) `?lang=en` 이 영어 화면으로 열리고 `<html lang=en>`·영어 title·메타 설명이 맞는지
  2) 해외 브라우저 언어(locale en-US)에서 `?lang` 없이도 영어가 선택되는지
  3) EN 홈·비교군·비교 표·상세에서 한글 잔존 0건(텍스트 + aria-label·title·placeholder)
  4) 390px 모바일 가로 넘침 0
  5) `🔗 링크 복사` 값에 `lang=en` 과 화면 파라미터가 들어가는지
  6) KO 화면이 그대로인지(회귀)
  7) 라이브 스크린샷 저장: live-v9-en-home.png · live-v9-en-compare.png

사용:
  LD_LIBRARY_PATH=... python3 projects/pharos/scripts/live_check_v9_en.py
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://aira1346.github.io/pharos/"
ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live"
KOREAN = re.compile(r"[\uac00-\ud7a3]")
RESULTS: list[tuple[str, bool, str]] = []


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


def wait(page, ms: int = 700) -> None:
    page.wait_for_timeout(ms)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    args = parser.parse_args()
    LIVE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        launch = {"executable_path": args.chrome} if args.chrome else {}
        browser = p.chromium.launch(**launch)

        # 1) ?lang=en — 데스크톱
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=2,
                                  locale="en-US", permissions=["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        errors: list[str] = []
        served: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("response", lambda r: served.append(r.url))
        page.goto(f"{BASE}?lang=en", wait_until="networkidle")
        wait(page, 900)
        expect(page.evaluate("document.documentElement.lang") == "en", "라이브 ?lang=en → <html lang=en>",
               page.evaluate("document.documentElement.lang"))
        expect(page.title().startswith("Pharos"), "라이브 EN title", page.title())
        expect(any(url.endswith("/data/en.json") for url in served), "라이브에서 data/en.json 로드", "")
        expect(not korean_left(page), "라이브 EN 홈 한글 잔존 0건", str(korean_left(page)[:4]))
        expect(overflow(page) == 0, "라이브 EN 홈 가로 넘침 0", str(overflow(page)))
        page.screenshot(path=str(LIVE / "live-v9-en-home.png"), full_page=False)

        # 2) 브라우저 언어만으로 영어
        auto = ctx.new_page()
        auto.goto(BASE, wait_until="networkidle")
        wait(auto, 700)
        expect(auto.evaluate("document.documentElement.lang") == "en", "라이브 자동 언어 감지(en-US → EN)",
               auto.evaluate("document.documentElement.lang"))
        auto.close()

        # 3) 비교군 → 상세 → 비교 표
        page.goto(f"{BASE}?lang=en&domain=game&arena=roguelike-deckbuilder", wait_until="networkidle")
        wait(page, 800)
        expect(not korean_left(page), "라이브 EN 비교군 한글 잔존 0건", str(korean_left(page)[:4]))
        page.click('#grid .card[data-id="balatro"]')
        wait(page, 800)
        body = page.inner_text("#modalBody")
        expect("Verdict" in body and "Facts" in body and "Evidence and sources" in body,
               "라이브 EN 상세 섹션", body[:60])
        expect(not korean_left(page), "라이브 EN 상세 한글 잔존 0건", str(korean_left(page)[:4]))
        page.keyboard.press("Escape")
        wait(page, 300)
        page.check('#grid .card[data-id="balatro"] input[data-compare]')
        page.check('#grid .card[data-id="slay-the-spire"] input[data-compare]')
        wait(page, 250)
        page.click("#compareOpen")
        wait(page, 800)
        table = page.inner_text("#compareTable")
        expect("Weighted score" in table and "Best" in table, "라이브 EN 비교 표", table[:60])
        expect(not korean_left(page), "라이브 EN 비교 표 한글 잔존 0건", str(korean_left(page)[:4]))
        page.screenshot(path=str(LIVE / "live-v9-en-compare.png"), full_page=True)

        # 4) 링크 복사
        page.click("[data-copy-link]")
        wait(page, 400)
        copied = page.evaluate("navigator.clipboard.readText()")
        params = page.evaluate("(url) => Object.fromEntries(new URLSearchParams(new URL(url).search))", copied)
        expect(params.get("lang") == "en" and params.get("compare") == "balatro,slay-the-spire",
               "라이브 🔗 링크 복사 = lang=en 딥링크", str(params))

        # 5) 390px
        mobile = ctx.new_page()
        mobile.set_viewport_size({"width": 390, "height": 844})
        mobile.goto(f"{BASE}?lang=en&domain=app&arena=pkm-notes", wait_until="networkidle")
        wait(mobile, 800)
        expect(overflow(mobile) == 0 and not korean_left(mobile), "라이브 EN 390px 넘침 0·한글 0",
               f"overflow={overflow(mobile)}")
        mobile.close()

        # 6) KO 회귀
        ko = ctx.new_page()
        ko.goto(f"{BASE}?lang=ko", wait_until="networkidle")
        wait(ko, 700)
        expect(ko.evaluate("document.documentElement.lang") == "ko" and ko.title().startswith("파로스"),
               "라이브 ?lang=ko 한국어 화면", ko.title()[:30])
        expect("별점 대신" in ko.inner_text(".hero"), "라이브 KO 히어로 문구 유지", "")
        ko.close()

        expect(not errors, "라이브 EN JS 예외 없음", "; ".join(errors))
        ctx.close()
        browser.close()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("=" * 70)
    print(f"결과: {passed}/{len(RESULTS)} 통과 · 스크린샷 {LIVE}/live-v9-en-home.png · live-v9-en-compare.png")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
