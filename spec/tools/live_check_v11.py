#!/usr/bin/env python3
"""파로스 라이브 검증 (v11) — 2차 대량 확장(AI 이미지·PDF·이미지 편집·턴제 전략 20종) 배포 확인.

확인 항목
  1) 라이브 데이터 칩 = 스키마 v0.4.0 · 107건 · 비교군 22
  2) 홈 22개 장르 블록(맨 앞 AI 이미지·PDF·이미지 편집·턴제 전략), 도메인 필터 22/10/9/3
  3) 신규 비교군 4개가 각각 5건 · 192px 아이콘 로드 · 대표 판정/점수
  4) ComfyUI 상세(무료·GPL·클라우드 $20)와 BG3 상세(₩66,000·454,406건)
  5) EN 전환 시 신규 4개 비교군 한글 잔존 0건
  6) 390px 가로 넘침 0
  7) 라이브 스크린샷: live/live-v11-batch2-home.png · live-v11-batch2-ai-image.png · live-v11-batch2-turnbased.png

사용:
  LD_LIBRARY_PATH=/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu \\
    python3 projects/pharos/scripts/live_check_v11.py
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


def wait(page, ms: int = 600) -> None:
    page.wait_for_timeout(ms)


def cards(page):
    return page.eval_on_selector_all(
        "#grid .card, #avoidGrid .card",
        "els => els.map(e => ({id: e.dataset.id, verdict: e.dataset.verdict, score: e.dataset.score}))",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    args = parser.parse_args()
    LIVE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        launch = {"executable_path": args.chrome} if args.chrome else {}
        browser = p.chromium.launch(**launch)

        ctx = browser.new_context(viewport={"width": 1440, "height": 1100}, device_scale_factor=1,
                                  locale="ko-KR")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        # 1) 홈 — 칩·장르 블록
        page.goto(BASE, wait_until="networkidle")
        wait(page, 900)
        chip = page.inner_text("#datasetChip")
        expect("107건" in chip and "비교군 22" in chip and "v0.4.0" in chip,
               "라이브 데이터 칩 = v0.4.0 · 107건 · 비교군 22", chip)
        blocks = page.eval_on_selector_all("#genreList .genre-block", "els => els.map(e => e.dataset.arena)")
        expect(len(blocks) == 22, "라이브 홈 장르 블록 22개", str(len(blocks)))
        expect(blocks[:4] == ["ai-image-gen", "pdf-tools", "image-editors", "turn-based-strategy"],
               "라이브 홈 맨 앞 = AI 이미지 · PDF · 이미지 편집 · 턴제 전략", str(blocks[:5]))
        ai_block = page.inner_text('.genre-block[data-arena="ai-image-gen"]')
        expect("ComfyUI" in ai_block and "5종" in ai_block, "라이브 AI 이미지 블록 = 5종·ComfyUI 노출",
               ai_block[:120].replace("\n", " | "))
        chips = page.eval_on_selector_all("#homeDomainFilter .domain-chip",
                                          "els => els.map(e => e.innerText.replace(/\\s+/g, ' ').trim())")
        expect(chips and "전체 22" in chips[0] and "앱 10" in chips and "게임 9" in chips and "AI 도구 3" in chips,
               "라이브 홈 도메인 필터 = 전체 22 · 앱 10 · 게임 9 · AI 3", str(chips))
        shot_home = LIVE / "live-v11-batch2-home.png"
        try:
            page.screenshot(path=str(shot_home), full_page=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 홈 스크린샷 실패: {exc}")
        expect(shot_home.exists() and shot_home.stat().st_size > 20_000,
               "라이브 홈 스크린샷 저장", str(shot_home.name))

        # 2) 신규 4개 비교군 — 5건·아이콘·대표 판정
        for arena_id in ("ai-image-gen", "pdf-tools", "image-editors", "turn-based-strategy"):
            page.goto(f"{BASE}?arena={arena_id}", wait_until="networkidle")
            wait(page, 500)
            rows = cards(page)
            expect(len(rows) == 5, f"라이브 {arena_id} = 5건", str([c["id"] for c in rows]))
            icons = page.eval_on_selector_all(
                "#grid .card .item-icon img",
                "els => els.map(e => e.complete && e.naturalWidth === 192)")
            expect(len(icons) == 5 and all(icons), f"라이브 {arena_id} 아이콘 5건 192px", str(icons))

        page.goto(f"{BASE}?arena=ai-image-gen", wait_until="networkidle")
        wait(page, 600)
        ai_rows = {c["id"]: c for c in cards(page)}
        expect(ai_rows.get("comfyui", {}).get("verdict") == "recommend"
               and float(ai_rows["comfyui"]["score"]) > 90,
               "라이브 ComfyUI = 추천 91.5", str(ai_rows.get("comfyui")))
        expect(ai_rows.get("midjourney", {}).get("verdict") == "conditional",
               "라이브 Midjourney = 조건부", str(ai_rows.get("midjourney")))

        page.click('#grid .card[data-id="comfyui"]')
        wait(page, 700)
        modal = page.inner_text("#modal")
        expect("GPL-3.0" in modal and "Comfy Cloud" in modal and "$20" in modal,
               "라이브 ComfyUI 상세 = GPL-3.0 · Comfy Cloud $20", modal[:160].replace("\n", " | "))
        page.keyboard.press("Escape")
        wait(page, 300)
        shot_ai = LIVE / "live-v11-batch2-ai-image.png"
        try:
            page.screenshot(path=str(shot_ai), full_page=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! AI 이미지 스크린샷 실패: {exc}")
        expect(shot_ai.exists() and shot_ai.stat().st_size > 20_000,
               "라이브 AI 이미지 비교군 스크린샷 저장", str(shot_ai.name))

        page.goto(f"{BASE}?arena=turn-based-strategy", wait_until="networkidle")
        wait(page, 600)
        game_rows = {c["id"]: c for c in cards(page)}
        expect(game_rows.get("baldurs-gate-3", {}).get("verdict") == "recommend"
               and float(game_rows["baldurs-gate-3"]["score"]) > 90,
               "라이브 Baldur's Gate 3 = 추천 94.0", str(game_rows.get("baldurs-gate-3")))
        expect(game_rows.get("xcom-2", {}).get("verdict") == "recommend",
               "라이브 XCOM 2 = 완결작 면제 추천", str(game_rows.get("xcom-2")))
        page.click('#grid .card[data-id="baldurs-gate-3"]')
        wait(page, 700)
        bg3 = page.inner_text("#modal")
        expect("₩66,000" in bg3 and "454,406" in bg3,
               "라이브 BG3 상세 = ₩66,000 · 454,406건", bg3[:160].replace("\n", " | "))
        page.keyboard.press("Escape")
        wait(page, 300)
        shot_tb = LIVE / "live-v11-batch2-turnbased.png"
        try:
            page.screenshot(path=str(shot_tb), full_page=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 턴제 스크린샷 실패: {exc}")
        expect(shot_tb.exists() and shot_tb.stat().st_size > 20_000,
               "라이브 턴제 전략 비교군 스크린샷 저장", str(shot_tb.name))

        page.goto(f"{BASE}?arena=pdf-tools", wait_until="networkidle")
        wait(page, 500)
        pdf_rows = {c["id"]: c for c in cards(page)}
        expect(pdf_rows.get("sumatrapdf", {}).get("verdict") == "recommend"
               and pdf_rows.get("adobe-acrobat", {}).get("verdict") == "conditional",
               "라이브 PDF = SumatraPDF 추천 · Acrobat 조건부",
               f'{pdf_rows.get("sumatrapdf")}/{pdf_rows.get("adobe-acrobat")}')

        # 3) 모바일 390px
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR").new_page()
        for arena_id in ("ai-image-gen", "pdf-tools", "image-editors", "turn-based-strategy"):
            mobile.goto(f"{BASE}?arena={arena_id}", wait_until="networkidle")
            wait(mobile, 600)
            expect(overflow(mobile) == 0, f"라이브 390px {arena_id} 가로 넘침 0", str(overflow(mobile)))
        mobile.close()

        # 4) EN — 신규 비교군 한글 0
        en = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US").new_page()
        en.goto(f"{BASE}?lang=en&arena=ai-image-gen", wait_until="networkidle")
        wait(en, 800)
        expect(en.evaluate("document.documentElement.lang") == "en", "라이브 EN 언어 전환", "")
        for arena_id in ("ai-image-gen", "pdf-tools", "image-editors", "turn-based-strategy"):
            en.goto(f"{BASE}?lang=en&arena={arena_id}", wait_until="networkidle")
            wait(en, 700)
            expect(not korean_left(en), f"라이브 EN {arena_id} 한글 잔존 0건", str(korean_left(en)[:4]))
        en.close()

        expect(not errors, "라이브 자바스크립트 예외 0건", "; ".join(errors[:3]))
        browser.close()

    passed = sum(1 for _l, ok, _e in RESULTS if ok)
    print("=" * 70)
    print(f"결과: {passed}/{len(RESULTS)} PASS")
    print("=" * 70)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
