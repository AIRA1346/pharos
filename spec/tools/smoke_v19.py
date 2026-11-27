#!/usr/bin/env python3
"""파로스 v19 🚨 등대(Lighthouse) 퀘스트 스모크 검증.

무엇을 확인하는가
  1) 상단 내비게이션 `🚨 등대` 탭 진입(?domain=lighthouse · ?tab=lighthouse 딥링크)
  2) 명작 50종 · 퀘스트 150개 로드(브라우저가 실제로 받은 데이터로 확인)
  3) `무료만` + `1단계` 선택 → 퀘스트 발급 → 새로고침 후에도 같은 게임·같은 퀘스트 유지(잠금)
  4) `🎬 광고 보고 건너뛰기` — 안내 모달 + 5초 카운트다운 뒤 건너뛰기 해금
  5) `✅ 퀘스트 완료` — 완료 기록 증가 & 재뽑기 해금
  6) `게임 상세 보기` — 기존 파로스 상세 모달이 등대 화면 위에서 열린다
  7) `?lang=en` 한글 잔존 0건 · 390×844 가로 넘침 0 · 콘솔/HTTP 오류 0
  8) 스크린샷 2장 (--shots-dir): lighthouse-desktop / lighthouse-mobile

사용
  python3 projects/pharos/scripts/smoke_v19.py
  python3 projects/pharos/scripts/smoke_v19.py --live --shots-dir projects/pharos/live
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
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
WEB_ROOT = ROOT / "web"
LIVE = "https://aira1346.github.io/pharos/"
KOREAN = re.compile(r"[\uac00-\ud7a3]")
RESULTS: list[tuple[str, bool, str]] = []


def expect(condition: bool, label: str, extra: str = "") -> None:
    RESULTS.append((label, bool(condition), str(extra)))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}" + ("" if condition else f"  ← {extra}"))


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
        return [...out];
      }""",
        KOREAN.pattern,
    )


def overflow(page) -> int:
    return page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


def card_state(page) -> dict:
    return page.evaluate(
        """() => {
        const card = document.querySelector('.lh-card');
        if (!card) return null;
        return {
          game: card.dataset.lhGame,
          title: card.querySelector('.lh-quest-title')?.innerText || '',
          quests: card.querySelectorAll('.lh-quest').length,
          complete: card.querySelector('[data-lh-complete]')?.disabled ?? null,
        };
      }"""
    )


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        return


