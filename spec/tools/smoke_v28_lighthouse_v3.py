#!/usr/bin/env python3
"""파로스 v28 등대 v3 스모크 — 4분야(게임·애니·영화·만화) + 전체 랜덤 · 리롤 잠금 · KO/EN · 390px.

무엇을 확인하는가
  1) 데이터 계약 — 게임 64종/125목표 유지 + 애니·영화·만화 각 25종/40목표 이상,
     모든 id 가 search-index.json 의 실제 카탈로그 항목과 일치(도메인·카테고리·비교군),
     분야마다 단계 × 난이도 9조합 모두 후보 2개 이상, KO/EN 필드 완비·EN 한글 0.
  2) 분야 선택 화면 — 🎮 게임 · 📺 애니 · 🎬 영화 · 📖 만화 · 🎲 상관없이 다섯 카드.
  3) 흐름 — 게임은 1/3(플랫폼·가격) → 2/3(시간) → 3/3(난이도) → 카드,
     애니·영화·만화·상관없이는 1/2(분량/시간) → 2/2(무게감) → 카드. 플랫폼·가격 단계가 없다.
  4) 결과 카드 — 분야 배지(🎮/📺/🎬/📖)와 목표 문구·소요 시간·난이도·상세 링크·완료·5초 광고 건너뛰기.
  5) 리롤 잠금 — 분야와 상관없이 등대 전체에서 current 는 하나. 새로고침·분야 이동에도 그대로.
  6) EN 전환 각 단계 한글 0건 · 390px 가로 넘침 0건 · 콘솔/HTTP 오류 0건 · 스크린샷 2장.

사용
  python3 projects/pharos/scripts/smoke_v28_lighthouse_v3.py
  python3 projects/pharos/scripts/smoke_v28_lighthouse_v3.py --live --shots-dir projects/pharos/live
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
CATEGORIES = ("game", "anime", "movie", "manga", "all")
MEDIA = ("anime", "movie", "manga")
CAT_LABEL = {
    "game": "🎮 게임",
    "anime": "📺 애니",
    "movie": "🎬 영화",
    "manga": "📖 만화",
    "all": "🎲 상관없이",
}
DIFF_LABEL = {"chill": "편안", "normal": "보통", "hardcore": "매운맛"}


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
        if (re.test(document.title)) out.add('title: ' + document.title);
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
          item: card.dataset.lhItem || card.dataset.lhGame,
          category: card.dataset.lhCategoryView,
          difficulty: card.dataset.lhDifficulty,
          badge: card.querySelector('.lh-diff')?.innerText || '',
          kind: card.querySelector('.lh-cat-badge')?.innerText.trim() || '',
          title: card.querySelector('.lh-quest-title')?.innerText || '',
          tier: card.querySelector('.lh-quest')?.dataset.lhTierView || '',
          chips: [...card.querySelectorAll('.lh-chip')].map((e) => e.innerText.trim()),
          locked: !!card.querySelector('.lh-locked'),
          detail: card.querySelector('[data-lh-detail]')?.dataset.lhDetail || '',
          hasAd: !!card.querySelector('[data-lh-ad]'),
          hasComplete: !!card.querySelector('[data-lh-complete]'),
        };
      }"""
    )


def checked(page, group: str) -> str:
    el = page.query_selector(f'[data-lh-pick="{group}"][aria-checked="true"]')
    return el.get_attribute("data-lh-value") if el else ""


def progress(page) -> str:
    el = page.query_selector(".lh-progress-text")
    return el.text_content().strip() if el else ""


def enter_target(page, category: str, label: str = "") -> None:
    """랜딩 → 서약(체크·서약) → 분야 카드 클릭."""
    if page.query_selector(".lh--landing"):
        page.click("[data-lh-goto='pledge']")
        page.wait_for_timeout(350)
    page.click(".lh-pledge-check")
    page.wait_for_timeout(120)
    page.click("[data-lh-oath]")
    page.wait_for_timeout(350)
    if page.query_selector(".lh--category"):
        page.click(f"[data-lh-cat='{category}']")
        page.wait_for_timeout(400)
    expect(page.query_selector(".lh--pledge") is None, f"{label} 서약 화면을 벗어남", "")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args, **kwargs):
        return


def serve(root: Path):
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


