#!/usr/bin/env python3
"""라이브(https://aira1346.github.io/pharos/) 확인 — 실제 배포본을 브라우저로 열어 검증한다.
게임 도메인 확장(액션 로그라이크 4종 · 모바일 수집형 RPG 3종) 배포 확인용.
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

        page.goto(f"{BASE}?v=73aeb33", wait_until="networkidle")
        page.wait_for_timeout(800)
        chip = page.inner_text("#datasetChip")
        expect("v0.4.0" in chip and "16건" in chip and "비교군 4" in chip, "라이브 데이터 칩", chip)
        shortcuts = page.eval_on_selector_all(".arena-card", "els => els.map(e => e.innerText.replace(/\\n/g,' | '))")
        expect(len(shortcuts) == 4, "홈 비교군 바로가기 4개", str(len(shortcuts)))
        expect("액션 로그라이크" in shortcuts[2] and "77.9" in shortcuts[2], "홈에 액션 로그라이크 카드", shortcuts[2][:80])
        expect("모바일 수집형 RPG" in shortcuts[3] and "3건" in shortcuts[3], "홈에 가챠 3건 카드", shortcuts[3][:80])
        gap = page.eval_on_selector_all(".gap-row", "els => els.map(e => e.innerText.replace(/\\n/g,' | '))")
        expect(len(gap) == 3 and "Hero Wars" in gap[0] and "Archero" in gap[1] and "Notion" in gap[2],
               "갭 리포트 3건(Hero Wars·Archero·Notion)", str([g[:28] for g in gap]))
        page.screenshot(path=str(SHOTS / "live-v2-home.png"), full_page=True)

        # 통합 검색
        page.fill("#homeSearch", "뱀파이어")
        page.wait_for_timeout(400)
        rows = page.eval_on_selector_all(".search-row", "els => els.map(e => e.dataset.item)")
        expect("vampire-survivors" in rows, "검색 '뱀파이어' → Vampire Survivors", str(rows))
        page.fill("#homeSearch", "하데스")
        page.wait_for_timeout(400)
        rows2 = page.eval_on_selector_all(".search-row", "els => els.map(e => e.dataset.item)")
        expect("hades" in rows2, "검색 '하데스' → Hades", str(rows2))

        # 새 비교군
        page.goto(f"{BASE}?v=73aeb33&domain=game&arena=action-roguelike", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("h1").strip().startswith("액션 로그라이크"), "액션 로그라이크 화면", page.inner_text("h1"))
        cs = cards(page)
        expect(len(cs) == 4, "라이브 액션 로그라이크 카드 4건", str([c["id"] for c in cs]))
        st = stats(page)
        expect(st.get("추천") == "3" and st.get("거름") == "1" and st.get("평균 가중 점수") == "77.9",
               "라이브 요약 3/0/1 · 77.9", str(st))
        expect({c["id"]: c["verdict"] for c in cs} == {
            "vampire-survivors": "recommend", "dead-cells": "recommend", "hades": "recommend", "archero": "avoid"},
               "라이브 판정 4건", str({c["id"]: c["verdict"] for c in cs}))
        page.screenshot(path=str(SHOTS / "live-v2-game-action.png"), full_page=True)

        # 1:1 비교
        page.check('#grid .card[data-id="hades"] input[data-compare]')
        page.wait_for_timeout(250)
        page.check('#grid .card[data-id="vampire-survivors"] input[data-compare]')
        page.wait_for_timeout(350)
        page.click("#compareOpen")
        page.wait_for_timeout(700)
        headers = page.eval_on_selector_all("#compareTable thead th", "els => els.map(e => e.innerText.split('\\n')[0])")
        expect(headers == ["기준", "Hades", "Vampire Survivors"], "라이브 비교 표 머리글", str(headers))
        table = page.inner_text("#compareTable")
        expect("82.7" in table and "89.8" in table, "라이브 비교 표 점수", table[:120])
        page.screenshot(path=str(SHOTS / "live-v2-game-compare.png"), full_page=True)

        # 상세(아르케로) — 필터 사유·대체제
        page.goto(f"{BASE}?v=73aeb33&domain=game&arena=action-roguelike&item=archero", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("#modalTitle") == "Archero (궁수의 전설)", "라이브 상세 제목", page.inner_text("#modalTitle"))
        body = page.inner_text("#modalBody")
        expect("확률형 아이템 제외 적중" in body, "라이브 상세: 확률형 아이템 적중", "")
        expect("가격대 미확인" in body and "인앱결제 없음" not in body, "라이브 상세: IAP 가격대 미확인 표기", "")
        alts = page.eval_on_selector_all("#secAlternatives .alt-row", "els => els.map(e => e.dataset.item)")
        expect(alts == ["vampire-survivors", "dead-cells", "hades"], "라이브 대체제 3건", str(alts))
        page.screenshot(path=str(SHOTS / "live-v2-game-detail.png"))

        # 모바일 수집형 RPG 3종
        page.goto(f"{BASE}?v=73aeb33&domain=game&arena=mobile-gacha-rpg", wait_until="networkidle")
        page.wait_for_timeout(900)
        gs = cards(page)
        expect(len(gs) == 3, "라이브 가챠 카드 3건", str([c["id"] for c in gs]))
        gst = stats(page)
        expect(gst.get("추천") == "0" and gst.get("거름") == "3" and gst.get("평균 가중 점수") == "62.0",
               "라이브 가챠 요약 0/0/3 · 62.0", str(gst))
        expect(abs(float({c["id"]: c["score"] for c in gs}.get("limbus-company") or 0) - 78.7) < 0.05,
               "라이브 Limbus 78.7", str({c["id"]: c["score"] for c in gs}))
        page.screenshot(path=str(SHOTS / "live-v2-game-gacha.png"), full_page=True)

        # 가챠 상세(림버스)
        page.goto(f"{BASE}?v=73aeb33&domain=game&arena=mobile-gacha-rpg&item=limbus-company", wait_until="networkidle")
        page.wait_for_timeout(800)
        body = page.inner_text("#modalBody")
        expect("확률형 아이템 제외 적중" in body, "라이브 림버스: 확률형 아이템 적중", "")
        expect("광고" in body, "라이브 림버스: 광고 없음 서술", "")

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