def serve(root: Path):
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="GitHub Pages 라이브 URL 로 검증")
    parser.add_argument("--shots-dir", default="")
    parser.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    args = parser.parse_args()

    httpd = None
    if args.live:
        base = LIVE
    else:
        httpd, base = serve(WEB_ROOT)
    shots = Path(args.shots_dir) if args.shots_dir else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    lh = json.loads((WEB_ROOT / "data" / "lighthouse-quests.json").read_text(encoding="utf-8"))
    games = {row["game_id"]: row for row in lh["games"]}
    counts = lh["counts"]
    free_ids = {row["game_id"] for row in lh["games"] if row["free_to_play"]}
    pc_ids = {row["game_id"] for row in lh["games"] if "pc" in row["platforms"]}
    index = {row["id"]: row for row in json.loads((WEB_ROOT / "data" / "search-index.json").read_text(encoding="utf-8"))["items"]}

    with sync_playwright() as p:
        launch = {"executable_path": args.chrome} if args.chrome else {}
        browser = p.chromium.launch(**launch)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="ko-KR")
        page = ctx.new_page()
        errors: list[str] = []
        bad_http: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: errors.append(f"console: {msg.text}") if msg.type == "error" else None)
        page.on("response", lambda res: bad_http.append(f"{res.status} {res.url}") if res.status >= 400 else None)

        # 1) 내비게이션 탭 · 딥링크
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(600)
        tab = page.query_selector('#domainTabs button[data-action="lighthouse"]')
        expect(tab is not None, "상단 내비게이션에 🚨 등대 탭이 있다", page.inner_text("#domainTabs"))
        tab.click()
        page.wait_for_timeout(700)
        expect("domain=lighthouse" in page.url, "탭 클릭 → ?domain=lighthouse", page.url)
        expect(page.is_visible(".lh-hero"), "등대 화면이 열린다", "")
        tab_active = page.get_attribute('#domainTabs button[data-action="lighthouse"]', "aria-selected")
        expect(tab_active == "true", "🚨 등대 탭이 선택 상태", str(tab_active))

        page.goto(f"{base}?tab=lighthouse", wait_until="networkidle")
        page.wait_for_timeout(600)
        expect(page.is_visible(".lh-hero"), "?tab=lighthouse 딥링크도 동작", page.url)

        # 2) 데이터 로드 — 브라우저가 실제로 받은 값
        loaded = page.evaluate("() => window.Pharos?.state?.lh?.data?.counts || null")
        expect(
            bool(loaded) and loaded.get("games") == 50 and loaded.get("quests") == 150,
            "브라우저가 명작 50종 · 퀘스트 150개를 로드",
            str(loaded),
        )
        expect(
            loaded is not None and loaded.get("free_to_play") == counts["free_to_play"],
            f"무료 게임 {counts['free_to_play']}종이 데이터와 일치",
            str(loaded),
        )
        stats = page.inner_text(".lh-stats").replace(",", "")
        expect("50" in stats and "150" in stats, "화면 통계에 50종 · 150개 표시", stats.replace("\n", " | "))

        # 3) 무료만 + 1단계 → 발급 → 새로고침 유지
        page.click("[data-lh-price='free']")
        page.wait_for_timeout(200)
        page.click("[data-lh-tier='1']")
        page.wait_for_timeout(200)
        page.click("[data-lh-draw]")
        page.wait_for_timeout(500)
        first = card_state(page)
        expect(first is not None and first["game"] in games, "퀘스트 카드가 발급된다", str(first))
        if first:
            quest = next(q for q in games[first["game"]]["quests"] if q["tier"] == 1)
            expect(first["game"] in free_ids, "무료만 조건 → 무료 게임만 나온다", first["game"])
            expect(first["title"] == quest["title_ko"], "1단계 퀘스트 제목이 데이터와 같다", first["title"])
            expect("쿼리" not in first["title"], "퀘스트 제목이 비어 있지 않다", first["title"])
        expect(
            page.eval_on_selector("[data-lh-draw]", "e => e.disabled"),
            "발급 직후 재뽑기 버튼이 잠긴다",
            "",
        )
        expect(
            page.eval_on_selector("[data-lh-price='all']", "e => e.disabled"),
            "발급 직후 조건 변경도 잠긴다",
            "",
        )
        if shots:
            page.wait_for_timeout(3400)  # 토스트가 사라진 뒤 카드만 담는다
            page.screenshot(path=str(shots / "live-v19-lighthouse-desktop.png"))

        page.reload(wait_until="networkidle")
        page.wait_for_timeout(700)
        after = card_state(page)
        expect(after is not None and after["game"] == first["game"], "새로고침 후에도 같은 게임", f"{first['game']} → {after and after['game']}")
        expect(after is not None and after["title"] == first["title"], "새로고침 후에도 같은 퀘스트 문구", f"{after and after['title']}")
        expect(page.eval_on_selector("[data-lh-draw]", "e => e.disabled"), "새로고침 후에도 잠금 유지", "")
        stored = page.evaluate("() => JSON.parse(localStorage.getItem('pharos_lighthouse_state_v1') || 'null')")
        expect(
            bool(stored) and stored.get("current", {}).get("game_id") == first["game"],
            "localStorage(pharos_lighthouse_state_v1)에 퀘스트가 남는다",
            str(bool(stored)),
        )

        # 4) 광고 슬롯 — 안내 모달 + 5초 카운트다운
        page.click("[data-lh-ad]")
        page.wait_for_timeout(400)
        expect(page.is_visible("#lhAdBackdrop"), "광고 슬롯 모달이 열린다", "")
        ad_text = page.inner_text("#lhAdModal")
        expect("정식 출시 시 보상형 동영상 광고가 재생되는 자리입니다" in ad_text, "보상형 광고 안내 문구 표시", ad_text[:120].replace("\n", " | "))
        expect(page.eval_on_selector("#lhAdSkip", "e => e.disabled"), "5초 전에는 건너뛰기 버튼이 잠겨 있다", "")
        page.wait_for_timeout(4600)
        expect(not page.eval_on_selector("#lhAdSkip", "e => e.disabled"), "5초 카운트다운 뒤 건너뛰기가 열린다", page.inner_text("#lhAdSkip"))
        page.click("#lhAdSkip")
        page.wait_for_timeout(500)
        expect(page.is_hidden("#lhAdBackdrop"), "건너뛰면 모달이 닫힌다", "")
        expect(not page.eval_on_selector("[data-lh-draw]", "e => e.disabled"), "건너뛰면 재뽑기가 해금된다", "")
        expect(page.query_selector(".lh-card") is None, "건너뛴 퀘스트는 카드에서 사라진다", "")

        # 5) 완료 → 기록 증가 · 재뽑기 해금
        page.click("[data-lh-draw]")
        page.wait_for_timeout(400)
        before_hist = page.inner_text("#lhHistory")
        page.click("[data-lh-complete]")
        page.wait_for_timeout(500)
        after_hist = page.inner_text("#lhHistory")
        expect(page.query_selector(".lh-card") is None, "완료하면 카드가 비워진다", "")
        expect(not page.eval_on_selector("[data-lh-draw]", "e => e.disabled"), "완료하면 재뽑기가 해금된다", "")
        expect("누적 완료 1" in after_hist.replace("\n", " "), "완료 기록이 1건 쌓인다", after_hist.replace("\n", " | ")[:160])
        expect(page.query_selector_all(".lh-history-list .lh-badge").__len__() == 1, "완료 배지 1개 표시", "")
        expect(before_hist != after_hist, "완료 전후 기록 영역이 달라진다", "")

        page.reload(wait_until="networkidle")
        page.wait_for_timeout(700)
        expect("누적 완료 1" in page.inner_text("#lhHistory").replace("\n", " "), "새로고침 후에도 완료 기록 유지", "")
        expect(not page.eval_on_selector("[data-lh-draw]", "e => e.disabled"), "새로고침 후에도 재뽑기 가능", "")

        # 6) 게임 상세 보기 — 기존 상세 모달
        page.click("[data-lh-draw]")
        page.wait_for_timeout(400)
        gid = page.get_attribute(".lh-card", "data-lh-game")
        page.click("[data-lh-detail]")
        page.wait_for_timeout(900)
        expect(page.eval_on_selector("#modalBackdrop", "e => !e.hidden"), "게임 상세 보기 → 파로스 상세 모달", "")
        expect(page.inner_text("#modalTitle") == index[gid]["name"], "모달 제목이 그 게임 이름", page.inner_text("#modalTitle"))
        expect("domain=lighthouse" in page.url and f"item={gid}" in page.url, "상세 딥링크가 등대 위에 얹힌다", page.url)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        expect(page.is_visible(".lh-hero"), "상세를 닫으면 등대 화면으로 돌아온다", page.url)

        # 7) EN — 한글 0
        en = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="en-US").new_page()
        en_errors: list[str] = []
        en.on("pageerror", lambda exc: en_errors.append(str(exc)))
        en.on("console", lambda msg: en_errors.append(f"console: {msg.text}") if msg.type == "error" else None)
        en.goto(f"{base}?lang=en&domain=lighthouse", wait_until="networkidle")
        en.wait_for_timeout(700)
        expect(en.evaluate("document.documentElement.lang") == "en", "EN 언어 전환", "")
        expect(not korean_left(en), "EN 등대 화면 한글 잔존 0건", str(korean_left(en)[:3]))
        en.click("[data-lh-price='free']")
        en.wait_for_timeout(150)
        en.click("[data-lh-tier='2']")
        en.wait_for_timeout(150)
        en.click("[data-lh-draw]")
        en.wait_for_timeout(500)
        en_card = card_state(en)
        expect(en_card is not None, "EN 화면에서도 퀘스트 카드 발급", str(en_card))
        if en_card:
            game = games[en_card["game"]]
            quest = next(q for q in game["quests"] if q["tier"] == 2)
            expect(en_card["title"] == quest["title_en"], "EN 카드가 영문 퀘스트 제목", en_card["title"])
        expect(not korean_left(en), "EN 카드·기록 한글 잔존 0건", str(korean_left(en)[:3]))
        en.click("[data-lh-detail]")
        en.wait_for_timeout(900)
        expect(not korean_left(en), "EN 상세 모달 한글 잔존 0건", str(korean_left(en)[:3]))
        en.keyboard.press("Escape")
        en.wait_for_timeout(300)
        expect(not en_errors, "EN 콘솔 오류 0건", "; ".join(en_errors[:2]))
        en.close()

        # 8) 390×844 모바일
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR").new_page()
        mobile.goto(f"{base}?domain=lighthouse", wait_until="networkidle")
        mobile.wait_for_timeout(600)
        expect(overflow(mobile) == 0, "390px 등대 빈 화면 가로 넘침 0", str(overflow(mobile)))
        mobile.click("[data-lh-draw]")
        mobile.wait_for_timeout(500)
        expect(overflow(mobile) == 0, "390px 퀘스트 카드 가로 넘침 0", str(overflow(mobile)))
        expect(mobile.is_visible("[data-lh-complete]") and mobile.is_visible("[data-lh-ad]"), "390px 액션 2개가 보인다", "")
        if shots:
            mobile.wait_for_timeout(3400)
            mobile.eval_on_selector(".lh-card", "e => e.scrollIntoView({ block: 'start' })")
            mobile.wait_for_timeout(300)
            mobile.screenshot(path=str(shots / "live-v19-lighthouse-mobile.png"))
        mobile.click("#themeToggle")
        mobile.wait_for_timeout(400)
        expect(overflow(mobile) == 0, "390px 라이트 테마 가로 넘침 0", str(overflow(mobile)))
        mobile.close()

        expect(not errors, "콘솔 오류·페이지 예외 0건", "; ".join(errors[:3]))
        expect(not bad_http, "HTTP 4xx/5xx 0건", "; ".join(bad_http[:3]))
        browser.close()
    if httpd:
        httpd.shutdown()

    passed = sum(1 for _l, ok, _e in RESULTS if ok)
    print("=" * 74)
    print(f"결과: {passed}/{len(RESULTS)} PASS · 등대 명작 {counts['games']}종 · 퀘스트 {counts['quests']}개 (무료 {counts['free_to_play']})")
    print("=" * 74)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
