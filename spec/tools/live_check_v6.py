#!/usr/bin/env python3
"""라이브(https://aira1346.github.io/pharos/) v0.5.0 평가 배분·표본 규모 검증 + 스크린샷.

검사
  0) 콘솔 에러·페이지 예외·HTTP 4xx 0건
  1) 집계 57/3/10/12 · 기본 배분 50/25/25 · 프리셋 5종
  2) 홈: 갭 리포트가 거름 4건(Hero Wars·Archero·MS To Do·Clash Royale), Notion 제외
  3) 노트·지식관리: Notion 77.0 조건부 · Obsidian 82.5 추천 · 요약 2/3/0
  4) AI 어시스턴트: Gemini 81.5 추천 · ChatGPT 84.0 추천 · 요약 4/1/0
  5) 프라이버시 프리셋: account_required·data_collection 자동 → Notion 거름, Obsidian 유지

스크린샷: live/live-v6-home.png · live-v6-pkm.png · live-v6-ai-assistants.png

  LD_LIBRARY_PATH=/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu \
  python3 projects/pharos/scripts/live_check_v6.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://aira1346.github.io/pharos/"
OUT = Path(__file__).resolve().parents[1] / "live"
RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label, str(extra)))


def stats(page):
    return page.evaluate(
        """() => { const out = {};
        document.querySelectorAll('#arenaSummary .stat').forEach((s) => {
          out[s.querySelector('.stat-label').textContent.trim()] = s.querySelector('.stat-value').textContent.trim();
        }); return out; }"""
    )


def card(page, item_id):
    return page.eval_on_selector_all(
        "#grid .card, #avoidGrid .card",
        "(els, id) => { const e = els.find(x => x.dataset.id === id);"
        " return e ? {verdict: e.dataset.verdict, score: e.dataset.score, avoid: !!e.closest('#avoidGrid'),"
        " text: e.innerText} : null; }",
        item_id,
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 1100}, device_scale_factor=2)
        page = ctx.new_page()
        errors, failed = [], []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)

        page.goto(BASE, wait_until="networkidle")
        page.wait_for_timeout(1200)
        ok(page.title().startswith("파로스"), "라이브 타이틀", page.title())
        ok(not errors, "콘솔 에러 0건", errors[:3])
        ok(not failed, "HTTP 4xx/5xx 0건", failed[:3])

        counts = page.evaluate("window.Pharos.state.core.index.counts")
        ok(counts == {"items": 57, "domains": 3, "categories": 10, "arenas": 12}, "집계 57/3/10/12", counts)
        weights = page.evaluate("window.Pharos.state.core.index.weights")
        ok(weights == {"user_rating": 0.5, "objective": 0.25, "ai_review": 0.25}, "기본 배분 50/25/25", weights)

        gaps = page.eval_on_selector_all(".gap-row", "els => els.map(e => e.innerText.replace(/\\n/g, ' | '))")
        ok(len(gaps) == 4, "갭 리포트 4건", gaps)
        ok("Hero Wars" in gaps[0] and "38" in gaps[0] and "거름" in gaps[0], "갭 1위 Hero Wars 38 거름", gaps[0][:120])
        ok("Archero" in gaps[1] and "58" in gaps[1], "갭 2위 Archero 58", gaps[1][:120])
        ok("Microsoft To Do" in gaps[2] and "66.75" in gaps[2], "갭 3위 MS To Do 66.75", gaps[2][:120])
        ok("Clash Royale" in gaps[3] and "61" in gaps[3], "갭 4위 Clash Royale 61", gaps[3][:120])
        ok(all("Notion" not in g for g in gaps), "Notion 은 갭 리포트에서 제외", str(gaps)[:160])
        page.screenshot(path=str(OUT / "live-v6-home.png"), full_page=True)

        page.goto(f"{BASE}?domain=app&arena=pkm-notes", wait_until="networkidle")
        page.wait_for_timeout(900)
        pkm_stats = stats(page)
        ok(pkm_stats.get("추천") == "2" and pkm_stats.get("조건부") == "3" and pkm_stats.get("거름") == "0",
           "노트 요약 2/3/0", pkm_stats)
        ok(pkm_stats.get("평균 가중 점수") == "71.2", "노트 평균 71.2", pkm_stats)
        notion = card(page, "notion")
        obsidian = card(page, "obsidian")
        joplin = card(page, "joplin")
        ok(notion and notion["verdict"] == "conditional" and abs(float(notion["score"]) - 77.0) < 0.05,
           "Notion 77.0 조건부", notion)
        ok(obsidian and obsidian["verdict"] == "recommend" and abs(float(obsidian["score"]) - 82.5) < 0.05,
           "Obsidian 82.5 추천", obsidian)
        ok(joplin and joplin["verdict"] == "recommend" and abs(float(joplin["score"]) - 81.0) < 0.05,
           "Joplin 81.0 추천", joplin)
        page.screenshot(path=str(OUT / "live-v6-pkm.png"), full_page=True)

        page.goto(f"{BASE}?domain=app&arena=pkm-notes&preset=privacy", wait_until="networkidle")
        page.wait_for_timeout(900)
        ok(card(page, "notion")["avoid"] is True, "프라이버시 프리셋 → Notion 거름", str(card(page, "notion"))[:110])
        ok(card(page, "obsidian")["avoid"] is False, "프라이버시 프리셋에서도 Obsidian 유지")

        page.goto(f"{BASE}?domain=ai&arena=ai-assistants", wait_until="networkidle")
        page.wait_for_timeout(900)
        ai_stats = stats(page)
        ok(ai_stats.get("추천") == "4" and ai_stats.get("조건부") == "1" and ai_stats.get("거름") == "0",
           "AI 어시스턴트 요약 4/1/0", ai_stats)
        ok(ai_stats.get("평균 가중 점수") == "83.3", "AI 어시스턴트 평균 83.3", ai_stats)
        for item_id, score, verdict in (("gemini", 81.5, "recommend"), ("chatgpt", 84.0, "recommend"),
                                        ("claude", 87.5, "recommend"), ("le-chat", 79.0, "conditional")):
            c = card(page, item_id)
            ok(c and c["verdict"] == verdict and abs(float(c["score"]) - score) < 0.05,
               f"{item_id} {score} {verdict}", c)
        page.screenshot(path=str(OUT / "live-v6-ai-assistants.png"), full_page=True)

        ok(not errors, "이동 후 콘솔 에러 0건", errors[:3])
        ok(not failed, "이동 후 HTTP 4xx/5xx 0건", failed[:3])
        browser.close()

    passed = sum(1 for r in RESULTS if r[0])
    for good, label, extra in RESULTS:
        print(f"[{'PASS' if good else 'FAIL'}] {label}" + (f"  ← {extra}" if not good and extra else ""))
    print("=" * 70)
    print(f"결과: {passed}/{len(RESULTS)} 통과")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
