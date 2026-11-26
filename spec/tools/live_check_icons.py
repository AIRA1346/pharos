#!/usr/bin/env python3
"""라이브(https://aira1346.github.io/pharos/) 확인 — 29종 공식 아이콘(v2.1).

배포본에서 아이콘 파일이 실제로 내려와 카드·상세·비교 표에 붙고, 콘솔 에러·4xx 없이
레이아웃이 유지되는지 확인하고 스크린샷 2장을 저장한다.
  live/live-v2-icons-gacha.png  모바일 수집형 RPG 목록
  live/live-v2-icons-pkm.png    노트·지식관리 목록
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://aira1346.github.io/pharos/"
SHOTS = Path("/workspace/projects/pharos/live")
BUST = "v=icons1"
RES = []


def expect(cond, label, extra=""):
    RES.append((label, bool(cond), str(extra)))


def icons(page, selector=".item-icon"):
    return page.evaluate(
        """(sel) => [...document.querySelectorAll(sel)].map(wrap => {
            const img = wrap.querySelector('img');
            return { src: img ? img.getAttribute('src') : '', has: !!img,
                     ok: !!img && img.complete && img.naturalWidth > 0,
                     size: Math.round(wrap.getBoundingClientRect().width),
                     radius: getComputedStyle(wrap).borderRadius,
                     fit: img ? getComputedStyle(img).objectFit : '' };
        })""",
        selector,
    )


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    console, pageerrors, failed = [], [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
        page = ctx.new_page()
        page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: pageerrors.append(str(e)))
        page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)

        # ------------------------------------------------------------------ 홈
        page.goto(f"{BASE}?{BUST}", wait_until="networkidle")
        page.wait_for_timeout(900)
        chip = page.inner_text("#datasetChip")
        expect("v0.4.0" in chip and "29건" in chip and "비교군 6" in chip, "라이브 데이터 칩 29건·비교군 6", chip)

        loaded = page.evaluate(
            """async () => {
            const items = window.Pharos.state.core.index.items;
            const load = (src) => new Promise((res) => {
              const im = new Image();
              im.onload = () => res(im.naturalWidth > 0);
              im.onerror = () => res(false);
              im.src = src;
            });
            const results = await Promise.all(items.map(i => load('./' + i.icon)));
            return { total: items.length, ok: results.filter(Boolean).length,
                     bad: items.filter((_, k) => !results[k]).map(i => i.id) };
        }"""
        )
        expect(loaded["total"] == 29 and loaded["ok"] == 29,
               "라이브에서 29종 아이콘 파일 전부 로드", str(loaded))

        gap_icons = icons(page, ".gap-row .item-icon")
        expect(len(gap_icons) == 4 and all(i["ok"] for i in gap_icons),
               "홈 갭 리포트 4건 아이콘 로드", str([i["ok"] for i in gap_icons]))

        page.fill("#homeSearch", "니케")
        page.wait_for_timeout(450)
        search_icons = icons(page, ".search-row .item-icon")
        expect(bool(search_icons) and all(i["ok"] for i in search_icons),
               "홈 통합 검색 결과 아이콘 로드", str(search_icons))
        page.fill("#homeSearch", "")
        page.wait_for_timeout(250)

        # ------------------------------------------------------- 노트·지식관리
        page.goto(f"{BASE}?{BUST}&domain=app&arena=pkm-notes", wait_until="networkidle")
        page.wait_for_timeout(900)
        card_icons = icons(page, "#grid .item-icon, #avoidGrid .item-icon")
        expect(len(card_icons) == 5 and all(i["ok"] for i in card_icons),
               "노트 비교군 카드 5건 아이콘 로드", str([(i["src"].split('/')[-1], i["ok"]) for i in card_icons]))
        expect(all(44 <= i["size"] <= 48 for i in card_icons), "라이브 카드 아이콘 44~48px", str([i["size"] for i in card_icons]))
        expect(all(i["fit"] == "cover" and i["radius"] == "10px" for i in card_icons),
               "라이브 카드 아이콘 cover·10px", str(card_icons[:1]))
        page.screenshot(path=str(SHOTS / "live-v2-icons-pkm.png"), full_page=True)

        # 상세 모달
        page.click('#grid .card[data-id="obsidian"]')
        page.wait_for_timeout(800)
        modal_icons = icons(page, "#modalIcon .item-icon")
        expect(len(modal_icons) == 1 and modal_icons[0]["ok"], "라이브 상세 아이콘 로드", str(modal_icons))
        expect(52 <= modal_icons[0]["size"] <= 56, "라이브 상세 아이콘 52~56px", str(modal_icons[0]["size"]))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ---------------------------------------------------- 모바일 수집형 RPG
        page.goto(f"{BASE}?{BUST}&domain=game&arena=mobile-gacha-rpg", wait_until="networkidle")
        page.wait_for_timeout(900)
        gacha_icons = icons(page, "#grid .item-icon, #avoidGrid .item-icon")
        expect(len(gacha_icons) == 6 and all(i["ok"] for i in gacha_icons),
               "모바일 수집형 RPG 카드 6건 아이콘 로드", str([(i["src"].split('/')[-1], i["ok"]) for i in gacha_icons]))
        page.screenshot(path=str(SHOTS / "live-v2-icons-gacha.png"), full_page=True)

        # 비교 표 아이콘
        first = page.eval_on_selector_all(
            "#grid .card", "els => els.slice(0, 2).map(e => e.dataset.id)"
        )
        if len(first) >= 2:
            for item_id in first:
                page.check(f'#grid .card[data-id="{item_id}"] input[data-compare]')
                page.wait_for_timeout(250)
            page.click("#compareOpen")
            page.wait_for_timeout(700)
            cmp_icons = icons(page, "#compareTable thead .item-icon")
            expect(len(cmp_icons) == 2 and all(i["ok"] for i in cmp_icons),
                   "라이브 비교 표 머리글 아이콘 로드", str(cmp_icons))
            expect(all(30 <= i["size"] <= 34 for i in cmp_icons), "라이브 비교 표 아이콘 32px",
                   str([i["size"] for i in cmp_icons]))

        expect(not console, "콘솔 에러 0건", "; ".join(console))
        expect(not pageerrors, "페이지 예외 0건", "; ".join(pageerrors))
        expect(not failed, "HTTP 4xx/5xx 0건", "; ".join(failed))
        b.close()

    passed = sum(1 for _, ok, _ in RES if ok)
    print("=" * 78)
    for label, ok, extra in RES:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}" + ("" if ok else f"  ← {extra}"))
    print("=" * 78)
    print(f"결과: {passed}/{len(RES)} 통과")
    return 0 if passed == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
