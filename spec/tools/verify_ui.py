#!/usr/bin/env python3
"""파로스 정적 웹 v2 동작 검증 (Playwright + headless Chromium).

무엇을 검증하는가 — 4단 계층 개편(스키마 v0.4.0 · 카탈로그 · 분할 로딩)
  1) 로드·계약: catalog.json·search-index.json·schema 를 읽고, 홈에서는 비교군 파일을 내려받지 않는다(지연 로딩).
     콘솔 에러·페이지 예외·HTTP 4xx/5xx 0건, 모든 요청이 web/ 배포 루트 안에서 해결됨.
  2) 홈 요약 뷰: 비교군 바로가기 카드(건수·평균·1위 — 6개), '별점은 높은데 거름 판정' 리포트(Hero Wars 4.6★ vs 34.6,
     Archero 4.2★ vs 53.9, Notion 4.6★ vs 66.6, Clash Royale 4.0★ vs 55.2), 통합 검색(이름·별칭·키워드 — '에버노트', '노트'), 보관함 섹션.
  3) 4단 탐색: 홈 → 도메인(앱·게임) → 대분류 → 비교군 → 항목. 비교군을 바꾸면 그 파일만 지연 로딩되고
     요약(추천/조건부/거름·평균)은 같은 비교군 안에서만 재계산된다(도메인·분야 평균 혼합 없음).
  4) 첫 화면 경량화: 기본 '균형 기본' 프리셋, 가중치·하드 필터·엄격 모드는 '내 기준 미세조정' 드로어 안.
     선택한 도메인의 필터 팩(게임 팩/앱 팩)이 먼저 노출된다.
  5) 1:1 비교: 같은 비교군 2~3개 체크 → 비교 표(점수·축·필터·별점·수명 단계·신선도), 4개째는 차단.
  6) 상세: 신선도(180일), 사실(Fact)과 의견(Opinion) 분리, 같은 비교군 대체제 링크, 공유 요약 복사,
     정정 제보 링크, 보관함 담기.
  7) URL 딥링크(domain·category·arena·item·compare·preset), 북마크(localStorage) 지속, 방법론 모달.
  8) 엔진 단위 테스트(가중 평균·6단 규칙·엄격/완화·완결작 면제·compat_risk·신선도·대체제·요약 텍스트).
  9) 스크린샷: preview-v2-home.png · preview-v2-arena.png · preview-v2-compare.png · preview-v2-mobile.png.

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
        expect("스키마 v0.4.0" in chip and "29건" in chip and "비교군 6" in chip, "데이터 칩 = v0.4.0 · 29건 · 비교군 6", chip)
        counts = page.evaluate("window.Pharos.state.core.index.counts")
        expect(counts == {"items": 29, "domains": 2, "categories": 6, "arenas": 6}, "카탈로그 계층 집계 29/2/6/6", str(counts))
        domains = page.evaluate("window.Pharos.state.core.catalog.domains.map(d => d.id)")
        expect(domains == ["app", "game"], "도메인 = 앱·게임", str(domains))
        tabs = page.eval_on_selector_all("#domainTabs button", "els => els.map(e => e.innerText.trim())")
        expect(tabs == ["홈", "앱", "게임"], "도메인 전환 탭 = 홈·앱·게임", str(tabs))

        # ---------------------------------------------------------------- 2 홈 뷰
        hero = page.inner_text(".hero")
        expect("별점 대신" in hero and "내 기준" in hero, "홈 히어로 문구", hero[:80])
        expect(page.inner_text("#bookmarkSection").startswith("☆ 내 보관함"), "홈에 보관함 섹션")
        shortcuts = page.eval_on_selector_all(".arena-card", "els => els.map(e => e.innerText.replace(/\\n/g, ' | '))")
        expect(len(shortcuts) == 6, "비교군 바로가기 카드 6개", str(len(shortcuts)))
        expect("노트·지식관리" in shortcuts[0] and "5건" in shortcuts[0] and "평균 69.8" in shortcuts[0],
               "노트 비교군 카드(5건·평균 69.8)", shortcuts[0])
        expect("덱빌딩 게임" in shortcuts[1] and "4건" in shortcuts[1] and "80.3" in shortcuts[1],
               "덱빌딩 비교군 카드(4건·평균 80.3)", shortcuts[1])
        expect("액션 로그라이크" in shortcuts[2] and "4건" in shortcuts[2] and "평균 77.9" in shortcuts[2],
               "액션 로그라이크 비교군 카드(4건·평균 77.9)", shortcuts[2])
        expect("모바일 수집형 RPG" in shortcuts[3] and "6건" in shortcuts[3] and "평균 66.9" in shortcuts[3],
               "가챠 비교군 카드(6건·평균 66.9)", shortcuts[3])
        expect("PC MMORPG" in shortcuts[4] and "4건" in shortcuts[4] and "평균 69.9" in shortcuts[4],
               "PC MMORPG 비교군 카드(4건·평균 69.9)", shortcuts[4])
        expect("모바일 전략·디펜스" in shortcuts[5] and "6건" in shortcuts[5] and "평균 70.6" in shortcuts[5],
               "모바일 전략·디펜스 비교군 카드(6건·평균 70.6)", shortcuts[5])

        gap_rows = page.eval_on_selector_all(".gap-row", "els => els.map(e => e.innerText.replace(/\\n/g, ' | '))")
        expect(len(gap_rows) == 4, "'별점은 높은데 거름 판정' 리포트 4건", str(len(gap_rows)))
        expect("Hero Wars: Alliance" in gap_rows[0] and "4.6" in gap_rows[0] and "34.6" in gap_rows[0] and "거름" in gap_rows[0],
               "Hero Wars 4.6★ vs 34.6점 거름", gap_rows[0])
        expect("확률형 아이템" in gap_rows[0] and "P2W" in gap_rows[0], "갭 리포트에 걸린 필터 사유", gap_rows[0])
        expect("Archero" in gap_rows[1] and "4.2" in gap_rows[1] and "53.85" in gap_rows[1] and "거름" in gap_rows[1],
               "Archero 4.2★ vs 53.85 거름", gap_rows[1])
        expect("Notion" in gap_rows[2] and "66.6" in gap_rows[2], "Notion 4.6★ vs 66.6 조건부", gap_rows[2])
        expect("Clash Royale" in gap_rows[3] and "4.0" in gap_rows[3] and "55.2" in gap_rows[3] and "거름" in gap_rows[3],
               "Clash Royale 4.0★ vs 55.2 거름", gap_rows[3])
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
        cats = page.eval_on_selector_all(".category-card", "els => els.map(e => e.innerText.replace(/\\n/g, ' | '))")
        expect(len(cats) == 5 and "전략 · 카드" in cats[0] and "RPG · 수집" in cats[1] and "액션 · 인디" in cats[2]
               and "RPG · MMORPG" in cats[3] and "모바일 전략 · 디펜스" in cats[4],
               "게임 도메인 대분류 5개", str(cats))
        domain_arenas = page.eval_on_selector_all(".arena-card", "els => els.map(e => e.dataset.arena)")
        expect(domain_arenas == ["roguelike-deckbuilder", "mobile-gacha-rpg", "action-roguelike",
                                 "pc-mmorpg", "mobile-strategy-defense"],
               "게임 도메인 비교군 5개", str(domain_arenas))
        page.click('.category-card[data-category="strategy-card"]')
        wait(page, 450)
        expect("category=strategy-card" in page.url, "대분류 URL", path_id(page))
        arena_cards = page.eval_on_selector_all(".arena-card", "els => els.map(e => e.dataset.arena)")
        expect(arena_cards == ["roguelike-deckbuilder"], "전략·카드 대분류 아래 비교군 1개", str(arena_cards))
        crumb = page.inner_text("#breadcrumb")
        expect("게임" in crumb and "전략 · 카드" in crumb, "경로 표시(홈/게임/전략·카드)", crumb)

        served.clear()
        page.click('.arena-card[data-arena="roguelike-deckbuilder"]')
        wait(page, 700)
        expect("arena=roguelike-deckbuilder" in page.url, "비교군 URL", path_id(page))
        expect(any(url.endswith("/data/game/roguelike-deckbuilder.json") for url in served),
               "비교군 선택 시 해당 분할 파일만 로드", str(served))
        expect(not any(url.endswith("/data/app/pkm-notes.json") for url in served),
               "다른 도메인 파일은 로드하지 않음", str(served))

        state = cards(page)
        expect(len(state) == 4, "덱빌딩 비교군 카드 4건(추천 3 + 거름 1)", str([c["id"] for c in state]))
        summary = stats(page)
        expect(summary.get("추천") == "3" and summary.get("조건부") == "0" and summary.get("거름") == "1",
               "비교군 요약 3/0/1", str(summary))
        expect(summary.get("평균 가중 점수") == "80.3", "비교군 평균 80.3", str(summary))
        expect(page.inner_text("#listCount").strip() == "4/4건", "목록 건수 4/4", page.inner_text("#listCount"))

        by_id = {c["id"]: c for c in state}
        for item_id, verdict, score in (("balatro", "recommend", 94.65), ("slay-the-spire", "recommend", 92.20),
                                        ("inscryption", "recommend", 80.15), ("night-of-the-full-moon", "avoid", 54.25)):
            c = by_id.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(by_id["night-of-the-full-moon"]["avoid"] is True, "거름 항목은 하단 분리 영역")
        expect("🔴 신호 2개" in by_id["night-of-the-full-moon"]["text"], "Night of the Full Moon 신호 기준 거름", by_id["night-of-the-full-moon"]["text"][-90:])
        expect("완결작" in by_id["inscryption"]["text"], "Inscryption 카드에 '완결작' 배지")
        expect("면제 · 완결작" in by_id["inscryption"]["text"], "Inscryption 카드에 '면제 · 완결작' 사유", by_id["inscryption"]["text"][-120:])
        expect("최신 · 1일" in by_id["balatro"]["text"], "카드에 평가 신선도(최신·1일)", by_id["balatro"]["text"][:160])

        # 비교군 안 검색은 그 비교군으로 AND
        page.fill("#arenaSearch", "inscryption")
        wait(page, 350)
        expect([c["id"] for c in cards(page)] == ["inscryption"], "비교군 내 검색 1건", str([c["id"] for c in cards(page)]))
        page.fill("#arenaSearch", "")
        wait(page, 300)
        page.select_option("#sort", "name")
        wait(page, 250)
        picks = [c["id"] for c in cards(page) if not c["avoid"]]
        expect(picks == ["balatro", "inscryption", "slay-the-spire"], "이름순 정렬", str(picks))
        page.select_option("#sort", "score")
        wait(page, 250)

        # ------------------------------------------------------- 5 미세조정 드로어
        expect(page.inner_text("#tuneSummary").strip() == "균형 기본", "기본 프리셋 = 균형 기본", page.inner_text("#tuneSummary"))
        open_drawer(page)
        expect(page.is_visible("#tuneDrawer"), "미세조정 드로어 열림")
        expect(page.get_attribute("#tuneBtn", "aria-expanded") == "true", "드로어 토글 aria-expanded")
        presets = page.eval_on_selector_all("#tuneBody .preset", "els => els.map(e => e.innerText.trim())")
        expect(presets == ["균형 기본", "대중 평가 중심", "쾌적성·노과금 중심", "AI 완성도 중심"], "프리셋 4종", str(presets))
        sliders = page.eval_on_selector_all("#tuneBody input[type=range]", "els => els.map(e => e.value)")
        expect(sliders == ["40", "35", "25"], "기본 가중치 40/35/25", str(sliders))
        packs = page.eval_on_selector_all("#tuneBody .filter-pack summary", "els => els.map(e => e.innerText.split('\\n')[0])")
        expect(packs[0].startswith("게임 팩") and packs[1].startswith("앱 팩") and packs[2].startswith("공통 코어"),
               "게임 도메인은 게임 팩을 먼저 노출", str(packs))
        open_packs = page.eval_on_selector_all("#tuneBody .filter-pack", "els => els.map(e => e.open)")
        expect(open_packs == [True, False, False], "현재 도메인 팩만 펼침", str(open_packs))
        expect(page.inner_text("#filterCount").strip() == "4/9", "필터 카운트 4/9", page.inner_text("#filterCount"))

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
        for label in ["가중 점수", "대표 티어 · 가격", "축 · 사용자 평가", "걸린 하드 필터", "스토어 누적 별점", "최근 리뷰", "수명 단계", "평가 신선도"]:
            expect(label in labels, f"비교 표 '{label}' 행", str(labels)[:160])
        table_text = page.inner_text("#compareTable")
        expect("94.7" in table_text and "92.2" in table_text, "비교 표에 두 항목 점수", table_text[:200])

        # 목록으로 돌아가 3개째 추가 → 4개째는 차단
        page.click('a[data-action="arena"], button[data-action="arena"]')
        wait(page, 600)
        page.check('#grid .card[data-id="inscryption"] input[data-compare]')
        wait(page, 350)
        expect("inscryption" in page.url and "compare=" in page.url, "3개째 선택 URL 반영", path_id(page))
        page.evaluate(
            """() => { const el = document.querySelector('[data-item="night-of-the-full-moon"]'); if (el) el.scrollIntoView(); }"""
        )
        page.check('#avoidGrid .card[data-id="night-of-the-full-moon"] input[data-compare]', force=True)
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
        alts = page.eval_on_selector_all("#secAlternatives .alt-row", "els => els.map(e => e.innerText.replace(/\\n/g, ' '))")
        expect(len(alts) == 2 and "Balatro" in alts[0] and "Slay the Spire" in alts[1], "같은 비교군 대체제 링크", str(alts))
        expect(page.eval_on_selector_all("#modalBody .source", "els => els.length") >= 3, "출처 목록 렌더")
        correction = page.get_attribute('#modalActions a[href*="issues/new"]', "href")
        expect(correction and "github.com/AIRA1346/pharos/issues/new" in correction and "template=correction.yml" in correction,
               "정정 제보 링크(correction.yml)", correction)

        page.click('[data-share="inscryption"]')
        wait(page, 400)
        clip = page.evaluate("navigator.clipboard.readText()")
        expect("Inscryption" in clip and "가중 점수 80.2" in clip and "파로스" in clip, "공유 요약 복사", clip[:120])

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
        expect(alts == ["joplin"], "Evernote 대체제 = 같은 비교군 추천 Joplin 만", str(alts))
        page.click('#secAlternatives .alt-row')
        wait(page, 700)
        expect(page.inner_text("#modalTitle") == "Joplin", "대체제 클릭 → Joplin 상세", page.inner_text("#modalTitle"))
        expect("item=joplin" in page.url, "대체제 이동 URL", path_id(page))
        close_modal(page)
        wait(page, 300)
        expect(len(cards(page)) == 5, "노트 비교군 카드 5건", str(len(cards(page))))
        page.screenshot(path=str(shots / "preview-v2-arena.png"), full_page=True)

        # ------------------------------------------------------ 8 방법론·딥링크
        page.click("#methodBtn")
        wait(page, 400)
        expect(page.is_visible("#methodModal"), "방법론 모달 열림")
        method = page.inner_text("#methodBody")
        for label in ["4단 구조", "네 축과 가중 점수", "근거 등급 A/B/C", "확률형·P2W 강도 3단계", "판정 규칙", "독립성", "용어 도움말"]:
            expect(label in method, f"방법론 '{label}' 섹션")
        expect("어필리에이트 링크·유료 광고·협찬 배치를 쓰지 않습니다" in method, "독립성·어필리에이트 배제 선언")
        expect("재검토 필요" in method and "180" in method, "용어 도움말에 신선도 기준")
        page.screenshot(path=str(shots / "preview-v2-method.png"))
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
        expect(page.eval_on_selector_all(".arena-card", "els => els.length") == 1, "딥링크 ?domain&category", "")
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

            return {
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
        expect(unit["defaults"] == {"user_rating": 40, "objective": 35, "ai_review": 25}, "엔진: 기본 가중치 40/35/25", str(unit["defaults"]))
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
        expect(summary.get("평균 가중 점수") == "77.9", "액션 로그라이크 평균 77.9", str(summary))
        ar = {c["id"]: c for c in arena_state}
        for item_id, verdict, score in (("hades", "recommend", 82.7), ("vampire-survivors", "recommend", 89.8),
                                        ("dead-cells", "recommend", 85.4), ("archero", "avoid", 53.85)):
            c = ar.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(ar["archero"]["avoid"] is True, "Archero 는 하단 거름 영역")
        expect("완결작" in ar["hades"]["text"] and "면제 · 완결작" in ar["hades"]["text"],
               "Hades 완결작 면제 배지", ar["hades"]["text"][-140:])
        expect("최신 · 0일" in ar["dead-cells"]["text"], "Dead Cells 평가 신선도(최신·0일)", ar["dead-cells"]["text"][:160])

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
        expect("82.7" in compare_text and "89.8" in compare_text, "비교 표에 두 항목 점수", compare_text[:200])

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
        expect(gsummary.get("추천") == "0" and gsummary.get("조건부") == "2" and gsummary.get("거름") == "4",
               "가챠 비교군 요약 0/2/4", str(gsummary))
        expect(gsummary.get("평균 가중 점수") == "66.9", "가챠 비교군 평균 66.9", str(gsummary))
        g = {c["id"]: c for c in gacha}
        expect(g["limbus-company"]["score"] and abs(float(g["limbus-company"]["score"]) - 78.7) < 0.05,
               "Limbus Company 78.7", g["limbus-company"]["score"])
        expect(g["genshin-impact"]["score"] and abs(float(g["genshin-impact"]["score"]) - 72.7) < 0.05,
               "Genshin Impact 72.7", g["genshin-impact"]["score"])
        expect(g["limbus-company"]["verdict"] == "conditional" and g["limbus-company"]["avoid"] is False,
               "Limbus Company = 조건부(선택 과금)", g["limbus-company"]["verdict"])
        expect(g["hero-wars-alliance"]["avoid"] is True and g["genshin-impact"]["avoid"] is True,
               "Hero Wars·Genshin 은 거름 영역(impact core)", str([c["id"] for c in gacha if c["avoid"]]))

        for item_id, verdict, score in (("goddess-of-victory-nikke", "avoid", 69.65),
                                        ("blue-archive", "conditional", 75.50),
                                        ("honkai-star-rail", "avoid", 70.10)):
            c = g.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(g["goddess-of-victory-nikke"]["avoid"] is True and g["honkai-star-rail"]["avoid"] is True
               and g["blue-archive"]["avoid"] is False,
               "니케·스타레일은 하단 거름, 블루 아카이브는 조건부", str([c["id"] for c in gacha if c["avoid"]]))
        expect("선택 과금 · 무과금 가능" in g["blue-archive"]["text"], "블루 아카이브 카드에 '선택 과금' 배지",
               g["blue-archive"]["text"][:180])
        expect("선택 과금 · 무과금 가능" not in g["goddess-of-victory-nikke"]["text"],
               "니케 카드에는 선택 과금 배지 없음(core)", g["goddess-of-victory-nikke"]["text"][:180])

        page.goto(f"{base}/?domain=game&arena=mobile-gacha-rpg&item=goddess-of-victory-nikke", wait_until="networkidle")
        wait(page, 700)
        body = page.inner_text("#modalBody")
        expect("160" in body and "마일리지" in body, "니케 160벽·마일리지 서술", "")
        expect("무과금 충분성" in body and "제한적" in body, "니케 무과금 = 제한적 표기", "")
        close_modal(page)

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
        expect(ms.get("평균 가중 점수") == "69.9", "PC MMORPG 평균 69.9", str(ms))
        m = {c["id"]: c for c in mmo}
        for item_id, verdict, score in (("final-fantasy-xiv", "recommend", 80.7), ("guild-wars-2", "conditional", 77.2),
                                        ("lost-ark", "avoid", 41.45), ("black-desert", "recommend", 80.1)):
            c = m.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])
        expect(m["guild-wars-2"]["avoid"] is False and m["lost-ark"]["avoid"] is True,
               "Lost Ark 만 하단 거름 영역(GW2 는 조건부로 복귀)")
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
        expect(alts == ["final-fantasy-xiv", "black-desert"], "GW2 대체제 = 같은 비교군 추천 2건", str(alts))
        close_modal(page)

        page.goto(f"{base}/?domain=game&arena=mobile-strategy-defense", wait_until="networkidle")
        wait(page, 700)
        expect("arena=mobile-strategy-defense" in page.url, "모바일 전략·디펜스 비교군 URL", path_id(page))
        mob = cards(page)
        expect(len(mob) == 6, "모바일 전략·디펜스 카드 6건", str([c["id"] for c in mob]))
        mst = stats(page)
        expect(mst.get("추천") == "3" and mst.get("조건부") == "1" and mst.get("거름") == "2",
               "모바일 전략·디펜스 요약 3/1/2", str(mst))
        expect(mst.get("평균 가중 점수") == "70.6", "모바일 전략·디펜스 평균 70.6", str(mst))
        d = {c["id"]: c for c in mob}
        for item_id, verdict, score in (("bloons-td-6", "recommend", 81.3), ("kingdom-rush-vengeance", "recommend", 80.2),
                                        ("clash-royale", "avoid", 55.2), ("plants-vs-zombies-2", "avoid", 48.0)):
            c = d.get(item_id)
            expect(c is not None, f"{item_id} 카드 존재")
            if not c:
                continue
            expect(c["verdict"] == verdict, f"{item_id} 판정 = {verdict}", c["verdict"])
            expect(c["score"] and abs(float(c["score"]) - score) < 0.05, f"{item_id} 점수 {score}", c["score"])

        for item_id, verdict, score in (("clash-of-clans", "conditional", 78.50), ("arknights", "recommend", 80.20)):
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
        expect(bdo_off and bdo_off["verdict"] == "recommend", "strict OFF → BDO 추천", str(bdo_off)[:100])
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

        # ------------------------------------------------------------- 11 스크린샷
        desktop = context.new_page()
        desktop.set_viewport_size({"width": 1440, "height": 1100})
        desktop.goto(f"{base}/", wait_until="networkidle")
        wait(desktop, 600)
        desktop.screenshot(path=str(shots / "preview-v2-home.png"), full_page=True)

        desktop.goto(f"{base}/?domain=game&arena=roguelike-deckbuilder", wait_until="networkidle")
        wait(desktop, 600)
        expect(len(cards(desktop)) == 4, "스크린샷: 덱빌딩 비교군 4건")
        desktop.screenshot(path=str(shots / "preview-v2-arena.png"), full_page=True)

        desktop.check('#grid .card[data-id="balatro"] input[data-compare]')
        wait(desktop, 200)
        desktop.check('#grid .card[data-id="slay-the-spire"] input[data-compare]')
        wait(desktop, 250)
        desktop.click("#compareOpen")
        wait(desktop, 600)
        expect(desktop.is_visible("#compareTable"), "스크린샷: 비교 표")
        desktop.screenshot(path=str(shots / "preview-v2-compare.png"), full_page=True)
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
        mobile.screenshot(path=str(shots / "preview-v2-mobile.png"), full_page=False)
        mobile.click("#tuneBtn")
        wait(mobile, 450)
        drawer_width = mobile.eval_on_selector("#tuneDrawer", "e => e.getBoundingClientRect().width")
        expect(drawer_width and drawer_width >= 389, "모바일 드로어 전체 폭", str(drawer_width))
        mobile.screenshot(path=str(shots / "preview-v2-mobile-tune.png"))
        mobile.click("#tuneClose")
        wait(mobile, 300)
        mobile.click('#grid .card[data-id="joplin"]')
        wait(mobile, 700)
        expect(mobile.is_visible("#modal"), "모바일 상세 모달")
        mobile.screenshot(path=str(shots / "preview-v2-mobile-detail.png"))
        mobile.close()

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
