#!/usr/bin/env python3
"""파로스 v20 메인 화면 개편(등대 랜딩 · 전체 탐색 탭) 스모크 검증.

무엇을 확인하는가
  1) 기본 URL(`/`) 이 등대 화면으로 열린다 — 히어로 카피 · 통계 · 3단계 안내
  2) 상단 탭 순서가 `🚨 등대 · 🧭 전체 탐색 · 앱 · 게임 · AI 도구` 이고 등대가 기본 활성
  3) `🧭 전체 탐색` 탭 · `?domain=catalog` · `?domain=all` 이 기존 카탈로그(검색창·1,467건·장르 추천)를 연다
  4) 로고 클릭 → 등대 복귀 / 등대 하단 배너 → 카탈로그 이동
  5) 앱·게임·AI 도구 탭과 기존 딥링크(`?domain=game&arena=…`, `?arena=…`, `?item=balatro`)가 그대로 동작
  6) 등대 퀘스트: 발급 · 새로고침 잠금 · 광고 슬롯(5초) · 완료 기록 · 게임 상세 모달
  7) `?lang=en` 한글 0건(등대·카탈로그) · 390×844 가로 넘침 0건 · 콘솔/HTTP 오류 0건
  8) 스크린샷 2장 (--shots-dir): {prefix}-desktop / {prefix}-mobile

사용
  python3 projects/pharos/scripts/smoke_v20.py
  python3 projects/pharos/scripts/smoke_v20.py --live --shots-dir projects/pharos/live
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
        const title = document.title;
        if (re.test(title)) out.add('title: ' + title);
        return [...out];
      }""",
        KOREAN.pattern,
    )


def overflow(page) -> int:
    return page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


def tab_labels(page) -> list[str]:
    return page.eval_on_selector_all("#domainTabs button", "els => els.map((e) => e.textContent.trim())")


def active_tab(page) -> str:
    el = page.query_selector('#domainTabs button[aria-selected="true"]')
    return el.inner_text().strip() if el else ""


