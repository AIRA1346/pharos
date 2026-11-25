#!/usr/bin/env python3
"""정적 배포용 사본 동기화 + 경량 인덱스 생성 — 단일 소스 원칙 유지.

원본은 `projects/pharos/data/catalog.json`, `data/{domain}/{arena}.json`,
`schema/item.schema.json` 이다. 웹 앱은 `projects/pharos/web/` 폴더 하나만
GitHub Pages 루트에 올려도 동작해야 하므로, 같은 파일을 `web/data/`, `web/schema/` 에
바이트 단위로 복사한다. 이 스크립트는 데이터 내용을 고치지 않는다(고치면 validate.py 가 잡는다).

하는 일
  1) 카탈로그에 정의된 비교군 파일을 모두 읽어 `data/search-index.json` 을 다시 만든다
     (통합 검색·홈 리포트용 경량 인덱스 — 손으로 고치지 않는다).
  2) 원본 → 웹 사본 복사 (스키마·카탈로그·검색 인덱스·비교군 데이터·영문 번들 en.json).
     구 통합 파일 `web/data/items.json` 이 남아 있으면 지운다.
  3) `schema/validate.py` 전체 검증을 실행해 PASS 를 확인한다(사본 해시까지 검사).

사용:
  python3 projects/pharos/scripts/sync_web_data.py          # 인덱스 생성 + 사본 동기화 + 검증
  python3 projects/pharos/scripts/sync_web_data.py --check  # 아무것도 쓰지 않고 최신 여부만 확인
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # projects/pharos
SCHEMA_DIR = ROOT / "schema"
sys.path.insert(0, str(SCHEMA_DIR))

import validate  # noqa: E402  (schema/validate.py — 빌더와 검증기를 한 곳에 둔다)

DATA_DIR = ROOT / "data"
CATALOG_PATH = DATA_DIR / "catalog.json"
INDEX_PATH = DATA_DIR / "search-index.json"
SCHEMA_PATH = SCHEMA_DIR / "item.schema.json"
WEB_DIR = ROOT / "web"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def source_pairs(catalog):
    """(원본, 웹 사본) 경로 목록."""
    pairs = [
        (SCHEMA_PATH, WEB_DIR / "schema" / "item.schema.json"),
        (CATALOG_PATH, WEB_DIR / "data" / "catalog.json"),
        (INDEX_PATH, WEB_DIR / "data" / "search-index.json"),
    ]
    en_path = DATA_DIR / "en.json"
    if en_path.exists():
        pairs.append((en_path, WEB_DIR / "data" / "en.json"))
    for arena in catalog.get("arenas") or []:
        src = DATA_DIR / arena["data_file"]
        pairs.append((src, WEB_DIR / "data" / arena["data_file"]))
    return pairs


def rebuild_index(catalog, contract):
    """분할 데이터 → data/search-index.json. 바뀐 내용이 없으면 파일을 건드리지 않는다."""
    items_by_arena = validate.load_items_by_arena(catalog, DATA_DIR)
    expected = validate.build_search_index(catalog, items_by_arena, contract)
    text = json.dumps(expected, ensure_ascii=False, indent=2) + "\n"
    current = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else None
    if current == text:
        print(f"= {INDEX_PATH.relative_to(ROOT.parent.parent)} (이미 최신)")
        return expected, False
    INDEX_PATH.write_text(text, encoding="utf-8")
    print(f"→ {INDEX_PATH.relative_to(ROOT.parent.parent)} (재생성 · "
          f"{expected['counts']['items']}건 · {len(expected['gap_report']['items'])} gap)")
    return expected, True


def main():
    parser = argparse.ArgumentParser(description="파로스 웹 배포 사본 동기화")
    parser.add_argument("--check", action="store_true", help="쓰지 않고 최신 여부만 확인")
    args = parser.parse_args()

    catalog = validate.load(CATALOG_PATH)
    schema = validate.load(SCHEMA_PATH)
    contract = (schema.get("x-pharos") or {}).get("client") or {}

    print("=" * 78)
    print("Pharos 웹 사본 동기화" + (" (--check)" if args.check else ""))
    print("=" * 78)

    if args.check:
        items_by_arena = validate.load_items_by_arena(catalog, DATA_DIR)
        expected = validate.build_search_index(catalog, items_by_arena, contract)
        stale = 0
        current = validate.load(INDEX_PATH) if INDEX_PATH.exists() else None
        if current != expected:
            stale += 1
            print(f"≠ {INDEX_PATH.relative_to(ROOT.parent.parent)} (분할 데이터와 다름)")
    else:
        expected, _changed = rebuild_index(catalog, contract)
        stale = 0

    for src, dst in source_pairs(catalog):
        same = digest(src) == digest(dst)
        rel = dst.relative_to(ROOT.parent.parent)
        if same:
            print(f"= {src.relative_to(ROOT.parent.parent)} → {rel} (동일)")
            continue
        stale += 1
        if args.check:
            print(f"≠ {src.relative_to(ROOT.parent.parent)} → {rel} (사본이 오래됨)")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"→ {src.relative_to(ROOT.parent.parent)} → {rel} (복사)")

    legacy = WEB_DIR / "data" / "items.json"
    if legacy.exists() and not args.check:
        legacy.unlink()
        print(f"× {legacy.relative_to(ROOT.parent.parent)} (구 통합 사본 제거 — 비교군 분할 파일로 대체)")

    if args.check:
        if stale:
            print(f"\n결과: FAIL — 사본/인덱스 {stale}개가 원본과 다릅니다. "
                  "python3 projects/pharos/scripts/sync_web_data.py 로 동기화하세요.")
            return 1
        print("\n결과: PASS — 인덱스·웹 사본이 원본과 일치합니다.")
        return 0

    print("\n검증(validate.py) 실행")
    return validate.main()


if __name__ == "__main__":
    sys.exit(main())
