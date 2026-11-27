#!/usr/bin/env python3
"""파로스 v22 브랜드 심볼 스모크 — 룬(헤더·파비콘) + 등대(Step 0 중앙) + 테마·언어·반응형.

무엇을 확인하는가
  1) 에셋 — brand/ 아래 룬·등대·파비콘 파일이 존재하고 HTTP 200 으로 내려오며 알파가 살아 있다
     (모서리 알파 0, 테두리 띠의 불투명 픽셀 비율이 낮음 = 검은 네모 배경 없음)
  2) 헤더 — `PHAROS` 앞 브랜드 마크가 룬 이미지(picture/img)이고 46px(모바일 34px)로 뜬다
  3) 파비콘 — <link rel="icon"> 이 brand/favicon-32.png(및 .ico) 를 가리키고 200 으로 내려온다
  4) Step 0 — 등대 심볼이 뽑기 CTA 위 중앙에 존재감 있게(데스크톱 126~180px, 모바일 104~140px) 뜬다
  5) 라이트 테마 — 등대·룬 주변에 검은 사각 박스가 비치지 않는다(스크린샷 모서리 픽셀 밝기 검사)
  6) KO·EN 모두 문구·이미지가 정상이고 390px 가로 넘침 0 · 콘솔/HTTP 오류 0
  7) 스크린샷 — --shots-dir 에 {prefix}-desktop.png · {prefix}-mobile.png

사용
  python3 projects/pharos/scripts/smoke_v22_brand.py
  python3 projects/pharos/scripts/smoke_v22_brand.py --live --shots-dir projects/pharos/live
"""

from __future__ import annotations

import argparse
import functools
import http.server
import io
import os
import socketserver
import threading
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
WEB_ROOT = ROOT / "web"
BRAND = WEB_ROOT / "assets" / "brand"
LIVE = "https://aira1346.github.io/pharos/"
RESULTS: list[tuple[str, bool, str]] = []

ASSETS = [
    "pharos-rune.png",
    "pharos-rune.webp",
    "pharos-rune-96.png",
    "pharos-rune-96.webp",
    "pharos-lighthouse.png",
    "pharos-lighthouse.webp",
    "favicon-16.png",
    "favicon-32.png",
    "favicon-48.png",
    "favicon.ico",
    "apple-touch-icon.png",
]


def expect(condition: bool, label: str, extra: str = "") -> None:
    RESULTS.append((label, bool(condition), str(extra)))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + ("" if condition else f"  ← {extra}"))


def edge_alpha_report(path: Path) -> tuple[float, float]:
    """(모서리 최대 알파, 테두리 2px 띠의 알파>16 비율)"""
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)[:, :, 3].astype(np.int16)
    corners = [a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]]
    band = np.concatenate([a[:2].ravel(), a[-2:].ravel(), a[:, :2].ravel(), a[:, -2:].ravel()])
    return float(max(corners)), float((band > 16).mean())


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        return


def serve(root: Path):
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def shot_array(page, clip: dict | None = None) -> np.ndarray:
    raw = page.screenshot(clip=clip) if clip else page.screenshot()
    return np.asarray(Image.open(io.BytesIO(raw)).convert("RGB")).astype(np.int16)


def top_corner_brightness(arr: np.ndarray, box: dict, patch: int = 4) -> int:
    """요소 박스의 '위쪽 두 모서리' 패치 최소 밝기.

    룬·등대 모두 모서리가 투명하므로 배경이 그대로 보여야 한다. 검은 사각 배경이 깔리면 여기가 어두워진다.
    (등대는 밑변 가로줄이 박스 아래 모서리까지 차 있어 아래쪽은 그린다.)
    """
    x, y = int(round(box["x"])), int(round(box["y"]))
    w = int(round(box["w"]))
    x0, y0 = max(0, x + 1), max(0, y + 1)
    a = arr[y0:y0 + patch, x0:x0 + patch]
    b = arr[y0:y0 + patch, max(0, x + w - 1 - patch):x + w - 1]
    return int(min(a.mean() if a.size else 999, b.mean() if b.size else 999))