def card_state(page) -> dict:
    return page.evaluate(
        """() => {
        const card = document.querySelector('.lh-card');
        if (!card) return null;
        return {
          game: card.dataset.lhGame,
          title: card.querySelector('.lh-quest-title')?.innerText || '',
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
    parser.add_argument("--shot-prefix", default="")
    parser.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    args = parser.parse_args()

    httpd = None
    if args.live:
        base = LIVE
    else:
        httpd, base = serve(WEB_ROOT)
    prefix = args.shot_prefix or ("live-v20" if args.live else "local-v20")
    shots = Path(args.shots_dir) if args.shots_dir else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    lh = json.loads((WEB_ROOT / "data" / "lighthouse-quests.json").read_text(encoding="utf-8"))
    games = {row["game_id"]: row for row in lh["games"]}
    counts = lh["counts"]
    free_ids = {row["game_id"] for row in lh["games"] if row["free_to_play"]}
    catalog = json.loads((WEB_ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    arena_labels = {row["id"]: row["label"] for row in catalog["arenas"]}
    index = {row["id"]: row for row in json.loads((WEB_ROOT / "data" / "search-index.json").read_text(encoding="utf-8"))["items"]}
    total_items = len(index)

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

        # 1) 기본 랜딩 = 등대
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(800)
        expect(page.is_visible(".lh-hero"), "기본 URL(/) → 등대 화면이 메인으로 열린다", page.url)
        expect("domain=lighthouse" in page.url, "기본 랜딩 URL 이 등대로 정규화된다", page.url)
        h1 = page.inner_text(".lh-hero h1").replace("\n", " ")
        expect("지금 도전할 목표" in h1 and "별점 사이트가 아니라" in h1, "히어로가 등대 정체성을 말한다", h1)
        expect(page.inner_text(".lh-hero .eyebrow").strip().upper().startswith("LIGHTHOUSE"), "히어로 아이브로우 = LIGHTHOUSE", page.inner_text(".lh-hero .eyebrow"))
        steps = page.inner_text(".lh-steps").replace("\n", " ").strip()
        expect("조건 고르기" in steps and "목표 하나 완료" in steps, "히어로에 3단계 안내가 있다", steps)
        stat_nums = page.eval_on_selector_all(".lh-stat b", "els => els.map((e) => e.textContent.trim())")
        expect(stat_nums == [str(counts["games"]), str(counts["quests"]), str(counts["free_to_play"]), "0"],
               f"통계 타일 {counts['games']}·{counts['quests']}·{counts['free_to_play']}·0", str(stat_nums))
        expect(page.eval_on_selector(".crumb-bar", "e => getComputedStyle(e).display") == "none",
               "등대 화면은 경로 막대 없이 히어로부터 시작", "")

        # 2) 탭 순서 · 기본 활성
        expect(tab_labels(page) == ["🚨 등대", "🧭 전체 탐색", "앱", "게임", "AI 도구"],
               "탭 순서 = 🚨 등대 · 🧭 전체 탐색 · 앱 · 게임 · AI 도구", str(tab_labels(page)))
        expect(active_tab(page) == "🚨 등대", "기본 활성 탭이 🚨 등대", active_tab(page))
        expect(page.query_selector('#domainTabs button[data-action="lighthouse"]') is not None, "🚨 등대 탭이 존재", "")
        if shots:
            page.screenshot(path=str(shots / f"{prefix}-desktop.png"))

        # 3) 등대 하단 카탈로그 배너
        banner = page.query_selector(".lh-catalog-banner")
        expect(banner is not None, "완료 기록 아래 카탈로그 배너가 있다", "")
        banner_text = page.inner_text(".lh-catalog-banner").replace("\n", " | ") if banner else ""
        expect(f"{total_items:,}개 앱·게임·AI 도구 직접 비교해 보기" in banner_text,
               f"배너에 `{total_items:,}개 앱·게임·AI 도구 직접 비교해 보기`", banner_text)
        expect(banner is not None and "domain=catalog" in (banner.get_attribute("href") or ""),
               "배너 href 가 ?domain=catalog", banner.get_attribute("href") if banner else "")
        if banner:
            banner.click()
            page.wait_for_timeout(700)

        # 4) 전체 탐색(카탈로그) 탭 · 랜딩
        expect("domain=catalog" in page.url, "배너 클릭 → ?domain=catalog", page.url)
        expect(page.is_visible("#homeSearch"), "카탈로그 통합 검색창이 보인다", "")
        expect(active_tab(page) == "🧭 전체 탐색", "🧭 전체 탐색 탭이 활성", active_tab(page))
        meta = page.inner_text(".hero-meta").replace("\n", " ")
        expect(f"{total_items:,}건" in meta, f"카탈로그 히어로에 {total_items:,}건 표시", meta[:120])
        genre_blocks = page.query_selector_all(".genre-block")
        expect(len(genre_blocks) > 0, "장르별 추천 쇼케이스가 그려진다", str(len(genre_blocks)))
        expect(page.query_selector(".pick-tile") is not None, "장르 추천 타일이 보인다", "")
        expect(page.query_selector("#gapReport") is not None, "갭 리포트 섹션이 남아 있다", "")
        expect(overflow(page) == 0, "1440px 카탈로그 가로 넘침 0", str(overflow(page)))

        # 5) 로고 → 등대 복귀
        page.click(".brand")
        page.wait_for_timeout(600)
        expect(page.is_visible(".lh-hero") and "domain=lighthouse" in page.url, "로고 클릭 → 등대 복귀", page.url)

        # 6) `?domain=all` · `?domain=catalog` · `?tab=catalog` 모두 카탈로그
        for query in ("?domain=all", "?domain=catalog", "?tab=catalog"):
            page.goto(base + query, wait_until="networkidle")
            page.wait_for_timeout(500)
            expect(page.is_visible("#homeSearch") and active_tab(page) == "🧭 전체 탐색",
                   f"{query} → 카탈로그 홈", page.url)

        # 7) 앱·게임·AI 탭
        for dom, label in (("app", "앱"), ("game", "게임"), ("ai", "AI 도구")):
            page.click(f'#domainTabs button[data-domain="{dom}"]')
            page.wait_for_timeout(600)
            expect(f"domain={dom}" in page.url and page.query_selector(".level-head") is not None,
                   f"{label} 탭 → 도메인 화면", page.url)
            expect(active_tab(page) == label, f"{label} 탭이 활성", active_tab(page))
        expect(overflow(page) == 0, "AI 도구 도메인 화면 가로 넘침 0", str(overflow(page)))

        # 8) 기존 딥링크 하위 호환
        page.goto(f"{base}?domain=game&arena=action-roguelike", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("#view h1").strip() == arena_labels["action-roguelike"],
               "?domain=game&arena=action-roguelike → 비교군 화면", page.inner_text("#view h1"))
        expect(len(page.query_selector_all("#arenaResults .card")) > 0, "비교군 카드가 그려진다", "")
        expect(active_tab(page) == "게임", "게임 탭 활성 유지", active_tab(page))
        crumb = page.inner_text("#breadcrumb").replace("\n", " ")
        expect("전체 탐색" in crumb and "액션 로그라이크" in crumb, "경로: 등대 / 전체 탐색 / 게임 / … / 비교군", crumb)

        page.goto(f"{base}?arena=action-roguelike", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("#view h1").strip() == arena_labels["action-roguelike"], "?arena=… 딥링크도 동작", page.url)

        page.goto(f"{base}?item=balatro", wait_until="networkidle")
        page.wait_for_timeout(1100)
        expect(page.eval_on_selector("#modalBackdrop", "e => !e.hidden"), "?item=balatro → 상세 모달", page.url)
        expect(page.inner_text("#modalTitle").strip() == index["balatro"]["name"],
               "상세 모달 제목이 Balatro", page.inner_text("#modalTitle"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        page.goto(f"{base}?domain=lighthouse", wait_until="networkidle")
        page.wait_for_timeout(600)
        expect(page.is_visible(".lh-hero"), "?domain=lighthouse 딥링크", page.url)
        page.goto(f"{base}?tab=lighthouse", wait_until="networkidle")
        page.wait_for_timeout(600)
        expect(page.is_visible(".lh-hero"), "?tab=lighthouse 딥링크", page.url)

        # 9) 등대 퀘스트 발급 · 잠금 · 완료
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(700)
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
            expect(first["game"] in free_ids, "무료만 조건 → 무료 게임만", first["game"])
            expect(first["title"] == quest["title_ko"], "1단계 퀘스트 제목이 데이터와 같다", first["title"])
        expect(page.eval_on_selector("[data-lh-draw]", "e => e.disabled"), "발급 직후 재뽑기 잠금", "")

        page.reload(wait_until="networkidle")
        page.wait_for_timeout(700)
        after = card_state(page)
        expect(after is not None and after["game"] == first["game"] and after["title"] == first["title"],
               "새로고침 후에도 같은 게임·같은 퀘스트", f"{first and first['game']} → {after and after['game']}")
        expect(page.eval_on_selector("[data-lh-draw]", "e => e.disabled"), "새로고침 후에도 잠금 유지", "")

        page.click("[data-lh-ad]")
        page.wait_for_timeout(400)
        expect(page.is_visible("#lhAdBackdrop"), "광고 슬롯 모달이 열린다", "")
        expect(page.eval_on_selector("#lhAdSkip", "e => e.disabled"), "5초 전 건너뛰기 잠금", "")
        page.wait_for_timeout(4700)
        expect(not page.eval_on_selector("#lhAdSkip", "e => e.disabled"), "5초 뒤 건너뛰기 해금", "")
        page.click("#lhAdSkip")
        page.wait_for_timeout(500)
        expect(page.query_selector(".lh-card") is None, "건너뛰면 카드가 비워진다", "")
        expect(page.eval_on_selector(".lh-catalog-banner", "e => !!e"), "배너는 카드 아래 그대로 남는다", "")

        page.click("[data-lh-draw]")
        page.wait_for_timeout(400)
        page.click("[data-lh-complete]")
        page.wait_for_timeout(500)
        hist = page.inner_text("#lhHistory").replace("\n", " ")
        expect("누적 완료 1" in hist, "완료 기록이 1건 쌓인다", hist[:120])
        expect(page.inner_text(".lh-stat:nth-child(4) b").strip() == "1", "통계 타일 '내 완료'가 1로 바뀐다", page.inner_text(".lh-stats"))

        page.click("[data-lh-draw]")
        page.wait_for_timeout(400)
        gid = page.get_attribute(".lh-card", "data-lh-game")
        page.click("[data-lh-detail]")
        page.wait_for_timeout(900)
        expect(page.eval_on_selector("#modalBackdrop", "e => !e.hidden"), "게임 상세 모달이 등대 위에서 열린다", "")
        expect(page.inner_text("#modalTitle").strip() == index[gid]["name"], "모달 제목이 그 게임 이름", page.inner_text("#modalTitle"))
        expect("domain=lighthouse" in page.url and f"item={gid}" in page.url, "상세 딥링크가 등대 위에 얹힌다", page.url)
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        expect(page.is_visible(".lh-hero"), "상세를 닫으면 등대 화면", page.url)

        # 10) EN — 등대·카탈로그 한글 0
        en = browser.new_context(viewport={"width": 1440, "height": 1100}, locale="en-US").new_page()
        en_errors: list[str] = []
        en.on("pageerror", lambda exc: en_errors.append(str(exc)))
        en.on("console", lambda msg: en_errors.append(f"console: {msg.text}") if msg.type == "error" else None)
        en.goto(base + "?lang=en", wait_until="networkidle")
        en.wait_for_timeout(800)
        expect(en.evaluate("document.documentElement.lang") == "en", "EN 언어 전환", "")
        expect(en.is_visible(".lh-hero"), "?lang=en 기본 랜딩도 등대", en.url)
        expect(tab_labels(en) == ["🚨 Lighthouse", "🧭 Explore", "Apps", "Games", "AI Tools"],
               "EN 탭 라벨", str(tab_labels(en)))
        expect("Not another ratings site" in en.inner_text(".lh-hero h1"), "EN 히어로 카피", en.inner_text(".lh-hero h1"))
        expect(not korean_left(en), "EN 등대 화면 한글 잔존 0건", str(korean_left(en)[:3]))
        en.click('#domainTabs button[data-action="catalog"]')
        en.wait_for_timeout(800)
        expect(en.is_visible("#homeSearch"), "EN 전체 탐색 탭 → 카탈로그", en.url)
        expect(not korean_left(en), "EN 카탈로그 화면 한글 잔존 0건", str(korean_left(en)[:3]))
        en.goto(base + "?lang=en&domain=lighthouse", wait_until="networkidle")
        en.wait_for_timeout(700)
        en.click("[data-lh-draw]")
        en.wait_for_timeout(500)
        expect(card_state(en) is not None, "EN 화면에서도 퀘스트 카드 발급", str(card_state(en)))
        expect(not korean_left(en), "EN 퀘스트 카드 한글 잔존 0건", str(korean_left(en)[:3]))
        expect(not en_errors, "EN 콘솔 오류 0건", "; ".join(en_errors[:2]))
        en.close()

        # 11) 390×844 모바일
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR").new_page()
        mobile_errors: list[str] = []
        mobile.on("pageerror", lambda exc: mobile_errors.append(str(exc)))
        mobile.on("console", lambda msg: mobile_errors.append(f"console: {msg.text}") if msg.type == "error" else None)
        mobile.goto(base, wait_until="networkidle")
        mobile.wait_for_timeout(800)
        expect(overflow(mobile) == 0, "390px 등대 랜딩 가로 넘침 0", str(overflow(mobile)))
        tab_fit = mobile.eval_on_selector("#domainTabs", "e => ({ sw: e.scrollWidth, cw: e.clientWidth })")
        expect(tab_fit["sw"] <= tab_fit["cw"] + 1, "390px 상단 탭 5개가 줄바꿈·가로 넘침 없이 들어간다", str(tab_fit))
        if shots:
            mobile.screenshot(path=str(shots / f"{prefix}-mobile.png"))
        mobile.click("[data-lh-draw]")
        mobile.wait_for_timeout(600)
        expect(overflow(mobile) == 0, "390px 퀘스트 카드 가로 넘침 0", str(overflow(mobile)))
        expect(mobile.is_visible("[data-lh-complete]") and mobile.eval_on_selector(".lh-catalog-banner", "e => !!e"),
               "390px 카드 액션·배너 접근 가능", "")
        mobile.click('.brand')
        mobile.wait_for_timeout(300)
        mobile.click('#domainTabs button[data-action="catalog"]')
        mobile.wait_for_timeout(700)
        expect(overflow(mobile) == 0, "390px 카탈로그 가로 넘침 0", str(overflow(mobile)))
        expect(mobile.is_visible("#homeSearch"), "390px 카탈로그 검색창", "")
        mobile.click("#themeToggle")
        mobile.wait_for_timeout(400)
        expect(overflow(mobile) == 0, "390px 라이트 테마 가로 넘침 0", str(overflow(mobile)))
        expect(not mobile_errors, "모바일 콘솔 오류 0건", "; ".join(mobile_errors[:2]))
        mobile.close()

        expect(not errors, "데스크톱 콘솔 오류·페이지 예외 0건", "; ".join(errors[:3]))
        expect(not bad_http, "HTTP 4xx/5xx 0건", "; ".join(bad_http[:3]))
        browser.close()
    if httpd:
        httpd.shutdown()

    passed = sum(1 for _l, ok, _e in RESULTS if ok)
    print("=" * 78)
    print(f"결과: {passed}/{len(RESULTS)} PASS · 등대 {counts['games']}종·퀘스트 {counts['quests']}개 · 카탈로그 {total_items:,}건")
    print("=" * 78)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
