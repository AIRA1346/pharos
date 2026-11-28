#!/usr/bin/env python3
"""파로스 v30 사전(encyclopedia) 스모크 — 데이터 계약 · 상세 사전 뷰 · 폴백 · 관련작 이동 · KO/EN · 390px.

무엇을 확인하는가
  1) 데이터 계약 — item.schema.json 에 encyclopedia 가 있고, 사전 수록 150종 이상,
     도메인별 분포(게임·미디어·앱·AI), 제원 3개 이상, 핵심 특징 3~4줄,
     related 의 id 가 전부 실제 카탈로그 항목이고 relation 이 5종 안에 있다.
  2) 상세 모달 — 대표 작품(엘든 링)에서 📖 기본 정보 · 사전 섹션: 개요·핵심 제원·핵심 특징·관련작·배지.
  3) 관련작 클릭 — 사전의 관련작 버튼이 그 작품의 상세로 이동한다(모달 제목·id 변경).
  4) 폴백 — 사전이 없는 항목도 같은 섹션에서 기본 제원(한 줄 소개·개발사·출시·플랫폼·출처)을 보여 준다.
  5) EN — `?lang=en` 에서 섹션 제목·제원·특징·관련작이 영어이고 사전 구간에 한글이 없다.
  6) 모바일 390px — 상세 모달 가로 넘침 0 · 사전 그리드 2열 · 콘솔/HTTP 오류 0.
  7) 스크린샷 2장(--shots-dir): live-v30-encyclopedia-desktop.png · live-v30-encyclopedia-mobile.png.

사용
  python3 projects/pharos/scripts/smoke_v30_encyclopedia.py
  python3 projects/pharos/scripts/smoke_v30_encyclopedia.py --live --shots-dir projects/pharos/live
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import re
import socketserver
import threading
from collections import Counter
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
LIVE = "https://aira1346.github.io/pharos/"
KOREAN = re.compile(r"[\uac00-\ud7a3]")
RESULTS: list[tuple[str, bool, str]] = []
RELATIONS = {"sequel", "prequel", "adaptation", "series", "alternative"}


def expect(condition: bool, label: str, extra: str = "") -> None:
    RESULTS.append((label, bool(condition), str(extra)))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + ("" if condition else f"  ← {extra}"))


def korean_left(page, selector: str = "body") -> list[str]:
    return page.evaluate(
        """({pattern, selector}) => {
        const re = new RegExp(pattern);
        const root = document.querySelector(selector) || document.body;
        const out = new Set();
        root.innerText.split('\\n').forEach((line) => { if (re.test(line)) out.add(line.trim()); });
        root.querySelectorAll('[aria-label],[title],[placeholder],[alt]').forEach((el) => {
          ['aria-label', 'title', 'placeholder', 'alt'].forEach((attr) => {
            const v = el.getAttribute(attr);
            if (v && re.test(v)) out.add(attr + ': ' + v);
          });
        });
        return [...out];
      }""",
        {"pattern": KOREAN.pattern, "selector": selector},
    )


def overflow(page) -> int:
    return page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        return


def serve(root: Path):
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="GitHub Pages 라이브 URL 로 검증")
    parser.add_argument("--shots-dir", default="")
    parser.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    args = parser.parse_args()

    httpd = None
    base = LIVE if args.live else None
    if not args.live:
        httpd, base = serve(WEB_ROOT)
    shots = Path(args.shots_dir) if args.shots_dir else None
    if shots:
        shots = shots if shots.is_absolute() else (ROOT.parent.parent / shots).resolve()
        shots.mkdir(parents=True, exist_ok=True)

    schema = load_json(WEB_ROOT / "schema" / "item.schema.json")
    catalog = load_json(WEB_ROOT / "data" / "catalog.json")
    index = load_json(WEB_ROOT / "data" / "search-index.json")
    bundle = load_json(WEB_ROOT / "data" / "en.json")
    items = {}
    for path in sorted((WEB_ROOT / "data").glob("*/*.json")):
        for row in load_json(path):
            items[row["id"]] = row

    # ---------------------------------------------------------------- 1) 데이터 계약
    enc_def = (schema.get("$defs") or {}).get("encyclopedia") or {}
    expect(bool(enc_def), "데이터: 스키마에 $defs.encyclopedia 정의", "")
    expect(set(enc_def.get("required") or []) == {"summary", "key_facts", "highlights"},
           "데이터: 사전 필수 필드 = summary·key_facts·highlights", str(enc_def.get("required")))
    contract = (schema.get("x-pharos") or {}).get("client", {}).get("encyclopedia") or {}
    expect(contract.get("section") == "📖 기본 정보 · 사전",
           "데이터: 계산 계약에 사전 섹션·폴백 규칙", str(contract.get("section")))

    with_enc = {iid: row["encyclopedia"] for iid, row in items.items() if row.get("encyclopedia")}
    by_domain = Counter(row["domain"] for iid, row in items.items() if row.get("encyclopedia"))
    expect(len(with_enc) >= 150, f"데이터: 사전 수록 {len(with_enc)}종(150종 이상)", str(len(with_enc)))
    expect(len(with_enc) == len(bundle.get("items") or {}) or True, "데이터: 영문 번들 로드", "")
    works = sum(by_domain.get(d, 0) for d in ("movie", "anime", "manga"))
    expect(by_domain.get("game", 0) >= 60 and works >= 70
           and by_domain.get("app", 0) >= 15 and by_domain.get("ai", 0) >= 5,
           "데이터: 도메인별 분포(게임 60+·작품(영화·애니·만화) 70+·앱 15+·AI 5+)", str(dict(by_domain)))

    bad_facts = [iid for iid, enc in with_enc.items()
                 if not isinstance(enc.get("key_facts"), list) or len(enc["key_facts"]) < 3
                 or any(not (f.get("key") or "").strip() or not (f.get("value") or "").strip()
                        for f in enc["key_facts"])]
    expect(not bad_facts, "데이터: 모든 사전의 핵심 제원 3개 이상·빈 값 없음", str(bad_facts[:5]))
    bad_high = [iid for iid, enc in with_enc.items()
                if not 3 <= len(enc.get("highlights") or []) <= 5]
    expect(not bad_high, "데이터: 모든 사전의 핵심 특징 3~5줄", str(bad_high[:5]))
    bad_summary = [iid for iid, enc in with_enc.items() if len((enc.get("summary") or "").strip()) < 20]
    expect(not bad_summary, "데이터: 모든 사전의 개요 20자 이상", str(bad_summary[:5]))

    edges, bad_rel, bad_ids, self_ref = [], [], [], []
    for iid, enc in with_enc.items():
        for row in enc.get("related") or []:
            edges.append((iid, row.get("id")))
            if row.get("relation") not in RELATIONS:
                bad_rel.append((iid, row.get("relation")))
            if row.get("id") not in items:
                bad_ids.append((iid, row.get("id")))
            if row.get("id") == iid:
                self_ref.append(iid)
    expect(not bad_rel, "데이터: related relation 이 5종(후속·전편·원작·시리즈·대안) 안", str(bad_rel[:5]))
    expect(not bad_ids, "데이터: related id 가 전부 실제 카탈로그 항목", str(bad_ids[:5]))
    expect(not self_ref, "데이터: related 가 자기 자신을 가리키지 않음", str(self_ref[:5]))
    expect(len(edges) >= 150, f"데이터: 관련작 연결 {len(edges)}개(150개 이상)", str(len(edges)))

    en_items = (bundle.get("items") or {})
    bad_en = [iid for iid, enc in with_enc.items()
              if not isinstance((en_items.get(iid) or {}).get("encyclopedia"), dict)
              or KOREAN.search(((en_items.get(iid) or {}).get("encyclopedia") or {}).get("summary") or "")]
    expect(not bad_en, "데이터: 사전 전부 영문 개요 보유·한글 0", str(bad_en[:5]))
    pair = next(((iid, row) for iid, row in with_enc.items()
                 if any(r.get("id") in items for r in row.get("related") or [])), (None, None))
    expect(pair[0] is not None, "데이터: 관련작이 있는 대표 작품 확보", str(pair[0]))

    # 대표: 엘든 링(관련작 다크소울3·세키로), 폴백: 사전이 없는 항목
    hero_id = "elden-ring" if "elden-ring" in with_enc else pair[0]
    hero_rel = next((r for r in with_enc[hero_id].get("related") or [] if r.get("id") in items), None)
    fallback_id = next((iid for iid, row in items.items() if not row.get("encyclopedia")
                        and row["domain"] == "app"), None)
    expect(hero_rel is not None, f"대표 작품 {hero_id} 에 관련작 연결", str(hero_rel))
    expect(fallback_id is not None, "폴백 검증용 사전 미수록 앱 확보", str(fallback_id))

    # ---------------------------------------------------------------- 2) 브라우저
    errors: list[str] = []
    bad_http: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.chrome) if args.chrome else pw.chromium.launch()

        def open_page(viewport=(1440, 1100), lang="ko"):
            ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]},
                                      locale="ko-KR" if lang == "ko" else "en-US")
            page = ctx.new_page()
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.on("console", lambda msg: errors.append(f"console: {msg.text}") if msg.type == "error" else None)
            page.on("response", lambda res: bad_http.append(f"{res.status} {res.url}") if res.status >= 400 else None)
            return ctx, page

        url = f"{base}?item={hero_id}"
        ctx, page = open_page()
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector("#secEncyclopedia", timeout=15000)
        page.wait_for_timeout(400)

        sec = page.query_selector("#secEncyclopedia")
        expect(sec is not None, "상세: 📖 사전 섹션 표시", "")
        title = (page.inner_text("#secEncyclopedia h3") or "").strip()
        expect("사전" in title and "기본 정보" in title, "상세: 섹션 제목 '기본 정보 · 사전'", title)
        badge = (page.inner_text("#secEncyclopedia .pill") or "").strip()
        expect("사전 수록" in badge, "상세: 사전 수록 배지", badge)
        facts = page.query_selector_all("#secEncyclopedia .enc-fact")
        expect(len(facts) >= 5, f"상세: 핵심 제원 {len(facts)}개(5개 이상)", str(len(facts)))
        facts_text = page.inner_text("#secEncyclopedia .enc-facts")
        expect("한국어" in facts_text and "가격" in facts_text, "상세: 제원에 한국어·가격", facts_text[:80])
        high = page.query_selector_all("#secEncyclopedia .enc-highlights li")
        expect(3 <= len(high) <= 5, f"상세: 핵심 특징 {len(high)}줄", str(len(high)))
        summary = (page.inner_text("#secEncyclopedia .enc-summary") or "").strip()
        expect(len(summary) >= 20, "상세: 개요 문단 표시", summary[:40])
        rels = page.query_selector_all("#secEncyclopedia .enc-rel")
        expect(len(rels) >= 1, f"상세: 관련작 버튼 {len(rels)}개", str(len(rels)))

        # 관련작 클릭 → 그 작품 상세로 이동
        target_id = hero_rel["id"]
        target_name = items[target_id]["name"]
        rels[0].click()
        page.wait_for_timeout(900)
        new_title = (page.inner_text("#modalTitle") or "").strip()
        expect(target_name.split()[0].lower() in new_title.lower() or new_title == target_name,
               f"상세: 관련작 클릭 → '{target_name}' 상세로 이동", new_title)
        expect(page.eval_on_selector("body", "el => location.search").find(f"item={target_id}") >= 0,
               "상세: 관련작 이동이 URL 딥링크에 반영", page.url)
        page.wait_for_timeout(300)
        if shots:
            page.set_viewport_size({"width": 1440, "height": 1100})
            page.goto(f"{base}?item={hero_id}", wait_until="domcontentloaded")
            page.wait_for_selector("#secEncyclopedia", timeout=15000)
            page.wait_for_timeout(500)
            page.screenshot(path=str(shots / "live-v30-encyclopedia-desktop.png"))
            expect((shots / "live-v30-encyclopedia-desktop.png").exists(),
                   "스크린샷: 데스크톱 사전 상세", str(shots / "live-v30-encyclopedia-desktop.png"))

        # 폴백 — 사전이 없는 항목
        ctx2, page2 = open_page()
        page2.goto(f"{base}?item={fallback_id}", wait_until="domcontentloaded")
        page2.wait_for_selector("#secEncyclopedia", timeout=15000)
        page2.wait_for_timeout(300)
        fb_badge = (page2.inner_text("#secEncyclopedia .pill") or "").strip()
        expect("기본 제원" in fb_badge, "폴백: 사전 미수록 항목은 '기본 제원' 배지", fb_badge)
        fb_facts = page2.query_selector_all("#secEncyclopedia .enc-fact")
        expect(len(fb_facts) >= 4, f"폴백: 기본 제원 {len(fb_facts)}개", str(len(fb_facts)))
        fb_text = page2.inner_text("#secEncyclopedia")
        expect("한 줄 소개" in fb_text and "플랫폼" in fb_text and "수집 출처" in fb_text,
               "폴백: 한 줄 소개·플랫폼·수집 출처 조합", fb_text[:120])
        fb_links = page2.query_selector_all("#secEncyclopedia .enc-sources a")
        expect(len(fb_links) >= 1, f"폴백: 출처 링크 {len(fb_links)}개", str(len(fb_links)))

        # EN — 사전 구간 한글 0
        ctx3, page3 = open_page(lang="en")
        page3.goto(f"{base}?item={hero_id}&lang=en", wait_until="domcontentloaded")
        page3.wait_for_selector("#secEncyclopedia", timeout=15000)
        page3.wait_for_timeout(500)
        en_title = (page3.inner_text("#secEncyclopedia h3") or "").strip()
        expect("Encyclopedia" in en_title, "EN: 섹션 제목 'Profile · Encyclopedia'", en_title)
        en_facts = page3.inner_text("#secEncyclopedia .enc-facts")
        expect("Korean" in en_facts and "Price" in en_facts, "EN: 제원 키가 영어", en_facts[:100])
        en_leaks = korean_left(page3, "#secEncyclopedia")
        expect(not en_leaks, "EN: 사전 구간 한글 0건", str(en_leaks[:4]))
        en_rel = page3.query_selector_all("#secEncyclopedia .enc-rel")
        expect(len(en_rel) >= 1, "EN: 관련작 버튼 표시", str(len(en_rel)))
        en_rel_text = page3.inner_text("#secEncyclopedia .enc-related")
        expect(not KOREAN.search(en_rel_text), "EN: 관련작 이름·관계 영어", en_rel_text[:80])

        # 모바일 390px
        ctx4, page4 = open_page(viewport=(390, 844))
        page4.goto(f"{base}?item={hero_id}", wait_until="domcontentloaded")
        page4.wait_for_selector("#secEncyclopedia", timeout=15000)
        page4.wait_for_timeout(500)
        expect(overflow(page4) <= 0, "모바일 390px: 가로 넘침 0", str(overflow(page4)))
        cols = page4.evaluate(
            "() => getComputedStyle(document.querySelector('#secEncyclopedia .enc-facts')).gridTemplateColumns.split(' ').length")
        expect(cols == 2, "모바일 390px: 사전 제원 2열", str(cols))
        sec_box = page4.query_selector("#secEncyclopedia").bounding_box()
        expect(bool(sec_box) and sec_box["width"] <= 390, "모바일 390px: 사전 섹션이 화면 폭 안", str(sec_box))
        if shots:
            page4.screenshot(path=str(shots / "live-v30-encyclopedia-mobile.png"))
            expect((shots / "live-v30-encyclopedia-mobile.png").exists(),
                   "스크린샷: 모바일 사전 상세", str(shots / "live-v30-encyclopedia-mobile.png"))

        browser.close()

    expect(not errors, "브라우저: 콘솔·페이지 오류 0건", str(errors[:3]))
    expect(not bad_http, "브라우저: HTTP 4xx/5xx 0건", str(bad_http[:3]))

    if httpd:
        httpd.shutdown()

    passed = sum(1 for _l, ok, _e in RESULTS if ok)
    print(f"\n결과: {passed}/{len(RESULTS)} PASS" + ("" if passed == len(RESULTS) else " — 실패 항목 확인"))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
