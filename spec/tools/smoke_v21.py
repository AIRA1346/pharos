#!/usr/bin/env python3
"""파로스 v21 등대 개편 스모크 검증 — 단계형 위저드 · 명작 50종 · 퀘스트 150개.

무엇을 확인하는가
  1) Step 0 심플 랜딩 — 히어로·통계·필터·빈 점선 박스·완료 기록 없이 카피와 `🚨 목표 탐색` 하나
  2) 위저드 전체 흐름 — 서약 → 분야 선택(🎮 게임) → Step 1(플랫폼·가격) → 2(소요 시간·카드 선택은 하이라이트만, `다음` 으로 이동)
     → 3(난이도·후보 수) → 4(목표 카드)
  3) 난이도 필터(chill·normal·hardcore)가 후보 수와 실제 발급 게임을 바꾼다
  4) 새로고침 잠금 유지 · 5초 광고 건너뛰기 · 완료 기록 누적
  5) EN 전환(토글·`?lang=en`) 한글 0건 · 390px 가로 넘침 0건
  6) 기존 카탈로그 딥링크(`?domain=catalog` · `?arena=` · `?item=`) 회귀
  7) 콘솔/HTTP 오류 0건 · 스크린샷 3장(--shots-dir)

사용
  python3 projects/pharos/scripts/smoke_v21.py
  python3 projects/pharos/scripts/smoke_v21.py --live --shots-dir projects/pharos/live
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
          difficulty: card.dataset.lhDifficulty,
          badge: card.querySelector('.lh-diff')?.innerText || '',
          title: card.querySelector('.lh-quest-title')?.innerText || '',
          tier: card.querySelector('.lh-quest')?.dataset.lhTierView || '',
          chips: [...card.querySelectorAll('.lh-chip')].map((e) => e.innerText.trim()),
          locked: !!card.querySelector('.lh-locked'),
        };
      }"""
    )


def wizard_state(page) -> dict:
    return page.evaluate(
        """() => ({
        step1: !!document.querySelector('.lh--step1'),
        step2: !!document.querySelector('.lh--step2'),
        step3: !!document.querySelector('.lh--step3'),
        result: !!document.querySelector('.lh--result'),
        landing: !!document.querySelector('.lh--landing'),
        progress: document.querySelector('.lh-progress-text')?.textContent?.trim() || '',
        summary: document.querySelector('.lh-summary')?.innerText || '',
        count: document.querySelector('.lh-count')?.innerText || '',
      })"""
    )


def checked(page, group: str) -> str:
    el = page.query_selector(f'[data-lh-pick="{group}"][aria-checked="true"]')
    return el.get_attribute("data-lh-value") if el else ""


def enter_wizard(page, label: str = "서약", category: str = "game") -> None:
    """랜딩 `목표 탐색` → 항해 서약(체크 + `서약하고 나아가기`) → 분야 선택 → Step 1."""
    page.click("[data-lh-goto='pledge']")
    page.wait_for_timeout(400)
    expect(page.is_visible(".lh--pledge"), f"{label}: 목표 탐색 직후 항해 서약 화면", "")
    page.click(".lh-pledge-check")
    page.wait_for_timeout(150)
    page.click("[data-lh-oath]")
    page.wait_for_timeout(400)
    expect(page.is_visible(".lh--category"), f"{label}: 서약 뒤 분야 선택 화면", "")
    page.click(f"[data-lh-cat='{category}']")
    page.wait_for_timeout(400)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        return


def serve(root: Path):
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


