#!/usr/bin/env python3
"""라이브(https://aira1346.github.io/pharos/) 확인 — 모바일 게임 3차 확장.

추가한 5종(클래시 오브 클랜·명일방주·승리의 여신: 니케·블루 아카이브·붕괴: 스타레일)이
실제 배포본에서 29건으로 집계되고, 판정·선택 과금 배지·상세가 정상 렌더되는지 확인한다.
콘솔 에러·JS 예외·HTTP 4xx/5xx 0건도 함께 본다.
스크린샷: live-v2-mobile-gacha-expanded.png · live-v2-mobile-strategy-expanded.png
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://aira1346.github.io/pharos/"
SHOTS = Path("/workspace/projects/pharos/live")
V = "?v=290981f"
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

        page.goto(BASE + V, wait_until="networkidle")
        page.wait_for_timeout(1000)
        chip = page.inner_text("#datasetChip")
        expect("v0.4.0" in chip and "29건" in chip and "비교군 6" in chip, "라이브 데이터 칩 v0.4.0·29건·비교군 6", chip)
        shortcuts = page.eval_on_selector_all(".arena-card", "els => els.map(e => e.innerText.replace(/\\n/g,' | '))")
        expect(len(shortcuts) == 6, "홈 비교군 바로가기 6개", str(len(shortcuts)))
        expect("모바일 수집형 RPG" in shortcuts[3] and "6건" in shortcuts[3] and "66.9" in shortcuts[3],
               "홈 모바일 수집형 RPG 카드(6건·평균 66.9)", shortcuts[3][:130])
        expect("모바일 전략·디펜스" in shortcuts[5] and "6건" in shortcuts[5] and "70.6" in shortcuts[5],
               "홈 모바일 전략·디펜스 카드(6건·평균 70.6)", shortcuts[5][:130])

        # ---- 모바일 수집형 RPG
        page.goto(BASE + V + "&domain=game&arena=mobile-gacha-rpg", wait_until="networkidle")
        page.wait_for_timeout(900)
        g = {c["id"]: c for c in cards(page)}
        expect(len(g) == 6, "모바일 수집형 RPG 카드 6건", str(list(g)))
        s = stats(page)
        expect(s.get("추천") == "0" and s.get("조건부") == "2" and s.get("거름") == "4", "가챠 요약 0/2/4", str(s))
        expect(s.get("평균 가중 점수") == "66.9", "가챠 평균 66.9", str(s))
        for item_id, verdict, score in (("goddess-of-victory-nikke", "avoid", 69.65),
                                        ("blue-archive", "conditional", 75.50),
                                        ("honkai-star-rail", "avoid", 70.10)):
            c = g.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect("선택 과금 · 무과금 가능" in g["blue-archive"]["text"], "블루 아카이브 선택 과금 배지", g["blue-archive"]["text"][:140])
        page.screenshot(path=str(SHOTS / "live-v2-mobile-gacha-expanded.png"), full_page=True)
        expect((SHOTS / "live-v2-mobile-gacha-expanded.png").exists(), "가챠 확장 스크린샷 저장",
               str(SHOTS / "live-v2-mobile-gacha-expanded.png"))

        page.goto(BASE + V + "&domain=game&arena=mobile-gacha-rpg&item=goddess-of-victory-nikke", wait_until="networkidle")
        page.wait_for_timeout(800)
        body = page.inner_text("#modalBody")
        expect(page.inner_text("#modalTitle").startswith("승리의 여신"), "니케 상세 열기", page.inner_text("#modalTitle"))
        expect("160" in body and "마일리지" in body and "무과금 충분성" in body, "니케 160벽·마일리지·무과금 충분성", "")
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)

        # ---- 모바일 전략·디펜스
        page.goto(BASE + V + "&domain=game&arena=mobile-strategy-defense", wait_until="networkidle")
        page.wait_for_timeout(900)
        d = {c["id"]: c for c in cards(page)}
        expect(len(d) == 6, "모바일 전략·디펜스 카드 6건", str(list(d)))
        s2 = stats(page)
        expect(s2.get("추천") == "3" and s2.get("조건부") == "1" and s2.get("거름") == "2", "전략·디펜스 요약 3/1/2", str(s2))
        expect(s2.get("평균 가중 점수") == "70.6", "전략·디펜스 평균 70.6", str(s2))
        for item_id, verdict, score in (("clash-of-clans", "conditional", 78.50), ("arknights", "recommend", 80.20)):
            c = d.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect("선택 과금 · 무과금 가능" in d["arknights"]["text"], "아크나이츠 선택 과금 배지", d["arknights"]["text"][:140])
        expect("선택 과금 · 무과금 가능" in d["clash-of-clans"]["text"], "CoC 선택 과금 배지", d["clash-of-clans"]["text"][:140])
        page.screenshot(path=str(SHOTS / "live-v2-mobile-strategy-expanded.png"), full_page=True)
        expect((SHOTS / "live-v2-mobile-strategy-expanded.png").exists(), "전략·디펜스 확장 스크린샷 저장",
               str(SHOTS / "live-v2-mobile-strategy-expanded.png"))

        page.goto(BASE + V + "&domain=game&arena=mobile-strategy-defense&item=arknights", wait_until="networkidle")
        page.wait_for_timeout(800)
        body = page.inner_text("#modalBody")
        expect(page.inner_text("#modalTitle").startswith("Arknights"), "아크나이츠 상세 열기", page.inner_text("#modalTitle"))
        expect("6성 2%" in body and "무과금 충분성" in body, "아크나이츠 6성 2%·무과금 충분성", "")

        expect(not console, "콘솔 에러 0건", "; ".join(console[:5]))
        expect(not pageerrors, "JS 예외 0건", "; ".join(pageerrors[:5]))
        expect(not failed, "HTTP 4xx/5xx 0건", "; ".join(failed[:5]))
        b.close()

    ok = sum(1 for _, c, _ in RES if c)
    for label, cond, extra in RES:
        print(f"[{'PASS' if cond else 'FAIL'}] {label}" + ("" if cond else f"  ← {extra}"))
    print("=" * 70)
    print(f"결과: {ok}/{len(RES)} 통과")
    return 0 if ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
