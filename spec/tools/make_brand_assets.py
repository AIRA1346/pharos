#!/usr/bin/env python3
"""파로스 브랜드 심볼 v22 — 룬(사파이어 나침반) · 등대(골드 모노라인) 에셋 생성.

원본(승인본)은 절대 덮어쓰지 않는다. downloads/ 의 두 PNG 를 읽어
  · 순수 검정(룬) / 딥 네이비(등대) 배경을 투명 알파로 분리하고
  · 가장자리 프린징이 남지 않도록 알파를 부드럽게 페더링한 뒤
  · 여백을 타이트하게 트리밍해 정사각(룬)·원본 비율(등대) 에셋으로 저장한다.

출력
  projects/pharos/web/assets/brand/pharos-rune.png        512×512 (알파)
  projects/pharos/web/assets/brand/pharos-rune.webp       512×512 (알파)
  projects/pharos/web/assets/brand/pharos-rune-96.png   96×96 (헤더 마크 2x)
  projects/pharos/web/assets/brand/pharos-rune-96.webp
  projects/pharos/web/assets/brand/pharos-lighthouse.png  높이 560 (알파)
  projects/pharos/web/assets/brand/pharos-lighthouse.webp
  projects/pharos/web/assets/brand/pharos-lighthouse-1024.png
  projects/pharos/web/assets/brand/favicon-32.png · favicon-48.png · favicon-16.png · favicon.ico
  projects/pharos/web/assets/brand/apple-touch-icon.png   (180×180, 다크 배경 위 룬)
  projects/pharos/assets/brand/...                        같은 파일의 로컬 사본(원본 포함)

사용
  python3 projects/pharos/scripts/make_brand_assets.py
  python3 projects/pharos/scripts/make_brand_assets.py --preview   # 검증용 합성 미리보기까지
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
WORKSPACE = ROOT.parents[1]
SRC_RUNE = WORKSPACE / "downloads" / "pharos-gem-pure-v2-sym.png"
SRC_LH = WORKSPACE / "downloads" / "pharos-symbol-lighthouse.png"
OUT = ROOT / "web" / "assets" / "brand"
LOCAL = ROOT / "assets" / "brand"
PREVIEW = ROOT / "live" / "brand-preview"


def smoothstep(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def key_black(im: Image.Image, lo: float = 3.0, hi: float = 17.0) -> Image.Image:
    """검정 배경 → 알파. 알파로 나눠 색을 복원(un-premultiply)해 검은 테두리가 남지 않게 한다."""
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    mx = rgb.max(axis=2)
    alpha = smoothstep(mx, lo, hi)
    # 아주 옅은 배경 잡음은 완전 투명으로
    alpha[mx <= lo] = 0.0
    a = np.repeat(alpha[:, :, None], 3, axis=2)
    safe = np.maximum(a, 1e-4)
    fg = np.clip(rgb / safe, 0, 255)
    # 알파가 낮은 곳의 색은 이웃에서 빌려온다(가장자리 검은 띠 방지): 밝은 쪽으로 1px 블러
    fg_img = Image.fromarray(fg.astype(np.uint8), "RGB").filter(ImageFilter.GaussianBlur(1.2))
    fg_np = np.asarray(fg_img).astype(np.float32)
    edge = (alpha < 0.85)[:, :, None]
    fg = np.where(edge, np.maximum(fg, fg_np), fg)
    out = np.dstack([np.clip(fg, 0, 255), alpha * 255.0])
    return Image.fromarray(out.round().astype(np.uint8), "RGBA")


def key_solid(im: Image.Image, bg: tuple[int, int, int], lo: float = 7.0, hi: float = 26.0) -> Image.Image:
    """단색 배경 → 알파. 경계 픽셀은 (C - (1-a)bg)/a 로 복원해 배경색 테두리를 없앤다."""
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    bgv = np.array(bg, dtype=np.float32)
    dist = np.abs(rgb - bgv).max(axis=2)
    alpha = smoothstep(dist, lo, hi)
    alpha[dist <= lo] = 0.0
    a = np.repeat(alpha[:, :, None], 3, axis=2)
    safe = np.maximum(a, 1e-4)
    fg = np.clip((rgb - (1.0 - a) * bgv) / safe, 0, 255)
    out = np.dstack([fg, alpha * 255.0])
    return Image.fromarray(out.round().astype(np.uint8), "RGBA")


def trim(im: Image.Image, pad_ratio: float = 0.02) -> Image.Image:
    alpha = np.asarray(im)[:, :, 3]
    ys, xs = np.where(alpha > 8)
    if not len(xs):
        raise SystemExit("빈 알파 — 키잉 임계값을 확인하세요")
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    side = max(x1 - x0, y1 - y0)
    pad = int(round(side * pad_ratio))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = side / 2 + pad
    box = (
        max(0, int(round(cx - half))), max(0, int(round(cy - half))),
        min(im.width, int(round(cx + half))), min(im.height, int(round(cy + half))),
    )
    return im.crop(box)


def square(im: Image.Image, size: int, pad_ratio: float = 0.02) -> Image.Image:
    """타이트 트리밍 → 정사각 캔버스 중앙 정렬 → 리사이즈(알파 프리멀티플라이로 헤일로 방지)."""
    alpha = np.asarray(im)[:, :, 3]
    ys, xs = np.where(alpha > 8)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    side = max(x1 - x0, y1 - y0)
    pad = int(round(side * pad_ratio))
    canvas_side = side + pad * 2
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    crop = im.crop((x0, y0, x1, y1))
    canvas.paste(crop, ((canvas_side - crop.width) // 2, (canvas_side - crop.height) // 2))
    return premultiplied_resize(canvas, (size, size))


def premultiplied_resize(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    arr = np.asarray(im).astype(np.float32) / 255.0
    a = arr[:, :, 3:4]
    pm = np.dstack([arr[:, :, :3] * a, a])
    chans = [Image.fromarray(pm[:, :, i], "F").resize(size, Image.LANCZOS) for i in range(4)]
    out = np.dstack([np.asarray(c) for c in chans])
    a2 = np.clip(out[:, :, 3:4], 0, 1)
    rgb = np.clip(out[:, :, :3] / np.maximum(a2, 1e-4), 0, 1)
    return Image.fromarray(np.dstack([rgb * 255, a2 * 255]).round().astype(np.uint8), "RGBA")


def tight(im: Image.Image, pad_ratio: float = 0.02) -> Image.Image:
    """비율 유지 타이트 트리밍(등대용)."""
    alpha = np.asarray(im)[:, :, 3]
    ys, xs = np.where(alpha > 8)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    pad = int(round(max(x1 - x0, y1 - y0) * pad_ratio))
    return im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))


def fit_height(im: Image.Image, height: int) -> Image.Image:
    w = round(im.width * height / im.height)
    return premultiplied_resize(im, (w, height))


def save(im: Image.Image, name: str, **kw) -> None:
    for base in (OUT, LOCAL):
        base.mkdir(parents=True, exist_ok=True)
        path = base / name
        if path.suffix == ".webp":
            im.save(path, "WEBP", quality=kw.get("quality", 92), method=6)
        else:
            im.save(path, **kw)
    print(f"  saved {name}  {im.size}")


def preview(assets: dict[str, Image.Image]) -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for theme, bg in (("dark", (7, 16, 28)), ("light", (243, 239, 229))):
        canvas = Image.new("RGBA", (1440, 760), bg + (255,))
        x = 20
        rune = assets["rune"]
        lh = assets["lighthouse"]
        for size in (512, 92, 46, 34, 32, 16):
            im = premultiplied_resize(rune, (size, size))
            canvas.alpha_composite(im, (x, 40))
            x += size + 24
        y = 120
        for h in (480, 160, 120, 60):
            im = fit_height(lh, h)
            canvas.alpha_composite(im, (20, y))
            y += h + 16
        canvas.save(PREVIEW / f"brand-{theme}.png")
    print(f"  previews → {PREVIEW}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True, exist_ok=True)
    # 1) 원본 사본 보관(덮어쓰기 금지 — 원본이 있으면 건너뛴다)
    for src, name in ((SRC_RUNE, "source/pharos-gem-pure-v2-sym.png"),
                      (SRC_LH, "source/pharos-symbol-lighthouse.png")):
        for base in (OUT, LOCAL):
            dst = base / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(src, dst)
        print(f"  archived {name}")

    # 2) 룬 — 검정 배경 → 알파, 타이트 정사각
    rune = key_black(Image.open(SRC_RUNE))
    rune_master = square(rune, 1024, pad_ratio=0.015)
    rune512 = premultiplied_resize(rune_master, (512, 512))
    save(rune_master, "pharos-rune-1024.png")
    save(rune512, "pharos-rune.png")
    save(rune512, "pharos-rune.webp")
    # 헤더 마크(46px·2x) — 작은 파일로 내려준다
    rune96 = premultiplied_resize(rune_master, (96, 96))
    save(rune96, "pharos-rune-96.png")
    save(rune96, "pharos-rune-96.webp")

    # 3) 등대 — 딥 네이비 배경 → 알파, 비율 유지 타이트 트리밍
    lh = key_solid(Image.open(SRC_LH), (12, 20, 31))
    lh_tight = tight(lh, 0.02)
    lh_master = fit_height(lh_tight, 1024)
    lh560 = fit_height(lh_tight, 560)
    save(lh_master, "pharos-lighthouse-1024.png")
    save(lh560, "pharos-lighthouse.png")
    save(lh560, "pharos-lighthouse.webp", quality=94)

    # 4) 파비콘 — 룬을 작은 크기에서도 읽히도록 살짝 대비 보정
    for size in (16, 32, 48, 180):
        icon = premultiplied_resize(rune_master, (size, size))
        if size <= 48:
            # 작은 크기는 다크 배경 위에 얹어 형태를 잡아준다(탭 바 파비콘 가독성)
            plate = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            disc = Image.new("RGBA", (size, size), (7, 14, 25, 255))
            mask = Image.new("L", (size, size), 0)
            from PIL import ImageDraw
            r = max(2, int(size * 0.18))
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=255)
            plate.paste(disc, (0, 0), mask)
            inner = premultiplied_resize(rune_master, (int(size * 0.88), int(size * 0.88)))
            plate.alpha_composite(inner, ((size - inner.width) // 2, (size - inner.height) // 2))
            icon = plate
        name = "apple-touch-icon.png" if size == 180 else f"favicon-{size}.png"
        save(icon, name)
    ico = Image.open(OUT / "favicon-48.png").convert("RGBA")
    ico.save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    shutil.copy2(OUT / "favicon.ico", LOCAL / "favicon.ico")
    print("  saved favicon.ico  [(16,16),(32,32),(48,48)]")

    if args.preview:
        preview({"rune": rune512, "lighthouse": lh560})


if __name__ == "__main__":
    main()
