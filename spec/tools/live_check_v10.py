#!/usr/bin/env python3
"""파로스 라이브 검증 (v10) — 1차 대량 확장(VPN·캘린더·FPS·서바이벌 20종) 배포 확인.

확인 항목
  1) 라이브 데이터 칩 = 스키마 v0.4.0 · 87건 · 비교군 18
  2) 홈 18개 장르 블록(맨 앞 VPN·캘린더)과 신규 4개 비교군 진입
  3) 신규 비교군 4개가 각각 5건 · 192px 아이콘 로드 · 대표 판정/점수
  4) VPN 상세(Mullvad)의 판정·가격·경고, ExpressVPN 조건부
  5) EN 전환 시 신규 비교군 한글 잔존 0건
  6) 390px 가로 넘침 0
  7) 라이브 스크린샷: live/live-v10-batch1-home.png · live/live-v10-batch1-vpn.png

사용:
  LD_LIBRARY_PATH=/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu \
    python3 projects/pharos/scripts/live_check_v10.py
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
        expect("87건" in chip and "비교군 18" in chip and "v0.4.0" in chip,
               "라이브 데이터 칩 = v0.4.0 · 87건 · 비교군 18", chip)
        blocks = page.eval_on_selector_all("#genreList .genre-block", "els => els.map(e => e.dataset.arena)")
        expect(len(blocks) == 18, "라이브 홈 장르 블록 18개", str(len(blocks)))
        expect(blocks[:2] == ["vpn", "calendar-apps"], "라이브 홈 맨 앞 = VPN · 캘린더", str(blocks[:3]))
        expect("fps-shooters" in blocks and "survival-crafting" in blocks,
               "라이브 홈 게임 구간에 FPS · 서바이벌", str(blocks))
        vpn_block = page.inner_text('.genre-block[data-arena="vpn"]')
        expect("Mullvad" in vpn_block and "5종" in vpn_block, "라이브 VPN 블록 = 5종·Mullvad 노출",
               vpn_block[:120].replace("\n", " | "))
        expect(page.eval_on_selector_all("#homeDomainFilter .domain-chip",
                                         "els => els.map(e => e.innerText.trim())")[0].startswith("전체 18"),
               "라이브 홈 도메인 필터 = 전체 18",
               str(page.eval_on_selector_all("#homeDomainFilter .domain-chip", "els => els.map(e => e.innerText.trim())")))
        shot_home = LIVE / "live-v10-batch1-home.png"
        try:
            page.screenshot(path=str(shot_home), full_page=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 홈 스크린샷 실패: {exc}")
        expect(shot_home.exists() and shot_home.stat().st_size > 20_000,
               "라이브 홈 스크린샷 저장", str(shot_home.name))

        # 2) 신규 4개 비교군 — 5건·아이콘·대표 판정
        for arena_id in ("vpn", "calendar-apps", "fps-shooters", "survival-crafting"):
            page.goto(f"{BASE}?arena={arena_id}", wait_until="networkidle")
            wait(page, 500)
            rows = cards(page)
            expect(len(rows) == 5, f"라이브 {arena_id} = 5건", str([c["id"] for c in rows]))
            icons = page.eval_on_selector_all(
                "#grid .card .item-icon img",
                "els => els.map(e => e.complete && e.naturalWidth === 192)")
            expect(len(icons) == 5 and all(icons), f"라이브 {arena_id} 아이콘 5건 192px", str(icons))

        page.goto(f"{BASE}?arena=vpn", wait_until="networkidle")
        wait(page, 600)
        vpn_rows = {c["id"]: c for c in cards(page)}
        expect(vpn_rows.get("mullvad-vpn", {}).get("verdict") == "recommend"
               and float(vpn_rows["mullvad-vpn"]["score"]) > 85,
               "라이브 Mullvad = 추천 88.25", str(vpn_rows.get("mullvad-vpn")))
        expect(vpn_rows.get("expressvpn", {}).get("verdict") == "conditional",
               "라이브 ExpressVPN = 조건부", str(vpn_rows.get("expressvpn")))

        page.click('#grid .card[data-id="mullvad-vpn"]')
        wait(page, 700)
        modal = page.inner_text("#modal")
        expect("€5" in modal and "5대" in modal and "포트 포워딩" in modal,
               "라이브 Mullvad 상세 = €5 · 5대 · 포트 포워딩 없음", modal[:160].replace("\n", " | "))
        page.keyboard.press("Escape")
        wait(page, 300)
        shot_vpn = LIVE / "live-v10-batch1-vpn.png"
        try:
            page.screenshot(path=str(shot_vpn), full_page=False)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! VPN 스크린샷 실패: {exc}")
        expect(shot_vpn.exists() and shot_vpn.stat().st_size > 20_000,
               "라이브 VPN 비교군 스크린샷 저장", str(shot_vpn.name))

        # 3) 모바일 390px
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR").new_page()
        mobile.goto(f"{BASE}?arena=vpn", wait_until="networkidle")
        wait(mobile, 700)
        expect(overflow(mobile) == 0, "라이브 390px VPN 가로 넘침 0", str(overflow(mobile)))
        mobile.close()

        # 4) EN — 신규 비교군 한글 0
        en = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-US").new_page()
        en.goto(f"{BASE}?lang=en&arena=calendar-apps", wait_until="networkidle")
        wait(en, 800)
        expect(en.evaluate("document.documentElement.lang") == "en", "라이브 EN 언어 전환", "")
        expect(not korean_left(en), "라이브 EN 캘린더 비교군 한글 잔존 0건", str(korean_left(en)[:4]))
        en.goto(f"{BASE}?lang=en&arena=survival-crafting", wait_until="networkidle")
        wait(en, 800)
        expect(not korean_left(en), "라이브 EN 서바이벌 비교군 한글 잔존 0건", str(korean_left(en)[:4]))
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
