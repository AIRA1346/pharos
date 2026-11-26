#!/usr/bin/env python3
"""라이브(v3 정보 계층) 확인 — 홈/도메인 장르 추천 타일, 비교군 카드 단순화, 상세 모달 유지.

https://aira1346.github.io/pharos/ 를 실제로 열어
  1) 홈: 히어로 <=250px, 장르 블록 6개, 타일 아이콘 40px+ 로드, 가챠 타일 = 니케·림버스·블루아카
  2) 게임 도메인: 장르 블록 5개, 덱빌딩 타일 3개(거름 제외)
  3) 비교군: 카드 4건, 카드 안에 3축 막대·가격 티어 칩이 없고 태그 <=2, 상세 모달에 3축·Fact/Opinion 유지
  4) 스크린샷: live/live-v3-home.png · live-v3-game.png · live-v3-arena.png

실행:
  LD_LIBRARY_PATH=/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu \
      python3 projects/pharos/scripts/live_check_v3_hierarchy.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://aira1346.github.io/pharos/"
OUT = Path(__file__).resolve().parents[1] / "live"
RESULTS: list[tuple[str, bool, str]] = []


def expect(ok: bool, label: str, extra: str = "") -> None:
    RESULTS.append((label, bool(ok), str(extra)))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 1100}, device_scale_factor=2)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        # ---------------------------------------------------------------- 홈
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(not errors, "라이브 콘솔 에러 없음", "; ".join(errors))
        genres = page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)")
        expect(genres == ["pkm-notes", "roguelike-deckbuilder", "action-roguelike", "mobile-gacha-rpg",
                          "pc-mmorpg", "mobile-strategy-defense"], "라이브 홈 장르 블록 6개", str(genres))
        hero_h = page.eval_on_selector(".hero", "e => Math.round(e.getBoundingClientRect().height)")
        expect(hero_h <= 250, "라이브 히어로 250px 이내", str(hero_h))
        show_top = page.eval_on_selector("#genreShowcase .genre-block", "e => Math.round(e.getBoundingClientRect().top)")
        expect(show_top < 640, "라이브 첫 화면에 장르 추천 노출", str(show_top))
        tile_icons = page.evaluate(
            """() => [...document.querySelectorAll('.pick-tile .item-icon')].map(w => {
              const img = w.querySelector('img');
              return {size: Math.round(w.getBoundingClientRect().width),
                      ok: !!img && img.complete && img.naturalWidth > 0};
            })"""
        )
        expect(bool(tile_icons) and all(t["size"] >= 40 and t["ok"] for t in tile_icons),
               "라이브 추천 타일 아이콘 40px+ 전부 로드", f"{len(tile_icons)}개")
        gacha = page.eval_on_selector_all('.genre-block[data-arena="mobile-gacha-rpg"] .pick-tile',
                                          "els => els.map(e => e.dataset.item)")
        expect(gacha == ["goddess-of-victory-nikke", "limbus-company", "blue-archive"],
               "라이브 가챠 장르 추천 타일(추천→조건부)", str(gacha))
        page.screenshot(path=str(OUT / "live-v3-home.png"), full_page=True)

        # ------------------------------------------------------------ 게임 도메인
        page.goto(BASE + "?domain=game", wait_until="networkidle")
        page.wait_for_timeout(800)
        game_genres = page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)")
        expect(game_genres == ["roguelike-deckbuilder", "mobile-gacha-rpg", "action-roguelike",
                               "pc-mmorpg", "mobile-strategy-defense"], "라이브 게임 장르 블록 5개", str(game_genres))
        deck = page.eval_on_selector_all('.genre-block[data-arena="roguelike-deckbuilder"] .pick-tile',
                                         "els => els.map(e => e.dataset.item)")
        expect(deck == ["balatro", "slay-the-spire", "inscryption"], "라이브 덱빌딩 타일 3개(거름 제외)", str(deck))
        expect(page.eval_on_selector_all(".arena-card, .category-card", "els => els.length") == 0,
               "라이브 도메인에 장황한 비교군 카드 없음")
        page.screenshot(path=str(OUT / "live-v3-game.png"), full_page=True)

        # -------------------------------------------------------------- 비교군
        page.goto(BASE + "?domain=game&arena=roguelike-deckbuilder", wait_until="networkidle")
        page.wait_for_timeout(900)
        count = page.eval_on_selector_all("#grid .card, #avoidGrid .card", "els => els.length")
        expect(count == 4, "라이브 덱빌딩 카드 4건", str(count))
        stripped = page.eval_on_selector("#grid .card", "e => e.querySelectorAll('.lights, .chip--tier, .chip--fresh').length")
        expect(stripped == 0, "라이브 목록 카드에 3축 막대·가격 티어 없음", str(stripped))
        tags = page.eval_on_selector("#grid .card", "e => e.querySelectorAll('.card-tags .chip').length")
        expect(tags <= 2, "라이브 카드 핵심 태그 최대 2개", str(tags))
        head = page.eval_on_selector("#grid .card",
                                     "e => ({name: e.querySelector('h3')?.textContent, "
                                     "score: e.querySelector('.score-num')?.textContent, "
                                     "verdict: e.querySelector('.verdict')?.textContent})")
        expect(head.get("name") == "Balatro" and head.get("score") == "94.7" and "추천" in (head.get("verdict") or ""),
               "라이브 카드 상단 = 이름·점수·판정", str(head))
        page.screenshot(path=str(OUT / "live-v3-arena.png"), full_page=True)
        page.click('#grid .card[data-id="inscryption"]')
        page.wait_for_timeout(900)
        body = page.inner_text("#modalBody")
        expect(page.is_visible("#modal"), "라이브 카드 클릭 → 상세 모달")
        expect("사실 (Fact)" in body and "의견 (Opinion)" in body, "라이브 상세에 Fact/Opinion 유지")
        expect(page.eval_on_selector_all("#modalBody .axis-card .axis-score", "els => els.length") == 4,
               "라이브 상세 05 축별 신호(3축 + 프로필)")
        browser.close()

    ok = sum(1 for _, passed, _ in RESULTS if passed)
    for label, passed, extra in RESULTS:
        print(f"[{'PASS' if passed else 'FAIL'}] {label}" + (f"  ← {extra}" if not passed and extra else ""))
    print(f"결과: {ok}/{len(RESULTS)} 통과 · 스크린샷 {OUT}")
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
