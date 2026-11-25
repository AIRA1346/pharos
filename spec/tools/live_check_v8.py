#!/usr/bin/env python3
"""라이브(https://aira1346.github.io/pharos/) v3.4 — auto_collect 파이프라인 신규 비교군 확인 + 스크린샷.

검사
  0) 콘솔 에러·페이지 예외·HTTP 4xx/5xx 0건
  1) 집계가 라이브 데이터와 일치(67건 · 도메인 3 · 대분류 10 · 비교군 14) · 홈 도메인 필터 「전체 14 · 앱 6 · 게임 6 · AI 도구 2」
  2) 홈: 두 신규 비교군 블록(메트로배니아 · 플랫포머, 이메일 클라이언트)이 보이고 추천 타일이 뜬다
  3) 게임 › 메트로배니아 · 플랫포머: 5종 전부 추천, 점수·아이콘, 상세 모달의 가격·리뷰 표본
  4) 앱 › 이메일 클라이언트: 추천 3 · 조건부 2(K-9 Mail 69.5 · Spark Mail 80.0),
     Thunderbird 는 스토어 표본이 없어 사용자 축 ⚪
  5) 상세 모달: 사실(Fact)·출처·가격 티어가 새 데이터에서도 렌더된다

스크린샷: live/live-v8-home.png · live/live-v8-auto-arena.png · live/live-v8-email-clients.png

  LD_LIBRARY_PATH=/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu \\
  python3 projects/pharos/scripts/live_check_v8.py
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
        """(els, id) => { const e = els.find(x => x.dataset.id === id);
        return e ? {verdict: e.dataset.verdict, score: e.dataset.score, avoid: !!e.closest('#avoidGrid'),
                     text: e.innerText} : null; }""",
        item_id,
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
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
        ok(counts == {"items": 67, "domains": 3, "categories": 10, "arenas": 14}, "집계 67/3/10/14", counts)
        chip = page.inner_text("#datasetChip")
        ok("67건" in chip and "비교군 14" in chip, "데이터 칩 = 67건 · 비교군 14", chip)

        dom_chips = page.eval_on_selector_all("#homeDomainFilter .domain-chip", "els => els.map(e => e.innerText.replace(/\\n/g, ' ').trim())")
        ok(dom_chips == ["전체 14", "앱 6", "게임 6", "AI 도구 2"], "홈 도메인 필터 = 전체 14 · 앱 6 · 게임 6 · AI 도구 2", dom_chips)

        blocks = page.eval_on_selector_all("#genreList .genre-block", "els => els.map(e => e.dataset.arena)")
        ok("metroidvania-platformer" in blocks and "email-clients" in blocks,
           "홈에 신규 비교군 두 블록 노출", blocks)
        mv_block = page.inner_text('.genre-block[data-arena="metroidvania-platformer"]').replace("\n", " | ")
        ok("메트로배니아" in mv_block and "Hollow Knight" in mv_block, "홈 메트로배니아 블록에 추천 타일", mv_block[:160])
        mail_block = page.inner_text('.genre-block[data-arena="email-clients"]').replace("\n", " | ")
        ok("이메일 클라이언트" in mail_block and ("Thunderbird" in mail_block or "Proton" in mail_block),
           "홈 이메일 클라이언트 블록에 추천 타일", mail_block[:160])
        gap = page.inner_text("#gapReportSection") if page.query_selector("#gapReportSection") else ""
        ok("Notion" not in gap and "Obsidian" not in gap, "갭 리포트에 검증된 항목 제외(Notion·Obsidian)", gap[:80])
        page.screenshot(path=str(OUT / "live-v8-home.png"), full_page=True)

        page.goto(f"{BASE}?domain=game&arena=metroidvania-platformer", wait_until="networkidle")
        page.wait_for_timeout(900)
        mv = stats(page)
        ok(mv.get("추천") == "5" and mv.get("거름") == "0", "메트로배니아 요약 5/0/0", mv)
        for item_id, score in (("hollow-knight", 90.0), ("celeste", 89.5), ("nine-sols", 89.25),
                               ("ori-and-the-will-of-the-wisps", 87.75), ("blasphemous", 83.0)):
            c = card(page, item_id)
            ok(c and c["verdict"] == "recommend" and abs(float(c["score"]) - score) < 0.05,
               f"{item_id} {score} 추천", c)
        icons = page.eval_on_selector_all("#grid .card .item-icon--card img",
                                          "els => els.map(e => ({src: e.getAttribute('src'), ok: e.complete && e.naturalWidth > 0}))")
        ok(len(icons) == 5 and all(i["ok"] for i in icons), "메트로배니아 5종 아이콘 로드", [i["src"] for i in icons])
        page.screenshot(path=str(OUT / "live-v8-auto-arena.png"), full_page=True)

        page.click('#grid .card[data-id="celeste"]')
        page.wait_for_timeout(700)
        text = page.inner_text("#modal")
        ok("₩21,500" in text and "완결작" in text, "Celeste 상세 = 가격·완결작 배지", text[:140].replace("\n", " | "))
        ok("전체(영어 리뷰)" in text and "97%" in text, "Celeste 상세 = 스팀 리뷰 표본", text[-500:].replace("\n", " | ")[:180])
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        page.goto(f"{BASE}?domain=app&arena=email-clients", wait_until="networkidle")
        page.wait_for_timeout(900)
        mail = stats(page)
        ok(mail.get("추천") == "3" and mail.get("조건부") == "2" and mail.get("거름") == "0",
           "이메일 클라이언트 요약 3/2/0", mail)
        k9 = card(page, "k9-mail")
        spark = card(page, "spark-mail")
        tb = card(page, "thunderbird")
        ok(k9 and k9["verdict"] == "conditional" and abs(float(k9["score"]) - 69.5) < 0.05, "K-9 Mail 69.5 조건부", k9)
        ok(spark and spark["verdict"] == "conditional" and abs(float(spark["score"]) - 80.0) < 0.05, "Spark Mail 80.0 조건부", spark)
        ok(tb and tb["verdict"] == "recommend" and abs(float(tb["score"]) - 86.0) < 0.05, "Thunderbird 86.0 추천", tb)
        page.screenshot(path=str(OUT / "live-v8-email-clients.png"), full_page=True)

        page.click('#grid .card[data-id="thunderbird"]')
        page.wait_for_timeout(700)
        tb_text = page.inner_text("#modal")
        ok("⚪" in tb_text, "Thunderbird 상세 = 사용자 축 ⚪(스토어 표본 없음)", tb_text[:200].replace("\n", " | "))
        ok("MPL" in tb_text or "오픈소스" in tb_text, "Thunderbird 상세 = 오픈소스 근거", tb_text[-600:].replace("\n", " | ")[:200])
        page.keyboard.press("Escape")

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
