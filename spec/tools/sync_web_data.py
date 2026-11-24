#!/usr/bin/env python3
"""정적 배포용 사본 동기화 — 단일 소스 원칙 유지.

원본은 `projects/pharos/data/items.json` 과 `projects/pharos/schema/item.schema.json` 이다.
웹 앱은 `projects/pharos/web/` 폴더 하나만 GitHub Pages 루트(또는 docs/)에 올려도 동작해야 하므로,
같은 파일을 `web/data/`, `web/schema/` 에 바이트 단위로 복사해 둔다.
이 스크립트는 복사만 하고 내용을 고치지 않는다(고치면 validate.py 가 원본과의 불일치를 잡는다).

사용:
  python3 projects/pharos/scripts/sync_web_data.py          # 원본 → 웹 사본 복사
  python3 projects/pharos/scripts/sync_web_data.py --check  # 사본이 최신인지만 확인(다르면 종료 코드 1)
"""

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # projects/pharos
PAIRS = [
    (ROOT / "data" / "items.json", ROOT / "web" / "data" / "items.json"),
    (ROOT / "schema" / "item.schema.json", ROOT / "web" / "schema" / "item.schema.json"),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main():
    parser = argparse.ArgumentParser(description="파로스 웹 배포 사본 동기화")
    parser.add_argument("--check", action="store_true", help="복사하지 않고 최신 여부만 확인")
    args = parser.parse_args()

    stale = 0
    for src, dst in PAIRS:
        if not src.exists():
            print(f"× 원본 없음: {src}")
            return 1
        same = digest(src) == digest(dst)
        rel = src.relative_to(ROOT.parent.parent)
        if same:
            print(f"= {rel} → {dst.relative_to(ROOT.parent.parent)} (동일)")
            continue
        stale += 1
        if args.check:
            print(f"≠ {rel} → {dst.relative_to(ROOT.parent.parent)} (사본이 오래됨)")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"→ {rel} → {dst.relative_to(ROOT.parent.parent)} (복사)")

    if args.check and stale:
        print(f"\n결과: FAIL — 사본 {stale}개가 원본과 다릅니다. "
              "python3 projects/pharos/scripts/sync_web_data.py 로 동기화하세요.")
        return 1
    print("\n결과: PASS — web/ 사본이 원본과 일치합니다." if args.check
          else "\n결과: PASS — 웹 배포 사본을 원본과 맞췄습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