class Pages:
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
    prefix = args.shot_prefix or ("live-v28" if args.live else "local-v28")
    shots = Path(args.shots_dir) if args.shots_dir else None
    if shots:
        shots = shots if shots.is_absolute() else (ROOT.parent.parent / shots).resolve()
        shots.mkdir(parents=True, exist_ok=True)

    lh = json.loads((WEB_ROOT / "data" / "lighthouse-quests.json").read_text(encoding="utf-8"))
    index = {
        row["id"]: row
        for row in json.loads((WEB_ROOT / "data" / "search-index.json").read_text(encoding="utf-8"))["items"]
    }
    counts = lh["counts"]
    games = {row["game_id"]: row for row in lh["games"]}
    media = {cat: {row["item_id"]: row for row in lh["media"][cat]} for cat in MEDIA}
    cat_meta = {row["id"]: row for row in lh["categories"]}

    def entries(category: str = "all"):
        out = []
        if category in ("all", "game"):
            for row in lh["games"]:
                out.append(("game", row["game_id"], row))
        for cat in MEDIA:
            if category in ("all", cat):
                for row in lh["media"][cat]:
                    out.append((cat, row["item_id"], row))
        return out

    def pool(category: str, tier: int, difficulty: str, platform: str = "all", price: str = "all"):
        out = set()
        for cat, item_id, row in entries(category):
            if category == "game":
                if price == "free" and not row["free_to_play"]:
                    continue
                if platform != "all" and platform not in row["platforms"]:
                    continue
            for quest in row["quests"]:
                if quest["tier"] != tier:
                    continue
                if difficulty != "all" and quest["difficulty"] != difficulty:
                    continue
                out.add((item_id, quest["tier"], quest["difficulty"]))
        return out

    # ---------------------------------------------------------------- 1) 데이터 계약
    expect(lh["schema_version"] == "3.0.0", "데이터: 등대 스키마 v3.0.0", lh["schema_version"])
    expect([row["id"] for row in lh["categories"]] == list(CATEGORIES),
           "데이터: 분야 메타 = 게임·애니·영화·만화·전체", str([row["id"] for row in lh["categories"]]))
    expect(len(games) == 64 and counts["by_category"]["game"]["quests"] == 125,
           "데이터: 기존 게임 64종 · 목표 125개 그대로 유지", str(counts["by_category"]["game"]))
    for cat in MEDIA:
        rows = media[cat]
        quests = sum(len(row["quests"]) for row in rows.values())
        expect(len(rows) == 25 and quests >= 40,
               f"데이터: {cat} 25종 · 목표 {quests}개(40개 이상)", f"{len(rows)}종/{quests}개")
        bad_ids = [iid for iid in rows if iid not in index or index[iid].get("domain") != "media"
                   or index[iid].get("category") != cat]
        expect(not bad_ids, f"데이터: {cat} 모든 item_id 가 카탈로그 media/{cat} 항목과 일치", str(bad_ids[:4]))
    expect(all(row["game_id"] in index and index[row["game_id"]].get("domain") == "game" for row in lh["games"]),
           "데이터: 게임 game_id 전부 카탈로그 game 항목", "")
    expect(counts["items"] == len(games) + sum(len(media[c]) for c in MEDIA) and counts["items"] >= 120,
           f"데이터: 등대 작품 {counts['items']}종(게임 64 + 미디어 75)", str(counts["items"]))

    empty_combos = []
    for cat in CATEGORIES:
        for tier in (1, 2, 3):
            for diff in ("chill", "normal", "hardcore"):
                if len(pool(cat, tier, diff)) < 2:
                    empty_combos.append((cat, tier, diff, len(pool(cat, tier, diff))))
    expect(not empty_combos, "데이터: 분야마다 단계(1~3) × 난이도(3) 9조합 모두 후보 2개 이상", str(empty_combos[:4]))

    leaks = []
    for cat, item_id, row in entries():
        for quest in row["quests"]:
            for field in ("title_en", "desc_en", "tip_en", "est_time_en"):
                if KOREAN.search(str(quest.get(field) or "")):
                    leaks.append((item_id, field))
            for field in ("title_ko", "desc_ko", "tip_ko", "est_time_ko"):
                if not str(quest.get(field) or "").strip():
                    leaks.append((item_id, field, "빈 값"))
    expect(not leaks, "데이터: 271개 목표 KO/EN 8필드 완비 · EN 한글 0건", str(leaks[:3]))
    expect(all(KOREAN.search(cat_meta[c]["label_ko"]) is not None and not KOREAN.search(cat_meta[c]["label_en"])
               for c in CATEGORIES), "데이터: 분야 라벨 KO/EN 완비", "")

    errors: list[str] = []
    bad_http: list[str] = []

    with sync_playwright() as p:
        launch = {"executable_path": args.chrome} if args.chrome else {}
        browser = p.chromium.launch(**launch)
        pages = Pages(browser, errors, bad_http)
        ctx, page = pages.open()
        page.goto(base + "?lang=ko", wait_until="networkidle")
        page.wait_for_timeout(700)

        # ------------------------------------------------------------ 2) 분야 선택
        page.click("[data-lh-goto='pledge']")
        page.wait_for_timeout(350)
        page.click(".lh-pledge-check")
        page.wait_for_timeout(120)
        page.click("[data-lh-oath]")
        page.wait_for_timeout(400)
        expect(page.is_visible(".lh--category"), "분야 선택: 서약 뒤 분야 화면", "")
        labels = page.eval_on_selector_all("[data-lh-cat] .lh-cat-label", "els => els.map(e => e.textContent.trim())")
        expect(labels == [CAT_LABEL[c] for c in CATEGORIES], "분야 선택: 다섯 카드(🎮·📺·🎬·📖·🎲) 순서", str(labels))
        expect(not page.query_selector(".lh-progress-text"), "분야 선택: 진행 표시(1/3)를 쓰지 않는다", "")
        expect(len(page.query_selector_all("[data-lh-cat]")) == 5, "분야 선택: 카드 5장", str(len(page.query_selector_all("[data-lh-cat]"))))
        if shots:
            page.screenshot(path=str(shots / f"{prefix}-lighthouse-v3-category.png"))

        # ------------------------------------------------------------ 3) 🎮 게임 흐름
        page.click("[data-lh-cat='game']")
        page.wait_for_timeout(400)
        expect(page.is_visible(".lh--step1") and progress(page) == "1 / 3", "게임: 1/3 플랫폼·가격", progress(page))
        expect(len(page.query_selector_all("[data-lh-pick='platform']")) == 3
               and len(page.query_selector_all("[data-lh-pick='price']")) == 2, "게임: 플랫폼 3 · 가격 2 선택지", "")
        page.click("[data-lh-pick='platform'][data-lh-value='all']")
        page.wait_for_timeout(120)
        page.click("[data-lh-pick='price'][data-lh-value='all']")
        page.wait_for_timeout(120)
        page.click(".lh-wizard-nav [data-lh-goto='2']")
        page.wait_for_timeout(300)
        expect(page.is_visible(".lh--step2") and progress(page) == "2 / 3", "게임: 2/3 소요 시간", progress(page))
        page.click("[data-lh-pick='tier'][data-lh-value='2']")
        page.wait_for_timeout(150)
        page.click(".lh-wizard-nav [data-lh-goto='3']")
        page.wait_for_timeout(300)
        expect(page.is_visible(".lh--step3") and progress(page) == "3 / 3", "게임: 3/3 난이도", progress(page))
        expect(f"목표 {len(pool('game', 2, 'all'))}개" in page.inner_text(".lh-count"),
               "게임: 후보 수가 데이터와 일치", page.inner_text(".lh-count"))
        page.click("[data-lh-pick='difficulty'][data-lh-value='normal']")
        page.wait_for_timeout(200)
        expect(f"목표 {len(pool('game', 2, 'normal'))}개" in page.inner_text(".lh-count"),
               "게임: 난이도 선택이 후보 수를 좁힌다", page.inner_text(".lh-count"))
        page.click("[data-lh-draw]")
        page.wait_for_timeout(500)
        state = card_state(page)
        expect(state is not None and state["category"] == "game", "게임: 결과 카드 발급", str(state))
        expect(state and state["kind"] == CAT_LABEL["game"], "게임: 결과 카드 배지 `🎮 게임`", state and state["kind"])
        expect(state and (state["item"], 2, "normal") in pool("game", 2, "normal"), "게임: 조건에 맞는 목표", str(state))
        expect(state and state["title"] == next(q for q in games[state["item"]]["quests"]
                                               if q["tier"] == 2 and q["difficulty"] == "normal")["title_ko"],
               "게임: 목표 문구가 데이터와 일치", state and state["title"])
        expect(state and state["hasComplete"] and state["hasAd"] and state["detail"] == state["item"],
               "게임: 완료·광고·상세 링크", str(state))

        # 리롤 잠금 — 새로고침해도 같은 목표 하나
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(700)
        after = card_state(page)
        expect(after is not None and after["item"] == state["item"] and after["title"] == state["title"],
               "잠금: 새로고침 후에도 같은 목표", f"{state['item']} → {after and after['item']}")
        stored = page.evaluate("() => JSON.parse(localStorage.getItem('pharos_lighthouse_state_v1') || '{}')")
        expect(isinstance(stored.get("current"), dict) and stored["current"].get("item_id") == state["item"]
               and stored.get("version") == 3, "잠금: localStorage current 는 하나(v3)", str(stored.get("current"))[:120])
        expect(page.query_selector("[data-lh-goto='pledge']") is None
               and page.query_selector("[data-lh-cat]") is None, "잠금: 잠긴 동안 분야·목표 탐색 진입 불가", "")
        page.click("[data-lh-complete]")
        page.wait_for_timeout(500)
        expect(page.query_selector(".lh--landing") is not None, "완료: 랜딩 복귀", "")
        hist = page.inner_text("#lhHistory").replace("\n", " ")
        expect("누적 완료 1" in hist, "완료: 기록 1건", hist[:100])

        # ------------------------------------------------------------ 4) 📺 애니·🎬 영화·📖 만화
        for cat, tier, diff in (("anime", 2, "normal"), ("movie", 3, "hardcore"), ("manga", 1, "chill")):
            enter_target(page, cat, label=f"{cat}:")
            expect(page.is_visible(".lh--step1") and progress(page) == "1 / 2",
                   f"{cat}: 1/2 분량·시간(플랫폼·가격 없음)", progress(page))
            expect(not page.query_selector("[data-lh-pick='platform']") and not page.query_selector("[data-lh-pick='price']"),
                   f"{cat}: 플랫폼·가격 단계를 건너뛴다", "")
            tier_labels = page.eval_on_selector_all("[data-lh-pick='tier'] .lh-choice-label", "els => els.map(e => e.textContent.trim())")
            expect(len(tier_labels) == 3 and tier_labels[0] != "1단계 · 짧게",
                   f"{cat}: 분야별 단계 문구(게임과 다름)", str(tier_labels))
            page.click(f"[data-lh-pick='tier'][data-lh-value='{tier}']")
            page.wait_for_timeout(150)
            page.click(".lh-wizard-nav [data-lh-goto='2']")
            page.wait_for_timeout(300)
            expect(page.is_visible(".lh--step2") and progress(page) == "2 / 2", f"{cat}: 2/2 무게감", progress(page))
            expect(page.is_visible("[data-lh-draw]"), f"{cat}: 2/2 에 목표 받기 버튼", "")
            page.click("[data-lh-pick='difficulty'][data-lh-value='all']")
            page.wait_for_timeout(200)
            expect(f"목표 {len(pool(cat, tier, 'all'))}개" in page.inner_text(".lh-count"),
                   f"{cat}: 후보 수가 데이터와 일치({tier}단계·무게감 상관없이)", page.inner_text(".lh-count"))
            page.click(f"[data-lh-pick='difficulty'][data-lh-value='{diff}']")
            page.wait_for_timeout(200)
            expect(f"목표 {len(pool(cat, tier, diff))}개" in page.inner_text(".lh-count"),
                   f"{cat}: 무게감 선택이 후보 수를 좁힌다", page.inner_text(".lh-count"))
            if cat == "anime" and shots:
                page.screenshot(path=str(shots / f"{prefix}-lighthouse-v3-media-quest.png"))
            page.click("[data-lh-draw]")
            page.wait_for_timeout(500)
            state = card_state(page)
            expect(state is not None and state["category"] == cat, f"{cat}: 결과 카드 발급", str(state))
            expect(state and state["kind"] == CAT_LABEL[cat], f"{cat}: 결과 카드 배지 `{CAT_LABEL[cat]}`", state and state["kind"])
            expect(state and (state["item"], tier, diff) in pool(cat, tier, diff), f"{cat}: 조건에 맞는 목표", str(state))
            quest = media[cat][state["item"]]["quests"]
            expect(state and state["title"] == next(q for q in quest if q["tier"] == tier and q["difficulty"] == diff)["title_ko"],
                   f"{cat}: 목표 문구가 데이터와 일치", state and state["title"])
            expect(state and state["badge"] == DIFF_LABEL[diff], f"{cat}: 난이도 배지 `{DIFF_LABEL[diff]}`", state and state["badge"])
            page.click("[data-lh-detail]")
            page.wait_for_timeout(900)
            expect(page.eval_on_selector("#modalBackdrop", "e => !e.hidden")
                   and page.inner_text("#modalTitle").strip() == index[state["item"]]["name"],
                   f"{cat}: 작품 상세 모달", page.inner_text("#modalTitle") if page.query_selector("#modalTitle") else "")
            page.keyboard.press("Escape")
            page.wait_for_timeout(350)
            page.click("[data-lh-complete]")
            page.wait_for_timeout(400)

        # ------------------------------------------------------------ 5) 🎲 전체 랜덤
        enter_target(page, "all", label="전체 랜덤:")
        expect(progress(page) == "1 / 2" and page.inner_text(".lh-q").strip() == "가볍게, 아니면 길게?",
               "전체 랜덤: 1/2 시간·분량", page.inner_text(".lh-q"))
        page.click("[data-lh-pick='tier'][data-lh-value='1']")
        page.wait_for_timeout(150)
        page.click(".lh-wizard-nav [data-lh-goto='2']")
        page.wait_for_timeout(300)
        page.click("[data-lh-pick='difficulty'][data-lh-value='all']")
        page.wait_for_timeout(200)
        expect(f"목표 {len(pool('all', 1, 'all'))}개" in page.inner_text(".lh-count"),
               "전체 랜덤: 네 분야 전체 후보 수", page.inner_text(".lh-count"))
        drawn = set()
        for attempt in range(12):
            if page.query_selector("[data-lh-draw]"):
                page.click("[data-lh-draw]")
                page.wait_for_timeout(350)
            state = card_state(page)
            if state:
                drawn.add(state["category"])
            page.click("[data-lh-ad]")
            page.wait_for_timeout(300)
            page.wait_for_timeout(5200)
            page.click("#lhAdSkip")
            page.wait_for_timeout(400)
            enter_target(page, "all", label="전체 랜덤:")
            page.click("[data-lh-pick='tier'][data-lh-value='1']")
            page.wait_for_timeout(120)
            page.click(".lh-wizard-nav [data-lh-goto='2']")
            page.wait_for_timeout(250)
            page.click("[data-lh-pick='difficulty'][data-lh-value='all']")
            page.wait_for_timeout(200)
            if len(drawn) >= 2:
                break
        expect(len(drawn) >= 2, "전체 랜덤: 여러 분야에서 목표가 나온다", str(sorted(drawn)))

        # 마지막 목표는 잠금 상태로 남겨 두고 EN·모바일을 본다
        if page.query_selector("[data-lh-draw]"):
            page.click("[data-lh-draw]")
            page.wait_for_timeout(400)
        state = card_state(page)
        expect(state is not None and state["category"] in ("game",) + MEDIA,
               "전체 랜덤: 목표 하나가 잠긴다", str(state and state["category"]))
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(700)
        again = card_state(page)
        expect(again is not None and again["item"] == state["item"], "전체 랜덤: 새로고침 후 같은 목표", "")
        page.click("[data-lh-complete]")
        page.wait_for_timeout(400)
        ctx.close()

        # ------------------------------------------------------------ 6) EN
        enctx, en = pages.open(locale="en-US")
        en.goto(base + "?lang=en", wait_until="networkidle")
        en.wait_for_timeout(700)
        expect(not korean_left(en), "EN: 랜딩 한글 0건", str(korean_left(en)[:3]))
        en.click("[data-lh-goto='pledge']")
        en.wait_for_timeout(350)
        en.click(".lh-pledge-check")
        en.wait_for_timeout(120)
        en.click("[data-lh-oath]")
        en.wait_for_timeout(400)
        expect(en.is_visible(".lh--category"), "EN: 분야 선택 화면", "")
        en_labels = en.eval_on_selector_all("[data-lh-cat] .lh-cat-label", "els => els.map(e => e.textContent.trim())")
        expect(en_labels == [cat_meta[c]["label_en"] for c in CATEGORIES], "EN: 분야 카드가 영문 메타와 일치", str(en_labels))
        expect(not korean_left(en), "EN: 분야 선택 한글 0건", str(korean_left(en)[:3]))
        en.click("[data-lh-cat='movie']")
        en.wait_for_timeout(400)
        expect(not korean_left(en), "EN: 영화 1/2 한글 0건", str(korean_left(en)[:3]))
        en.click(".lh-wizard-nav [data-lh-goto='2']")
        en.wait_for_timeout(350)
        expect("goals match" in en.inner_text(".lh-count"), "EN: 후보 수 문구", en.inner_text(".lh-count"))
        expect(not korean_left(en), "EN: 영화 2/2 한글 0건", str(korean_left(en)[:3]))
        en.click("[data-lh-draw]")
        en.wait_for_timeout(500)
        ec = card_state(en)
        expect(ec is not None and ec["kind"] == CAT_LABEL["movie"].split(" ", 1)[1] or (ec and "Movie" in ec["kind"]),
               "EN: 결과 카드 분야 배지", ec and ec["kind"])
        expect(not korean_left(en), "EN: 결과 카드 한글 0건", str(korean_left(en)[:3]))
        en.click("[data-lh-complete]")
        en.wait_for_timeout(300)
        enctx.close()

        # ------------------------------------------------------------ 7) 390px 모바일
        moctx, mobile = pages.open(viewport=(390, 844))
        mobile.goto(base + "?lang=ko", wait_until="networkidle")
        mobile.wait_for_timeout(700)
        mobile.click("[data-lh-goto='pledge']")
        mobile.wait_for_timeout(350)
        mobile.click(".lh-pledge-check")
        mobile.wait_for_timeout(120)
        mobile.click("[data-lh-oath]")
        mobile.wait_for_timeout(400)
        expect(mobile.is_visible(".lh--category"), "390px: 분야 선택 화면", "")
        expect(overflow(mobile) == 0, "390px 분야 선택 가로 넘침 0", str(overflow(mobile)))
        cards = mobile.eval_on_selector_all("[data-lh-cat]", "els => els.map(e => e.getBoundingClientRect().right)")
        expect(all(x <= 390 + 1 for x in cards), "390px: 분야 카드가 화면 안", str(cards))
        mobile.click("[data-lh-cat='anime']")
        mobile.wait_for_timeout(400)
        expect(overflow(mobile) == 0, "390px 애니 1/2 가로 넘침 0", str(overflow(mobile)))
        mobile.click("[data-lh-pick='tier'][data-lh-value='2']")
        mobile.wait_for_timeout(150)
        mobile.click(".lh-wizard-nav [data-lh-goto='2']")
        mobile.wait_for_timeout(300)
        expect(overflow(mobile) == 0, "390px 애니 2/2 가로 넘침 0", str(overflow(mobile)))
        mobile.click("[data-lh-pick='difficulty'][data-lh-value='normal']")
        mobile.wait_for_timeout(200)
        mobile.click("[data-lh-draw]")
        mobile.wait_for_timeout(500)
        expect(overflow(mobile) == 0, "390px 결과 카드 가로 넘침 0", str(overflow(mobile)))
        expect(mobile.is_visible("[data-lh-complete]") and mobile.is_visible("[data-lh-ad]"),
               "390px: 카드 액션 접근 가능", "")
        mobile.wait_for_timeout(3300)
        if shots:
            mobile.screenshot(path=str(shots / f"{prefix}-lighthouse-v3-media-mobile.png"))
        mobile.click(".brand")
        mobile.wait_for_timeout(400)
        expect(card_state(mobile) is not None, "390px: 로고로 돌아와도 잠긴 목표 유지", "")
        mobile.click("[data-lh-complete]")
        mobile.wait_for_timeout(400)
        moctx.close()

        for item in list(bad_http):
            status, _, url = item.partition(" ")
            if status == "503" and "/assets/" in url:
                try:
                    if page.request.get(url).status == 200:
                        bad_http.remove(item)
                except Exception:  # noqa: BLE001
                    pass
        expect(not errors, "콘솔 오류·페이지 예외 0건", "; ".join(errors[:3]))
        expect(not bad_http, "HTTP 4xx/5xx 0건", "; ".join(bad_http[:3]))
        browser.close()
    if httpd:
        httpd.shutdown()

    passed = sum(1 for _l, ok, _e in RESULTS if ok)
    print("=" * 78)
    print(f"결과: {passed}/{len(RESULTS)} PASS · 등대 {counts['items']}종/{counts['quests']}목표 "
          f"(게임 {counts['by_category']['game']['items']} · 애니 {counts['by_category']['anime']['items']} · "
          f"영화 {counts['by_category']['movie']['items']} · 만화 {counts['by_category']['manga']['items']})")
    print("=" * 78)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
