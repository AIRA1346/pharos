#!/usr/bin/env python3
"""라이브(https://aira1346.github.io/pharos/) 확인 — 2차 게임 확장(PC MMORPG 4종 · 모바일 전략·디펜스 4종).

새 비교군 2개가 실제 배포본에서 렌더되고, 판정·요약·상세·대체제가 데이터와 일치하며
콘솔 에러 0건인지 확인하고 스크린샷을 저장한다.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://aira1346.github.io/pharos/"
SHOTS = Path("/workspace/projects/pharos/live")
RES = []


def expect(cond, label, extra=""):
    RES.append((label, bool(cond), str(extra)))


def cards(page):
    return page.eval_on_selector_all(
        "#grid .card, #avoidGrid .card",
        "els => els.map(e => ({id:e.dataset.id, verdict:e.dataset.verdict, score:e.dataset.score, avoid:!!e.closest('#avoidGrid')}))",
    )


def stats(page):
    return page.evaluate(
        """() => { const out={}; document.querySelectorAll('#arenaSummary .stat').forEach(s=>{
             out[s.querySelector('.stat-label').textContent.trim()]=s.querySelector('.stat-value').textContent.trim();}); return out; }"""
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

        page.goto(f"{BASE}?v=22e7315", wait_until="networkidle")
        page.wait_for_timeout(900)
        chip = page.inner_text("#datasetChip")
        expect("v0.4.0" in chip and "24건" in chip and "비교군 6" in chip, "라이브 데이터 칩 24건·비교군 6", chip)
        shortcuts = page.eval_on_selector_all(".arena-card", "els => els.map(e => e.innerText.replace(/\\n/g,' | '))")
        expect(len(shortcuts) == 6, "홈 비교군 바로가기 6개", str(len(shortcuts)))
        expect("PC MMORPG" in shortcuts[4] and "63.4" in shortcuts[4], "홈에 PC MMORPG 카드", shortcuts[4][:90])
        expect("모바일 전략·디펜스" in shortcuts[5] and "66.2" in shortcuts[5], "홈에 모바일 전략·디펜스 카드", shortcuts[5][:90])
        gap = page.eval_on_selector_all(".gap-row", "els => els.map(e => e.innerText.replace(/\\n/g,' | '))")
        expect(len(gap) == 4 and "Clash Royale" in gap[3] and "55.2" in gap[3], "갭 리포트 4건(마지막 Clash Royale)",
               str([g[:30] for g in gap]))

        # ---------------------------------------------------------- PC MMORPG
        page.goto(f"{BASE}?v=22e7315&domain=game&arena=pc-mmorpg", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("h1").strip().startswith("PC MMORPG"), "PC MMORPG 화면", page.inner_text("h1"))
        mmo = cards(page)
        expect(len(mmo) == 4, "라이브 PC MMORPG 카드 4건", str([c["id"] for c in mmo]))
        ms = stats(page)
        expect(ms.get("추천") == "1" and ms.get("거름") == "3" and ms.get("평균 가중 점수") == "63.4",
               "라이브 PC MMORPG 요약 1/0/3 · 63.4", str(ms))
        expect({c["id"]: c["verdict"] for c in mmo} == {
            "final-fantasy-xiv": "recommend", "guild-wars-2": "avoid",
            "lost-ark": "avoid", "black-desert": "avoid"}, "라이브 PC MMORPG 판정 4건",
               str({c["id"]: c["verdict"] for c in mmo}))
        expect(abs(float({c["id"]: c["score"] for c in mmo}.get("final-fantasy-xiv") or 0) - 80.7) < 0.05,
               "라이브 FFXIV 80.7", str({c["id"]: c["score"] for c in mmo}))
        page.screenshot(path=str(SHOTS / "live-v2-game-mmorpg.png"), full_page=True)

        # 상세 — FFXIV(정액제 기준점)
        page.goto(f"{BASE}?v=22e7315&domain=game&arena=pc-mmorpg&item=final-fantasy-xiv", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("#modalTitle") == "FINAL FANTASY XIV", "라이브 FFXIV 상세 제목", page.inner_text("#modalTitle"))
        body = page.inner_text("#modalBody")
        expect("19,800" in body, "라이브 FFXIV 30일 이용권 19,800원", "")
        expect("80" in body and "무료" in body, "라이브 FFXIV 80레벨 무료 체험", "")
        expect("구독" in body, "라이브 FFXIV 구독 필터 서술", "")

        # 상세 — Guild Wars 2(확률형 상자 거름 + 대체제)
        page.goto(f"{BASE}?v=22e7315&domain=game&arena=pc-mmorpg&item=guild-wars-2", wait_until="networkidle")
        page.wait_for_timeout(900)
        body = page.inner_text("#modalBody")
        expect("확률형 아이템 제외 적중" in body, "라이브 GW2 확률형 아이템 적중", "")
        expect("블랙 라이온" in body, "라이브 GW2 블랙 라이온 상자 서술", "")
        alts = page.eval_on_selector_all("#secAlternatives .alt-row", "els => els.map(e => e.dataset.item)")
        expect(alts == ["final-fantasy-xiv"], "라이브 GW2 대체제 = FFXIV", str(alts))

        # ------------------------------------------------- 모바일 전략·디펜스
        page.goto(f"{BASE}?v=22e7315&domain=game&arena=mobile-strategy-defense", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("h1").strip().startswith("모바일 전략·디펜스"), "모바일 전략·디펜스 화면", page.inner_text("h1"))
        mob = cards(page)
        expect(len(mob) == 4, "라이브 모바일 전략·디펜스 카드 4건", str([c["id"] for c in mob]))
        st = stats(page)
        expect(st.get("추천") == "1" and st.get("거름") == "3" and st.get("평균 가중 점수") == "66.2",
               "라이브 모바일 전략·디펜스 요약 1/0/3 · 66.2", str(st))
        expect({c["id"]: c["verdict"] for c in mob} == {
            "bloons-td-6": "avoid", "kingdom-rush-vengeance": "recommend",
            "clash-royale": "avoid", "plants-vs-zombies-2": "avoid"}, "라이브 모바일 전략·디펜스 판정 4건",
               str({c["id"]: c["verdict"] for c in mob}))
        expect(abs(float({c["id"]: c["score"] for c in mob}.get("kingdom-rush-vengeance") or 0) - 80.2) < 0.05,
               "라이브 KR Vengeance 80.2", str({c["id"]: c["score"] for c in mob}))
        page.screenshot(path=str(SHOTS / "live-v2-game-mobile-strategy.png"), full_page=True)

        # 상세 — Bloons TD 6(유료·무광고인데 확률형 표기로 거름)
        page.goto(f"{BASE}?v=22e7315&domain=game&arena=mobile-strategy-defense&item=bloons-td-6", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("#modalTitle") == "Bloons TD 6", "라이브 BTD6 상세 제목", page.inner_text("#modalTitle"))
        body = page.inner_text("#modalBody")
        expect("확률형 아이템 제외 적중" in body, "라이브 BTD6 확률형 아이템 적중", "")
        expect("6,500" in body and "광고" in body, "라이브 BTD6 가격·광고 서술", "")
        alts = page.eval_on_selector_all("#secAlternatives .alt-row", "els => els.map(e => e.dataset.item)")
        expect(alts == ["kingdom-rush-vengeance"], "라이브 BTD6 대체제 = KR Vengeance", str(alts))

        expect(not pageerrors, "라이브 JS 예외 0건", "; ".join(pageerrors[:3]))
        expect(not console, "라이브 콘솔 에러 0건", "; ".join(console[:3]))
        expect(not failed, "라이브 HTTP 4xx/5xx 0건", "; ".join(failed[:3]))
        b.close()

    ok = sum(1 for _, v, _ in RES if v)
    for label, v, extra in RES:
        print(("[PASS] " if v else "[FAIL] ") + label + ("" if v else f"  <- {extra}"))
    print(f"결과: {ok}/{len(RES)} 통과")
    return 0 if ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
