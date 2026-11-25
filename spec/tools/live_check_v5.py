#!/usr/bin/env python3
"""라이브(https://aira1346.github.io/pharos/) v0.4.3 분야 확장 검증 + 스크린샷.

검사
  0) 콘솔 에러·페이지 예외·HTTP 4xx 0건
  1) 카탈로그 집계 57건 / 도메인 3 / 대분류 10 / 비교군 12, 탭 홈·앱·게임·AI 도구
  2) 홈 장르 블록 12개, 갭 리포트 4건, 57종 아이콘 로드
  3) AI 어시스턴트·검색 5건(2/3/0), 웹 브라우저 5건(2/3/0), 클라우드 스토리지 5건(1/4/0)
  4) 신규 비교군 상세: Claude·Chrome·Proton Drive의 핵심 서술

스크린샷: live/live-v5-home.png · live-v5-ai-assistants.png · live-v5-browsers.png

  LD_LIBRARY_PATH=/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu \\
  python3 projects/pharos/scripts/live_check_v5.py
"""
from playwright.sync_api import sync_playwright
from pathlib import Path

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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
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
        tabs = page.eval_on_selector_all("#domainTabs button", "els => els.map(e => e.innerText.trim())")
        ok(tabs == ["홈", "앱", "게임", "AI 도구"], "탭 홈·앱·게임·AI 도구", tabs)
        blocks = page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)")
        ok(len(blocks) == 12 and "web-browsers" in blocks and "cloud-storage" in blocks
           and "ai-assistants" in blocks, "홈 장르 블록 12개(신규 3개 포함)", blocks)
        gaps = page.eval_on_selector_all(".gap-row", "els => els.map(e => e.innerText.split('\\n')[0])")
        ok(len(gaps) == 4 and "Microsoft To Do" in gaps[1], "갭 리포트 4건 · MS To Do 2위", gaps)
        icons = page.evaluate(
            """async () => {
              const items = window.Pharos.state.core.index.items;
              const load = (src) => new Promise((res) => {
                const im = new Image(); im.onload = () => res(im.naturalWidth > 0);
                im.onerror = () => res(false); im.src = './' + src;
              });
              const results = await Promise.all(items.map((i) => load(i.icon)));
              return {ok: results.filter(Boolean).length, total: results.length};
            }"""
        )
        ok(icons["ok"] == 57 and icons["total"] == 57, "57종 아이콘 라이브 로드", icons)
        page.screenshot(path=str(OUT / "live-v5-home.png"), full_page=True)

        # AI 어시스턴트 · 검색
        page.goto(f"{BASE}?domain=ai&arena=ai-assistants", wait_until="networkidle")
        page.wait_for_timeout(900)
        ai_n = page.eval_on_selector_all("#grid .card, #avoidGrid .card", "els => els.length")
        ai_stats = stats(page)
        ok(ai_n == 5 and ai_stats.get("추천") == "2" and ai_stats.get("조건부") == "3"
           and ai_stats.get("평균 가중 점수") == "80.3", "AI 어시스턴트 5건 · 2/3/0 · 평균 80.3",
           f"{ai_n} {ai_stats}")
        ai_icons = page.evaluate(
            """() => [...document.querySelectorAll('#grid .card img, #avoidGrid .card img')]
                 .map(i => ({src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0}))"""
        )
        ok(len(ai_icons) == 5 and all(i["ok"] and "assets/icons/" in i["src"] for i in ai_icons),
           "AI 어시스턴트 카드 아이콘 5건 로드", [i["src"] for i in ai_icons if not i["ok"]])
        page.screenshot(path=str(OUT / "live-v5-ai-assistants.png"), full_page=True)

        page.goto(f"{BASE}?domain=ai&arena=ai-assistants&item=claude", wait_until="networkidle")
        page.wait_for_timeout(900)
        body = page.inner_text("#modalBody")
        ok("ad-free" in body or "광고 없음" in body, "Claude 상세 · 광고 없음", body[:120])
        ok("5년" in body, "Claude 상세 · 학습 보존 5년", "")

        # 웹 브라우저
        page.goto(f"{BASE}?domain=app&arena=web-browsers", wait_until="networkidle")
        page.wait_for_timeout(900)
        wb_n = page.eval_on_selector_all("#grid .card, #avoidGrid .card", "els => els.length")
        wb_stats = stats(page)
        ok(wb_n == 5 and wb_stats.get("추천") == "2" and wb_stats.get("조건부") == "3"
           and wb_stats.get("평균 가중 점수") == "77.1", "웹 브라우저 5건 · 2/3/0 · 평균 77.1",
           f"{wb_n} {wb_stats}")
        wb_icons = page.evaluate(
            """() => [...document.querySelectorAll('#grid .card img, #avoidGrid .card img')]
                 .map(i => ({src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0}))"""
        )
        ok(len(wb_icons) == 5 and all(i["ok"] and "assets/icons/" in i["src"] for i in wb_icons),
           "웹 브라우저 카드 아이콘 5건 로드", [i["src"] for i in wb_icons if not i["ok"]])
        page.screenshot(path=str(OUT / "live-v5-browsers.png"), full_page=True)

        page.goto(f"{BASE}?domain=app&arena=web-browsers&item=chrome", wait_until="networkidle")
        page.wait_for_timeout(900)
        body = page.inner_text("#modalBody")
        ok("uBlock Origin" in body and "MV2" in body, "Chrome 상세 · MV2·uBlock Origin", body[:120])

        # 클라우드 스토리지
        page.goto(f"{BASE}?domain=app&arena=cloud-storage", wait_until="networkidle")
        page.wait_for_timeout(900)
        cs_n = page.eval_on_selector_all("#grid .card, #avoidGrid .card", "els => els.length")
        cs_stats = stats(page)
        ok(cs_n == 5 and cs_stats.get("추천") == "1" and cs_stats.get("조건부") == "4"
           and cs_stats.get("평균 가중 점수") == "76.3", "클라우드 5건 · 1/4/0 · 평균 76.3",
           f"{cs_n} {cs_stats}")

        page.goto(f"{BASE}?domain=app&arena=cloud-storage&item=proton-drive", wait_until="networkidle")
        page.wait_for_timeout(900)
        body = page.inner_text("#modalBody")
        ok("종단간" in body and "12개월" in body, "Proton 상세 · E2EE·12개월 유예", body[:120])

        ok(not errors, "이동 후 콘솔 에러 0건", errors[:3])
        ok(not failed, "이동 후 HTTP 오류 0건", failed[:3])
        browser.close()

    passed = sum(1 for good, _, _ in RESULTS if good)
    for good, label, extra in RESULTS:
        print(f"[{'PASS' if good else 'FAIL'}] {label}" + ("" if good else f"  ← {extra}"))
    print(f"결과: {passed}/{len(RESULTS)} 통과")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
