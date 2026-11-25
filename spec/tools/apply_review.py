#!/usr/bin/env python3
"""파로스 수집 초안 + 사람 검토 → 최종 데이터 파일 (apply_review.py)

auto_collect.py 가 만든 초안(`drafts/{id}.draft.json`)에 리뷰어가 채운 30%를 담은
오버레이(`drafts/reviewed/{id}.json`)를 병합해 `data/{domain}/{arena}.json` 에 넣는다.
병합 뒤에는 하드 필터·축 신호·티어 판정·대표 판정을 **계산 규칙으로 다시 맞추므로**,
사람이 판정 문장과 점수만 정확히 주면 validate.py 와 어긋나지 않는다.

오버레이 형식(초안에서 바꾸거나 더할 값만 적는다)
  {
    "id": "celeste",
    "one_liner": "...",
    "flags": {"stale_over_12m": {"value": "yes", ...}},
    "tiers": [{"tier_id": "steam", "limits": ["..."], "one_liner": "..."}],
    "axes": {"objective": {"score": 62, "summary": "...", ...}},
    "verdict": {"one_liner": "...", "reasons": ["..."]},
    "sources": [{"id": "official-celeste", ...}]
  }
  · 리스트 안의 dict 는 `tier_id`·`id` 같은 키가 같으면 항목별 병합, 없으면 통째로 교체한다.

사용
  python3 projects/pharos/scripts/apply_review.py --spec drafts/spec-2026-11-25.json \
      --reviews drafts/reviewed --write
  python3 projects/pharos/scripts/apply_review.py --spec ... --reviews ... --check   # 쓰지 않고 검사만
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "schema"))
sys.path.insert(0, str(ROOT / "scripts"))

import validate as vlib  # noqa: E402


def deep_merge(base, overlay):
    """dict 는 재귀 병합, dict 리스트는 tier_id/id 로 항목 병합, 그 외 리스트는 교체."""
    if isinstance(base, dict) and isinstance(overlay, dict):
        out = dict(base)
        for key, value in overlay.items():
            out[key] = deep_merge(base[key], value) if key in base else value
        return out
    if isinstance(base, list) and isinstance(overlay, list):
        key_name = None
        if all(isinstance(x, dict) for x in base + overlay) and overlay:
            for candidate in ("tier_id", "id"):
                if all(candidate in x for x in base + overlay):
                    key_name = candidate
                    break
        if key_name is None:
            return overlay
        merged = [dict(x) for x in base]
        index = {x[key_name]: pos for pos, x in enumerate(merged)}
        for item in overlay:
            pos = index.get(item[key_name])
            if pos is None:
                merged.append(dict(item))
                index[item[key_name]] = len(merged) - 1
            else:
                merged[pos] = deep_merge(merged[pos], item)
        return merged
    return overlay


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="수집 초안 + 검토 오버레이 → 파로스 데이터")
    parser.add_argument("--spec", required=True, help="auto_collect.py 와 같은 스펙 파일")
    parser.add_argument("--drafts", default=str(ROOT / "drafts"), help="초안 폴더")
    parser.add_argument("--reviews", required=True, help="검토 오버레이 폴더(drafts/reviewed)")
    parser.add_argument("--check", action="store_true", help="파일을 쓰지 않고 병합·검증만")
    parser.add_argument("--write", action="store_true", help="data/{domain}/{arena}.json 에 반영")
    args = parser.parse_args()

    spec_data = load(Path(args.spec))
    specs = spec_data.get("items") if isinstance(spec_data, dict) else spec_data
    drafts_dir, reviews_dir = Path(args.drafts), Path(args.reviews)
    schema = load(ROOT / "schema" / "item.schema.json")
    catalog = load(ROOT / "data" / "catalog.json")
    ctx = {
        "arenas": {a["id"]: a for a in catalog["arenas"]},
        "domains": {d["id"] for d in catalog["domains"]},
        "categories": {c["id"] for c in catalog["categories"]},
    }
    from jsonschema import Draft202012Validator, FormatChecker
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    # 비교군별로 모은다.
    by_arena: dict[str, list[dict]] = {}
    failures = 0
    print("=" * 78)
    print(f"Pharos apply_review — 항목 {len(specs)}건" + (" (--check)" if args.check else ""))
    print("=" * 78)

    for spec in specs:
        item_id = spec["id"]
        draft_path = drafts_dir / f"{item_id}.draft.json"
        if not draft_path.exists():
            print(f"  × {item_id}: 초안 없음 ({draft_path})")
            failures += 1
            continue
        item = load(draft_path)
        overlay_path = reviews_dir / f"{item_id}.json"
        if overlay_path.exists():
            overlay = load(overlay_path)
            # 리뷰어가 자동 수집 출처 중 쓸모없는 것을 뺄 수 있게 한다(예: 메일 앱이 아닌 릴리스).
            drop = overlay.pop("_drop_sources", []) if isinstance(overlay, dict) else []
            item = deep_merge(item, overlay)
            if drop:
                item["sources"] = [s for s in item["sources"] if s["id"] not in drop]
            source = "초안+검토"
        else:
            source = "초안만(검토 없음)"

        item = collect_finalize(item)
        problems = [f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}"
                    for e in validator.iter_errors(item)]
        arenas = item.get("arenas") or []
        for arena in arenas:
            if arena not in ctx["arenas"]:
                problems.append(f"catalog.json 에 없는 비교군 {arena}")
                continue
            errs, warns = vlib.semantic_errors(item, ctx, arena)
            problems.extend(errs)
        todo = count_todos(item)
        status = "PASS" if not problems else "FAIL"
        print(f"  ▸ {item_id:<24} {source:<14} 스키마·의미 {status} · TODO 문자열 {todo}")
        for problem in problems[:8]:
            print(f"      × {problem}")
        if problems:
            failures += 1
        for arena in arenas:
            by_arena.setdefault(arena, []).append(item)

    # 비교군 파일 쓰기(스펙 순서 유지)
    written = []
    for arena, items in by_arena.items():
        meta = ctx["arenas"].get(arena)
        if not meta:
            continue
        target = ROOT / "data" / meta["data_file"]
        order = [spec["id"] for spec in specs if arena in (spec.get("arenas") or [spec.get("arena")])]
        items.sort(key=lambda it: order.index(it["id"]) if it["id"] in order else 999)
        existing = load(target) if target.exists() else []
        merged_ids = {it["id"] for it in items}
        kept = [it for it in existing if it["id"] not in merged_ids]
        payload = kept + items
        print(f"\n  ▸ {arena}: {len(items)}건 병합 (기존 {len(kept)}건 유지) → {target.relative_to(ROOT.parent.parent)}")
        if args.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            written.append(str(target.relative_to(ROOT.parent.parent)))

    if written:
        print("\n  기록 완료: " + ", ".join(written))
        print("  다음: python3 projects/pharos/scripts/sync_web_data.py")
    elif not args.check:
        print("\n  (파일을 쓰지 않았다 — 반영하려면 --write)")

    print("=" * 78)
    print(f"결과: {'PASS' if not failures else f'FAIL — {failures}건 문제'}")
    print("=" * 78)
    return 0 if not failures else 1


def count_todos(item: dict) -> str:
    found = total = 0

    def walk(node):
        nonlocal found, total
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            total += 1
            if node.startswith("TODO(리뷰):"):
                found += 1

    walk(item)
    return f"{found}/{total}"


def collect_finalize(item: dict) -> dict:
    """auto_collect 의 finalize_item 을 그대로 쓴다(판정 규칙 단일 소스)."""
    from auto_collect import finalize_item  # 지역 import — 스크립트 단독 실행 대비
    return finalize_item(item)


if __name__ == "__main__":
    sys.exit(main())
