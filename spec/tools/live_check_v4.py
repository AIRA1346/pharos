#!/usr/bin/env python3
"""라이브(https://aira1346.github.io/pharos/) v0.4.2 분야 확장 검증 + 스크린샷.

검사
  0) 콘솔 에러·페이지 예외·HTTP 4xx 0건
  1) 카탈로그 집계 42건 / 도메인 3 / 대분류 8 / 비교군 9, 탭 홈·앱·게임·AI 도구
  2) 홈 장르 블록 9개, 갭 리포트 4건(Microsoft To Do 포함), 42종 아이콘 로드
  3) 앱 도메인(3비교군·14건) · AI 도메인(1비교군·4건) · 할 일 5건 · 비밀번호 4건 · AI 4건
  4) AI 도구 팩 표시 이름(불투명 크레딧·한도 함정 제외)

스크린샷: live/live-v4-home.png · live-v4-app.png · live-v4-ai.png

  LD_LIBRARY_PATH=/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu \
  python3 projects/pharos/scripts/live_check_v4.py
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://aira1346.github.io/pharos/"
OUT = Path(__file__).resolve().parents[1] / "live"
RESULTS = []


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label, str(extra)))


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
        ok(counts == {"items": 42, "domains": 3, "categories": 8, "arenas": 9}, "집계 42/3/8/9", counts)
        tabs = page.eval_on_selector_all("#domainTabs button", "els => els.map(e => e.innerText.trim())")
        ok(tabs == ["홈", "앱", "게임", "AI 도구"], "탭 홈·앱·게임·AI 도구", tabs)
        blocks = page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)")
        ok(len(blocks) == 9 and "task-managers" in blocks and "password-managers" in blocks
           and "ai-coding-tools" in blocks, "홈 장르 블록 9개(신규 3개 포함)", blocks)
        gaps = page.eval_on_selector_all(".gap-row", "els => els.map(e => e.innerText.split('\\n')[0])")
        ok(len(gaps) == 4 and "Microsoft To Do" in gaps[1], "갭 리포트 4건 · MS To Do 2위", gaps)
        icons = page.evaluate(
            """async () => {
              const items = window.Pharos.state.core.index.items;
              const load = (src) => new Promise((res) => {
                const im = new Image(); im.onload = () => res(im.naturalWidth > 0);
                im.onerror = () => res(false); im.src = src;
              });
              const results = await Promise.all(items.map((i) => load('./' + i.icon)));
              return {ok: results.filter(Boolean).length, total: results.length};
            }"""
        )
        ok(icons["ok"] == 42 and icons["total"] == 42, "42종 아이콘 라이브 로드", icons)
        page.screenshot(path=str(OUT / "live-v4-home.png"), full_page=True)

        page.click('#domainTabs [data-domain="app"]')
        page.wait_for_timeout(800)
        ok("domain=app" in page.url, "앱 탭 URL", page.url)
        app_h1 = page.inner_text(".level-head h1")
        ok("장르 3 · 14건" in app_h1, "앱 도메인 장르 3 · 14건", app_h1)
        page.screenshot(path=str(OUT / "live-v4-app.png"), full_page=True)

        page.click('#domainTabs [data-domain="ai"]')
        page.wait_for_timeout(800)
        ai_h1 = page.inner_text(".level-head h1")
        ok("장르 1 · 4건" in ai_h1, "AI 도구 도메인 장르 1 · 4건", ai_h1)
        ai_picks = page.eval_on_selector_all(".pick-tile", "els => els.map(e => e.dataset.item)")
        ok(ai_picks == ["cline", "github-copilot", "windsurf", "cursor"], "AI 추천 타일 4개", ai_picks)
        page.screenshot(path=str(OUT / "live-v4-ai.png"), full_page=True)

        page.click('#tuneBtn')
        page.wait_for_timeout(600)
        drawer = page.inner_text("#tuneBody")
        ok("AI 도구 팩" in drawer and "불투명 크레딧·한도 함정 제외" in drawer, "AI 도구 팩 표시 이름", drawer[:120])
        page.click('#tuneClose')
        page.wait_for_timeout(300)

        for arena, domain, expect_cards in (("task-managers", "app", 5), ("password-managers", "app", 4),
                                            ("ai-coding-tools", "ai", 4)):
            page.goto(f"{BASE}?domain={domain}&arena={arena}", wait_until="networkidle")
            page.wait_for_timeout(700)
            n = page.eval_on_selector_all("#grid .card, #avoidGrid .card", "els => els.length")
            ok(n == expect_cards, f"{arena} 카드 {expect_cards}건", n)
        ok(not errors, "이동 후 콘솔 에러 0건", errors[:3])
        ok(not failed, "이동 후 HTTP 오류 0건", failed[:3])
        browser.close()

    passed = sum(1 for good, _, _ in RESULTS if good)
    for good, label, extra in RESULTS:
        print(f"[{'PASS' if good else 'FAIL'}] {label}" + ("" if good else f"  ← {extra}"))
    print(f"결과: {passed}/{len(RESULTS)} 통과")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