class Pages:
    """브라우저·컨텍스트·페이지를 만들면서 콘솔/HTTP 오류를 한곳에 모은다."""

    def __init__(self, browser, errors: list[str], bad_http: list[str]):
        self.browser = browser
        self.errors = errors
        self.bad_http = bad_http

    def open(self, viewport=(1440, 1100), locale="ko-KR"):
        ctx = self.browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, locale=locale)
        page = ctx.new_page()
        page.on("pageerror", lambda exc: self.errors.append(str(exc)))
        page.on(
            "console",
            lambda msg: self.errors.append(f"console: {msg.text}") if msg.type == "error" else None,
        )
        page.on(
            "response",
            lambda res: self.bad_http.append(f"{res.status} {res.url}") if res.status >= 400 else None,
        )
        return ctx, page


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
    prefix = args.shot_prefix or ("live-v21" if args.live else "local-v21")
    shots = Path(args.shots_dir) if args.shots_dir else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    lh = json.loads((WEB_ROOT / "data" / "lighthouse-quests.json").read_text(encoding="utf-8"))
    games = {row["game_id"]: row for row in lh["games"]}
    counts = lh["counts"]
    index = {
        row["id"]: row
        for row in json.loads((WEB_ROOT / "data" / "search-index.json").read_text(encoding="utf-8"))["items"]
    }
    catalog = json.loads((WEB_ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    arena_labels = {row["id"]: row["label"] for row in catalog["arenas"]}
    total_items = len(index)

    def pool(platform="all", price="all", diff="all", tier="all"):
        """조건에 맞는 목표(게임+단계+난이도) 집합 — 추첨 단위는 게임이 아니라 퀘스트다."""
        out = set()
        for g in lh["games"]:
            if price == "free" and not g["free_to_play"]:
                continue
            if platform != "all" and platform not in g["platforms"]:
                continue
            for q in g["quests"]:
                if tier != "all" and q["tier"] != int(tier):
                    continue
                if diff != "all" and q["difficulty"] != diff:
                    continue
                out.add((g["game_id"], q["tier"], q["difficulty"]))
        return out

    # 데이터 계약 — 50~70종 · 100개 이상 · 퀘스트별 난이도 · 모든 조합 후보 2개 이상
    expect(50 <= len(games) <= 70 and counts["quests"] >= 100,
           "데이터: 명작 50~70종 · 상징 목표 100개 이상", str(counts))
    expect(
        {q["difficulty"] for g in lh["games"] for q in g["quests"]} == {"chill", "normal", "hardcore"},
        "데이터: 퀘스트 난이도는 chill·normal·hardcore 세 종류",
        str({q["difficulty"] for g in lh["games"] for q in g["quests"]}),
    )
    expect(
        all(len({q["difficulty"] for q in g["quests"]}) >= 1 for g in lh["games"]),
        "데이터: 모든 퀘스트에 자체 난이도",
        "",
    )
    empty_combos = [
        (p, pr, t, d)
        for p in ("all", "pc", "mobile")
        for pr in ("all", "free")
        for t in (1, 2, 3)
        for d in ("all", "chill", "normal", "hardcore")
        if len(pool(p, pr, d, t)) < 2
    ]
    expect(not empty_combos, "데이터: 플랫폼×가격×단계×난이도 모든 조합에 후보 2개 이상", str(empty_combos[:4]))
    expect(
        all(len(pool("mobile", "free", d, t)) >= 2 for d in ("chill", "normal", "hardcore") for t in (1, 2, 3)),
        "데이터: 모바일+무료에서 단계·난이도 모든 조합 후보 2개 이상",
        str({(t, d): len(pool("mobile", "free", d, t)) for t in (1, 2, 3) for d in ("chill", "normal", "hardcore")}),
    )
    expect(
        {"goddess-of-victory-nikke", "uma-musume", "geometry-dash", "minecraft", "dark-souls-iii",
         "pubg-battlegrounds", "portal-2", "stardew-valley", "balatro", "blue-archive", "undertale",
         "elden-ring", "sekiro", "vampire-survivors", "slay-the-spire", "outer-wilds", "monument-valley",
         "limbus-company"}.issubset(games),
        "데이터: 사용자 확정 목표 18종 게임 포함",
        str({"goddess-of-victory-nikke", "uma-musume", "geometry-dash", "minecraft", "dark-souls-iii",
             "pubg-battlegrounds", "portal-2", "stardew-valley", "balatro", "blue-archive", "undertale",
             "elden-ring", "sekiro", "vampire-survivors", "slay-the-spire", "outer-wilds", "monument-valley",
             "limbus-company"} - set(games)),
    )
    fixed_quests = {("geometry-dash", 1, "chill"), ("geometry-dash", 1, "hardcore"),
                    ("undertale", 2, "chill"), ("undertale", 1, "hardcore"),
                    ("minecraft", 2, "hardcore"), ("limbus-company", 2, "hardcore")}
    expect(fixed_quests.issubset(pool("all", "all", "all", "all")),
           "데이터: 같은 게임·단계의 복수 난이도 목표 포함", str(fixed_quests - pool()))
    expect(
        {"arknights", "wuthering-waves", "genshin-impact", "honkai-star-rail", "apex-legends", "valorant",
         "counter-strike-2", "path-of-exile"}.issubset(games),
        "데이터: 무료 대표작 8종 보강 포함",
        "",
    )
    expect(
        {"brawl-stars", "clash-of-clans", "marvel-snap", "overwatch-2", "the-finals"}.isdisjoint(games),
        "데이터: 가벼운 라이브 게임 5종 제외",
        "",
    )

    errors: list[str] = []
    bad_http: list[str] = []

    with sync_playwright() as p:
        launch = {"executable_path": args.chrome} if args.chrome else {}
        browser = p.chromium.launch(**launch)
        pages = Pages(browser, errors, bad_http)
        ctx, page = pages.open()
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(800)

        # 1) Step 0 — 심플 랜딩
        st = wizard_state(page)
        expect(st["landing"], "Step 0: 기본 URL(/) 이 심플 랜딩", page.url)
        expect("domain=lighthouse" in page.url, "Step 0: URL 이 등대로 정규화", page.url)
        title = page.inner_text(".lh-landing-title").replace("\n", " ")
        expect("지금 해볼 만한 명작" in title and "목표 하나를 비춥니다" in title,
               "Step 0: 카피 `지금 해볼 만한 명작 / 목표 하나를 비춥니다`", title)
        cta = page.inner_text("[data-lh-goto='pledge']").replace("\n", " ").strip()
        expect("목표 탐색" in cta, "Step 0: `🚨 목표 탐색` 버튼", cta)
        expect(len(page.query_selector_all(".lh-landing .primary-btn")) == 1,
               "Step 0: 중앙 CTA 는 하나뿐", str(len(page.query_selector_all(".lh-landing .primary-btn"))))
        expect(
            page.query_selector(".lh-hero") is None
            and page.query_selector(".lh-stats") is None
            and page.query_selector(".lh-controls") is None,
            "Step 0: 히어로·통계 타일·3축 필터 없음",
            "",
        )
        expect(page.query_selector("#lhHistory") is None and page.query_selector(".lh-history") is None,
               "Step 0: 완료 기록 0건이면 기록 영역 없음", "")
        expect(page.query_selector(".lh-empty") is None, "Step 0: 빈 점선 결과 박스·`완료한 퀘스트가 없습니다` 없음", "")
        banner = page.query_selector(".lh-catalog-banner")
        banner_text = page.inner_text(".lh-catalog-banner").replace("\n", " | ") if banner else ""
        expect(f"{total_items:,}개 앱·게임·AI 도구 직접 비교해 보기" in banner_text,
               f"Step 0: 카탈로그 배너 `{total_items:,}개 … 비교해 보기` 유지", banner_text[:90])
        expect(tab_labels(page)[:2] == ["🚨 등대", "🧭 전체 탐색"] and active_tab(page) == "🚨 등대",
               "상단 탭 순서·활성 = 등대", str(tab_labels(page)))
        if shots:
            page.screenshot(path=str(shots / f"{prefix}-step0-desktop.png"))

        # 2) 위저드 Step 1 → 4
        enter_wizard(page, "서약(첫 진입)")
        st = wizard_state(page)
        expect(st["step1"] and st["progress"] == "1 / 3", "Step 1: 진행 표시 1 / 3", str(st))
        expect(page.is_visible(".lh--step1 [data-lh-pick='platform'][data-lh-value='all']")
               and page.is_visible("[data-lh-pick='price'][data-lh-value='free']"),
               "Step 1: 플랫폼(전체·PC·모바일) + 가격(전체·무료만) 선택지", "")
        expect(len(page.query_selector_all("[data-lh-pick='platform']")) == 3
               and len(page.query_selector_all("[data-lh-pick='price']")) == 2,
               "Step 1: 선택지 개수 3 + 2", "")
        expect(checked(page, "platform") == "all" and checked(page, "price") == "all",
               "Step 1: 기본 선택 = 전체 / 전체", f"{checked(page, 'platform')}/{checked(page, 'price')}")
        nav1 = page.inner_text(".lh-wizard-nav").replace("\n", " ")
        expect("분야 선택" in nav1 and "다음" in nav1, "Step 1: `← 분야 선택` / `다음 →` 버튼", nav1)

        page.click("[data-lh-pick='platform'][data-lh-value='pc']")
        page.wait_for_timeout(200)
        page.click("[data-lh-pick='price'][data-lh-value='free']")
        page.wait_for_timeout(200)
        expect(checked(page, "platform") == "pc" and checked(page, "price") == "free",
               "Step 1: PC · 무료만 선택이 반영", f"{checked(page, 'platform')}/{checked(page, 'price')}")
        page.click(".lh-wizard-nav [data-lh-goto='2']")
        page.wait_for_timeout(400)

        st = wizard_state(page)
        expect(st["step2"] and st["progress"] == "2 / 3", "Step 2: 진행 표시 2 / 3 · 소요 시간 화면", str(st))
        tiers = page.eval_on_selector_all(
            "[data-lh-pick='tier'] .lh-choice-label", "els => els.map((e) => e.textContent.trim())"
        )
        expect(len(tiers) == 3 and "1단계" in tiers[0] and "2단계" in tiers[1] and "3단계" in tiers[2],
               "Step 2: 1·2·3단계 카드", str(tiers))
        nav2 = page.inner_text(".lh-wizard-nav").replace("\n", " ")
        expect("이전" in nav2 and "다음" in nav2, "Step 2: `← 이전` / `다음 →` 버튼", nav2)
        page.click("[data-lh-pick='tier'][data-lh-value='2']")
        page.wait_for_timeout(400)

        st = wizard_state(page)
        expect(st["step2"] and st["progress"] == "2 / 3",
               "Step 2 카드 클릭만으로는 넘어가지 않고 선택만 반영", str(st))
        expect(checked(page, "tier") == "2" and page.is_visible("[data-lh-pick='tier'][data-lh-value='2'].is-on"),
               "Step 2: 고른 2단계 카드가 활성 하이라이트", checked(page, "tier"))
        page.click(".lh-wizard-nav [data-lh-goto='3']")
        page.wait_for_timeout(400)

        st = wizard_state(page)
        expect(st["step3"] and st["progress"] == "3 / 3", "Step 2 `다음` 클릭 → Step 3 이동", str(st))
        expect("PC" in st["summary"] and "무료만" in st["summary"] and "2단계" in st["summary"],
               "Step 3: 고른 조건 요약(PC · 무료만 · 2단계)", st["summary"])
        expected_count = len(pool("pc", "free", "all", 2))
        expect(f"목표 {expected_count}개" in st["count"], f"Step 3: 후보 수 `목표 {expected_count}개`", st["count"])
        diffs = page.eval_on_selector_all(
            "[data-lh-pick='difficulty'] .lh-choice-label", "els => els.map((e) => e.textContent.trim())"
        )
        expect(diffs == ["상관없이", "편안", "보통", "매운맛"], "Step 3: 난이도 4선택(상관없이·편안·보통·매운맛)", str(diffs))

        page.click("[data-lh-pick='difficulty'][data-lh-value='chill']")
        page.wait_for_timeout(300)
        st = wizard_state(page)
        expected_chill = len(pool("pc", "free", "chill", 2))
        expect(f"목표 {expected_chill}개" in st["count"],
               f"Step 3: 편안 선택 시 후보 {expected_chill}개로 갱신", st["count"])
        expect(page.is_visible("[data-lh-draw]"), "Step 3: `🚨 목표 받기` 버튼", "")
        if shots:
            page.screenshot(path=str(shots / f"{prefix}-step2-3-desktop.png"))

        page.click("[data-lh-draw]")
        page.wait_for_timeout(600)
        card = card_state(page)
        expect(card is not None, "Step 4: 목표 카드 발급", str(card))
        if card:
            chosen = (card["game"], int(card["tier"]), card["difficulty"]) if card["tier"] else None
            expect(chosen in pool("pc", "free", "chill", 2) if chosen else False,
                   "Step 4: 조건(PC·무료·2단계·편안)에 맞는 목표", str(chosen))
            expect(card["difficulty"] == "chill" and card["badge"] == "편안",
                   "Step 4: 난이도 배지 `편안`", f"{card['difficulty']}/{card['badge']}")
            quest = next(q for q in games[card["game"]]["quests"] if q["tier"] == 2 and q["difficulty"] == "chill")
            expect(card["title"] == quest["title_ko"], "Step 4: 2단계 퀘스트 제목이 데이터와 일치", card["title"])
            expect(card["tier"] == "2", "Step 4: 고른 2단계 퀘스트", card["tier"])
            expect(any("무료" in c for c in card["chips"]) and any("PC" in c for c in card["chips"]),
                   "Step 4: 가격·플랫폼 태그", str(card["chips"]))
            expect(card["locked"], "Step 4: 진행 중 표시(잠금 안내)", "")
        expect(page.query_selector("[data-lh-goto='pledge']") is None, "잠금 중에는 목표 탐색으로 돌아갈 수 없음", "")

        # 3) 새로고침 잠금 유지
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(700)
        after = card_state(page)
        expect(after is not None and after["game"] == card["game"] and after["title"] == card["title"],
               "새로고침 후 같은 게임·같은 퀘스트 유지", f"{card['game']} → {after and after['game']}")

        # 4) 5초 광고 건너뛰기 → 랜딩 복귀
        page.click("[data-lh-ad]")
        page.wait_for_timeout(400)
        expect(page.is_visible("#lhAdBackdrop"), "광고 슬롯 모달 열림", "")
        expect(page.eval_on_selector("#lhAdSkip", "e => e.disabled"), "5초 전 건너뛰기 잠금", "")
        page.wait_for_timeout(4800)
        expect(not page.eval_on_selector("#lhAdSkip", "e => e.disabled"), "5초 뒤 건너뛰기 해금", "")
        page.click("#lhAdSkip")
        page.wait_for_timeout(500)
        expect(page.query_selector(".lh-card") is None and wizard_state(page)["landing"],
               "건너뛰면 목표 카드가 비고 랜딩으로", "")
        expect(page.query_selector("#lhHistory") is None, "건너뛰기는 완료 기록을 남기지 않음", "")

        # 5) 완료 기록 누적
        enter_wizard(page, "서약(건너뛰기 뒤 재진입)")
        expect(checked(page, "platform") == "pc" and checked(page, "price") == "free",
               "조건은 건너뛰기 뒤에도 유지", f"{checked(page, 'platform')}/{checked(page, 'price')}")
        page.click(".lh-wizard-nav [data-lh-goto='2']")
        page.wait_for_timeout(300)
        page.click(".lh-wizard-nav [data-lh-goto='3']")
        page.wait_for_timeout(300)
        page.click("[data-lh-draw]")
        page.wait_for_timeout(500)
        done_game = card_state(page)["game"]
        page.click("[data-lh-complete]")
        page.wait_for_timeout(500)
        expect(wizard_state(page)["landing"], "완료 후 랜딩으로 복귀", "")
        hist = page.inner_text("#lhHistory").replace("\n", " ")
        expect("누적 완료 1" in hist, "완료 기록 1건 누적", hist[:120])
        expect(index[done_game]["name"] in hist, "기록에 완료한 게임 이름", hist[:120])
        expect(page.is_visible(".lh-catalog-banner"), "완료 기록 아래 카탈로그 배너 유지", "")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(600)
        hist = page.inner_text("#lhHistory").replace("\n", " ")
        expect("누적 완료 1" in hist, "새로고침 후에도 완료 기록 유지", hist[:100])
        enter_wizard(page, "서약(새로고침 뒤 재진입)")
        page.click(".lh-wizard-nav [data-lh-goto='2']")
        page.wait_for_timeout(300)
        page.click(".lh-wizard-nav [data-lh-goto='3']")
        page.wait_for_timeout(300)
        page.click("[data-lh-draw]")
        page.wait_for_timeout(500)
        page.click("[data-lh-complete]")
        page.wait_for_timeout(500)
        hist = page.inner_text("#lhHistory").replace("\n", " ")
        expect("누적 완료 2" in hist, "완료 기록이 2건으로 누적", hist[:100])

        # 6) 난이도 필터 — 세 난이도 각각 새 컨텍스트에서 확인
        for diff, label in (("chill", "편안"), ("normal", "보통"), ("hardcore", "매운맛")):
            dctx, dp = pages.open()
            dp.goto(base + "?domain=lighthouse", wait_until="networkidle")
            dp.wait_for_timeout(600)
            enter_wizard(dp, f"서약(난이도 {label})")
            dp.click(".lh-wizard-nav [data-lh-goto='2']")
            dp.wait_for_timeout(250)
            dp.click(".lh-wizard-nav [data-lh-goto='3']")
            dp.wait_for_timeout(250)
            dp.click(f"[data-lh-pick='difficulty'][data-lh-value='{diff}']")
            dp.wait_for_timeout(300)
            n_expected = len(pool("all", "all", diff, 1))
            txt = dp.inner_text(".lh-count")
            expect(f"목표 {n_expected}개" in txt, f"난이도 {label}: 후보 {n_expected}개", txt)
            dp.click("[data-lh-draw]")
            dp.wait_for_timeout(500)
            dc = card_state(dp)
            expect(dc is not None and dc["difficulty"] == diff and dc["badge"] == label,
                   f"난이도 {label}: 발급된 게임 난이도 일치", str(dc))
            dctx.close()

        # 7) 모바일+무료+매운맛 조합 (딥링크 파라미터)
        mctx, mp = pages.open()
        mp.goto(base + "?domain=lighthouse&lh_cat=game&lh_platform=mobile&lh_price=free&lh_diff=hardcore&lh_tier=3",
                wait_until="networkidle")
        mp.wait_for_timeout(600)
        enter_wizard(mp, "서약(딥링크)")
        expect(checked(mp, "platform") == "mobile" and checked(mp, "price") == "free",
               "딥링크: lh_platform·lh_price 가 위저드에 반영", f"{checked(mp, 'platform')}/{checked(mp, 'price')}")
        mp.click(".lh-wizard-nav [data-lh-goto='2']")
        mp.wait_for_timeout(300)
        expect(checked(mp, "tier") == "3", "딥링크: lh_tier 가 반영", checked(mp, "tier"))
        mp.click(".lh-wizard-nav [data-lh-goto='3']")
        mp.wait_for_timeout(300)
        expect(checked(mp, "difficulty") == "hardcore", "딥링크: lh_diff 가 반영", checked(mp, "difficulty"))
        n_mobile = len(pool("mobile", "free", "hardcore", 3))
        expect(f"목표 {n_mobile}개" in mp.inner_text(".lh-count"),
               f"모바일+무료+매운맛 후보 {n_mobile}개", mp.inner_text(".lh-count"))
        mp.click("[data-lh-draw]")
        mp.wait_for_timeout(500)
        mc = card_state(mp)
        expect(mc is not None and (mc["game"], int(mc["tier"] or 0), mc["difficulty"]) in pool("mobile", "free", "hardcore", 3),
               "모바일+무료+매운맛에서도 목표 발급", str(mc))
        mctx.close()

        # 7-1) 후보 0종 조합 — 버튼 비활성 + 이유 안내 (데이터를 잠시 좁혀 UI 경로만 확인)
        zctx, zp = pages.open()
        zp.goto(base + "?domain=lighthouse&lh_platform=mobile&lh_price=free", wait_until="networkidle")
        zp.wait_for_timeout(700)
        zp.evaluate(
            "() => { window.Pharos.state.lh.data.games = []; }"
        )
        enter_wizard(zp, "서약(후보 0종)")
        zp.click(".lh-wizard-nav [data-lh-goto='2']")
        zp.wait_for_timeout(300)
        zp.click(".lh-wizard-nav [data-lh-goto='3']")
        zp.wait_for_timeout(400)
        zero_count = zp.inner_text(".lh-count")
        zero_disabled = zp.eval_on_selector("[data-lh-draw]", "e => e.disabled")
        zero_hint = zp.inner_text(".lh-panel").replace("\n", " ")
        expect("목표가 없습니다" in zero_count and zero_disabled and "플랫폼" in zero_hint,
               "후보 0종: 후보 수 0 안내 + 목표 받기 비활성 + 이유 문구", f"{zero_count} / disabled={zero_disabled}")
        zctx.close()

        # 8) 기존 카탈로그 딥링크 회귀
        page.goto(base + "?domain=catalog", wait_until="networkidle")
        page.wait_for_timeout(700)
        expect(page.is_visible("#homeSearch") and active_tab(page) == "🧭 전체 탐색",
               "회귀: ?domain=catalog → 전체 탐색", page.url)
        page.goto(base + "?arena=action-roguelike", wait_until="networkidle")
        page.wait_for_timeout(900)
        expect(page.inner_text("#view h1").strip() == arena_labels["action-roguelike"],
               "회귀: ?arena=action-roguelike → 비교군", page.inner_text("#view h1"))
        page.goto(base + "?item=balatro", wait_until="networkidle")
        page.wait_for_timeout(1100)
        expect(page.eval_on_selector("#modalBackdrop", "e => !e.hidden")
               and page.inner_text("#modalTitle").strip() == index["balatro"]["name"],
               "회귀: ?item=balatro → 상세 모달", page.inner_text("#modalTitle"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # 9) EN 전환
        enctx, en = pages.open(locale="en-US")
        en.goto(base + "?lang=en", wait_until="networkidle")
        en.wait_for_timeout(800)
        expect(en.evaluate("document.documentElement.lang") == "en", "EN: <html lang=en>", "")
        expect(en.is_visible(".lh--landing"), "EN: 랜딩이 등대로", en.url)
        en_title = en.inner_text(".lh-landing-title").replace("\n", " ")
        expect("One masterpiece." in en_title and "One real goal." in en_title,
               "EN: `One masterpiece. One real goal.`", en_title)
        expect("Find a goal" in en.inner_text("[data-lh-goto='pledge']"), "EN: `Find a goal` CTA", "")
        expect(not korean_left(en), "EN: 랜딩 한글 잔존 0건", str(korean_left(en)[:3]))
        en.click("[data-lh-goto='pledge']")
        en.wait_for_timeout(400)
        expect(en.is_visible(".lh--pledge"), "EN: 항해 서약 화면", "")
        expect(not korean_left(en), "EN: 항해 서약 한글 0건", str(korean_left(en)[:3]))
        expect(en.inner_text(".lh-pledge-go").strip() == "Take the Oath", "EN: `Take the Oath`", en.inner_text(".lh-pledge-go"))
        en.click(".lh-pledge-check")
        en.wait_for_timeout(150)
        en.click("[data-lh-oath]")
        en.wait_for_timeout(400)
        expect(en.is_visible(".lh--category"), "EN: 분야 선택 화면", "")
        expect(not korean_left(en), "EN: 분야 선택 한글 0건", str(korean_left(en)[:3]))
        en.click("[data-lh-cat='game']")
        en.wait_for_timeout(400)
        expect(not korean_left(en), "EN: Step 1 한글 0건", str(korean_left(en)[:3]))
        en.click(".lh-wizard-nav [data-lh-goto='2']")
        en.wait_for_timeout(300)
        en.click(".lh-wizard-nav [data-lh-goto='3']")
        en.wait_for_timeout(300)
        en.click("[data-lh-pick='difficulty'][data-lh-value='hardcore']")
        en.wait_for_timeout(300)
        expect("goals match" in en.inner_text(".lh-count"), "EN: 후보 수 문구", en.inner_text(".lh-count"))
        en.click("[data-lh-draw]")
        en.wait_for_timeout(500)
        ec = card_state(en)
        expect(ec is not None and ec["badge"] == "Spicy", "EN: 난이도 배지 `Spicy`", str(ec))
        expect(not korean_left(en), "EN: 결과 카드 한글 0건", str(korean_left(en)[:3]))
        enctx.close()

        # 10) KO ↔ EN 토글
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(600)
        page.click('#langToggle [data-lang="en"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(600)
        expect(page.evaluate("document.documentElement.lang") == "en"
               and "One masterpiece." in page.inner_text(".lh-landing-title").replace("\n", " "),
               "KO → EN 토글이 같은 화면을 영문으로 다시 연다", page.url)
        page.click('#langToggle [data-lang="ko"]')
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(600)
        expect(page.evaluate("document.documentElement.lang") == "ko"
               and "지금 해볼 만한 명작" in page.inner_text(".lh-landing-title").replace("\n", " "),
               "EN → KO 토글 복귀", page.url)

        # 11) 390px 모바일
        moctx, mobile = pages.open(viewport=(390, 844))
        mobile.goto(base, wait_until="networkidle")
        mobile.wait_for_timeout(800)
        expect(overflow(mobile) == 0, "390px Step 0 가로 넘침 0", str(overflow(mobile)))
        tab_fit = mobile.eval_on_selector("#domainTabs", "e => ({ sw: e.scrollWidth, cw: e.clientWidth })")
        expect(tab_fit["sw"] <= tab_fit["cw"] + 1, "390px 상단 탭 줄바꿈·가로 넘침 없음", str(tab_fit))
        mobile.click("[data-lh-goto='pledge']")
        mobile.wait_for_timeout(400)
        expect(page.is_visible(".lh--pledge") or mobile.is_visible(".lh--pledge"), "390px: 항해 서약 화면", "")
        expect(overflow(mobile) == 0, "390px 항해 서약 가로 넘침 0", str(overflow(mobile)))
        mobile.click(".lh-pledge-check")
        mobile.wait_for_timeout(150)
        mobile.click("[data-lh-oath]")
        mobile.wait_for_timeout(400)
        expect(mobile.is_visible(".lh--category"), "390px: 분야 선택 화면", "")
        expect(overflow(mobile) == 0, "390px 분야 선택 가로 넘침 0", str(overflow(mobile)))
        mobile.click("[data-lh-cat='game']")
        mobile.wait_for_timeout(400)
        expect(overflow(mobile) == 0, "390px Step 1 가로 넘침 0", str(overflow(mobile)))
        mobile.click(".lh-wizard-nav [data-lh-goto='2']")
        mobile.wait_for_timeout(300)
        expect(overflow(mobile) == 0, "390px Step 2 가로 넘침 0", str(overflow(mobile)))
        mobile.click("[data-lh-pick='tier'][data-lh-value='1']")
        mobile.wait_for_timeout(400)
        expect(overflow(mobile) == 0, "390px Step 2 선택 후 가로 넘침 0", str(overflow(mobile)))
        mobile.click(".lh-wizard-nav [data-lh-goto='3']")
        mobile.wait_for_timeout(400)
        expect(overflow(mobile) == 0, "390px Step 3 가로 넘침 0", str(overflow(mobile)))
        mobile.click("[data-lh-pick='difficulty'][data-lh-value='normal']")
        mobile.wait_for_timeout(250)
        mobile.click("[data-lh-draw]")
        mobile.wait_for_timeout(600)
        expect(overflow(mobile) == 0, "390px Step 4 카드 가로 넘침 0", str(overflow(mobile)))
        expect(mobile.is_visible("[data-lh-complete]") and mobile.is_visible("[data-lh-ad]"),
               "390px 카드 액션 접근 가능", "")
        mobile.wait_for_timeout(3400)  # 발급 토스트가 사라진 뒤 카드만 담는다
        if shots:
            mobile.screenshot(path=str(shots / f"{prefix}-result-mobile.png"))
        mobile.click("[data-lh-detail]")
        mobile.wait_for_timeout(900)
        expect(mobile.eval_on_selector("#modalBackdrop", "e => !e.hidden"), "390px 게임 상세 모달 열림", "")
        mobile.keyboard.press("Escape")
        mobile.wait_for_timeout(400)
        mobile.click(".brand")
        mobile.wait_for_timeout(400)
        mobile.click('#domainTabs button[data-action="catalog"]')
        mobile.wait_for_timeout(700)
        expect(overflow(mobile) == 0 and mobile.is_visible("#homeSearch"), "390px 카탈로그 회귀", str(overflow(mobile)))
        moctx.close()

        # GitHub Pages 가 아이콘 한 장에 일시적으로 503 을 주는 경우가 있다(2026-11-26·27 관측).
        # 상태 코드만으로 실패시키지 않고 같은 URL 을 한 번 더 조회해 200 이면 넘긴다.
        for item in list(bad_http):
            status, _, url = item.partition(" ")
            if status == "503" and "/assets/" in url:
                try:
                    if page.request.get(url).status == 200:
                        bad_http.remove(item)
                except Exception:  # noqa: BLE001 - 재조회 실패는 원래 오류로 남긴다
                    pass
        expect(not errors, "콘솔 오류·페이지 예외 0건", "; ".join(errors[:3]))
        expect(not bad_http, "HTTP 4xx/5xx 0건", "; ".join(bad_http[:3]))
        browser.close()
    if httpd:
        httpd.shutdown()

    passed = sum(1 for _l, ok, _e in RESULTS if ok)
    print("=" * 78)
    print(f"결과: {passed}/{len(RESULTS)} PASS · 등대 {counts['games']}종·목표 {counts['quests']}개 "
          f"(무료 {counts['free_to_play']}) · 카탈로그 {total_items:,}건")
    print("=" * 78)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
