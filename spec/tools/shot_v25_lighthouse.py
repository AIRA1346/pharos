#!/usr/bin/env python3
"""v25 등대 목표 리뉴얼 — 라이브 스크린샷 2장(데스크톱·모바일).

실제 라이브 사이트에서 결과 카드를 띄워 찍는다. 추첨이 매번 달라지므로,
`localStorage` 의 등대 진행 상태에 검증된 목표 하나를 넣고 새로고침해
같은 카드를 재현한다(앱이 지원하는 '진행 중인 목표' 복원 경로 그대로).

  python3 projects/pharos/scripts/shot_v25_lighthouse.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LIVE = "https://aira1346.github.io/pharos/"
OUT = ROOT / "live"
STATE_KEY = "pharos_lighthouse_state_v1"


def seed(page, game_id: str, tier: int, difficulty: str) -> None:
    state = {
        "version": 2,
        "filters": {"price": "all", "platform": "all", "tier": tier, "difficulty": "all"},
        "current": {
            "game_id": game_id,
            "tier": tier,
            "difficulty": difficulty,
            "issued_at": "2026-11-27T18:30:00.000Z",
            "filters": {"price": "all", "platform": "all", "tier": tier, "difficulty": "all"},
        },
        "history": [],
        "skips": 0,
        "last_game_id": game_id,
    }
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [STATE_KEY, json.dumps(state)])
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(900)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    chrome = os.environ.get("CHROME_PATH")
    launch = {"executable_path": chrome} if chrome else {}
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch)

        ctx = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="ko-KR")
        page = ctx.new_page()
        page.goto(LIVE, wait_until="networkidle")
        page.wait_for_timeout(800)
        seed(page, "elden-ring", 3, "hardcore")
        assert page.is_visible(".lh-card"), "데스크톱 결과 카드가 보이지 않음"
        page.wait_for_timeout(3200)  # 발급 토스트가 사라진 뒤
        page.screenshot(path=str(OUT / "live-v25-lighthouse-quests-desktop.png"))
        ctx.close()

        ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR")
        page = ctx.new_page()
        page.goto(LIVE, wait_until="networkidle")
        page.wait_for_timeout(800)
        seed(page, "goddess-of-victory-nikke", 3, "normal")
        assert page.is_visible(".lh-card"), "모바일 결과 카드가 보이지 않음"
        page.wait_for_timeout(3200)
        page.screenshot(path=str(OUT / "live-v25-lighthouse-quests-mobile.png"))
        ctx.close()
        browser.close()
    print("saved", OUT / "live-v25-lighthouse-quests-desktop.png")
    print("saved", OUT / "live-v25-lighthouse-quests-mobile.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
