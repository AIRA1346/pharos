#!/usr/bin/env python3
"""라이브(https://aira1346.github.io/pharos/) 확인 — 기준표 v0.4.0 확률형·P2W 3단계 강제성(impact).

확률형·P2W 강도 재적용(Black Desert·Guild Wars 2·Bloons TD 6·Limbus Company)이 실제 배포본에서
배지·상세·미세조정 토글로 동작하는지 확인하고 스크린샷을 저장한다.
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
        "els => els.map(e => ({id:e.dataset.id, verdict:e.dataset.verdict, score:e.dataset.score,"
        " avoid:!!e.closest('#avoidGrid'), text:e.innerText}))",
    )


def stats(page):
    return page.evaluate(
        """() => { const out={}; document.querySelectorAll('#arenaSummary .stat').forEach(s=>{
             out[s.querySelector('.stat-label').textContent.trim()]=s.querySelector('.stat-value').textContent.trim();}); return out; }"""
    )


def card(page, item_id):
    return next((c for c in cards(page) if c["id"] == item_id), None)


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    console, pageerrors, failed = [], [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 1100}, device_scale_factor=2)
        page = ctx.new_page()
        page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: pageerrors.append(str(e)))
        page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)

        page.goto(f"{BASE}?v=97a1250", wait_until="networkidle")
        page.wait_for_timeout(900)
        chip = page.inner_text("#datasetChip")
        expect("v0.4.0" in chip and "24건" in chip and "비교군 6" in chip, "라이브 데이터 칩 v0.4.0·24건·비교군 6", chip)
        shortcuts = page.eval_on_selector_all(".arena-card", "els => els.map(e => e.innerText.replace(/\\n/g,' | '))")
        expect(len(shortcuts) == 6, "홈 비교군 바로가기 6개", str(len(shortcuts)))
        expect("PC MMORPG" in shortcuts[4] and "69.9" in shortcuts[4], "홈 PC MMORPG 카드(평균 69.9)", shortcuts[4][:110])
        expect("모바일 전략·디펜스" in shortcuts[5] and "66.2" in shortcuts[5], "홈 모바일 전략·디펜스 카드(평균 66.2)", shortcuts[5][:110])
        gap = page.eval_on_selector_all(".gap-row", "els => els.map(e => e.innerText.replace(/\\n/g,' | '))")
        expect(len(gap) == 4 and "Hero Wars" in gap[0] and "Clash Royale" in gap[3], "갭 리포트 4건 유지",
               str([g[:26] for g in gap]))
        expect(all("Black Desert" not in g and "Bloons" not in g for g in gap),
               "선택 과금으로 추천이 된 BDO·BTD6 는 갭 리포트에서 빠짐", str([g[:26] for g in gap]))

        # ---------------------------------------------------- PC MMORPG (검은사막)
        page.goto(f"{BASE}?v=97a1250&domain=game&arena=pc-mmorpg", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("h1").strip().startswith("PC MMORPG"), "PC MMORPG 화면", page.inner_text("h1"))
        mmo = cards(page)
        expect(len(mmo) == 4, "라이브 PC MMORPG 카드 4건", str([c["id"] for c in mmo]))
        ms = stats(page)
        expect(ms.get("추천") == "2" and ms.get("조건부") == "1" and ms.get("거름") == "1" and ms.get("평균 가중 점수") == "69.9",
               "라이브 PC MMORPG 요약 2/1/1 · 69.9", str(ms))
        verdicts = {c["id"]: c["verdict"] for c in mmo}
        expect(verdicts == {"final-fantasy-xiv": "recommend", "guild-wars-2": "conditional",
                            "lost-ark": "avoid", "black-desert": "recommend"},
               "라이브 PC MMORPG 판정 4건", str(verdicts))
        bdo = card(page, "black-desert")
        expect(bdo and abs(float(bdo["score"]) - 80.1) < 0.05, "라이브 Black Desert 80.1", str(bdo and bdo["score"]))
        expect(bdo and "선택 과금 · 무과금 가능" in bdo["text"], "라이브 BDO '선택 과금 · 무과금 가능' 배지",
               str(bdo and bdo["text"])[:160])
        expect(bdo and bdo["avoid"] is False, "라이브 BDO 는 거름 영역이 아님")
        gw2 = card(page, "guild-wars-2")
        expect(gw2 and abs(float(gw2["score"]) - 77.2) < 0.05 and gw2["verdict"] == "conditional",
               "라이브 GW2 77.2 조건부", str(gw2 and gw2["score"]))
        lost = card(page, "lost-ark")
        expect(lost and lost["avoid"] is True and "핵심 과금" in lost["text"], "라이브 Lost Ark 는 핵심 과금(거름)",
               str(lost and lost["text"])[:160])
        page.screenshot(path=str(SHOTS / "live-v2-mmorpg-v04.png"), full_page=True)

        # 상세 — 검은사막
        page.goto(f"{BASE}?v=97a1250&domain=game&arena=pc-mmorpg&item=black-desert", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("#modalTitle") == "Black Desert", "라이브 BDO 상세 제목", page.inner_text("#modalTitle"))
        body = page.inner_text("#modalBody")
        expect("선택 과금 · 무과금 가능" in body, "BDO 상세 '선택 과금 · 무과금 가능'", "")
        expect("P2W 강도" in body and "IMPACT" in body.upper(), "BDO 상세 확률형·P2W 강도 블록", "")
        expect("무과금 충분성" in body and "무과금으로 충분" in body, "BDO 상세 무과금 충분성(충분)", "")
        expect("투발라" in body and "거래소" in body, "BDO 무과금 근거(투발라·거래소)", "")
        expect("확률형 아이템 제외" in body and "선택 과금" in body, "BDO 필터는 fail·선택 과금으로 표기", "")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ---------------------------------------- 모바일 전략·디펜스 (Bloons TD 6)
        page.goto(f"{BASE}?v=97a1250&domain=game&arena=mobile-strategy-defense", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("h1").strip().startswith("모바일 전략·디펜스"), "모바일 전략·디펜스 화면", page.inner_text("h1"))
        mob = cards(page)
        expect(len(mob) == 4, "라이브 모바일 전략·디펜스 카드 4건", str([c["id"] for c in mob]))
        st = stats(page)
        expect(st.get("추천") == "2" and st.get("조건부") == "0" and st.get("거름") == "2" and st.get("평균 가중 점수") == "66.2",
               "라이브 모바일 전략·디펜스 요약 2/0/2 · 66.2", str(st))
        bloons = card(page, "bloons-td-6")
        expect(bloons and abs(float(bloons["score"]) - 81.3) < 0.05 and bloons["verdict"] == "recommend",
               "라이브 Bloons TD 6 81.3 추천", str(bloons and (bloons["score"], bloons["verdict"])))
        expect(bloons and "선택 과금 · 무과금 가능" in bloons["text"], "라이브 BTD6 선택 과금 배지",
               str(bloons and bloons["text"])[:160])
        clash = card(page, "clash-royale")
        expect(clash and clash["avoid"] is True and "핵심 과금" in clash["text"], "라이브 Clash Royale 핵심 과금(거름)",
               str(clash and clash["text"])[:160])
        page.screenshot(path=str(SHOTS / "live-v2-mobile-strategy-v04.png"), full_page=True)

        page.goto(f"{BASE}?v=97a1250&domain=game&arena=mobile-strategy-defense&item=bloons-td-6", wait_until="networkidle")
        page.wait_for_timeout(900)
        body = page.inner_text("#modalBody")
        expect("선택 과금" in body and "무과금 충분성" in body, "BTD6 상세 선택 과금·무과금 충분성", "")
        expect("6,500" in body and "광고" in body, "BTD6 가격·광고 서술", "")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ---------------------------------------------- 미세조정 strict_monetization
        page.goto(f"{BASE}?v=97a1250&domain=game&arena=pc-mmorpg", wait_until="networkidle")
        page.wait_for_timeout(800)
        page.click("#tuneBtn")
        page.wait_for_timeout(500)
        expect(page.is_visible("#strictMonetizationToggle"), "라이브 미세조정에 strict_monetization 토글")
        expect(page.is_checked("#strictMonetizationToggle") is False, "라이브 기본값 OFF")
        page.click("#strictMonetizationToggle + .switch-track")
        page.wait_for_timeout(650)
        strict_bdo = card(page, "black-desert")
        expect(strict_bdo and strict_bdo["avoid"] is True and strict_bdo["verdict"] == "avoid",
               "라이브 strict ON → BDO 거름", str(strict_bdo and strict_bdo["text"])[:140])
        page.screenshot(path=str(SHOTS / "live-v2-strict-monetization.png"))
        page.click("#strictMonetizationToggle + .switch-track")
        page.wait_for_timeout(600)
        expect(page.is_checked("#strictMonetizationToggle") is False, "라이브 토글 되돌리기(OFF)")
        page.click("#tuneClose")
        page.wait_for_timeout(300)
        after = card(page, "black-desert")
        expect(after and after["verdict"] == "recommend", "라이브 OFF 복귀 → BDO 추천", str(after and after["verdict"]))

        # 방법론 모달
        page.click("#methodBtn")
        page.wait_for_timeout(500)
        method = page.inner_text("#methodBody")
        expect("확률형·P2W 강도 3단계" in method and "optional" in method and "strict_monetization" in method,
               "라이브 방법론에 3단계·토글 설명", "")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # 스키마 계약이 라이브로 올라갔는지
        contract = page.evaluate("window.Pharos.state.core.contract.monetization_impact")
        expect(contract and contract.get("strict_toggle", {}).get("default") is False,
               "라이브 스키마에 monetization_impact 계약", str(contract)[:120])

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