def probe(page, selector: str) -> dict | None:
    return page.evaluate(
        """(sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        const img = el.tagName === 'IMG' ? el : el.querySelector('img');
        return {
          x: r.x + window.scrollX, y: r.y + window.scrollY, w: r.width, h: r.height,
          complete: img ? img.complete : null,
          natural: img ? [img.naturalWidth, img.naturalHeight] : null,
          src: img ? img.currentSrc : null,
          alt: img ? img.getAttribute('alt') : null,
        };
      }""",
        selector,
    )


def corners_min_brightness(arr: np.ndarray, box: dict, pad: int = 2) -> int:
    """요소 박스 모서리 바로 안쪽/바깥 픽셀의 최소 밝기 — 검은 사각 배경이 있으면 0 에 가깝다."""
    x, y, w, h = int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])
    pts = [(x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1),
           (x + w // 2, y), (x + w // 2, y + h - 1), (x, y + h // 2), (x + w - 1, y + h // 2)]
    vals = []
    for px, py in pts:
        for dx, dy in ((0, 0), (-pad, -pad), (pad, pad)):
            cx, cy = px + dx, py + dy
            if 0 <= cy < arr.shape[0] and 0 <= cx < arr.shape[1]:
                vals.append(int(arr[cy, cx].mean()))
    return min(vals)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--shots-dir", default="")
    parser.add_argument("--shot-prefix", default="")
    parser.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    args = parser.parse_args()

    # 1) 로컬 파일 자체 검사
    for name in ASSETS:
        path = BRAND / name
        expect(path.exists(), f"에셋 존재: assets/brand/{name}", str(path))
    for name in ("pharos-rune.png", "pharos-lighthouse.png"):
        path = BRAND / name
        if path.exists():
            corner, band = edge_alpha_report(path)
            expect(corner == 0, f"{name}: 모서리 알파 0 (검은 사각 모서리 없음)", str(corner))
            expect(band < 0.26, f"{name}: 테두리 띠 불투명 비율 낮음(타이트 트리밍+투명 여백)", f"{band:.3f}")
    expect((BRAND / "source" / "pharos-gem-pure-v2-sym.png").exists(), "원본 사본 보관: 룬 소스", "")
    expect((BRAND / "source" / "pharos-symbol-lighthouse.png").exists(), "원본 사본 보관: 등대 소스", "")
    if (BRAND / "pharos-rune.png").exists():
        size = Image.open(BRAND / "pharos-rune.png").size
        expect(size == (512, 512), "pharos-rune.png = 512×512", str(size))
    if (BRAND / "favicon-32.png").exists():
        expect(Image.open(BRAND / "favicon-32.png").size == (32, 32), "favicon-32.png = 32×32", "")

    httpd = None
    if args.live:
        base = LIVE
    else:
        httpd, base = serve(WEB_ROOT)
    prefix = args.shot_prefix or ("live-v22-brand" if args.live else "local-v22-brand")
    shots = Path(args.shots_dir) if args.shots_dir else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    # 2) 브라우저 검사
    r = expect
    try:
        with sync_playwright() as p:
            launch = {"executable_path": args.chrome} if args.chrome else {}
            browser = p.chromium.launch(**launch)

            def open_page(viewport, lang="ko"):
                ctx = browser.new_context(
                    viewport={"width": viewport[0], "height": viewport[1]},
                    locale="ko-KR" if lang == "ko" else "en-US",
                )
                page = ctx.new_page()
                errs: list[str] = []
                bad: list[str] = []
                page.on("pageerror", lambda exc: errs.append(str(exc)))
                page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                page.on("response", lambda res: bad.append(f"{res.status} {res.url}") if res.status >= 400 else None)
                return ctx, page, errs, bad

            # 에셋 HTTP 상태
            ctx, page, errs, bad = open_page((1280, 800))
            page.goto(base + "?lang=ko", wait_until="networkidle")
            page.wait_for_timeout(500)
            for name in ASSETS:
                status = page.evaluate(
                    "async (u) => { const res = await fetch(u, {cache: 'no-store'}); return [res.status, res.headers.get('content-type')]; }",
                    f"./assets/brand/{name}",
                )
                r(status[0] == 200, f"HTTP 200: assets/brand/{name}", str(status))

            # 헤더 룬
            mark = probe(page, ".brand .mark")
            r(mark is not None and mark["complete"] and mark["natural"][0] > 0,
              "헤더: 브랜드 마크가 룬 이미지로 로드됨", str(mark))
            r(mark is not None and "pharos-rune" in (mark["src"] or ""), "헤더: 룬 에셋 경로", str(mark and mark["src"]))
            r(mark is not None and 44 <= mark["w"] <= 48 and 44 <= mark["h"] <= 48,
              "헤더: 데스크톱 룬 46px", str(mark and [mark["w"], mark["h"]]))
            r(mark is not None and (mark["alt"] or "") == "", "헤더: 마크 alt='' (장식 요소)", str(mark and mark["alt"]))
            r(page.query_selector(".brand svg.mark") is None, "헤더: 기존 SVG 마크 제거", "")

            # 파비콘
            icons = page.eval_on_selector_all(
                "link[rel='icon'], link[rel='apple-touch-icon']", "els => els.map(e => e.getAttribute('href'))"
            )
            r(any("brand/favicon-32.png" in (h or "") for h in icons), "파비콘: brand/favicon-32.png 연결", str(icons))
            r(any("brand/favicon.ico" in (h or "") for h in icons), "파비콘: brand/favicon.ico 연결", str(icons))
            r(not any((h or "").startswith("data:image/svg") for h in icons), "파비콘: 인라인 SVG 제거", str(icons))

            # Step 0 등대
            sym = probe(page, ".lh-symbol")
            r(sym is not None and sym["complete"] and sym["natural"][1] > 0, "Step 0: 등대 이미지 로드", str(sym))
            r(sym is not None and "pharos-lighthouse" in (sym["src"] or ""), "Step 0: 등대 에셋 경로", str(sym and sym["src"]))
            r(sym is not None and 126 <= sym["h"] <= 180,
              "Step 0: 등대 높이 126~180px(데스크톱)", str(sym and sym["h"]))
            r(sym is not None and abs((sym["x"] + sym["w"] / 2) - 640) <= 2,
              "Step 0: 등대 가로 중앙 정렬", str(sym and sym["x"] + sym["w"] / 2))
            cta_top = page.evaluate("() => document.querySelector('[data-lh-goto=\"pledge\"]').getBoundingClientRect().top")
            r(sym is not None and sym["y"] < cta_top, "Step 0: 등대는 뽑기 CTA 위에 있음",
              f"symbol {sym and sym['y']} < cta {cta_top:.0f}")
            r(page.inner_text("[data-lh-goto='pledge']").strip() == "목표 탐색", "Step 0: CTA 문구 정리(🚨 제거)",
              page.inner_text("[data-lh-goto='pledge']"))
            r("🚨" not in page.inner_text(".lh-landing"), "Step 0: 🚨 이모지 중복 없음", "")
            order = page.evaluate(
                """() => Array.from(document.querySelectorAll('.lh-landing > *')).map(e => e.className || e.tagName)"""
            )
            r(order and order[0] == "lh-symbol", "Step 0: 랜딩 첫 요소가 등대 심볼", str(order))
            r((page.query_selector(".lh-hero") is None), "Step 0: 구 히어로 블록 없음", "")

            # 다크 테마 — 검은 박스 비침(배경과 같은 어두운 톤이라 밝기 검사는 라이트에서)
            arr = shot_array(page)
            dark_corner = corners_min_brightness(arr, sym)
            r(dark_corner >= 0, "다크: 등대 모서리 픽셀 측정", str(dark_corner))
            if shots:
                page.screenshot(path=str(shots / f"{prefix}-desktop.png"))

            # 라이트 테마 — 이미지를 숨긴 컷과 비교해 모서리에 검은 사각 배경이 비치는지 본다
            page.evaluate("() => document.documentElement.setAttribute('data-theme','light')")
            page.wait_for_timeout(350)
            sym_l = probe(page, ".lh-symbol")
            mark_l = probe(page, ".brand .mark")
            page.evaluate("() => window.scrollTo(0, 0)")
            page.wait_for_timeout(150)
            sym_l = probe(page, ".lh-symbol")
            mark_l = probe(page, ".brand .mark")
            arr = shot_array(page)
            lh_corner = top_corner_brightness(arr, sym_l)
            mk_corner = top_corner_brightness(arr, mark_l, patch=3)
            r(lh_corner >= 190, "라이트: 등대 위 모서리에 사각 배경 비침 없음(밝기 ≥190)", str(lh_corner))
            r(mk_corner >= 190, "라이트: 헤더 룬 모서리에 네모 비침 없음(밝기 ≥190)", str(mk_corner))
            shadow = page.evaluate("() => getComputedStyle(document.querySelector('.lh-symbol')).filter")
            r("drop-shadow" in shadow, "라이트: 등대에 어두운 드롭섀도우(금색 라인 대비)", shadow[:80])
            if shots:
                page.screenshot(path=str(shots / f"{prefix}-light.png"))
            r(not errs, "콘솔/페이지 오류 0", "; ".join(errs[:3]))
            r(not bad, "HTTP 4xx/5xx 0", "; ".join(bad[:3]))
            ctx.close()

            # 모바일 390×844 (다크)
            ctx, page, errs, bad = open_page((390, 844))
            page.goto(base + "?lang=ko", wait_until="networkidle")
            page.wait_for_timeout(500)
            sym = probe(page, ".lh-symbol")
            mark = probe(page, ".brand .mark")
            r(sym is not None and 104 <= sym["h"] <= 140, "모바일: 등대 높이 104~140px", str(sym and sym["h"]))
            r(mark is not None and 32 <= mark["w"] <= 36, "모바일: 헤더 룬 34px", str(mark and mark["w"]))
            r(mark is not None and mark["complete"], "모바일: 헤더 룬 로드", "")
            overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            r(overflow == 0, "모바일: 가로 넘침 0", str(overflow))
            btn = page.evaluate(
                """() => { const b = document.querySelector('[data-lh-goto="pledge"]').getBoundingClientRect();
                     return [b.left, b.right, innerWidth]; }"""
            )
            r(btn[0] >= 0 and btn[1] <= btn[2] + 1, "모바일: CTA 가 화면 안", str(btn))
            if shots:
                page.screenshot(path=str(shots / f"{prefix}-mobile.png"))
            r(not errs, "모바일: 콘솔/페이지 오류 0", "; ".join(errs[:3]))
            r(not bad, "모바일: HTTP 4xx/5xx 0", "; ".join(bad[:3]))
            ctx.close()

            # 영어 모드
            ctx, page, errs, bad = open_page((1280, 800), lang="en")
            page.goto(base + "?lang=en", wait_until="networkidle")
            page.wait_for_timeout(500)
            sym = probe(page, ".lh-symbol")
            en_cta = page.inner_text("[data-lh-goto='pledge']").strip()
            r(sym is not None and sym["complete"] and "pharos-lighthouse" in (sym["src"] or ""),
              "EN: 등대 이미지 정상", str(sym and sym["src"]))
            r(en_cta == "Find a goal", "EN: CTA 'Find a goal'", en_cta)
            r("LIGHTHOUSE" in page.inner_text(".lh-landing-kicker"), "EN: 키커 LIGHTHOUSE", "")
            overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            r(overflow == 0, "EN: 가로 넘침 0", str(overflow))
            if shots:
                page.screenshot(path=str(shots / f"{prefix}-en.png"))
            r(not errs, "EN: 콘솔/페이지 오류 0", "; ".join(errs[:3]))
            r(not bad, "EN: HTTP 4xx/5xx 0", "; ".join(bad[:3]))
            ctx.close()

            # Step 1~4 회귀(문구만 확인 — 상세 흐름은 smoke_v21 이 본다)
            ctx, page, errs, bad = open_page((1280, 800))
            page.goto(base + "?lang=ko", wait_until="networkidle")
            page.wait_for_timeout(400)
            page.click("[data-lh-goto='pledge']")
            page.wait_for_timeout(350)
            r(page.query_selector(".lh--pledge") is not None, "회귀: 목표 탐색 → 항해 서약", "")
            page.click(".lh-pledge-check")
            page.wait_for_timeout(150)
            page.click("[data-lh-oath]")
            page.wait_for_timeout(400)
            r(page.query_selector(".lh--category") is not None, "회귀: 서약 뒤 분야 선택 진입", "")
            page.click("[data-lh-cat='game']")
            page.wait_for_timeout(400)
            r(page.query_selector(".lh--step1") is not None, "회귀: 분야 선택 뒤 Step 1 진입", "")
            ctx.close()
            browser.close()
    finally:
        if httpd:
            httpd.shutdown()

    failed = [x for x in RESULTS if not x[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} PASS")
    for label, _, extra in failed:
        print(f"  FAIL {label}  ← {extra}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
