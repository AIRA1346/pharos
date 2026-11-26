#!/usr/bin/env python3
"""6차 배치 보정 — Steam 개발사 공지가 '시즌' 표기라 자동 수집이 놓친 실제 업데이트를 반영한다.

`bulk_ingest.py` 의 UPDATE_RE 는 patch·hotfix·update·changelog·version 표기만 업데이트로 본다.
Torchlight: Infinite 는 2026-10-16 "Tartarus" SEASON 공지를 냈는데도 제목에 'patch' 가 없어
마지막 업데이트가 2024-04-17 로 남았고, 그 결과 라이브 서비스 게임이 '12개월 공백 → 거름'이 됐다.
공지 자체(Steam 개발사 공지, 등급 A)를 근거로 사실을 바로잡는다.

python3 projects/pharos/drafts/bulk6-2026-11-26/fix_recent_announcement.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "schema"))

import bulk_ingest as bi  # noqa: E402

EN_PATH = ROOT / "data" / "en.json"

# 근거: Steam 개발사 공지(ISteamNews, 2026-11-26 조회) — feedname=steam_community_announcements
FIXES = {
    "torchlight-infinite": {
        "file": ROOT / "data" / "game" / "mobile-cross-mmorpg.json",
        "date": "2026-10-16",
        "title": 'Torchlight: Infinite - "Tartarus" SEASON',
        "url": "https://store.steampowered.com/news/app/1974050",
        "note_ko": "마지막 Steam 개발사 공지 2026-10-16 \"Tartarus\" SEASON(시즌 업데이트) — 12개월 이내 활동.",
        "note_en": 'Latest Steam developer announcement 2026-10-16, "Tartarus" SEASON update — active within the last 12 months.',
        "flag_ko": "2026-10-16 시즌 업데이트 공지가 있어 12개월 공백이 아니다(Steam 개발사 공지, 등급 A).",
        "flag_en": "A season update was announced on 2026-10-16, so the 12-month gap does not apply (Steam developer announcement, grade A).",
    },
}


def main() -> int:
    en = json.loads(EN_PATH.read_text(encoding="utf-8"))
    for iid, fix in FIXES.items():
        items = json.loads(fix["file"].read_text(encoding="utf-8"))
        item = next(x for x in items if x["id"] == iid)
        src_id = f"steam-news-{iid}-recent"
        item["sources"].append({
            "id": src_id,
            "title": f"Steam — {item['name']} 개발사 공지",
            "url": fix["url"],
            "type": "official",
            "grade": "A",
            "accessed_at": bi.TODAY,
            "note": f"{fix['date']} 공지 \"{fix['title']}\" — 시즌 업데이트.",
        })
        prof = item["update_profile"]
        prof["latest_update"] = fix["date"]
        prof["latest_update_platform"] = "steam"
        prof["cadence"] = "active"
        prof["entries"] = [{
            "date": fix["date"], "type": "content", "platform": "steam",
            "promise_status": "not_applicable", "evidence_grade": "A",
            "source_ids": [src_id],
            "note": f"시즌 업데이트 공지 \"{fix['title']}\".",
        }] + prof["entries"]
        prof["assessment"] = fix["note_ko"]
        item["maintenance_status"] = "active"
        item["maintenance_note"] = fix["note_ko"]
        item["flags"]["stale_over_12m"] = {
            "value": "no", "evidence_grade": "A", "source_ids": [src_id], "note": fix["flag_ko"],
        }

        overlay = en["items"][iid]
        overlay.setdefault("sources", []).append({
            "id": src_id,
            "title": f"Steam — {item['name']} developer announcements",
            "note": f"Announcement on {fix['date']}: \"{fix['title']}\" — a seasonal update.",
        })
        overlay["update_profile"] = {
            "entries": [{
                "date": fix["date"], "type": "content", "platform": "steam",
                "promise_status": "not_applicable", "evidence_grade": "A",
                "source_ids": [src_id],
                "note": f"Season update announcement \"{fix['title']}\".",
            }] + (overlay.get("update_profile") or {}).get("entries", []),
            "assessment": fix["note_en"],
        }
        overlay["maintenance_note"] = fix["note_en"]
        overlay.setdefault("flags", {}).setdefault("stale_over_12m", {})["note"] = fix["flag_en"]

        bi.finalize(item, overlay)
        fix["file"].write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"  ✓ {iid}: {item['maintenance_status']} · {item['verdict']['overall']} · "
              f"{item['verdict']['one_liner'][:90]}")
    EN_PATH.write_text(json.dumps(en, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
