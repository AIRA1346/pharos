#!/usr/bin/env python3
"""파로스 정적 웹 v2 동작 검증 (Playwright + headless Chromium).

무엇을 검증하는가 — 4단 계층 개편(스키마 v0.4.0 · 카탈로그 · 분할 로딩) + v3 정보 계층 + v0.4.3 분야 확장 + v0.5.0 평가 배분
  0) 3단 정보 계층: (1) 홈·도메인 = 장르 이름 + 그 장르의 추천 항목 타일,
     (2) 비교군 화면 = 핵심만 남긴 목록 카드, (3) 상세 모달 = 3축 점수·필터·가격 티어까지 전부.
  1) 로드·계약: catalog.json·search-index.json·schema 를 읽고, 홈에서는 비교군 파일을 내려받지 않는다(지연 로딩).
     콘솔 에러·페이지 예외·HTTP 4xx/5xx 0건, 모든 요청이 web/ 배포 루트 안에서 해결됨.
  2) 홈 쇼케이스: 장르 블록 9개(카탈로그 순서)에 그 장르의 추천/조건부 3~4개가 공식 아이콘(40px+)·이름·
     판정 배지·가중 점수 타일로 바로 보이고, 타일 클릭 = 상세 모달, 장르 헤더·'전체 N종 비교 →' = 비교군 이동.
     '별점은 높은데 거름 판정' 리포트(Hero Wars 4.6★ vs 38.0, Archero 4.2★ vs 58.25, Microsoft To Do 4.6★ vs 66.75,
     Clash Royale 4.0★ vs 61.0 — 거름(avoid)만), 통합 검색(이름·별칭·키워드), 보관함 섹션.
  3) 4단 탐색: 홈 → 도메인(앱·게임·AI 도구) → 대분류 → 비교군 → 항목. 도메인·대분류 화면도 장르별 추천 타일로 시작하고,
     비교군을 바꾸면 그 파일만 지연 로딩되며 요약(추천/조건부/거름·평균)은 같은 비교군 안에서만 재계산된다.
  4) 첫 화면 경량화: 히어로는 250px 이내, 기본 '균형 기본' 프리셋, 가중치·하드 필터·엄격 모드는 '내 기준 미세조정' 드로어 안.
  5) 1:1 비교: 같은 비교군 2~3개 체크 → 비교 표(점수·축·필터·별점·수명 단계·신선도), 4개째는 차단.
  6) 상세: 신선도(180일), 사실(Fact)과 의견(Opinion) 분리, 3축 점수·티어·필터 목록은 모달에만, 같은 비교군 대체제 링크,
     공유 요약 복사, 정정 제보 링크, 보관함 담기.
  7) URL 딥링크(domain·category·arena·item·compare·preset), 북마크(localStorage) 지속, 방법론 모달.
  8) 엔진 단위 테스트(가중 평균·6단 규칙·엄격/완화·완결작 면제·compat_risk·신선도·대체제·요약 텍스트).
  9) 공식 아이콘(v2.1): 57종 아이콘 파일이 모두 실제 이미지로 로드되고, 카드 44~48px·상세 52~56px·
     비교표 32px·추천 타일 40px+·갭 리포트·검색 결과에 object-fit: cover 둥근 사각형으로 들어가며,
     로드 실패 시 이니셜 배지로 대체된다.
  10) v0.4.3 분야 확장: 새 대분류 2개(인터넷 · 프라이버시 · 대화 · 리서치)와 새 비교군 3개
     (웹 브라우저·클라우드 스토리지·AI 어시스턴트)의 목록·요약·상세, AI 탭의 두 비교군 전환, 신규 15종 아이콘 192×192 로드.
  11) 스크린샷: preview-v3-home.png · preview-v3-arena.png · preview-v3-compare.png · preview-v3-mobile.png.

실행:
  pip install playwright
  python3 -m playwright install chromium   # 또는 CHROME_PATH 로 실행 파일 지정
  python3 projects/pharos/web/tests/verify_ui.py [--shots-dir DIR]

환경 변수 CHROME_PATH 가 있으면 그 실행 파일을 쓴다. 시스템에 Chromium 의 공유 라이브러리
(libnspr4·libnss3 등)가 없으면 LD_LIBRARY_PATH 로 해당 라이브러리 경로를 지정한다.
종료 코드 0 = 전부 통과.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import socketserver
import sys
import threading
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

WEB_ROOT = Path(__file__).resolve().parents[1]  # projects/pharos/web — 배포 단위 그대로
RESULTS: list[tuple[str, bool, str]] = []


def expect(condition: bool, label: str, extra: str = "") -> None:
    RESULTS.append((label, bool(condition), str(extra)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D401 - 조용한 서버
        pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_server() -> tuple[str, Server]:
    httpd = Server(("127.0.0.1", 0), functools.partial(Handler, directory=str(WEB_ROOT)))
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{base}/index.html", timeout=1).read(1)
            break
        except Exception:
            pass
    return base, httpd


def cards(page, selector="#grid .card, #avoidGrid .card"):
    return page.eval_on_selector_all(
        selector,
        "els => els.map(e => ({id: e.dataset.id, verdict: e.dataset.verdict, score: e.dataset.score,"
        " avoid: !!e.closest('#avoidGrid'), text: e.innerText}))",
    )


def card(page, item_id):
    return page.eval_on_selector_all(
        "#grid .card, #avoidGrid .card",
        "(els, id) => { const e = els.find(x => x.dataset.id === id);"
        " return e ? {verdict: e.dataset.verdict, score: e.dataset.score, avoid: !!e.closest('#avoidGrid'),"
        " text: e.innerText} : null; }",
        item_id,
    )


def stats(page):
    return page.evaluate(
        """() => {
        const out = {};
        document.querySelectorAll('#arenaSummary .stat').forEach((stat) => {
          out[stat.querySelector('.stat-label').textContent.trim()] = stat.querySelector('.stat-value').textContent.trim();
        });
        return out;
      }"""
    )


def path_id(page):
    return page.evaluate("location.pathname + location.search")


def wait(page, ms=300):
    page.wait_for_timeout(ms)


def modal_open(page):
    return page.is_visible("#modal")


def close_modal(page):
    page.keyboard.press("Escape")
    wait(page, 250)


def open_drawer(page):
    if page.is_hidden("#tuneDrawer"):
        page.click("#tuneBtn")
        wait(page, 350)


def close_drawer(page):
    if page.is_visible("#tuneDrawer"):
        page.click("#tuneClose")
        wait(page, 250)


def set_range(page, axis, value):
    page.eval_on_selector(
        f'#range-{axis}',
        "(el, v) => { el.value = String(v); el.dispatchEvent(new Event('input', {bubbles: true})); }",
        value,
    )
    wait(page, 160)


def set_filter(page, key, checked):
    page.evaluate(
        """([key, want]) => {
          const input = document.querySelector(`#tuneBody input[data-filter="${key}"]`);
          if (!input) return;
          const details = input.closest('details');
          if (details) details.open = true;
          if (input.checked !== want) {
            input.checked = want;
            input.dispatchEvent(new Event('change', {bubbles: true}));
          }
        }""",
        [key, checked],
    )
    wait(page, 220)


def select_arena(page, domain, arena):
    page.goto(f"{page.url.split('?')[0]}?domain={domain}&arena={arena}", wait_until="networkidle")
    wait(page, 500)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots-dir", default=str(WEB_ROOT))
    parser.add_argument("--chrome", default=os.environ.get("CHROME_PATH"))
    parser.add_argument("--keep-open", action="store_true")
    args = parser.parse_args()
    shots = Path(args.shots_dir)
    shots.mkdir(parents=True, exist_ok=True)

    base, httpd = start_server()
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []
    served: list[str] = []

    with sync_playwright() as p:
        launch_kwargs = {}
        if args.chrome:
            launch_kwargs["executable_path"] = args.chrome
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000},
            device_scale_factor=2,
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on("response", lambda r: failed_requests.append(f"{r.status} {r.url}") if r.status >= 400 else None)
        page.on("response", lambda r: served.append(r.url))

        page.goto(f"{base}/", wait_until="networkidle")
        page.evaluate("localStorage.clear()")
        page.reload(wait_until="networkidle")
        wait(page, 500)

        # ------------------------------------------------------------ 1 로드·계약
        expect(page.title().startswith("파로스"), "페이지 타이틀 로드", page.title())
        expect(not page_errors, "JS 예외 없음", "; ".join(page_errors))
        expect(not console_errors, "콘솔 에러 0건", "; ".join(console_errors))
        expect(not failed_requests, "HTTP 4xx/5xx 없음", "; ".join(failed_requests))
        expect(all(url.startswith(base) for url in served), "모든 요청이 배포 루트 안에서 해결됨", str([u for u in served if not u.startswith(base)]))
        expect(any(url.endswith("/data/catalog.json") for url in served), "data/catalog.json 로드", "")
        expect(any(url.endswith("/data/search-index.json") for url in served), "data/search-index.json 로드", "")
        expect(any(url.endswith("/schema/item.schema.json") for url in served), "schema/item.schema.json 로드", "")
        expect(not any("/data/app/" in url or "/data/game/" in url for url in served),
               "홈에서는 비교군 분할 파일을 내려받지 않음(지연 로딩)", str([u for u in served if "/data/app/" in u or "/data/game/" in u]))
        chip = page.inner_text("#datasetChip")
        expect("스키마 v0.4.0" in chip and "57건" in chip and "비교군 12" in chip, "데이터 칩 = v0.4.0 · 57건 · 비교군 12", chip)
        counts = page.evaluate("window.Pharos.state.core.index.counts")
        expect(counts == {"items": 57, "domains": 3, "categories": 10, "arenas": 12}, "카탈로그 계층 집계 57/3/10/12", str(counts))
        domains = page.evaluate("window.Pharos.state.core.catalog.domains.map(d => d.id)")
        expect(domains == ["app", "game", "ai"], "도메인 = 앱·게임·AI 도구", str(domains))
        tabs = page.eval_on_selector_all("#domainTabs button", "els => els.map(e => e.innerText.trim())")
        expect(tabs == ["홈", "앱", "게임", "AI 도구"], "도메인 전환 탭 = 홈·앱·게임·AI 도구", str(tabs))

        # ---------------------------------------------------------------- 2 홈 뷰
        hero = page.inner_text(".hero")
        expect("별점 대신" in hero and "내 기준" in hero, "홈 히어로 문구", hero[:80])
        hero_box = page.eval_on_selector(".hero", "e => Math.round(e.getBoundingClientRect().height)")
        expect(hero_box <= 250, "홈 히어로를 컴팩트하게 축약(<=250px)", str(hero_box))
        expect(page.is_visible("#homeSearch") and page.inner_text("#homeSearchForm").strip() != "", "홈 검색창 유지", "")
        show_top = page.eval_on_selector("#genreShowcase .genre-block", "e => Math.round(e.getBoundingClientRect().top)")
        expect(show_top < 640, "스크롤 없이 장르별 추천이 첫 화면에 들어옴", str(show_top))
        expect(page.inner_text("#bookmarkSection").startswith("☆ 내 보관함"), "홈에 보관함 섹션")
        genres = page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)")
        expect(genres == ["pkm-notes", "task-managers", "password-managers", "cloud-storage", "web-browsers",
                          "roguelike-deckbuilder", "action-roguelike", "mobile-gacha-rpg", "pc-mmorpg",
                          "mobile-strategy-defense", "ai-assistants", "ai-coding-tools"],
               "홈 장르 블록 12개(카탈로그 순서)", str(genres))
        expect(page.eval_on_selector_all(".arena-card, .category-card", "els => els.length") == 0,
               "홈에는 장황한 비교군 소개 카드가 없음", "")
        first = page.eval_on_selector('.genre-block[data-arena="pkm-notes"]', "e => e.innerText.replace(/\\n/g, ' | ')")
        expect("노트·지식관리" in first and "5종" in first and "추천 2" in first,
               "첫 장르 블록 = 노트·지식관리(5종·추천 1)", first[:140])
        expect("전체 5종 비교" in first, "장르 블록에 '전체 N종 비교' 링크", first[:180])

        picks = page.eval_on_selector_all(
            '.genre-block[data-arena="pkm-notes"] .pick-tile',
            "els => els.map(e => ({id: e.dataset.item, verdict: e.dataset.verdict, score: e.dataset.score,"
            " text: e.innerText.replace(/\\n/g, ' | ')}))",
        )
        expect([p["id"] for p in picks] == ["obsidian", "joplin", "notion", "simplenote"],
               "장르 타일 = 추천 우선 → 조건부 점수순(최대 4)", str([p["id"] for p in picks]))
        expect(picks[0]["verdict"] == "recommend" and abs(float(picks[0]["score"]) - 82.5) < 0.05
               and "추천" in picks[0]["text"] and "82.5" in picks[0]["text"],
               "타일에 판정 배지·가중 점수", picks[0]["text"])
        expect(picks[2]["verdict"] == "conditional" and "조건부" in picks[2]["text"],
               "조건부 항목은 🟡 조건부로 표시", picks[2]["text"])
        gacha_picks = page.eval_on_selector_all('.genre-block[data-arena="mobile-gacha-rpg"] .pick-tile',
                                                "els => els.map(e => e.dataset.item)")
        expect(gacha_picks == ["goddess-of-victory-nikke", "limbus-company", "blue-archive"],
               "가챠 장르 = 추천 니케 먼저 + 조건부 2건(거름 제외)", str(gacha_picks))
        pick_icon = page.eval_on_selector(
            ".pick-tile .item-icon",
            "e => { const img = e.querySelector('img'); return {size: Math.round(e.getBoundingClientRect().width),"
            " loaded: !!img && img.complete && img.naturalWidth > 0}; }",
        )
        expect(pick_icon["size"] >= 40 and pick_icon["loaded"], "추천 타일 아이콘 40px+ 실제 이미지", str(pick_icon))

        # 타일 클릭 = 상세 모달, 헤더/전체 링크 = 비교군 화면
        page.click('.genre-block[data-arena="pkm-notes"] .pick-tile[data-item="joplin"]')
        wait(page, 700)
        expect(modal_open(page) and page.inner_text("#modalTitle") == "Joplin", "홈 추천 타일 클릭 → 상세 모달",
               page.inner_text("#modalTitle"))
        expect("arena=pkm-notes" in page.url and "item=joplin" in page.url, "타일 상세가 URL 딥링크로 동기화", path_id(page))
        close_modal(page)
        wait(page, 300)
        page.click('#domainTabs [data-action="home"]')
        wait(page, 500)
        page.click('.genre-block[data-arena="action-roguelike"] .genre-more')
        wait(page, 700)
        expect("arena=action-roguelike" in page.url, "'전체 N종 비교 →' 클릭 = 비교군 화면", path_id(page))
        page.go_back()
        wait(page, 600)
        page.click('.genre-block[data-arena="action-roguelike"] .genre-title')
        wait(page, 700)
        expect("arena=action-roguelike" in page.url, "장르 헤더 클릭 = 비교군 화면", path_id(page))
        page.click('#domainTabs [data-action="home"]')
        wait(page, 500)

        gap_rows = page.eval_on_selector_all(".gap-row", "els => els.map(e => e.innerText.replace(/\\n/g, ' | '))")
        expect(len(gap_rows) == 4, "'별점은 높은데 거름 판정' 리포트 4건", str(len(gap_rows)))
        expect("Hero Wars: Alliance" in gap_rows[0] and "4.6" in gap_rows[0] and "38" in gap_rows[0] and "거름" in gap_rows[0],
               "Hero Wars 4.6★ vs 38점 거름", gap_rows[0])
        expect("확률형 아이템" in gap_rows[0] and "P2W" in gap_rows[0], "갭 리포트에 걸린 필터 사유", gap_rows[0])
        expect("Microsoft To Do" in gap_rows[2] and "4.6" in gap_rows[2] and "66.75" in gap_rows[2] and "거름" in gap_rows[2],
               "Microsoft To Do 4.6★ vs 66.75 거름(2027-06-30 종료 예고)", gap_rows[2])
        expect("종료" in gap_rows[2] or "AI 검토" in gap_rows[2], "MS To Do 갭 리포트에 걸린 사유", gap_rows[2])
        expect("Archero" in gap_rows[1] and "4.2" in gap_rows[1] and "58.25" in gap_rows[1] and "거름" in gap_rows[1],
               "Archero 4.2★ vs 58.25 거름", gap_rows[1])
        expect("Clash Royale" in gap_rows[3] and "61" in gap_rows[3], "Clash Royale 4.0★ vs 61 거름", gap_rows[3])
        expect(all("Notion" not in row for row in gap_rows), "규모가 검증된 Notion 은 '거름' 리포트에서 제외", str(gap_rows))
        expect(all("Obsidian" not in row for row in gap_rows), "별점·점수 격차가 작은 Obsidian 은 리포트에서 제외", str(gap_rows))

        # --------------------------------------------------------- 3 통합 검색
        page.fill("#homeSearch", "에버노트")
        wait(page, 350)
        rows = page.eval_on_selector_all(".search-row", "els => els.map(e => e.innerText.replace(/\\n/g, ' | '))")
        expect(len(rows) == 1 and "Evernote" in rows[0], "통합 검색 '에버노트' → Evernote", str(rows))
        expect("노트·지식관리" in rows[0], "검색 결과에 비교군 표시", rows[0])
        page.fill("#homeSearch", "노트")
        wait(page, 350)
        note_rows = page.eval_on_selector_all(".search-row", "els => els.map(e => e.dataset.item)")
        expect(len(note_rows) >= 2 and "evernote" in note_rows and "joplin" in note_rows,
               "비교군 라벨('노트')로도 검색", str(note_rows))
        page.fill("#homeSearch", "없는검색어xyz")
        wait(page, 300)
        expect(page.is_visible("#homeSearchResults") and "맞는 항목이 없습니다" in page.inner_text("#homeSearchResults"),
               "검색 결과 없음 안내", page.inner_text("#homeSearchResults")[:80])
        page.fill("#homeSearch", "에버노트")
        wait(page, 300)
        page.click(".search-row")
        wait(page, 600)
        expect(modal_open(page) and page.inner_text("#modalTitle") == "Evernote", "검색 결과 클릭 → 상세 열림", page.inner_text("#modalTitle"))
        expect("domain=app" in page.url and "arena=pkm-notes" in page.url and "item=evernote" in page.url,
               "검색에서 연 상세가 URL 딥링크로 동기화", path_id(page))
        close_modal(page)
        page.click('#domainTabs [data-action="home"]')
        wait(page, 500)
        expect(page.is_visible("#homeSearch"), "홈으로 복귀", path_id(page))

        # ------------------------------------------------------- 4 도메인 탐색
        page.click('#domainTabs [data-domain="game"]')
        wait(page, 500)
        expect("domain=game" in page.url, "게임 도메인 전환 URL", path_id(page))
        dom_head = page.inner_text(".level-head")
        expect("게임 — 장르 5 · 24건" in dom_head, "게임 도메인 헤더 = 장르 5 · 24건", dom_head[:120])
        cats = page.eval_on_selector_all(".chip--link", "els => els.map(e => e.dataset.category)")
        expect(cats == ["strategy-card", "rpg", "action-indie", "mmorpg", "mobile-strategy"],
               "게임 도메인 대분류 5개", str(cats))
        dom_arenas = page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)")
        expect(dom_arenas == ["roguelike-deckbuilder", "mobile-gacha-rpg", "action-roguelike",
                              "pc-mmorpg", "mobile-strategy-defense"],
               "게임 도메인 장르 블록 5개", str(dom_arenas))
        dom_top = page.eval_on_selector(".genre-block", "e => Math.round(e.getBoundingClientRect().top)")
        expect(dom_top < 480, "도메인 화면도 장르별 추천이 바로 보임", str(dom_top))
        dom_picks = page.eval_on_selector_all('.genre-block[data-arena="mobile-gacha-rpg"] .pick-tile',
                                              "els => els.map(e => e.dataset.item)")
        expect(dom_picks == ["goddess-of-victory-nikke", "limbus-company", "blue-archive"],
               "도메인 화면의 가챠 장르 추천 타일", str(dom_picks))
        expect(page.eval_on_selector_all(".arena-card, .category-card", "els => els.length") == 0,
               "도메인 화면에 장황한 비교군 카드 없음", "")
        page.click('.chip--link[data-category="strategy-card"]')
        wait(page, 450)
        expect("category=strategy-card" in page.url, "대분류 URL", path_id(page))
        arena_cards = page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)")
        expect(arena_cards == ["roguelike-deckbuilder"], "전략·카드 대분류 아래 비교군 1개", str(arena_cards))
        crumb = page.inner_text("#breadcrumb")
        expect("게임" in crumb and "전략 · 카드" in crumb, "경로 표시(홈/게임/전략·카드)", crumb)

        served.clear()
        page.click('.genre-block[data-arena="roguelike-deckbuilder"] .genre-title')
        wait(page, 700)
        expect("arena=roguelike-deckbuilder" in page.url, "비교군 URL", path_id(page))
        expect(any(url.endswith("/data/game/roguelike-deckbuilder.json") for url in served),
               "비교군 선택 시 해당 분할 파일만 로드", str(served))
        expect(not any(url.endswith("/data/app/pkm-notes.json") for url in served),
               "다른 도메인 파일은 로드하지 않음", str(served))

        state = cards(page)
        expect(len(state) == 4, "덱빌딩 비교군 카드 4건(추천 3 + 거름 1)", str([c["id"] for c in state]))
        summary = stats(page)
        expect(summary.get("추천") == "3" and summary.get("조건부") == "1" and summary.get("거름") == "0",
               "비교군 요약 3/1/0", str(summary))
        expect(summary.get("평균 가중 점수") == "82.2", "비교군 평균 82.2", str(summary))
        expect(page.inner_text("#listCount").strip() == "4/4건", "목록 건수 4/4", page.inner_text("#listCount"))

        by_id = {c["id"]: c for c in state}
        for item_id, verdict, score in (("balatro", "recommend", 94.75), ("slay-the-spire", "recommend", 92.50),
                                        ("inscryption", "recommend", 84.25), ("night-of-the-full-moon", "conditional", 57.25)):
            c = by_id.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(by_id["night-of-the-full-moon"]["avoid"] is False, "조건부 항목은 일반 목록(덱빌딩에 거름 없음)")
        expect("조건부" in by_id["night-of-the-full-moon"]["text"] and "57.3" in by_id["night-of-the-full-moon"]["text"], "Night of the Full Moon 조건부·57.3", by_id["night-of-the-full-moon"]["text"][-120:])

        # 목록 카드는 핵심만: 아이콘 + 이름 + 개발사/장르 + 판정 + 점수 / 한 줄 요약 / 핵심 태그 2개
        head = page.eval_on_selector(
            '#grid .card[data-id="balatro"]',
            "e => ({icon: !!e.querySelector('.card-head .item-icon--card img'),"
            " name: e.querySelector('.card-name-text h3')?.textContent.trim(),"
            " dev: e.querySelector('.card-dev')?.textContent.trim(),"
            " score: e.querySelector('.card-score .score-num')?.textContent.trim(),"
            " verdict: e.querySelector('.card-score .verdict')?.textContent.trim(),"
            " summary: e.querySelector('.one-liner')?.textContent.trim()})",
        )
        expect(head["icon"] and head["name"] == "Balatro" and "LocalThunk" in head["dev"],
               "카드 상단 = 공식 아이콘·이름·개발사/장르", str(head))
        expect(head["score"] == "94.8" and "추천" in head["verdict"], "카드 상단 = 판정 배지 + 가중 점수", str(head))
        expect(head["summary"] and len(head["summary"]) > 10, "카드 중간 = 핵심 한 줄 요약", str(head["summary"]))
        for item_id in ("balatro", "slay-the-spire", "inscryption", "night-of-the-full-moon"):
            scope = f'#grid .card[data-id="{item_id}"], #avoidGrid .card[data-id="{item_id}"]'
            tags_count = page.eval_on_selector(scope, "e => e.querySelectorAll('.card-tags .chip').length")
            expect(tags_count <= 2, f"{item_id} 카드 핵심 태그 최대 2개", str(tags_count))
            stripped = page.eval_on_selector(
                scope,
                "e => e.querySelectorAll('.lights, .chip--tier, .chip--fresh, .chip--path').length",
            )
            expect(stripped == 0, f"{item_id} 카드에는 3축 막대·가격 티어·신선도 칩 없음", str(stripped))
        expect("하드 필터 통과" in by_id["balatro"]["text"], "추천 카드 핵심 태그 = 하드 필터 통과", by_id["balatro"]["text"][:160])
        expect("완결작" in by_id["inscryption"]["text"], "Inscryption 카드에 '완결작' 태그", by_id["inscryption"]["text"][-120:])
        expect("최신" not in by_id["balatro"]["text"], "평가 신선도는 목록 카드가 아니라 상세에", by_id["balatro"]["text"][:160])

        # 비교군 안 검색은 그 비교군으로 AND
        page.fill("#arenaSearch", "inscryption")
        wait(page, 350)
        expect([c["id"] for c in cards(page)] == ["inscryption"], "비교군 내 검색 1건", str([c["id"] for c in cards(page)]))
        page.fill("#arenaSearch", "")
        wait(page, 300)
        page.select_option("#sort", "name")
        wait(page, 250)
        picks = [c["id"] for c in cards(page) if not c["avoid"]]
        expect(picks == ["balatro", "inscryption", "night-of-the-full-moon", "slay-the-spire"], "이름순 정렬", str(picks))
        page.select_option("#sort", "score")
        wait(page, 250)

        # ------------------------------------------------------- 5 미세조정 드로어
        expect(page.inner_text("#tuneSummary").strip() == "균형 기본", "기본 프리셋 = 균형 기본", page.inner_text("#tuneSummary"))
        open_drawer(page)
        expect(page.is_visible("#tuneDrawer"), "미세조정 드로어 열림")
        expect(page.get_attribute("#tuneBtn", "aria-expanded") == "true", "드로어 토글 aria-expanded")
        presets = page.eval_on_selector_all("#tuneBody .preset", "els => els.map(e => e.innerText.trim())")
        expect(presets == ["균형 기본", "대중 평가 중심", "쾌적성·노과금 중심", "프라이버시·로컬 중시", "AI 완성도 중심"], "프리셋 5종", str(presets))
        sliders = page.eval_on_selector_all("#tuneBody input[type=range]", "els => els.map(e => e.value)")
        expect(sliders == ["50", "25", "25"], "기본 가중치 50/25/25", str(sliders))
        packs = page.eval_on_selector_all("#tuneBody .filter-pack summary", "els => els.map(e => e.innerText.split('\\n')[0])")
        expect(packs[0].startswith("게임 팩") and packs[1].startswith("앱 팩") and packs[2].startswith("AI 도구 팩")
               and packs[3].startswith("공통 코어"),
               "게임 도메인은 게임 팩을 먼저 노출(앱·AI·공통 순)", str(packs))
        open_packs = page.eval_on_selector_all("#tuneBody .filter-pack", "els => els.map(e => e.open)")
        expect(open_packs == [True, False, False, False], "현재 도메인 팩만 펼침", str(open_packs))
        expect(page.inner_text("#filterCount").strip() == "4/9", "필터 카운트 4/9", page.inner_text("#filterCount"))

        page.click('#tuneBody [data-preset="privacy"]')
        wait(page, 500)
        expect(page.eval_on_selector_all("#tuneBody input[type=range]", "els => els.map(e => e.value)") == ["25", "55", "20"],
               "프라이버시 프리셋 → 25/55/20")
        expect(page.inner_text("#filterCount").strip() == "6/9", "프라이버시 프리셋 → 계정·데이터 수집 필터 자동 6/9", page.inner_text("#filterCount"))
        expect(page.eval_on_selector('#tuneBody input[data-filter="account_required"]', "e => e.checked") is True,
               "프라이버시 프리셋이 account_required 필터를 켬")
        expect(page.eval_on_selector('#tuneBody input[data-filter="data_collection"]', "e => e.checked") is True,
               "프라이버시 프리셋이 data_collection 필터를 켬")
        expect("preset=privacy" in page.url, "프라이버시 프리셋 URL 반영", path_id(page))
        page.click('#tuneBody [data-preset="balanced"]')
        wait(page, 500)
        expect(page.inner_text("#filterCount").strip() == "4/9", "프리셋을 떠나면 프리셋이 켠 필터만 되돌림 4/9", page.inner_text("#filterCount"))
        expect(page.eval_on_selector_all("#tuneBody input[type=range]", "els => els.map(e => e.value)") == ["50", "25", "25"],
               "균형 기본으로 복귀 50/25/25")

        page.click('#tuneBody [data-preset="ai"]')
        wait(page, 450)
        expect(page.eval_on_selector_all("#tuneBody input[type=range]", "els => els.map(e => e.value)") == ["20", "25", "55"],
               "AI 프리셋 → 20/25/55")
        expect("preset=ai" in page.url, "프리셋이 URL 에 반영", path_id(page))
        balatro = card(page, "balatro")
        expect(balatro and abs(float(balatro["score"]) - 93.55) < 0.05, "AI 프리셋 재계산 93.55", str(balatro))
        page.click('#tuneBody [data-preset="balanced"]')
        wait(page, 400)

        set_range(page, "user_rating", 100)
        set_range(page, "objective", 0)
        set_range(page, "ai_review", 0)
        balatro = card(page, "balatro")
        expect(balatro and abs(float(balatro["score"]) - 96.0) < 0.05, "단일 축 100% → 96", str(balatro))
        expect("w=" in page.url or "%2C" in page.url or "w" in page.url, "직접 설정 가중치도 URL 에 반영", path_id(page))
        page.click('#tuneBody [data-preset="balanced"]')
        wait(page, 400)

        set_filter(page, "account_required", True)
        expect(page.inner_text("#filterCount").strip() == "5/9", "계정 필수 필터 켜기 → 5/9", page.inner_text("#filterCount"))
        expect(len(cards(page)) == 4, "필터 추가에도 비교군 목록 유지", str(len(cards(page))))
        set_filter(page, "account_required", False)
        open_drawer(page)
        page.click("#strictToggle + .switch-track")
        wait(page, 400)
        expect(page.inner_text("#strictState").strip() == "OFF", "엄격 모드 OFF", page.inner_text("#strictState"))
        close_drawer(page)

        # ------------------------------------------------------------ 6 비교 표
        page.check('#grid .card[data-id="balatro"] input[data-compare]')
        wait(page, 250)
        page.check('#grid .card[data-id="slay-the-spire"] input[data-compare]')
        wait(page, 350)
        expect(page.is_visible("#compareBar"), "2개 선택 시 비교 바 노출")
        bar = page.inner_text("#compareBar")
        expect("Balatro" in bar and "Slay the Spire" in bar and "2개 나란히 비교" in bar, "비교 바 구성", bar.replace("\n", " | "))
        expect("compare=balatro%2Cslay-the-spire" in page.url, "비교 선택이 URL 에 반영", path_id(page))
        page.click("#compareOpen")
        wait(page, 600)
        expect(page.is_visible("#compareTable"), "비교 표 노출")
        headers = page.eval_on_selector_all("#compareTable thead th", "els => els.map(e => e.innerText.split('\\n')[0])")
        expect(headers == ["기준", "Balatro", "Slay the Spire"], "비교 표 머리글", str(headers))
        rows_count = page.eval_on_selector_all("#compareTable tbody tr", "els => els.length")
        labels = page.eval_on_selector_all("#compareTable tbody th", "els => els.map(e => e.innerText)")
        expect(rows_count >= 12, "비교 항목 12행 이상", str(rows_count))
        for label in ["가중 점수", "대표 티어 · 가격", "축 · 사용자 평가", "걸린 하드 필터", "누적 별점·평점", "최근 리뷰", "수명 단계", "평가 신선도"]:
            expect(label in labels, f"비교 표 '{label}' 행", str(labels)[:160])
        table_text = page.inner_text("#compareTable")
        expect("94.8" in table_text and "92.5" in table_text, "비교 표에 두 항목 점수", table_text[:200])

        # 목록으로 돌아가 3개째 추가 → 4개째는 차단
        page.click('a[data-action="arena"], button[data-action="arena"]')
        wait(page, 600)
        page.check('#grid .card[data-id="inscryption"] input[data-compare]')
        wait(page, 350)
        expect("inscryption" in page.url and "compare=" in page.url, "3개째 선택 URL 반영", path_id(page))
        page.evaluate(
            """() => { const el = document.querySelector('[data-item="night-of-the-full-moon"]'); if (el) el.scrollIntoView(); }"""
        )
        page.check('#grid .card[data-id="night-of-the-full-moon"] input[data-compare]', force=True)
        wait(page, 300)
        expect("night-of-the-full-moon" not in page.url, "네 번째 항목은 비교에 담기지 않음(최대 3개)", path_id(page))
        toast_text = page.inner_text("#toast") if page.is_visible("#toast") else ""
        expect("최대 3개" in toast_text, "4개째 선택 시 안내 토스트", toast_text)
        page.click("#compareOpen")
        wait(page, 600)
        headers = page.eval_on_selector_all("#compareTable thead th", "els => els.map(e => e.innerText.split('\\n')[0])")
        expect(headers == ["기준", "Balatro", "Slay the Spire", "Inscryption"], "3개 비교 표", str(headers))

        # ------------------------------------------------------------ 7 상세 모달
        page.click('#compareTable [data-item="inscryption"]')
        wait(page, 700)
        expect(modal_open(page) and page.inner_text("#modalTitle") == "Inscryption", "비교 표에서 상세 열기", page.inner_text("#modalTitle"))
        body = page.inner_text("#modalBody")
        for label in ["판정 요약", "사실 (Fact)", "의견 (Opinion)", "티어별 판정 비교", "축별 신호와 근거", "같은 비교군", "누적 vs 최근 리뷰", "과금·광고 4분해", "업데이트 성격", "근거·출처"]:
            expect(label in body, f"상세 섹션 '{label}'", body[:120])
        expect("스토어 표기·가격·업데이트 날짜" in body, "사실(Fact) 섹션 설명", body[:200])
        expect("AI·편집 검토 · 사실과 구분" in body, "의견(Opinion) 구분 배지", "")
        expect("수명 단계 · 완결작" in body, "완결작 수명 단계 표기")
        expect("완결작은 stale_over_12m 필터가 켜져 있어도 면제(exempt)로 계산합니다" in body, "완결작 면제 설명")
        expect("최신 · 1일" in body, "상세에 신선도 표시")
        expect("면제 · 완결작" in body, "완결작 면제는 카드가 아니라 상세 모달에", "")
        axis_scores = page.eval_on_selector_all("#modalBody .axis-card .axis-score", "els => els.map(e => e.textContent.trim())")
        expect(len(axis_scores) == 4 and all(axis_scores), "상세 05 축별 신호에 3축 + 프로필 축 점수", str(axis_scores))
        expect("프로필 전용" in body and "가중치 0 · 판정 미포함" in body, "상세 축별 신호에 프로필 축·가중치 0 구분", "")
        tier_rows = page.eval_on_selector_all("#modalBody .tier-name", "els => els.map(e => e.textContent.trim())")
        expect(bool(tier_rows) and "1회 구매" in " ".join(tier_rows), "상세 04 티어별 판정에 가격 티어", str(tier_rows)[:160])
        alts = page.eval_on_selector_all("#secAlternatives .alt-row", "els => els.map(e => e.innerText.replace(/\\n/g, ' '))")
        expect(len(alts) == 2 and "Balatro" in alts[0] and "Slay the Spire" in alts[1], "같은 비교군 대체제 링크", str(alts))
        expect(page.eval_on_selector_all("#modalBody .source", "els => els.length") >= 3, "출처 목록 렌더")
        correction = page.get_attribute('#modalActions a[href*="issues/new"]', "href")
        expect(correction and "github.com/AIRA1346/pharos/issues/new" in correction and "template=correction.yml" in correction,
               "정정 제보 링크(correction.yml)", correction)

        page.click('[data-share="inscryption"]')
        wait(page, 400)
        clip = page.evaluate("navigator.clipboard.readText()")
        expect("Inscryption" in clip and "가중 점수 84.3" in clip and "파로스" in clip, "공유 요약 복사", clip[:120])

        # 보관함 담기(모달)
        page.click('#modalActions [data-bookmark="inscryption"]')
        wait(page, 350)
        expect(page.inner_text("#bookmarkCount") == "1", "모달에서 보관함 담기", page.inner_text("#bookmarkCount"))
        expect("★ 보관됨" in page.inner_text("#modalActions"), "보관 상태 버튼 표시")
        close_modal(page)
        expect(not modal_open(page), "ESC 로 상세 닫힘")
        expect("item=" not in page.url, "상세를 닫으면 URL 에서 item 제거", path_id(page))

        # 대체제 링크 이동(거름 항목 상세)
        page.goto(f"{base}/?domain=app&arena=pkm-notes&item=evernote", wait_until="networkidle")
        wait(page, 700)
        expect(page.inner_text("#modalTitle") == "Evernote", "딥링크로 Evernote 상세", page.inner_text("#modalTitle"))
        alts = page.eval_on_selector_all("#secAlternatives .alt-row", "els => els.map(e => e.dataset.item)")
        expect(alts == ["obsidian", "joplin"], "Evernote 대체제 = 같은 비교군 추천 2건(점수순)", str(alts))
        page.click('#secAlternatives .alt-row')
        wait(page, 700)
        expect(page.inner_text("#modalTitle") == "Obsidian", "대체제 클릭 → Obsidian 상세", page.inner_text("#modalTitle"))
        expect("item=obsidian" in page.url, "대체제 이동 URL", path_id(page))
        close_modal(page)
        wait(page, 300)
        expect(len(cards(page)) == 5, "노트 비교군 카드 5건", str(len(cards(page))))

        # v0.5.0 프라이버시·로컬 중시 프리셋 — 계정·데이터 수집 필터로 로컬·프라이버시 목적을 가른다
        page.goto(f"{base}/?domain=app&arena=pkm-notes&preset=privacy", wait_until="networkidle")
        wait(page, 700)
        expect(card(page, "notion")["avoid"] is True, "프라이버시 프리셋 → 계정 필수인 Notion 거름",
               str(card(page, "notion"))[:120])
        expect(card(page, "obsidian")["avoid"] is False and card(page, "joplin")["avoid"] is False,
               "프라이버시 프리셋에서도 계정 없는 Obsidian·Joplin 은 유지")
        page.goto(f"{base}/?domain=app&arena=pkm-notes", wait_until="networkidle")
        wait(page, 600)

        page.goto(f"{base}/?domain=app&arena=pkm-notes&item=notion", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("v0.5.0 산정 메모" in body and "표본 규모 검증" in body,
               "Notion 상세에 v0.5.0 산정 메모(표본 규모 검증)", body[-400:])
        expect("계정·클라우드 전제" in body or "계정·클라우드 테제" in body,
               "Notion 객관 재평가 근거가 상세에 남음", body[-200:])
        close_modal(page)
        page.goto(f"{base}/?domain=app&arena=pkm-notes", wait_until="networkidle")
        wait(page, 500)
        page.screenshot(path=str(shots / "preview-v3-arena.png"), full_page=True)

        # ------------------------------------------------------ 8 방법론·딥링크
        page.click("#methodBtn")
        wait(page, 400)
        expect(page.is_visible("#methodModal"), "방법론 모달 열림")
        method = page.inner_text("#methodBody")
        for label in ["4단 구조", "네 축과 가중 점수", "표본 규모 검증", "근거 등급 A/B/C", "확률형·P2W 강도 3단계", "판정 규칙", "독립성", "용어 도움말"]:
            expect(label in method, f"방법론 '{label}' 섹션")
        expect("어필리에이트 링크·유료 광고·협찬 배치를 쓰지 않습니다" in method, "독립성·어필리에이트 배제 선언")
        expect("재검토 필요" in method and "180" in method, "용어 도움말에 신선도 기준")
        page.screenshot(path=str(shots / "preview-v3-method.png"))
        page.keyboard.press("Escape")
        wait(page, 250)
        expect(page.is_hidden("#methodModal"), "ESC 로 방법론 닫힘")

        page.goto(f"{base}/?domain=app&arena=pkm-notes&item=obsidian", wait_until="networkidle")
        wait(page, 700)
        expect(page.inner_text("#modalTitle") == "Obsidian", "딥링크 ?domain&arena&item", page.inner_text("#modalTitle"))
        expect(len(cards(page)) == 5, "딥링크 뒤 배경 목록도 노트 비교군", str(len(cards(page))))
        close_modal(page)

        page.goto(f"{base}/?domain=game&category=strategy-card", wait_until="networkidle")
        wait(page, 500)
        expect(page.eval_on_selector_all(".genre-block", "els => els.length") == 1, "딥링크 ?domain&category", "")
        page.goto(f"{base}/?arena=roguelike-deckbuilder", wait_until="networkidle")
        wait(page, 600)
        expect(len(cards(page)) == 4 and "domain=game" in page.url, "도메인 없는 ?arena 딥링크도 해석", path_id(page))
        page.goto(f"{base}/?preset=ai&domain=game&arena=roguelike-deckbuilder", wait_until="networkidle")
        wait(page, 600)
        open_drawer(page)
        expect(page.eval_on_selector_all("#tuneBody input[type=range]", "els => els.map(e => e.value)") == ["20", "25", "55"],
               "딥링크 preset=ai 가 가중치에 반영")
        close_drawer(page)
        expect(abs(float(card(page, "balatro")["score"]) - 93.55) < 0.05, "딥링크 프리셋으로 재계산", card(page, "balatro")["score"])

        # ---------------------------------------------------------- 9 북마크
        page.goto(f"{base}/", wait_until="networkidle")
        wait(page, 500)
        expect(page.inner_text("#bookmarkCount") == "1", "보관함 카운트 유지(새로고침 후)", page.inner_text("#bookmarkCount"))
        bookmark_section = page.inner_text("#bookmarkSection")
        expect("Inscryption" in bookmark_section and "1건" in bookmark_section, "홈 보관함에 담긴 항목", bookmark_section[:160])
        stored = page.evaluate("JSON.parse(localStorage.getItem('pharos-bookmarks'))")
        expect(stored == ["inscryption"], "localStorage 보관함 저장", str(stored))
        page.click('#bookmarkSection [data-bookmark="inscryption"]')
        wait(page, 350)
        expect(page.inner_text("#bookmarkCount") == "0", "보관함에서 빼기", page.inner_text("#bookmarkCount"))
        expect(page.evaluate("JSON.parse(localStorage.getItem('pharos-bookmarks'))") == [], "localStorage 갱신")

        # ------------------------------------------------------ 10 엔진 단위 테스트
        unit = page.evaluate(
            """() => {
            const { engine, state } = window.Pharos;
            const contract = state.contract || window.Pharos.state.core.contract;
            const passes = Object.fromEntries(contract.hard_filters.map(f => [f.key, {status:'pass', evidence_grade:'A', note:''}]));
            const mk = (axes, hard) => ({
              axes,
              tiers: [{ tier_id:'t', label:'T', kind:'free', price:{display:'무료'},
                        hard_filters: {...passes, ...(hard||{})}, verdict:'conditional' }],
              verdict: { tier_of_record:'t' }
            });
            const item = mk({
              user_rating:{score:90, signal:'green', evidence_grade:'A'},
              objective:{score:60, signal:'yellow', evidence_grade:'A'},
              ai_review:{score:null, signal:'unknown', evidence_grade:'unknown'},
            });
            const settings = (w, filters, strict) => ({contract, weights:w, enabledFilters:filters||[], strict: strict!==false});
            const a = engine.evaluateTier(item, item.tiers[0], settings({user_rating:50, objective:50, ai_review:0}));
            const b = engine.evaluateTier(item, item.tiers[0], settings({user_rating:0, objective:0, ai_review:100}));
            const norm = engine.normalizeWeights({user_rating:1, objective:1, ai_review:2});
            const thresholds = [engine.signalFromScore(75, contract.signal_thresholds), engine.signalFromScore(74.9, contract.signal_thresholds), engine.signalFromScore(49.9, contract.signal_thresholds)];

            const failC = mk({user_rating:{score:90,signal:'green'}, objective:{score:90,signal:'green'}, ai_review:{score:90,signal:'green'}},
                             {forced_ads:{status:'fail', evidence_grade:'C', note:'3자'}});
            const strict = engine.evaluateTier(failC, failC.tiers[0], settings({user_rating:34,objective:33,ai_review:33}, ['forced_ads'], true));
            const lenient = engine.evaluateTier(failC, failC.tiers[0], settings({user_rating:34,objective:33,ai_review:33}, ['forced_ads'], false));
            const failA = mk({user_rating:{score:90,signal:'green'}, objective:{score:90,signal:'green'}, ai_review:{score:90,signal:'green'}},
                             {forced_ads:{status:'fail', evidence_grade:'A', note:'스토어'}});
            const lenientA = engine.evaluateTier(failA, failA.tiers[0], settings({user_rating:34,objective:33,ai_review:33}, ['forced_ads'], false));

            const twoRed = mk({user_rating:{score:40,signal:'red'}, objective:{score:40,signal:'red'}, ai_review:{score:90,signal:'green'}});
            const oneRed = mk({user_rating:{score:40,signal:'red'}, objective:{score:70,signal:'yellow'}, ai_review:{score:90,signal:'green'}});
            const twoYellow = mk({user_rating:{score:60,signal:'yellow'}, objective:{score:60,signal:'yellow'}, ai_review:{score:90,signal:'green'}});
            const highGreen = mk({user_rating:{score:90,signal:'green'}, objective:{score:90,signal:'green'}, ai_review:{score:90,signal:'green'}});
            const v = (it, w) => engine.evaluateTier(it, it.tiers[0], settings(w||{user_rating:34,objective:33,ai_review:33}));

            const override = mk({user_rating:{score:10,signal:'red'}, objective:{score:10,signal:'red'}, ai_review:{score:10,signal:'red'}});
            override.tiers[0].axis_overrides = {objective:{score:95, signal:'green', note:'티어 전용'}};
            const ov = engine.evaluateTier(override, override.tiers[0], settings({user_rating:34,objective:33,ai_review:33}));

            const staleTier = (status) => ({ forced_ads:{status:'pass', evidence_grade:'A', note:''},
                                            stale_over_12m:{status, evidence_grade:'A', note:'마지막 업데이트 2022-06.'} });
            const life = (mstatus, compat) => {
              const it = mk({user_rating:{score:96,signal:'green'}, objective:{score:55,signal:'yellow'}, ai_review:{score:90,signal:'green'}}, staleTier('fail'));
              it.maintenance_status = mstatus;
              if (compat) it.flags = {compat_risk:{value:compat, evidence_grade:'unknown', note:'테스트'}};
              return it;
            };
            const wBal = {user_rating:40, objective:35, ai_review:25};
            const complete = engine.evaluateTier(life('feature_complete'), life('feature_complete').tiers[0], settings(wBal, ['stale_over_12m']));
            const abandoned = engine.evaluateTier(life('abandoned'), life('abandoned').tiers[0], settings(wBal, ['stale_over_12m']));
            const compatItem = life('feature_complete', 'yes');
            const compatEval = engine.evaluateTier(compatItem, compatItem.tiers[0], settings(wBal, ['stale_over_12m']));

            const freshOld = engine.freshness({assessed_at:'2026-01-01'}, contract, new Date('2026-11-25T00:00:00'));
            const freshNew = engine.freshness({assessed_at:'2026-11-24'}, contract, new Date('2026-11-25T00:00:00'));
            const defaults = engine.defaultWeights(contract);

            const pool = [
              {id:'x', name:'X', arenas:['a1'], tiers:[{tier_id:'t', label:'T', kind:'free', price:{display:'무료'}}], axes:{user_rating:{score:90,signal:'green'},objective:{score:90,signal:'green'},ai_review:{score:90,signal:'green'}}, verdict:{tier_of_record:'t'}},
              {id:'y', name:'Y', arenas:['a1'], tiers:[{tier_id:'t', label:'T', kind:'free', price:{display:'무료'}}], axes:{user_rating:{score:40,signal:'red'},objective:{score:40,signal:'red'},ai_review:{score:90,signal:'green'}}, verdict:{tier_of_record:'t'}},
              {id:'z', name:'Z', arenas:['a2'], tiers:[{tier_id:'t', label:'T', kind:'free', price:{display:'무료'}}], axes:{user_rating:{score:90,signal:'green'},objective:{score:90,signal:'green'},ai_review:{score:90,signal:'green'}}, verdict:{tier_of_record:'t'}},
            ];
            const alts = engine.alternatives({id:'y', arenas:['a1']}, pool, settings(wBal));

            const fitItem = mk({
              user_rating:{score:90, signal:'green', evidence_grade:'A'},
              objective:{score:90, signal:'green', evidence_grade:'A'},
              ai_review:{score:90, signal:'green', evidence_grade:'A'},
              personal_fit:{score:20, signal:'red', evidence_grade:'A'},
            });
            const fitOff = engine.evaluateTier(fitItem, fitItem.tiers[0], settings({user_rating:50, objective:25, ai_review:25}));
            const fitOn = engine.evaluateTier(fitItem, fitItem.tiers[0], settings({user_rating:50, objective:25, ai_review:25, personal_fit:25}));

            return {
              fitOff: fitOff.verdict, fitOffScore: fitOff.score, fitOn: fitOn.verdict, fitOnScore: fitOn.score,
              score: a.score, excluded: b.score, rule: a.rule, verdict: a.verdict,
              norm: [norm.user_rating, norm.objective, norm.ai_review], thresholds,
              strictVerdict: strict.verdict, strictRule: strict.rule,
              lenientVerdict: lenient.verdict, lenientRule: lenient.rule, lenientA: lenientA.verdict,
              twoRed: v(twoRed).verdict, oneRed: v(oneRed).verdict, twoYellow: v(twoYellow).verdict, highGreen: v(highGreen).verdict,
              overrideAxis: ov.axisStates.find(x=>x.key==='objective').score, overrideScore: ov.score,
              completeVerdict: complete.verdict, completeStatus: complete.filterChecks.find(f=>f.key==='stale_over_12m').status,
              completeExempts: complete.exempts.length, completeBlocking: complete.blocking.length,
              abandonedVerdict: abandoned.verdict, compatVerdict: compatEval.verdict, compatRule: compatEval.rule,
              freshOld: [freshOld.stale, freshOld.label, freshOld.elapsed], freshNew: [freshNew.stale, freshNew.label, freshNew.elapsed],
              defaults, altIds: alts.map(r => r.item.id),
            };
        }"""
        )
        expect(abs(unit["score"] - 75.0) < 0.01, "엔진: 가중 평균 (50*90+50*60)/100 = 75", str(unit["score"]))
        expect(unit["excluded"] is None, "엔진: 점수 없는 축만 남으면 score=null", str(unit["excluded"]))
        expect(unit["verdict"] == "conditional" and unit["rule"] == 6, "엔진: 6단 규칙 fallback", f'{unit["verdict"]}/{unit["rule"]}')
        expect([round(x, 3) for x in unit["norm"]] == [0.25, 0.25, 0.5], "엔진: 가중치 정규화", str(unit["norm"]))
        expect(unit["thresholds"] == ["green", "yellow", "red"], "엔진: 임계값 75/50", str(unit["thresholds"]))
        expect(unit["strictVerdict"] == "avoid" and unit["strictRule"] == 1, "엔진: 엄격 모드 등급 C 필터 → 거름", f'{unit["strictVerdict"]}/{unit["strictRule"]}')
        expect(unit["lenientVerdict"] == "conditional" and unit["lenientRule"] == "1w", "엔진: 완화 모드 등급 C 필터 → 조건부", f'{unit["lenientVerdict"]}/{unit["lenientRule"]}')
        expect(unit["lenientA"] == "avoid", "엔진: 완화 모드여도 등급 A 필터는 거름")
        expect(unit["twoRed"] == "avoid", "엔진: 🔴 2개 → 거름")
        expect(unit["oneRed"] == "conditional", "엔진: 🔴 1개 → 조건부")
        expect(unit["twoYellow"] == "conditional", "엔진: 🟡 2개 → 조건부")
        expect(unit["highGreen"] == "recommend", "엔진: 전부 🟢 + 80 이상 → 추천")
        expect(unit["overrideAxis"] == 95 and abs(unit["overrideScore"] - 38.05) < 0.05, "엔진: 티어 축 오버라이드", f'{unit["overrideAxis"]}/{unit["overrideScore"]}')
        expect(unit["completeVerdict"] == "recommend" and unit["completeStatus"] == "exempt" and unit["completeBlocking"] == 0,
               "엔진: 완결작 면제 → 추천·exempt·차단 없음", f'{unit["completeVerdict"]}/{unit["completeStatus"]}')
        expect(unit["abandonedVerdict"] == "avoid", "엔진: abandoned 는 거름", unit["abandonedVerdict"])
        expect(unit["compatVerdict"] == "conditional" and unit["compatRule"] == "1c", "엔진: compat_risk → 조건부 경고", f'{unit["compatVerdict"]}/{unit["compatRule"]}')
        expect(unit["freshOld"][0] is True and unit["freshOld"][1] == "재검토 필요", "엔진: 180일 초과 → 재검토 필요", str(unit["freshOld"]))
        expect(unit["freshNew"][0] is False and unit["freshNew"][1] == "최신", "엔진: 최근 평가 → 최신", str(unit["freshNew"]))
        expect(unit["defaults"] == {"user_rating": 50, "objective": 25, "ai_review": 25}, "엔진: 기본 가중치 50/25/25", str(unit["defaults"]))
        expect(unit["fitOff"] == "recommend" and abs(unit["fitOffScore"] - 90) < 0.01,
               "엔진: 가중치 0인 personal_fit(🔴)은 판정에 세지 않음", f'{unit["fitOff"]}/{unit["fitOffScore"]}')
        expect(unit["fitOn"] == "conditional" and abs(unit["fitOnScore"] - 76) < 0.01,
               "엔진: personal_fit 가중치를 주면 4번째 축으로 참여", f'{unit["fitOn"]}/{unit["fitOnScore"]}')
        expect(unit["altIds"] == ["x"], "엔진: 대체제는 같은 비교군·추천만", str(unit["altIds"]))

        # ----------------------------------------- 10-1 새 비교군: 액션 로그라이크
        page.goto(f"{base}/?domain=game&arena=action-roguelike", wait_until="networkidle")
        wait(page, 700)
        expect("arena=action-roguelike" in page.url, "액션 로그라이크 비교군 URL", path_id(page))
        arena_state = cards(page)
        expect(len(arena_state) == 4, "액션 로그라이크 카드 4건", str([c["id"] for c in arena_state]))
        summary = stats(page)
        expect(summary.get("추천") == "3" and summary.get("조건부") == "0" and summary.get("거름") == "1",
               "액션 로그라이크 요약 3/0/1", str(summary))
        expect(summary.get("평균 가중 점수") == "80.9", "액션 로그라이크 평균 80.9", str(summary))
        ar = {c["id"]: c for c in arena_state}
        for item_id, verdict, score in (("hades", "recommend", 86.5), ("vampire-survivors", "recommend", 91.0),
                                        ("dead-cells", "recommend", 88.0), ("archero", "avoid", 58.25)):
            c = ar.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(ar["archero"]["avoid"] is True, "Archero 는 하단 거름 영역")
        expect("완결작" in ar["hades"]["text"], "Hades 카드에 '완결작' 태그", ar["hades"]["text"][-140:])
        expect("면제 · 완결작" not in ar["hades"]["text"], "필터 면제 서술은 목록 카드가 아니라 상세에", ar["hades"]["text"][-140:])
        expect("최신" not in ar["dead-cells"]["text"], "Dead Cells 신선도도 목록 카드에는 없음", ar["dead-cells"]["text"][:160])

        # 새 비교군에서도 비교 표가 동작한다
        page.check('#grid .card[data-id="hades"] input[data-compare]')
        wait(page, 250)
        page.check('#grid .card[data-id="vampire-survivors"] input[data-compare]')
        wait(page, 350)
        page.click("#compareOpen")
        wait(page, 600)
        headers = page.eval_on_selector_all("#compareTable thead th", "els => els.map(e => e.innerText.split('\\n')[0])")
        expect(headers == ["기준", "Hades", "Vampire Survivors"], "액션 로그라이크 비교 표", str(headers))
        compare_text = page.inner_text("#compareTable")
        expect("86.5" in compare_text and "91.0" in compare_text, "비교 표에 두 항목 점수", compare_text[:200])

        page.goto(f"{base}/?domain=game&arena=action-roguelike&item=hades", wait_until="networkidle")
        wait(page, 700)
        expect(page.inner_text("#modalTitle") == "Hades", "Hades 상세 열기", page.inner_text("#modalTitle"))
        body = page.inner_text("#modalBody")
        expect("수명 단계 · 완결작" in body, "Hades 수명 단계 = 완결작", "")
        expect("완결작은 stale_over_12m 필터가 켜져 있어도 면제(exempt)로 계산합니다" in body, "Hades 완결작 면제 설명", "")
        alts = page.eval_on_selector_all("#secAlternatives .alt-row", "els => els.map(e => e.dataset.item)")
        expect(alts == ["vampire-survivors", "dead-cells"], "Hades 대체제 = 같은 비교군 추천 2건(점수순)", str(alts))
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=action-roguelike&item=vampire-survivors", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("모바일 무료(광고·인앱 결제)" in body and "조건부" in body, "VS 모바일 티어 = 조건부", "")
        expect("₩5,000" in body, "VS Steam 티어 가격 ₩5,000", "")
        expect("3.7" in body, "VS 모바일 3.7★ 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=action-roguelike&item=dead-cells", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("모바일 에디션(Playdigious)" in body and "₩13,000" in body, "Dead Cells 모바일 티어·가격", "")
        expect("2GB" in body, "Dead Cells 모바일 RAM 경고", "")
        expect("4종" in body or "DLC" in body, "Dead Cells DLC 분기 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=action-roguelike&item=archero", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("확률형 아이템" in body and "거름" in body, "Archero 확률형 아이템 거름 사유", "")
        expect("미확인" in body, "Archero 미확인 항목 주의 표시", "")
        expect("가격대 미확인" in body and "인앱결제 없음" not in body, "IAP 있음·가격 미확인 표기", "")
        alts = page.eval_on_selector_all("#secAlternatives .alt-row", "els => els.map(e => e.dataset.item)")
        expect(alts == ["vampire-survivors", "dead-cells", "hades"], "Archero 대체제 = 추천 3건 점수순", str(alts))
        close_modal(page)

        # ------------------------------------- 10-2 보강한 비교군: 모바일 수집형 RPG(3종)
        page.goto(f"{base}/?domain=game&arena=mobile-gacha-rpg", wait_until="networkidle")
        wait(page, 700)
        gacha = cards(page)
        expect(len(gacha) == 6, "모바일 수집형 RPG 6건", str([c["id"] for c in gacha]))
        expect(page.inner_text("#listCount").strip() == "6/6건", "가챠 목록 건수 6/6", page.inner_text("#listCount"))
        gsummary = stats(page)
        expect(gsummary.get("추천") == "2" and gsummary.get("조건부") == "1" and gsummary.get("거름") == "3",
               "가챠 비교군 요약 2/1/3", str(gsummary))
        expect(gsummary.get("평균 가중 점수") == "71.0", "가챠 비교군 평균 71.0", str(gsummary))
        g = {c["id"]: c for c in gacha}
        expect(g["limbus-company"]["score"] and abs(float(g["limbus-company"]["score"]) - 81.5) < 0.05,
               "Limbus Company 81.5", g["limbus-company"]["score"])
        expect(g["genshin-impact"]["score"] and abs(float(g["genshin-impact"]["score"]) - 74.5) < 0.05,
               "Genshin Impact 74.5", g["genshin-impact"]["score"])
        expect(g["limbus-company"]["verdict"] == "recommend" and g["limbus-company"]["avoid"] is False,
               "Limbus Company = 추천(선택 과금)", g["limbus-company"]["verdict"])
        expect(g["hero-wars-alliance"]["avoid"] is True and g["genshin-impact"]["avoid"] is True,
               "Hero Wars·Genshin 은 거름 영역(impact core)", str([c["id"] for c in gacha if c["avoid"]]))

        for item_id, verdict, score in (("goddess-of-victory-nikke", "recommend", 83.00),
                                        ("blue-archive", "conditional", 77.50),
                                        ("honkai-star-rail", "avoid", 71.50)):
            c = g.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(g["goddess-of-victory-nikke"]["avoid"] is False and g["honkai-star-rail"]["avoid"] is True
               and g["blue-archive"]["avoid"] is False,
               "스타레일만 하단 거름, 니케(본질 경험 개방)·블루 아카이브는 추천/조건부", str([c["id"] for c in gacha if c["avoid"]]))
        expect("선택 과금 · 무과금 가능" in g["blue-archive"]["text"], "블루 아카이브 카드에 '선택 과금' 배지",
               g["blue-archive"]["text"][:180])
        expect("선택 과금 · 무과금 가능" in g["goddess-of-victory-nikke"]["text"],
               "니케 카드에 '선택 과금' 배지(본질 경험 기준)", g["goddess-of-victory-nikke"]["text"][:180])
        expect("3돌" in g["goddess-of-victory-nikke"]["text"] or "160" in g["goddess-of-victory-nikke"]["text"],
               "니케 카드에 160벽 사실 유지", g["goddess-of-victory-nikke"]["text"][:220])

        page.goto(f"{base}/?domain=game&arena=mobile-gacha-rpg&item=goddess-of-victory-nikke", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("160" in body and "마일리지" in body, "니케 160벽·마일리지 서술", "")
        expect("무과금 충분성" in body and "무과금으로 충분" in body, "니케 무과금 = 충분 표기(본질 경험)", "")
        expect("선택 과금" in body and "스토리" in body, "니케 상세에 선택 과금·스토리 본질 서술", "")
        close_modal(page)

        # strict_monetization 을 켜면 같은 니케가 다시 거름 — 사실은 지우지 않는다
        page.goto(f"{base}/?domain=game&arena=mobile-gacha-rpg&strictmon=1", wait_until="networkidle")
        wait(page, 700)
        nikke_strict = card(page, "goddess-of-victory-nikke")
        expect(nikke_strict and nikke_strict["avoid"] is True,
               "strict_monetization ON → 니케 거름", str(nikke_strict and nikke_strict["text"])[:140])
        page.goto(f"{base}/?domain=game&arena=mobile-gacha-rpg", wait_until="networkidle")
        wait(page, 500)

        page.goto(f"{base}/?domain=game&arena=mobile-gacha-rpg&item=blue-archive", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("무과금 충분성" in body and "200회" in body, "블루 아카이브 무과금 충분성·200회 천장", "")
        expect("모집 스택" in body or "100회" in body, "블루 아카이브 모집 스택 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=mobile-gacha-rpg&item=honkai-star-rail", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("워프" in body and "확률형" in body, "스타레일 워프·확률형 사유", "")
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=mobile-gacha-rpg&item=limbus-company", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("선택 과금" in body and "자판기" in body, "Limbus 선택 과금·자판기 사유", "")
        expect("광고 없음" in body or "광고" in body, "Limbus 광고 없음 서술", "")
        close_modal(page)

        # ------------------------------- 10-3 2차 확장: PC MMORPG · 모바일 전략·디펜스
        page.goto(f"{base}/?domain=game&arena=pc-mmorpg", wait_until="networkidle")
        wait(page, 700)
        expect("arena=pc-mmorpg" in page.url, "PC MMORPG 비교군 URL", path_id(page))
        mmo = cards(page)
        expect(len(mmo) == 4, "PC MMORPG 카드 4건", str([c["id"] for c in mmo]))
        ms = stats(page)
        expect(ms.get("추천") == "2" and ms.get("조건부") == "1" and ms.get("거름") == "1",
               "PC MMORPG 요약 2/1/1", str(ms))
        expect(ms.get("평균 가중 점수") == "71.2", "PC MMORPG 평균 71.2", str(ms))
        m = {c["id"]: c for c in mmo}
        for item_id, verdict, score in (("final-fantasy-xiv", "recommend", 82.5), ("guild-wars-2", "recommend", 80.0),
                                        ("lost-ark", "avoid", 42.75), ("black-desert", "conditional", 79.5)):
            c = m.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(m["guild-wars-2"]["avoid"] is False and m["black-desert"]["avoid"] is False and m["lost-ark"]["avoid"] is True,
               "Lost Ark 만 하단 거름 영역(GW2 는 추천, BDO 는 조건부)")
        expect("선택 과금 · 무과금 가능" in m["black-desert"]["text"], "BDO 카드에 '선택 과금 · 무과금 가능' 배지",
               m["black-desert"]["text"][:180])
        expect("선택 과금 · 무과금 가능" in m["guild-wars-2"]["text"], "GW2 카드에 '선택 과금' 배지",
               m["guild-wars-2"]["text"][:180])

        page.goto(f"{base}/?domain=game&arena=pc-mmorpg&item=final-fantasy-xiv", wait_until="networkidle")
        wait(page, 700)
        expect(page.inner_text("#modalTitle") == "FINAL FANTASY XIV", "FFXIV 상세 열기", page.inner_text("#modalTitle"))
        body = page.inner_text("#modalBody")
        expect("19,800" in body, "FFXIV 한국 30일 이용권 19,800원", "")
        expect("80" in body and "무료" in body, "FFXIV 80레벨 무료 체험 서술", "")
        expect("구독" in body, "FFXIV 구독 필터 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=pc-mmorpg&item=guild-wars-2", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("확률형 아이템 제외 선택 과금" in body, "GW2 확률형 아이템 = 선택 과금(적중 아님)", "")
        expect("블랙 라이온" in body, "GW2 블랙 라이온 상자 서술", "")
        expect("무과금 충분성" in body and "무과금으로 충분" in body, "GW2 무과금 충분성 표기", "")
        alts = page.eval_on_selector_all("#secAlternatives .alt-row", "els => els.map(e => e.dataset.item)")
        expect(alts == ["final-fantasy-xiv"], "GW2 대체제 = 같은 비교군 추천 1건(BDO 는 조건부)", str(alts))
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=mobile-strategy-defense", wait_until="networkidle")
        wait(page, 700)
        expect("arena=mobile-strategy-defense" in page.url, "모바일 전략·디펜스 비교군 URL", path_id(page))
        mob = cards(page)
        expect(len(mob) == 6, "모바일 전략·디펜스 카드 6건", str([c["id"] for c in mob]))
        mst = stats(page)
        expect(mst.get("추천") == "4" and mst.get("조건부") == "0" and mst.get("거름") == "2",
               "모바일 전략·디펜스 요약 4/0/2", str(mst))
        expect(mst.get("평균 가중 점수") == "74.3", "모바일 전략·디펜스 평균 74.3", str(mst))
        d = {c["id"]: c for c in mob}
        for item_id, verdict, score in (("bloons-td-6", "recommend", 84.5), ("kingdom-rush-vengeance", "recommend", 84.0),
                                        ("clash-royale", "avoid", 61.0), ("plants-vs-zombies-2", "avoid", 52.5)):
            c = d.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])

        for item_id, verdict, score in (("clash-of-clans", "recommend", 81.50), ("arknights", "recommend", 82.00)):
            c = d.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(d["arknights"]["avoid"] is False and d["clash-of-clans"]["avoid"] is False,
               "아크나이츠·클래시 오브 클랜은 거름 아님", str([c["id"] for c in mob if c["avoid"]]))
        expect("선택 과금 · 무과금 가능" in d["arknights"]["text"], "아크나이츠 카드에 '선택 과금' 배지",
               d["arknights"]["text"][:180])
        expect("선택 과금 · 무과금 가능" in d["clash-of-clans"]["text"], "클래시 오브 클랜 카드에 '선택 과금' 배지",
               d["clash-of-clans"]["text"][:180])

        page.goto(f"{base}/?domain=game&arena=mobile-strategy-defense&item=clash-of-clans", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("무작위 아이템" in body and "골드 패스" in body, "CoC 무작위 아이템·골드 패스 서술", "")
        expect("무과금 충분성" in body and "무과금으로 충분" in body, "CoC 무과금 충분성 표기", "")
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=mobile-strategy-defense&item=arknights", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("6성 2%" in body and "150" in body, "아크나이츠 6성 2%·150 보장 서술", "")
        expect("무과금 충분성" in body and "무과금으로 충분" in body, "아크나이츠 무과금 충분성 표기", "")
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=mobile-strategy-defense&item=bloons-td-6", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("확률형 아이템 제외 선택 과금" in body, "BTD6 확률형 아이템 = 선택 과금(적중 아님)", "")
        expect("6,500" in body and "광고" in body, "BTD6 가격·광고 서술", "")
        expect("무과금 충분성" in body and "무과금으로 충분" in body, "BTD6 무과금 충분성 표기", "")
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=mobile-strategy-defense&item=clash-royale", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("P2W" in body and "확률형 아이템" in body, "Clash Royale P2W·확률형 사유", "")
        expect("365,000" in body, "Clash Royale IAP 최고가 365,000원", "")
        close_modal(page)

        # ------------------------------ 10-4 v0.4 확률형·P2W 강도 3단계 + strict_monetization
        page.goto(f"{base}/?domain=game&arena=pc-mmorpg", wait_until="networkidle")
        wait(page, 700)
        open_drawer(page)
        expect(page.is_visible("#strictMonetizationToggle"), "미세조정에 strict_monetization 토글")
        expect(page.is_checked("#strictMonetizationToggle") is False, "strict_monetization 기본 OFF")
        expect(page.inner_text("#strictMonetizationState").strip() == "OFF", "strict_monetization 상태 표시 OFF")
        expect("상점에 확률형·P2W 상품이 하나라도 있으면 거름" in page.inner_text("#tuneBody"), "토글 라벨 문구", "")
        page.click("#strictMonetizationToggle + .switch-track")
        wait(page, 550)
        expect(page.inner_text("#strictMonetizationState").strip() == "ON", "strict_monetization 켜기")
        expect("strictmon=1" in page.url, "토글이 URL 에 반영", path_id(page))
        bdo_strict = card(page, "black-desert")
        expect(bdo_strict and bdo_strict["verdict"] == "avoid" and bdo_strict["avoid"] is True,
               "strict ON → BDO 거름", str(bdo_strict and bdo_strict["text"])[:120])
        expect("선택 과금 · 무과금 가능" not in (bdo_strict["text"] if bdo_strict else ""),
               "strict ON 이면 배지 대신 적중으로 표시", str(bdo_strict and bdo_strict["text"])[:120])
        page.click("#strictMonetizationToggle + .switch-track")
        wait(page, 550)
        expect(page.inner_text("#strictMonetizationState").strip() == "OFF", "strict_monetization 되돌리기")
        expect("strictmon" not in page.url, "끄면 URL 에서 빠짐", path_id(page))
        bdo_off = card(page, "black-desert")
        expect(bdo_off and bdo_off["verdict"] == "conditional", "strict OFF → BDO 조건부(79.5)", str(bdo_off)[:100])
        close_drawer(page)

        page.goto(f"{base}/?domain=game&arena=mobile-strategy-defense", wait_until="networkidle")
        wait(page, 700)
        expect("선택 과금 · 무과금 가능" in (card(page, "bloons-td-6") or {}).get("text", ""),
               "Bloons 카드에 선택 과금 배지", "")
        clash_card = card(page, "clash-royale")
        expect(clash_card and clash_card["avoid"] is True and "핵심 과금" in clash_card["text"],
               "Clash Royale 는 impact core로 거름", str(clash_card and clash_card["text"])[:140])

        # 상세 08번의 강도·무과금 충분성
        page.goto(f"{base}/?domain=game&arena=pc-mmorpg&item=black-desert", wait_until="networkidle")
        wait(page, 800)
        body = page.inner_text("#modalBody")
        expect("P2W 강도" in body and "IMPACT" in body.upper(), "상세에 확률형·P2W 강도 블록", "")
        expect("선택 과금 · 무과금 가능" in body and "무과금으로 충분" in body, "상세에 선택 과금·무과금 충분성", "")
        expect("시즌" in body and "투발라" in body, "BDO 무과금 근거(시즌·투발라) 서술", "")
        close_modal(page)

        # 엔진 단위 테스트 — impact 3단계·추론·토글
        impact_unit = page.evaluate(
            """() => {
            const { engine, state } = window.Pharos;
            const contract = state.contract || state.core.contract;
            const passes = Object.fromEntries(contract.hard_filters.map(f => [f.key, {status:'pass', evidence_grade:'A', note:''}]));
            const mk = (hard) => ({
              axes: {user_rating:{score:90,signal:'green'}, objective:{score:90,signal:'green'}, ai_review:{score:90,signal:'green'}},
              tiers: [{tier_id:'t', label:'T', kind:'one_time', price:{display:'₩1'}, hard_filters:{...passes, ...hard}, verdict:'conditional'}],
              verdict: {tier_of_record:'t'},
            });
            const settings = (strictMon) => ({contract, weights:{user_rating:40,objective:35,ai_review:25},
              enabledFilters:['gacha_random_items','p2w'], strict:true, strictMonetization:!!strictMon});
            const opt = mk({gacha_random_items:{status:'fail', evidence_grade:'A', note:'x', impact:'optional'}});
            const core = mk({gacha_random_items:{status:'fail', evidence_grade:'A', note:'x', impact:'core'}});
            const inferred = mk({p2w:{status:'fail', evidence_grade:'A', note:'x'}});
            const e1 = engine.evaluateTier(opt, opt.tiers[0], settings(false));
            const e2 = engine.evaluateTier(opt, opt.tiers[0], settings(true));
            const e3 = engine.evaluateTier(core, core.tiers[0], settings(false));
            const e4 = engine.evaluateTier(inferred, inferred.tiers[0], settings(false));
            return {
              optionalVerdict: e1.verdict, optionalBlocking: e1.blocking.length,
              optionalBadges: e1.optionalFails.map(f => f.key),
              strictVerdict: e2.verdict, strictBlocking: e2.blocking.length,
              coreVerdict: e3.verdict,
              inferredImpact: e4.filterChecks.find(f => f.key === 'p2w').impact, inferredVerdict: e4.verdict,
              keys: engine.MONETIZATION_IMPACT_KEYS.join(','), label: engine.IMPACT_META.optional.label,
              badgeText: contract.monetization_impact.badge.optional,
            };
        }"""
        )
        expect(impact_unit["optionalVerdict"] == "recommend" and impact_unit["optionalBlocking"] == 0,
               "엔진: impact optional → 차단 없이 추천", str(impact_unit))
        expect(impact_unit["optionalBadges"] == ["gacha_random_items"], "엔진: optionalFails 에 기록", str(impact_unit["optionalBadges"]))
        expect(impact_unit["strictVerdict"] == "avoid" and impact_unit["strictBlocking"] == 1,
               "엔진: strict_monetization → optional 도 거름", str(impact_unit["strictVerdict"]))
        expect(impact_unit["coreVerdict"] == "avoid", "엔진: impact core → 거름", impact_unit["coreVerdict"])
        expect(impact_unit["inferredImpact"] == "core" and impact_unit["inferredVerdict"] == "avoid",
               "엔진: impact 미기록 fail → core 추론", str(impact_unit["inferredImpact"]))
        expect(impact_unit["keys"] == "gacha_random_items,p2w", "엔진: impact 키 = 확률형·P2W", impact_unit["keys"])
        expect(impact_unit["label"] == "선택 과금 · 무과금 가능", "엔진: 선택 과금 라벨", impact_unit["label"])

        # ------------------------------------------------ 10-5 공식 아이콘 (v2.1)
        icon_index = page.evaluate(
            """() => {
            const items = window.Pharos.state.core.index.items;
            return {total: items.length, withIcon: items.filter(i => i.icon).length,
                    missing: items.filter(i => !i.icon).map(i => i.id)};
        }"""
        )
        expect(icon_index["withIcon"] == 57 and icon_index["total"] == 57,
               "검색 인덱스 57건 모두 icon 경로를 가짐", str(icon_index))

        icon_load = page.evaluate(
            """async () => {
            const items = window.Pharos.state.core.index.items;
            const load = (src) => new Promise((res) => {
              const im = new Image();
              im.onload = () => res(im.naturalWidth > 0 && im.naturalHeight > 0);
              im.onerror = () => res(false);
              im.src = src;
            });
            const results = await Promise.all(items.map(i => load('./' + i.icon)));
            return {ok: results.filter(Boolean).length, total: results.length,
                    bad: items.filter((_, k) => !results[k]).map(i => i.id)};
        }"""
        )
        expect(icon_load["ok"] == 57, "57종 공식 아이콘 파일이 모두 실제 이미지로 로드됨", str(icon_load))

        page.goto(f"{base}/?domain=game&arena=mobile-gacha-rpg", wait_until="networkidle")
        wait(page, 700)
        card_icons = page.evaluate(
            """() => [...document.querySelectorAll('#grid .card, #avoidGrid .card')].map(card => {
              const wrap = card.querySelector('.item-icon--card');
              const img = wrap && wrap.querySelector('img');
              return { id: card.dataset.id, hasIcon: !!img,
                       loaded: !!img && img.complete && img.naturalWidth > 0,
                       size: wrap ? Math.round(wrap.getBoundingClientRect().width) : 0,
                       objectFit: img ? getComputedStyle(img).objectFit : '',
                       radius: wrap ? getComputedStyle(wrap).borderRadius : '' };
            })"""
        )
        expect(len(card_icons) == 6 and all(c["hasIcon"] and c["loaded"] for c in card_icons),
               "모바일 수집형 RPG 카드 6건 모두 아이콘 로드(complete && naturalWidth>0)",
               str([c for c in card_icons if not c["loaded"]] or len(card_icons)))
        expect(all(44 <= c["size"] <= 48 for c in card_icons), "카드 아이콘 44~48px", str([c["size"] for c in card_icons]))
        expect(all(c["objectFit"] == "cover" for c in card_icons), "카드 아이콘 object-fit: cover", str(card_icons[:1]))
        expect(all(c["radius"] == "10px" for c in card_icons), "카드 아이콘 둥근 사각형 10px", str(card_icons[:1]))

        page.goto(f"{base}/?domain=app&arena=pkm-notes", wait_until="networkidle")
        wait(page, 700)
        all_imgs = page.evaluate(
            """() => [...document.querySelectorAll('#grid .card img, #avoidGrid .card img')]
                 .map(i => ({src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0}))"""
        )
        expect(len(all_imgs) == 5 and all(i["ok"] for i in all_imgs),
               "노트 비교군 카드의 모든 <img> 가 정상 로드", str(all_imgs))
        expect(all("assets/icons/" in i["src"] for i in all_imgs), "카드 아이콘이 web/assets/icons/ 로컬 파일", str(all_imgs[:1]))

        page.click('#grid .card[data-id="obsidian"]')
        wait(page, 700)
        modal_icon = page.evaluate(
            """() => {
              const wrap = document.querySelector('#modalIcon .item-icon');
              const img = wrap && wrap.querySelector('img');
              return {has: !!wrap, loaded: !!img && img.complete && img.naturalWidth > 0,
                      size: wrap ? Math.round(wrap.getBoundingClientRect().width) : 0,
                      src: img ? img.getAttribute('src') : ''};
            }"""
        )
        expect(modal_icon["has"] and modal_icon["loaded"], "상세 모달 머리에 아이콘 로드", str(modal_icon))
        expect(52 <= modal_icon["size"] <= 56, "상세 아이콘 52~56px", str(modal_icon["size"]))
        expect(modal_icon["src"].endswith("assets/icons/obsidian.webp"), "상세 아이콘이 그 항목의 파일", modal_icon["src"])
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=roguelike-deckbuilder", wait_until="networkidle")
        wait(page, 600)
        page.check('#grid .card[data-id="balatro"] input[data-compare]')
        wait(page, 200)
        page.check('#grid .card[data-id="slay-the-spire"] input[data-compare]')
        wait(page, 300)
        page.click("#compareOpen")
        wait(page, 600)
        compare_icons = page.evaluate(
            """() => [...document.querySelectorAll('#compareTable thead th .item-icon')].map(wrap => {
              const img = wrap.querySelector('img');
              return {size: Math.round(wrap.getBoundingClientRect().width), loaded: !!img && img.complete && img.naturalWidth > 0};
            })"""
        )
        expect(len(compare_icons) == 2 and all(c["loaded"] for c in compare_icons), "비교 표 머리글 아이콘 2건 로드", str(compare_icons))
        expect(all(30 <= c["size"] <= 34 for c in compare_icons), "비교 표 아이콘 32px", str([c["size"] for c in compare_icons]))
        table_headers = page.eval_on_selector_all("#compareTable thead th", "els => els.map(e => e.innerText.split('\\n')[0])")
        expect(table_headers == ["기준", "Balatro", "Slay the Spire"], "아이콘을 넣어도 비교 표 머리글 텍스트 유지", str(table_headers))

        page.goto(f"{base}/", wait_until="networkidle")
        wait(page, 600)
        gap_icons = page.evaluate(
            """() => [...document.querySelectorAll('.gap-row .item-icon')].map(wrap => {
              const img = wrap.querySelector('img');
              return !!img && img.complete && img.naturalWidth > 0;
            })"""
        )
        expect(len(gap_icons) == 4 and all(gap_icons), "갭 리포트 4건 아이콘 로드", str(gap_icons))
        page.fill("#homeSearch", "니케")
        wait(page, 400)
        search_icons = page.evaluate(
            """() => [...document.querySelectorAll('.search-row .item-icon')].map(wrap => {
              const img = wrap.querySelector('img');
              return !!img && img.complete && img.naturalWidth > 0;
            })"""
        )
        expect(bool(search_icons) and all(search_icons), "홈 통합 검색 결과 아이콘 로드", str(search_icons))
        page.fill("#homeSearch", "")
        wait(page, 250)

        # 이미지가 깨져도 깨진 아이콘 대신 이니셜 배지가 남는지(대체 표시)
        fallback = page.evaluate(
            """() => {
              const wrap = document.createElement('span');
              wrap.className = 'item-icon item-icon--card';
              wrap.dataset.initial = 'X';
              const img = document.createElement('img');
              img.src = 'data:image/png;base64,AAAA';
              wrap.appendChild(img);
              document.body.appendChild(wrap);
              return new Promise((res) => setTimeout(() => {
                const badge = getComputedStyle(wrap, '::before').content;
                const hidden = img.hidden;
                wrap.remove();
                res({badge, hidden});
              }, 500));
            }"""
        )
        expect(fallback["hidden"] is True and "X" in str(fallback["badge"]),
               "아이콘 로드 실패 시 이니셜 배지로 대체", str(fallback))

        # ------------------- 10-6 v0.4.2 분야 확장: 할 일 · 비밀번호 · AI 코딩
        page.goto(f"{base}/?domain=app", wait_until="networkidle")
        wait(page, 600)
        app_head = page.inner_text(".level-head")
        app_h1 = page.inner_text(".level-head h1")
        expect("앱 — 장르 5 · 24건" in app_h1, "앱 도메인 헤더 = 장르 5 · 24건", app_h1)
        app_cats = page.eval_on_selector_all(".chip--link", "els => els.map(e => e.dataset.category)")
        expect(app_cats == ["productivity", "security-utilities", "internet-privacy"], "앱 도메인 대분류 3개(생산성·보안·인터넷)", str(app_cats))
        app_arenas = page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)")
        expect(app_arenas == ["pkm-notes", "task-managers", "password-managers", "web-browsers", "cloud-storage"], "앱 도메인 장르 블록 5개", str(app_arenas))
        expect("보안 · 유틸리티" in app_head and "인터넷 · 프라이버시" in app_head and "필터 팩 · 앱 팩" in app_head, "앱 도메인에 새 대분류·필터 팩 표시", app_head)

        todo_picks = page.eval_on_selector_all('.genre-block[data-arena="task-managers"] .pick-tile',
                                               "els => els.map(e => e.dataset.item)")
        expect(todo_picks == ["things-3", "tasks-org", "todoist", "ticktick"],
               "할 일 장르 타일 = 추천 점수순 4개(거름 MS To Do 제외)", str(todo_picks))
        pw_picks = page.eval_on_selector_all('.genre-block[data-arena="password-managers"] .pick-tile',
                                             "els => els.map(e => e.dataset.item)")
        expect(pw_picks == ["bitwarden", "1password", "keepassxc", "dashlane"],
               "비밀번호 장르 타일 = 추천 3 + 조건부 1", str(pw_picks))
        new_tile_icons = page.eval_on_selector_all(
            '.genre-block[data-arena="task-managers"] .pick-tile .item-icon, '
            '.genre-block[data-arena="password-managers"] .pick-tile .item-icon, '
            '.genre-block[data-arena="ai-coding-tools"] .pick-tile .item-icon',
            "els => els.map(e => { const img = e.querySelector('img');"
            " return {size: Math.round(e.getBoundingClientRect().width), loaded: !!img && img.complete && img.naturalWidth > 0}; })",
        )
        expect(len(new_tile_icons) == 8 and all(40 <= t["size"] <= 48 and t["loaded"] for t in new_tile_icons),
               "앱 도메인 신규 타일 아이콘 8건 40px+ 로드", str(new_tile_icons[:3]))

        # --- 할 일 · 일정 관리 비교군
        page.goto(f"{base}/?domain=app&arena=task-managers", wait_until="networkidle")
        wait(page, 700)
        tm = cards(page)
        expect(len(tm) == 5, "할 일 비교군 5건", str([c["id"] for c in tm]))
        expect(page.inner_text("#listCount").strip() == "5/5건", "할 일 목록 건수 5/5", page.inner_text("#listCount"))
        tms = stats(page)
        expect(tms.get("추천") == "4" and tms.get("조건부") == "0" and tms.get("거름") == "1", "할 일 요약 4/0/1", str(tms))
        expect(tms.get("평균 가중 점수") == "82.5", "할 일 평균 82.5", str(tms))
        tm_by = {c["id"]: c for c in tm}
        for item_id, verdict, score in (("tasks-org", "recommend", 88.0), ("things-3", "recommend", 89.0),
                                        ("todoist", "recommend", 85.0), ("ticktick", "recommend", 83.5),
                                        ("microsoft-to-do", "avoid", 66.75)):
            c = tm_by.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(tm_by["microsoft-to-do"]["avoid"] is True, "Microsoft To Do 는 하단 거름 영역")
        expect("별점" not in tm_by["tasks-org"]["text"], "목록 카드에는 별점 대신 판정·점수", tm_by["tasks-org"]["text"][:120])

        page.goto(f"{base}/?domain=app&arena=task-managers&item=microsoft-to-do", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("2027-06-30" in body and "종료" in body, "MS To Do 상세에 종료일 명시", body[:200])
        expect("이전되지 않" in body or "Planner" in body, "MS To Do 개인 계정 이관 불가 서술", "")
        expect("내보내기" in body, "MS To Do 내보내기 미공개 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=app&arena=task-managers&item=things-3", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("구독 없음" in body and "1회 구매" in body, "Things 3 구독 없음·1회 구매 표기", "")
        expect("세일" in body or "6.99" in body, "Things 3 세일가 표기", "")
        expect("Android" in body and "없다" in body, "Things 3 Apple 전용 한계 표기", "")
        close_modal(page)

        # --- 비밀번호 관리 비교군
        page.goto(f"{base}/?domain=app&arena=password-managers", wait_until="networkidle")
        wait(page, 700)
        pw = cards(page)
        expect(len(pw) == 4, "비밀번호 비교군 4건", str([c["id"] for c in pw]))
        pws = stats(page)
        expect(pws.get("추천") == "3" and pws.get("조건부") == "1" and pws.get("거름") == "0", "비밀번호 요약 3/1/0", str(pws))
        expect(pws.get("평균 가중 점수") == "84.9", "비밀번호 평균 84.9", str(pws))
        pw_by = {c["id"]: c for c in pw}
        for item_id, verdict, score in (("bitwarden", "recommend", 91.5), ("keepassxc", "recommend", 84.0),
                                        ("1password", "recommend", 86.0), ("dashlane", "conditional", 78.25)):
            c = pw_by.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect("구독 필수" in pw_by["1password"]["text"] or "무료" in pw_by["1password"]["text"],
               "1Password 카드에 무료 플랜 없음 표시", pw_by["1password"]["text"][:160])

        # '구독 필수' 필터를 켜면 무료 플랜이 없는 두 항목이 거름으로 내려간다
        open_drawer(page)
        set_filter(page, "subscription_required", True)
        expect(page.inner_text("#filterCount").strip() == "5/9", "구독 필수 필터 켜기 → 5/9", page.inner_text("#filterCount"))
        close_drawer(page)
        wait(page, 300)
        expect(card(page, "1password")["avoid"] is True and card(page, "dashlane")["avoid"] is True,
               "구독 필수 ON → 1Password·Dashlane 거름", str([c["id"] for c in cards(page) if c["avoid"]]))
        expect(card(page, "bitwarden")["avoid"] is False and card(page, "keepassxc")["avoid"] is False,
               "구독 필수 ON 에도 무료 티어 항목은 유지")
        open_drawer(page)
        set_filter(page, "subscription_required", False)
        close_drawer(page)
        wait(page, 300)

        page.goto(f"{base}/?domain=app&arena=password-managers&item=dashlane", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("무차별 대입" in body and "20명" in body, "Dashlane 2026-06 사고 서술", "")
        expect("무료 플랜" in body and "종료" in body, "Dashlane 무료 플랜 종료 서술", "")
        expect("Intigriti" in body or "SOC 2" in body, "Dashlane 감사·인증 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=app&arena=password-managers&item=keepassxc", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("모바일" in body and "없" in body, "KeePassXC 모바일 앱 없음 서술", "")
        expect("미확인" in body or "⚪" in body, "KeePassXC 사용자 평가 ⚪ 표기", "")
        close_modal(page)

        # --- AI 도구 도메인
        page.goto(f"{base}/?domain=ai", wait_until="networkidle")
        wait(page, 700)
        expect("domain=ai" in page.url, "AI 도구 도메인 URL", path_id(page))
        ai_head = page.inner_text(".level-head")
        expect("AI 도구 — 장르 2 · 9건" in page.inner_text(".level-head h1"), "AI 도메인 헤더 = 장르 2 · 9건", ai_head[:120])
        ai_cats = page.eval_on_selector_all(".chip--link", "els => els.map(e => e.dataset.category)")
        expect(ai_cats == ["ai-chat-research", "ai-coding"], "AI 도메인 대분류 2개(대화·리서치·개발·코딩)", str(ai_cats))
        expect("AI 도구 팩" in ai_head, "AI 도메인 필터 팩 표시", ai_head)
        ai_blocks = page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)")
        expect(ai_blocks == ["ai-assistants", "ai-coding-tools"], "AI 도메인 장르 블록 2개", str(ai_blocks))
        ai_dom_picks = page.eval_on_selector_all('.genre-block[data-arena="ai-coding-tools"] .pick-tile',
                                                 "els => els.map(e => e.dataset.item)")
        expect(ai_dom_picks == ["github-copilot", "cline", "cursor", "windsurf"], "AI 도메인 추천 타일 4개", str(ai_dom_picks))

        page.goto(f"{base}/?domain=ai&arena=ai-coding-tools", wait_until="networkidle")
        wait(page, 700)
        ai = cards(page)
        expect(len(ai) == 4, "AI 코딩 비교군 4건", str([c["id"] for c in ai]))
        ais = stats(page)
        expect(ais.get("추천") == "2" and ais.get("조건부") == "2" and ais.get("거름") == "0", "AI 코딩 요약 2/2/0", str(ais))
        expect(ais.get("평균 가중 점수") == "81.1", "AI 코딩 평균 81.1", str(ais))
        ai_by = {c["id"]: c for c in ai}
        for item_id, verdict, score in (("cline", "recommend", 84.25), ("github-copilot", "recommend", 84.5),
                                        ("windsurf", "conditional", 77.5), ("cursor", "conditional", 78.0)):
            c = ai_by.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect("검토 필요" not in ai_by["cursor"]["text"], "Cursor 목록 카드에는 신선도 대신 판정만", ai_by["cursor"]["text"][:140])
        ai_card_icons = page.evaluate(
            """() => [...document.querySelectorAll('#grid .card, #avoidGrid .card')].map(card => {
              const img = card.querySelector('.item-icon--card img');
              return {id: card.dataset.id, loaded: !!img && img.complete && img.naturalWidth > 0};
            })""")
        expect(len(ai_card_icons) == 4 and all(c["loaded"] for c in ai_card_icons), "AI 코딩 카드 4건 아이콘 로드", str(ai_card_icons))

        # AI 도메인의 필터 표시 이름 — 같은 9개 필터를 크레딧 문법으로 부른다
        open_drawer(page)
        ai_packs = page.eval_on_selector_all("#tuneBody .filter-pack summary", "els => els.map(e => e.innerText.split('\\n')[0])")
        expect(ai_packs[0].startswith("AI 도구 팩"), "AI 도메인은 AI 도구 팩을 먼저 노출", str(ai_packs))
        drawer_text = page.inner_text("#tuneBody")
        expect("불투명 크레딧·한도 함정 제외" in drawer_text, "AI 도메인 필터 이름 = 불투명 크레딧·한도 함정 제외", drawer_text[:200])
        expect("계정·클라우드 강제 제외" in drawer_text, "AI 도메인 필터 이름 = 계정·클라우드 강제 제외", "")
        close_drawer(page)

        page.goto(f"{base}/?domain=ai&arena=ai-coding-tools&item=cursor", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("서드파티 모델" in body and "API 정가" in body, "Cursor 서드파티 모델 별도 과금 서술", "")
        expect("첫 요청" in body or "30" in body, "Cursor $30 플랜·첫 요청 과금 서술", "")
        expect("G2" in body or "3.7" in body, "Cursor 최근 리뷰 하락 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=ai&arena=ai-coding-tools&item=github-copilot", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("AI 크레딧" in body and "0.01" in body, "Copilot AI 크레딧 단가 서술", "")
        expect("완성" in body and "크레딧을 쓰지 않" in body, "Copilot 코드 완성 = 크레딧 미소모", "")
        close_modal(page)

        page.goto(f"{base}/?domain=ai&arena=ai-coding-tools&item=windsurf", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("Devin Desktop" in body and "쿼터" in body, "Windsurf 개명·쿼터 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=ai&arena=ai-coding-tools&item=cline", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("Apache" in body and "BYOK" in body, "Cline 오픈소스·BYOK 서술", "")
        close_modal(page)

        # --------------------------- 10-7 v0.4.3 분야 확장: 브라우저 · 클라우드 · AI 어시스턴트
        page.goto(f"{base}/?domain=app", wait_until="networkidle")
        wait(page, 600)
        for arena, picks in (
            ("web-browsers", ["brave", "firefox", "vivaldi", "edge"]),
            ("cloud-storage", ["proton-drive", "google-drive", "onedrive", "nextcloud"]),
        ):
            tiles = page.eval_on_selector_all(f'.genre-block[data-arena="{arena}"] .pick-tile',
                                              "els => els.map(e => e.dataset.item)")
            expect(tiles == picks, f"{arena} 장르 타일 = 추천 점수순 4개", str(tiles))
        new_blocks = page.eval_on_selector_all(
            '.genre-block[data-arena="web-browsers"], .genre-block[data-arena="cloud-storage"]',
            "els => els.map(e => ({arena: e.dataset.arena, text: e.innerText.replace(/\\n/g, ' | ')}))")
        expect(len(new_blocks) == 2 and all("전체 5종 비교" in b["text"] for b in new_blocks),
               "새 앱 비교군 2개 블록에 '전체 5종 비교' 링크", str(new_blocks)[:160])
        expect("인터넷 · 프라이버시" in new_blocks[0]["text"] and "보안 · 유틸리티" in new_blocks[1]["text"],
               "새 블록이 각자의 새 대분류를 표시", str([b["text"][:47] for b in new_blocks]))
        new_block_icons = page.eval_on_selector_all(
            '.genre-block[data-arena="web-browsers"] .pick-tile .item-icon, '
            '.genre-block[data-arena="cloud-storage"] .pick-tile .item-icon',
            "els => els.map(e => { const img = e.querySelector('img');"
            " return {size: Math.round(e.getBoundingClientRect().width), loaded: !!img && img.complete && img.naturalWidth > 0}; })")
        expect(len(new_block_icons) == 8 and all(40 <= t["size"] <= 48 and t["loaded"] for t in new_block_icons),
               "새 앱 비교군 타일 아이콘 8건 40px+ 로드", str(new_block_icons[:3]))

        # --- 웹 브라우저 비교군
        page.goto(f"{base}/?domain=app&arena=web-browsers", wait_until="networkidle")
        wait(page, 700)
        wb = cards(page)
        expect(len(wb) == 5, "웹 브라우저 비교군 5건", str([c["id"] for c in wb]))
        expect(page.inner_text("#listCount").strip() == "5/5건", "웹 브라우저 목록 건수 5/5", page.inner_text("#listCount"))
        wbs = stats(page)
        expect(wbs.get("추천") == "2" and wbs.get("조건부") == "3" and wbs.get("거름") == "0", "웹 브라우저 요약 2/3/0", str(wbs))
        expect(wbs.get("평균 가중 점수") == "80.7", "웹 브라우저 평균 80.7", str(wbs))
        wb_by = {c["id"]: c for c in wb}
        for item_id, verdict, score in (("brave", "recommend", 88.0), ("firefox", "recommend", 87.0),
                                        ("vivaldi", "conditional", 82.25), ("edge", "conditional", 76.0),
                                        ("chrome", "conditional", 70.0)):
            c = wb_by.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(all(c["avoid"] is False for c in wb), "웹 브라우저는 모두 거름 영역 밖", str([c["id"] for c in wb if c["avoid"]]))
        expect("인터넷 · 프라이버시" in page.inner_text(".level-head") and "웹 브라우저" in page.inner_text("#breadcrumb"),
               "웹 브라우저 화면의 대분류·경로 표시", page.inner_text(".level-head")[:80])
        expect("Manifest" not in wb_by["firefox"]["text"], "목록 카드에는 MV3 서술을 넣지 않음", wb_by["firefox"]["text"][:120])

        page.goto(f"{base}/?domain=app&arena=web-browsers&item=chrome", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("uBlock Origin" in body and "MV2" in body, "Chrome 상세에 MV2·uBlock Origin 제한 서술", body[:200])
        expect("서드파티 쿠키" in body and "Privacy Sandbox" in body, "Chrome 상세에 쿠키·Privacy Sandbox 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=app&arena=web-browsers&item=brave", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("Shields" in body and "기본" in body, "Brave 상세에 Shields 기본 차단 서술", "")
        expect("자사 광고" in body or "Brave Ads" in body, "Brave 상세에 자사 광고 기본 노출 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=app&arena=web-browsers&item=firefox", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("Total Cookie Protection" in body and "MV2" in body, "Firefox 상세에 쿠키 격리·MV2 유지 서술", "")
        expect("텔레메트리" in body, "Firefox 상세에 텔레메트리 기본값 서술", "")
        close_modal(page)

        # --- 클라우드 스토리지 비교군
        page.goto(f"{base}/?domain=app&arena=cloud-storage", wait_until="networkidle")
        wait(page, 700)
        cs = cards(page)
        expect(len(cs) == 5, "클라우드 비교군 5건", str([c["id"] for c in cs]))
        css = stats(page)
        expect(css.get("추천") == "3" and css.get("조건부") == "2" and css.get("거름") == "0", "클라우드 요약 3/2/0", str(css))
        expect(css.get("평균 가중 점수") == "81.7", "클라우드 평균 81.7", str(css))
        cs_by = {c["id"]: c for c in cs}
        for item_id, verdict, score in (("proton-drive", "recommend", 87.0), ("nextcloud", "conditional", 83.0),
                                        ("google-drive", "recommend", 81.5), ("dropbox", "conditional", 75.5),
                                        ("onedrive", "recommend", 81.25)):
            c = cs_by.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect("보안 · 유틸리티" in page.inner_text("#breadcrumb"), "클라우드는 기존 보안 · 유틸리티 대분류 아래", page.inner_text("#breadcrumb"))

        page.goto(f"{base}/?domain=app&arena=cloud-storage&item=proton-drive", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("종단간" in body and "12개월" in body, "Proton 상세에 E2EE·12개월 유예 서술", body[:200])
        close_modal(page)

        page.goto(f"{base}/?domain=app&arena=cloud-storage&item=dropbox", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("2GB" in body and "3기기" in body, "Dropbox 상세에 무료 2GB·3기기 서술", "")
        expect("삭제" in body and "30일" in body, "Dropbox 상세에 초과 시 삭제·30일 복구 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=app&arena=cloud-storage&item=onedrive", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("3개월" in body and "6개월" in body, "OneDrive 상세에 동결 3개월·삭제 6개월 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=app&arena=cloud-storage&item=nextcloud", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("자체 호스팅" in body and "AGPL" in body, "Nextcloud 상세에 자체 호스팅·AGPL 서술", "")
        close_modal(page)

        # --- AI 어시스턴트 · 검색 비교군 + AI 도메인의 두 비교군
        page.goto(f"{base}/?domain=ai&arena=ai-assistants", wait_until="networkidle")
        wait(page, 700)
        ai2 = cards(page)
        expect(len(ai2) == 5, "AI 어시스턴트 비교군 5건", str([c["id"] for c in ai2]))
        expect(page.inner_text("#listCount").strip() == "5/5건", "AI 어시스턴트 목록 건수 5/5", page.inner_text("#listCount"))
        ais = stats(page)
        expect(ais.get("추천") == "4" and ais.get("조건부") == "1" and ais.get("거름") == "0", "AI 어시스턴트 요약 4/1/0", str(ais))
        expect(ais.get("평균 가중 점수") == "83.3", "AI 어시스턴트 평균 83.3", str(ais))
        ai_by = {c["id"]: c for c in ai2}
        for item_id, verdict, score in (("claude", "recommend", 87.5), ("perplexity", "recommend", 84.5),
                                        ("chatgpt", "recommend", 84.0), ("gemini", "recommend", 81.5),
                                        ("le-chat", "conditional", 79.0)):
            c = ai_by.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect("대화 · 리서치" in page.inner_text(".level-head") and "AI 어시스턴트" in page.inner_text("#breadcrumb"),
               "AI 어시스턴트 화면의 새 대분류·경로", page.inner_text(".level-head")[:80])
        # AI 탭에는 두 비교군(대화·리서치 / 개발·코딩)이 함께 보이고 서로 전환된다
        page.click('#domainTabs [data-domain="ai"]')
        wait(page, 600)
        ai_tiles = page.eval_on_selector_all('.genre-block[data-arena="ai-assistants"] .pick-tile',
                                             "els => els.map(e => e.dataset.item)")
        expect(ai_tiles == ["claude", "perplexity", "chatgpt", "gemini"], "AI 어시스턴트 장르 타일 4개", str(ai_tiles))
        ai_blocks = page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)")
        expect(ai_blocks == ["ai-assistants", "ai-coding-tools"], "AI 탭 = 두 비교군 블록", str(ai_blocks))
        ai_cat_chips = page.eval_on_selector_all(".chip--link", "els => els.map(e => e.dataset.category)")
        expect(ai_cat_chips == ["ai-chat-research", "ai-coding"], "AI 탭 = 두 대분류 칩", str(ai_cat_chips))
        page.click('.genre-block[data-arena="ai-assistants"] .genre-title')
        wait(page, 700)
        expect("arena=ai-assistants" in page.url, "AI 탭에서 어시스턴트 비교군으로 이동", path_id(page))
        page.click('#domainTabs [data-domain="ai"]')
        wait(page, 500)
        page.click('.chip--link[data-category="ai-chat-research"]')
        wait(page, 500)
        expect("category=ai-chat-research" in page.url, "AI 대분류 '대화 · 리서치' URL", path_id(page))
        expect(page.eval_on_selector_all(".genre-block", "els => els.map(e => e.dataset.arena)") == ["ai-assistants"],
               "대화 · 리서치 대분류 아래 비교군 1개")

        page.goto(f"{base}/?domain=ai&arena=ai-assistants&item=chatgpt", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("광고" in body and "Free" in body, "ChatGPT 상세에 무료 광고 서술", body[:200])
        expect("Improve the model" in body or "학습" in body, "ChatGPT 상세에 학습 사용 기본값 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=ai&arena=ai-assistants&item=gemini", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("Flash-Lite" in body, "Gemini 상세에 무료 Flash-Lite 서술", "")
        close_modal(page)

        page.goto(f"{base}/?domain=ai&arena=ai-assistants&item=claude", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("ad-free" in body or "광고 없음" in body, "Claude 상세에 광고 없음 서술", "")
        expect("5년" in body, "Claude 상세에 학습 보존 5년 서술", "")
        close_modal(page)

        # 신규 15종 아이콘 — 파일 규칙과 로드 (검색 인덱스 경유)
        new_icons = page.evaluate(
            """async () => {
            const ids = ['claude','chatgpt','perplexity','gemini','le-chat','firefox','brave','vivaldi','chrome','edge',
                         'proton-drive','nextcloud','google-drive','dropbox','onedrive'];
            const items = window.Pharos.state.core.index.items.filter(i => ids.includes(i.id));
            const load = (src) => new Promise((res) => { const im = new Image();
              im.onload = () => res(im.naturalWidth === 192 && im.naturalHeight === 192); im.onerror = () => res(false);
              im.src = './' + src; });
            const results = await Promise.all(items.map(i => load(i.icon)));
            return {total: items.length, ok: results.filter(Boolean).length,
                    paths: items.map(i => i.icon), bad: items.filter((_, k) => !results[k]).map(i => i.id)};
        }"""
        )
        expect(new_icons["total"] == 15 and new_icons["ok"] == 15, "신규 15종 아이콘이 192×192로 로드", str(new_icons["bad"]))
        expect(all(p.startswith("assets/icons/") and p.endswith(".webp") for p in new_icons["paths"]),
               "신규 아이콘 경로 = assets/icons/{id}.webp", str(new_icons["paths"][:3]))
        compare_manifest = page.evaluate(
            """() => { const m = window.Pharos.state.core.index.items; return m.length; }"""
        )
        expect(compare_manifest == 57, "인덱스 57건 기준 신규 아이콘 검사", str(compare_manifest))

        # ------------------------------------------------------------- 11 스크린샷
        desktop = context.new_page()
        desktop.set_viewport_size({"width": 1440, "height": 1100})
        desktop.goto(f"{base}/", wait_until="networkidle")
        wait(desktop, 600)
        expect(desktop.eval_on_selector_all(".genre-block", "els => els.length") == 12, "스크린샷: 홈 장르 블록 12개")
        desktop.screenshot(path=str(shots / "preview-v3-home.png"), full_page=True)

        desktop.goto(f"{base}/?domain=game", wait_until="networkidle")
        wait(desktop, 600)
        expect(desktop.eval_on_selector_all(".genre-block", "els => els.length") == 5, "스크린샷: 게임 도메인 장르 5개")
        desktop.screenshot(path=str(shots / "preview-v3-game.png"), full_page=True)

        desktop.goto(f"{base}/?domain=game&arena=roguelike-deckbuilder", wait_until="networkidle")
        wait(desktop, 600)
        expect(len(cards(desktop)) == 4, "스크린샷: 덱빌딩 비교군 4건")
        desktop.screenshot(path=str(shots / "preview-v3-arena.png"), full_page=True)

        desktop.check('#grid .card[data-id="balatro"] input[data-compare]')
        wait(desktop, 200)
        desktop.check('#grid .card[data-id="slay-the-spire"] input[data-compare]')
        wait(desktop, 250)
        desktop.click("#compareOpen")
        wait(desktop, 600)
        expect(desktop.is_visible("#compareTable"), "스크린샷: 비교 표")
        desktop.screenshot(path=str(shots / "preview-v3-compare.png"), full_page=True)
        desktop.close()

        mobile = context.new_page()
        mobile.set_viewport_size({"width": 390, "height": 844})
        mobile.goto(f"{base}/?domain=app&arena=pkm-notes", wait_until="networkidle")
        wait(mobile, 700)
        expect(len(cards(mobile)) == 5, "모바일: 노트 비교군 5건", str(len(cards(mobile))))
        expect(mobile.is_visible("#domainTabs"), "모바일에서도 도메인 탭 노출")
        expect(mobile.is_visible("#tuneBtn"), "모바일 '내 기준 미세조정' 버튼")
        box = mobile.eval_on_selector("#grid .card", "e => e.getBoundingClientRect().width")
        expect(box and box < 380, "모바일 카드 폭이 한 열", str(box))
        mobile.screenshot(path=str(shots / "preview-v3-mobile.png"), full_page=False)
        mobile.click("#tuneBtn")
        wait(mobile, 450)
        drawer_width = mobile.eval_on_selector("#tuneDrawer", "e => e.getBoundingClientRect().width")
        expect(drawer_width and drawer_width >= 389, "모바일 드로어 전체 폭", str(drawer_width))
        mobile.screenshot(path=str(shots / "preview-v3-mobile-tune.png"))
        mobile.click("#tuneClose")
        wait(mobile, 300)
        mobile.click('#grid .card[data-id="joplin"]')
        wait(mobile, 700)
        expect(mobile.is_visible("#modal"), "모바일 상세 모달")
        mobile.screenshot(path=str(shots / "preview-v3-mobile-detail.png"))
        mobile.close()

        # 홈·도메인 쇼케이스의 타일 아이콘(40px+)이 모바일에서도 로드되는지
        tile_mobile = context.new_page()
        tile_mobile.set_viewport_size({"width": 390, "height": 844})
        tile_mobile.goto(f"{base}/", wait_until="networkidle")
        wait(tile_mobile, 700)
        tile_icons = tile_mobile.evaluate(
            """() => [...document.querySelectorAll('.pick-tile .item-icon')].map(wrap => {
              const img = wrap.querySelector('img');
              return {size: Math.round(wrap.getBoundingClientRect().width),
                      loaded: !!img && img.complete && img.naturalWidth > 0};
            })"""
        )
        expect(bool(tile_icons) and all(40 <= t["size"] <= 48 and t["loaded"] for t in tile_icons),
               "모바일 홈 장르 타일 아이콘 40px+ 전부 로드", str(tile_icons[:3]))
        first_tile_top = tile_mobile.eval_on_selector(".pick-tile", "e => Math.round(e.getBoundingClientRect().top)")
        expect(first_tile_top < 844, "모바일 첫 화면에 장르 추천 타일이 들어옴", str(first_tile_top))
        tile_mobile.close()

        if args.keep_open:
            page.wait_for_timeout(30000)
        browser.close()

    httpd.shutdown()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("=" * 78)
    for label, ok, extra in RESULTS:
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {label}"
        if not ok and extra:
            line += f"  ← {extra}"
        print(line)
    print("=" * 78)
    print(f"결과: {passed}/{len(RESULTS)} 통과")
    if page_errors or console_errors or failed_requests:
        print("콘솔/네트워크 기록:", page_errors, console_errors, failed_requests)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
