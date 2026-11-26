#!/usr/bin/env python3
"""라이브(https://aira1346.github.io/pharos/) 확인 — 기준표 v0.4.1 니케 재평가.

승리의 여신: 니케가 본질 경험 기준(core_experience)으로 다시 채점되어
모바일 수집형 RPG 비교군에서 🟢 추천 81.2 로 보이는지, 160벽·아레나 사실이
카드·상세에 그대로 남아 있는지, strict_monetization 을 켜면 다시 거름이 되는지 확인한다.
콘솔 에러·JS 예외·HTTP 4xx/5xx 0건도 함께 본다.
스크린샷: live-v2-mobile-gacha-nikke.png · live-v2-mobile-gacha-nikke-detail.png
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://aira1346.github.io/pharos/"
SHOTS = Path("/workspace/projects/pharos/live")
V = "?v=4db456d"
RES = []


def expect(cond, label, extra=""):
    RES.append((label, bool(cond), str(extra)))


def cards(page):
    return page.eval_on_selector_all(
        "#grid .card, #avoidGrid .card",
        "els => els.map(e => ({id:e.dataset.id, verdict:e.dataset.verdict, score:e.dataset.score,"
        " avoid:!!e.closest('#avoidGrid'), text:e.innerText}))",
    )


def card(page, item_id):
    for c in cards(page):
        if c["id"] == item_id:
            return c
    return None


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
        shortcuts = page.eval_on_selector_all(".arena-card", "els => els.map(e => e.innerText.replace(/\\n/g,' | '))")
        expect(len(shortcuts) == 6, "홈 비교군 바로가기 6개", str(len(shortcuts)))
        expect("모바일 수집형 RPG" in shortcuts[3] and "6건" in shortcuts[3] and "68.8" in shortcuts[3],
               "홈 모바일 수집형 RPG 카드(6건·평균 68.8)", shortcuts[3][:150])

        # ---- 모바일 수집형 RPG 목록
        page.goto(BASE + V + "&domain=game&arena=mobile-gacha-rpg", wait_until="networkidle")
        page.wait_for_timeout(1000)
        g = {c["id"]: c for c in cards(page)}
        expect(len(g) == 6, "모바일 수집형 RPG 카드 6건", str(list(g)))
        s = stats(page)
        expect(s.get("추천") == "1" and s.get("조건부") == "2" and s.get("거름") == "3", "가챠 요약 1/2/3", str(s))
        expect(s.get("평균 가중 점수") == "68.8", "가챠 평균 68.8", str(s))
        nikke = g.get("goddess-of-victory-nikke")
        expect(nikke is not None, "니케 카드 존재")
        if nikke:
            expect(nikke["verdict"] == "recommend" and nikke["avoid"] is False, "니케 = 추천(상단 영역)", nikke["verdict"])
            expect(nikke["score"] and abs(float(nikke["score"]) - 81.2) < 0.05, "니케 점수 81.2", nikke["score"])
            expect("선택 과금 · 무과금 가능" in nikke["text"], "니케 카드에 선택 과금 배지", nikke["text"][:180])
            expect("160" in nikke["text"], "니케 카드에 160벽 사실 유지", nikke["text"][:220])
            expect("🟢" in nikke["text"] and "추천" in nikke["text"], "니케 카드 🟢 추천 표시", nikke["text"][:160])
        for item_id, verdict, score in (("blue-archive", "conditional", 75.50),
                                        ("honkai-star-rail", "avoid", 70.10)):
            c = g.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        page.screenshot(path=str(SHOTS / "live-v2-mobile-gacha-nikke.png"), full_page=True)
        expect((SHOTS / "live-v2-mobile-gacha-nikke.png").exists(), "가챠 목록 스크린샷 저장",
               str(SHOTS / "live-v2-mobile-gacha-nikke.png"))

        # ---- 니케 상세
        page.goto(BASE + V + "&domain=game&arena=mobile-gacha-rpg&item=goddess-of-victory-nikke",
                  wait_until="networkidle")
        page.wait_for_timeout(900)
        body = page.inner_text("#modalBody")
        expect(page.inner_text("#modalTitle").startswith("승리의 여신"), "니케 상세 열기", page.inner_text("#modalTitle"))
        expect("160" in body and "마일리지" in body, "니케 160벽·마일리지 서술", "")
        expect("무과금 충분성" in body and "무과금으로 충분" in body, "니케 무과금 충분성 = 충분", "")
        expect("선택 과금" in body and "스토리" in body, "니케 선택 과금·스토리 본질 서술", "")
        expect("아레나" in body and "스킨" in body, "니케 엔드 경쟁·스킨 사실 유지", "")
        page.screenshot(path=str(SHOTS / "live-v2-mobile-gacha-nikke-detail.png"), full_page=False)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ---- strict_monetization 을 켜면 다시 거름(사실 유지)
        page.goto(BASE + V + "&domain=game&arena=mobile-gacha-rpg&strictmon=1", wait_until="networkidle")
        page.wait_for_timeout(900)
        strict = card(page, "goddess-of-victory-nikke")
        expect(strict and strict["avoid"] is True, "strict_monetization ON → 니케 거름",
               str(strict and strict["text"])[:160])

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
