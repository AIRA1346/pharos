#!/usr/bin/env python3
"""파로스 v23 항해 서약(Pledge) 스모크 — 목표 탐색 직후의 각서 단계.

무엇을 확인하는가
  1) 흐름 — Step 0 `목표 탐색` → **항해 서약** → Step 1(플랫폼·가격) → … → 결과 카드.
     서약을 건너뛰고 바로 Step 1 로 가는 경로가 없다.
  2) 문구 — 키커 `LIGHTHOUSE PLEDGE · 항해 서약`, 제목 `시작 전 각오`, 세 문장(확정 문구)이 그대로.
  3) 게이트 — 체크 전에는 `서약하고 나아가기` 가 disabled, 체크해야 열린다(마우스·키보드 둘 다).
     `돌아가기` 는 언제나 Step 0 으로 돌아가고, 다시 들어오면 체크는 비어 있다(서약은 매번 새로).
  4) 잠금 — 이미 받은 퀘스트(localStorage)가 있으면 서약을 거치지 않고 곧바로 결과 카드.
  5) EN — 같은 도발·각오 톤의 영문, 한글 잔존 0건(본문·버튼·aria/title 포함).
  6) 테마·반응형 — 다크·라이트 모두 룬에 검은 사각 배경이 비치지 않고, 390px 가로 넘침 0.
  7) 오류 0건 · 스크린샷(--shots-dir) {prefix}-desktop.png · {prefix}-mobile.png.

사용
  python3 projects/pharos/scripts/smoke_v23_pledge.py
  python3 projects/pharos/scripts/smoke_v23_pledge.py --live --shots-dir projects/pharos/live
"""

from __future__ import annotations

import argparse
import functools
import http.server
import io
import os
import re
import socketserver
import threading
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
WEB_ROOT = ROOT / "web"
LIVE = "https://aira1346.github.io/pharos/"
KOREAN = re.compile(r"[\uac00-\ud7a3]")
RESULTS: list[tuple[str, bool, str]] = []

KO_KICKER = "LIGHTHOUSE PLEDGE · 항해 서약"
KO_TITLE = "시작 전 각오"
KO_BODY = [
    "아무거나 대충 구경만 할 거면 지금 돌아가도 좋습니다.",
    "등대는 룰렛을 돌리는 곳이 아니라, 한 번 비춘 목표를 끝까지 걸어가는 사람을 위한 곳입니다.",
    "오늘 받는 좌표는 변명 없이, 다시 뽑을 수 없습니다.",
]
KO_CHECK = "오늘 받는 목표를 끝까지 완수할 각오가 되어 있습니다."
EN_TITLE = "Before we set sail"
EN_BODY2_WORDS = "walk the path to the end"


def expect(condition: bool, label: str, extra: str = "") -> None:
    RESULTS.append((label, bool(condition), str(extra)))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + ("" if condition else f"  ← {extra}"))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        return


def serve(root: Path):
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def shot_array(page) -> np.ndarray:
    raw = page.screenshot()
    return np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")).astype(np.int16)


def probe(page, selector: str) -> dict | None:
    return page.evaluate(
        """(sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        const img = el.tagName === 'IMG' ? el : el.querySelector('img');
        return {
          x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height,
          complete: img ? img.complete : null,
          natural: img ? [img.naturalWidth, img.naturalHeight] : null,
          src: img ? img.currentSrc : null,
          alt: img ? img.getAttribute('alt') : null,
        };
      }""",
        selector,
    )


def top_corner_brightness(arr: np.ndarray, box: dict, patch: int = 4) -> int:
    x, y = int(round(box["x"])), int(round(box["y"]))
    w = int(round(box["w"]))
    x0, y0 = max(0, x + 1), max(0, y + 1)
    a = arr[y0:y0 + patch, x0:x0 + patch]
    b = arr[y0:y0 + patch, max(0, x + w - 1 - patch):x + w - 1]
    return int(min(a.mean() if a.size else 999, b.mean() if b.size else 999))


def korean_left(page) -> list[str]:
    return page.evaluate(
        """(pattern) => {
        const re = new RegExp(pattern);
        const out = new Set();
        document.body.innerText.split('\\n').forEach((line) => { if (re.test(line)) out.add(line.trim()); });
        document.querySelectorAll('[aria-label],[title],[placeholder],[alt]').forEach((el) => {
          ['aria-label', 'title', 'placeholder', 'alt'].forEach((attr) => {
            const v = el.getAttribute(attr);
            if (v && re.test(v)) out.add(attr + ': ' + v);
          });
        });
        if (re.test(document.title)) out.add('title: ' + document.title);
        return [...out];
      }""",
        KOREAN.pattern,
    )


def pledge_state(page) -> dict:
    return page.evaluate(
        """() => {
        const sec = document.querySelector('.lh--pledge');
        if (!sec) return { present: false };
        const input = sec.querySelector('[data-lh-oath-check]');
        const go = sec.querySelector('[data-lh-oath]');
        return {
          present: true,
          sworn: sec.classList.contains('is-sworn'),
          checked: !!input?.checked,
          disabled: !!go?.disabled,
          hintVisible: (() => { const h = sec.querySelector('.lh-pledge-hint'); return !!h && h.offsetParent !== null; })(),
          kicker: sec.querySelector('.lh-pledge-kicker')?.innerText.trim() || '',
          title: sec.querySelector('.lh-pledge-title')?.innerText.trim() || '',
          clauses: [...sec.querySelectorAll('.lh-pledge-clauses p')].map((p) => p.innerText.trim()),
          check: sec.querySelector('.lh-pledge-check-text')?.innerText.trim() || '',
          go: go?.innerText.trim() || '',
          back: sec.querySelector('.lh-pledge-back')?.innerText.trim() || '',
          labelledby: sec.getAttribute('aria-labelledby'),
          titleId: sec.querySelector('.lh-pledge-title')?.id || '',
          step1: !!document.querySelector('.lh--step1'),
        };
      }"""
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--shots-dir", default="")
    parser.add_argument("--shot-prefix", default="")
    parser.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    args = parser.parse_args()

    httpd = None
    if args.live:
        base = LIVE
    else:
        httpd, base = serve(WEB_ROOT)
    prefix = args.shot_prefix or ("live-v23-pledge" if args.live else "local-v23-pledge")
    shots = Path(args.shots_dir) if args.shots_dir else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    # 스크립트가 live/ 밖에서 실행될 때를 대비해 상대 경로를 프로젝트 기준으로 푼다.
    if shots and not shots.is_absolute():
        shots = (ROOT / ".." / ".." / shots).resolve()

    errors: list[str] = []
    bad_http: list[str] = []

    try:
        with sync_playwright() as p:
            launch = {"executable_path": args.chrome} if args.chrome else {}
            browser = p.chromium.launch(**launch)

            def open_page(viewport=(1280, 900), lang="ko"):
                ctx = browser.new_context(
                    viewport={"width": viewport[0], "height": viewport[1]},
                    locale="ko-KR" if lang == "ko" else "en-US",
                )
                page = ctx.new_page()
                page.on("pageerror", lambda exc: errors.append(str(exc)))
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("response", lambda res: bad_http.append(f"{res.status} {res.url}") if res.status >= 400 else None)
                return ctx, page

            def land(page, url_suffix="?lang=ko"):
                page.goto(base + url_suffix, wait_until="networkidle")
                page.wait_for_timeout(600)

            # ---------------------------------------------------------- KO 첫 진입
            ctx, page = open_page()
            land(page)
            expect(page.query_selector(".lh--landing") is not None, "Step 0 랜딩이 먼저 뜬다", "")
            expect(page.query_selector(".lh--pledge") is None, "랜딩 단계에서는 서약 화면이 없다", "")
            cta = page.inner_text("[data-lh-goto='pledge']").strip()
            expect(cta == "목표 탐색", "Step 0 CTA = `목표 탐색`", cta)

            page.click("[data-lh-goto='pledge']")
            page.wait_for_timeout(450)
            st = pledge_state(page)
            expect(st["present"], "목표 탐색 → 항해 서약 화면", str(st)[:120])
            expect(not st.get("step1"), "서약 단계에서 Step 1 이 함께 뜨지 않는다", "")
            expect(st.get("kicker") == KO_KICKER, f"서약 키커 `{KO_KICKER}`", st.get("kicker"))
            expect(st.get("title") == KO_TITLE, f"서약 제목 `{KO_TITLE}`", st.get("title"))
            expect(st.get("clauses") == KO_BODY, "서약 본문 3문장이 확정 문구와 일치", str(st.get("clauses")))
            expect(KO_BODY[1] in (st.get("clauses") or []), "2문장 `끝까지 걸어가는` 반영", KO_BODY[1])
            expect(st.get("check") == KO_CHECK, "체크 문구 일치", st.get("check"))
            expect(st.get("go") == "서약하고 나아가기", "주 CTA = `서약하고 나아가기`", st.get("go"))
            expect(st.get("back") == "돌아가기", "보조 버튼 = `돌아가기`", st.get("back"))
            expect(st.get("labelledby") == st.get("titleId") and st.get("titleId"), "서약 제목이 aria-labelledby 로 연결", str(st.get("labelledby")))
            expect(st.get("disabled") and not st.get("checked"), "체크 전 주 CTA 비활성·미체크", str(st))
            expect(st.get("hintVisible"), "체크 전 안내 문구 표시", "")
            focused = page.evaluate("() => document.activeElement?.className || ''")
            expect("lh-pledge-title" in focused, "서약 진입 시 제목으로 포커스", focused)

            rune = probe(page, ".lh-pledge-rune")
            expect(rune is not None and rune["complete"] and rune["natural"][0] > 0,
                   "서약 상단 브랜드 룬 로드", str(rune and rune["src"]))
            expect(rune is not None and "pharos-rune" in (rune["src"] or ""), "룬 에셋 = pharos-rune", str(rune and rune["src"]))
            expect(rune is not None and 32 <= rune["w"] <= 60, "룬 크기 32~60px", str(rune and rune["w"]))

            if shots:
                page.screenshot(path=str(shots / f"{prefix}-desktop.png"))

            # 체크 전 CTA 클릭은 아무 일도 하지 않는다(disabled).
            page.evaluate("() => document.querySelector('[data-lh-oath]')?.click()")
            page.wait_for_timeout(250)
            expect(pledge_state(page)["present"], "체크 전 주 CTA 클릭으로 넘어가지 않는다", "")

            # 키보드 — 포커스 + Space 로 체크
            page.focus("[data-lh-oath-check]")
            page.keyboard.press(" ")
            page.wait_for_timeout(250)
            st = pledge_state(page)
            expect(st["checked"] and not st["disabled"], "키보드(Space)로 체크 → CTA 활성", str(st)[:120])
            expect(st["sworn"] and not st["hintVisible"], "체크 시 카드 상태·안내 문구 정리", str(st)[:120])

            # 다시 해제 → 비활성
            page.click(".lh-pledge-check")
            page.wait_for_timeout(250)
            st = pledge_state(page)
            expect(not st["checked"] and st["disabled"], "체크 해제 → CTA 다시 비활성", str(st)[:100])

            # 체크 → 서약
            page.click(".lh-pledge-check")
            page.wait_for_timeout(250)
            page.click("[data-lh-oath]")
            page.wait_for_timeout(450)
            expect(page.query_selector(".lh--step1") is not None, "서약 뒤 Step 1(플랫폼·가격) 진입", "")
            progress = page.inner_text(".lh-progress-text").strip()
            expect(progress == "1 / 3", "서약은 진행 표시(1/3)를 먹지 않는다", progress)
            expect(page.query_selector(".lh--pledge") is None, "Step 1 에서 서약 화면이 사라진다", "")

            # Step 1 → 처음으로 → 목표 탐색 → 서약 체크 초기화
            page.click(".lh-wizard-nav [data-lh-goto='0']")
            page.wait_for_timeout(350)
            page.click("[data-lh-goto='pledge']")
            page.wait_for_timeout(350)
            st = pledge_state(page)
            expect(st["present"] and not st["checked"] and st["disabled"],
                   "다시 목표 탐색 → 서약 체크는 비어 있다(매번 새로)", str(st)[:120])

            # 돌아가기 → Step 0
            page.click(".lh-pledge-back")
            page.wait_for_timeout(350)
            expect(page.query_selector(".lh--landing") is not None and page.query_selector(".lh--pledge") is None,
                   "`돌아가기` → Step 0 복귀", "")

            # ---------------------------------------------------------- 잠긴 퀘스트
            page.click("[data-lh-goto='pledge']")
            page.wait_for_timeout(350)
            page.click(".lh-pledge-check")
            page.wait_for_timeout(150)
            page.click("[data-lh-oath]")
            page.wait_for_timeout(350)
            page.click(".lh-wizard-nav [data-lh-goto='2']")
            page.wait_for_timeout(300)
            page.click(".lh-wizard-nav [data-lh-goto='3']")
            page.wait_for_timeout(350)
            page.click("[data-lh-draw]")
            page.wait_for_timeout(600)
            card = page.query_selector(".lh-card")
            expect(card is not None, "서약 → 조건 → 추첨으로 목표 카드 발급", "")

            page.reload(wait_until="networkidle")
            page.wait_for_timeout(700)
            expect(page.query_selector(".lh--result .lh-card") is not None, "잠긴 퀘스트: 새로고침하면 결과 카드", "")
            expect(page.query_selector(".lh--pledge") is None, "잠긴 퀘스트: 서약 화면을 거치지 않는다", "")
            expect(page.query_selector("[data-lh-goto='pledge']") is None, "잠긴 퀘스트: 목표 탐색 CTA 없음", "")

            page.click(".brand")
            page.wait_for_timeout(500)
            expect(page.query_selector(".lh--result .lh-card") is not None and page.query_selector(".lh--pledge") is None,
                   "로고로 돌아와도 결과 카드 유지(서약 없음)", "")

            # 완료 → 랜딩 → 목표 탐색은 다시 서약부터
            page.click("[data-lh-complete]")
            page.wait_for_timeout(600)
            expect(page.query_selector(".lh--landing") is not None, "완료 후 랜딩 복귀", "")
            page.click("[data-lh-goto='pledge']")
            page.wait_for_timeout(350)
            expect(pledge_state(page)["present"], "완료 뒤 새 목표 탐색도 서약부터", "")

            # ---------------------------------------------------------- 테마
            page.evaluate("() => document.documentElement.setAttribute('data-theme','light')")
            page.wait_for_timeout(350)
            rune_l = probe(page, ".lh-pledge-rune")
            page.evaluate("() => window.scrollTo(0, 0)")
            page.wait_for_timeout(200)
            rune_l = probe(page, ".lh-pledge-rune")
            arr = shot_array(page)
            corner = top_corner_brightness(arr, rune_l, patch=3)
            expect(corner >= 185, "라이트 테마: 룬 위 모서리에 검은 사각 배경 없음(밝기 ≥185)", str(corner))
            page.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
            page.wait_for_timeout(250)
            expect(not errors, "KO: 콘솔/페이지 오류 0", "; ".join(errors[:3]))
            ctx.close()

            # ---------------------------------------------------------- EN
            ctx, page = open_page(lang="en")
            land(page, "?lang=en")
            en_cta = page.inner_text("[data-lh-goto='pledge']").strip()
            expect(en_cta == "Find a goal", "EN: 랜딩 CTA `Find a goal`", en_cta)
            page.click("[data-lh-goto='pledge']")
            page.wait_for_timeout(450)
            st = pledge_state(page)
            expect(st["present"], "EN: 항해 서약 화면", "")
            expect(st.get("kicker") == "LIGHTHOUSE PLEDGE", "EN: 키커 `LIGHTHOUSE PLEDGE`", st.get("kicker"))
            expect(st.get("title") == EN_TITLE, f"EN: 제목 `{EN_TITLE}`", st.get("title"))
            expect(len(st.get("clauses") or []) == 3, "EN: 본문 3문장", str(st.get("clauses")))
            expect(EN_BODY2_WORDS in (st.get("clauses") or [""])[1], f"EN: 2문장에 `{EN_BODY2_WORDS}`", str(st.get("clauses")))
            expect(st.get("go") == "Take the Oath", "EN: `Take the Oath`", st.get("go"))
            expect(st.get("back") == "Turn Back", "EN: `Turn Back`", st.get("back"))
            expect(st.get("disabled"), "EN: 체크 전 CTA 비활성", "")
            expect(not korean_left(page), "EN: 서약 화면 한글 잔존 0건", str(korean_left(page)[:3]))
            page.click(".lh-pledge-check")
            page.wait_for_timeout(200)
            expect(not korean_left(page), "EN: 체크 뒤에도 한글 0건", str(korean_left(page)[:3]))
            page.click("[data-lh-oath]")
            page.wait_for_timeout(400)
            expect(page.query_selector(".lh--step1") is not None, "EN: 서약 뒤 Step 1", "")
            expect(not korean_left(page), "EN: Step 1 한글 0건", str(korean_left(page)[:3]))
            expect(not errors, "EN: 콘솔/페이지 오류 0", "; ".join(errors[:3]))
            ctx.close()

            # ---------------------------------------------------------- 모바일
            ctx, page = open_page(viewport=(390, 844))
            land(page)
            page.click("[data-lh-goto='pledge']")
            page.wait_for_timeout(450)
            overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            expect(overflow == 0, "390px: 서약 화면 가로 넘침 0", str(overflow))
            st = pledge_state(page)
            expect(st["present"] and st["clauses"] == KO_BODY, "390px: 서약 본문 그대로", "")
            actions = page.evaluate(
                """() => { const b = document.querySelector('[data-lh-oath]').getBoundingClientRect();
                     const c = document.querySelector('.lh-pledge-check').getBoundingClientRect();
                     return [b.left, b.right, b.top, c.top, innerWidth]; }"""
            )
            expect(actions[0] >= 0 and actions[1] <= actions[2] + 1 and actions[2] > actions[3],
                   "390px: 체크 아래에 서약 버튼, 화면 안", str(actions))
            if shots:
                page.screenshot(path=str(shots / f"{prefix}-mobile.png"))
            expect(not errors, "모바일: 콘솔/페이지 오류 0", "; ".join(errors[:3]))
            ctx.close()
            browser.close()
    finally:
        if httpd:
            httpd.shutdown()

    # GitHub Pages 아이콘 503 은 한 번 더 확인
    for item in list(bad_http):
        status, _, url = item.partition(" ")
        if status == "503" and "/assets/" in url:
            try:
                import urllib.request

                if urllib.request.urlopen(url, timeout=10).status == 200:
                    bad_http.remove(item)
            except Exception:
                pass
    expect(not bad_http, "HTTP 4xx/5xx 0 (아이콘 503 재확인)", "; ".join(bad_http[:3]))

    failed = [x for x in RESULTS if not x[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} PASS")
    for label, _, extra in failed:
        print(f"  FAIL {label}  ← {extra}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
