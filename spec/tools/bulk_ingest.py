#!/usr/bin/env python3
"""파로스 대량 팩트 적재 — bulk_ingest.py (v1.0)

파로스를 **2단계 발행 구조**로 돌리기 위한 대량 적재기.
사람이 손으로 30%를 채우는 `auto_collect.py` + `apply_review.py` 흐름과 달리,
이 스크립트는 **공개 API 사실만으로 스키마를 100% 채운 `auto_fact` 항목**을 한 배치에
100종 단위로 만들어 `data/{domain}/{arena}.json` · `data/en.json` · `data/catalog.json` 에 바로 기록한다.

수집 소스 (모두 무료 공개 API, API 키 불필요 — auto_collect.py 의 수집 모듈·아이콘 저장기를 재사용)
  · Steam      — storesearch(이름→AppID) · appdetails(한국어/영어) · 상점 페이지 평가 요약 · ISteamNews · SteamSpy
  · App Store  — iTunes search/lookup (한국·미국) — 평점·평가 수·가격·최근 버전·아트워크
  · Google Play— 스토어 페이지(JSON-LD 평점·평가 수·업데이트 날짜·광고 표기·og:image)
  · GitHub     — repos/{owner}/{repo} (라이선스·스타·최근 푸시·아카이브) — 1회 요청으로 끝낸다

자동 산정 규칙 (사실 → 점수, 모두 요약에 근거를 적는다)
  · 사용자 축   : 스토어 평점·평가 수를 표본 가중 평균(Steam 누적·최근, App Store 한국/미국, Play)
  · 객관 축     : 라이선스·가격 표기·업데이트 주기·플랫폼 수·출시 연수로 0~100 초기 산정
  · AI 검토 축  : 본질 검토 전 중립값(60)에서 스토어 평점·업데이트 주기·표본 규모·라이선스로만 보정한 잠정값
  · 판정        : 검증기와 같은 규칙(`validate.compute_verdict`)으로 계산 — 손으로 쓴 판정이 아니다
  · 확인하지 못한 것(확률형 상품·구독·계정·데이터 수집)은 지어내지 않고 `unknown` 으로 두고,
                  UI 는 `자동 수집` 배지와 안내 문구로 "순차 검수 전"임을 밝힌다.

병렬 처리
  항목 단위로 ThreadPoolExecutor(기본 8워커)에서 HTTP 를 모아 온다. 응답은 `cache/` 에 URL 해시로
  저장해 재실행(GitHub 시간당 60회 제한, 아이콘 재시도)에서 같은 요청을 다시 보내지 않는다.

사용
  python3 projects/pharos/scripts/bulk_ingest.py --spec projects/pharos/drafts/bulk-2026-11-26/spec.json
  python3 projects/pharos/scripts/bulk_ingest.py --spec ... --resolve-only     # ID 확정만
  python3 projects/pharos/scripts/bulk_ingest.py --spec ... --ids elden-ring,factorio
  python3 projects/pharos/scripts/bulk_ingest.py --spec ... --limit 3 --no-write --no-icon

종료 코드 0 = 모든 항목 생성·기록 완료, 1 = 일부 실패(실패 목록은 로그 JSON 에 남는다).
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import gzip
import hashlib
import html as htmllib
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "schema"))

import auto_collect as ac  # noqa: E402 — 수집 도우미·아이콘 저장기를 그대로 재사용한다
import encyclopedia as enc  # noqa: E402 — 사전(encyclopedia) 자동 블록
import scale_rules as srules  # noqa: E402 — v0.6.0 표본 규모 보정 규칙(기준표 2.1.1)
import validate as vlib    # noqa: E402 — 판정 규칙을 검증기와 한 곳에서 쓴다

DATA_DIR = ROOT / "data"
EN_PATH = DATA_DIR / "en.json"
CATALOG_PATH = DATA_DIR / "catalog.json"
SCHEMA_PATH = ROOT / "schema" / "item.schema.json"
TODAY = date.today().isoformat()
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
STORE_UA = {**UA, "Accept-Language": "en-US,en;q=0.9"}
KOREAN = re.compile(r"[\uac00-\ud7a3]")

CACHE_DIR: Path = Path("/tmp")
CACHE_LOCK = threading.Lock()
HTTP_LOG: list[dict] = []
LOG_LOCK = threading.Lock()

UPDATE_RE = re.compile(
    r"(patch|hotfix|changelog|change log|update now|now live|version\s*\d|ver\.?\s*\d|업데이트|패치|핫픽스"
    r"|\bseason\b|시즌|expansion|release notes|major update|content update)",
    re.I,
)

# Apple App Store 장르 → 한국어 표기(카드의 개발사·장르 줄에 쓴다). 사전에 없으면 영문 그대로 둔다.
APPLE_GENRES_KO = {
    "Social Networking": "소셜 네트워킹",
    "Productivity": "생산성",
    "Business": "비즈니스",
    "Utilities": "유틸리티",
    "Photo & Video": "사진 및 비디오",
    "Music": "음악",
    "Entertainment": "엔터테인먼트",
    "Video Players & Editors": "동영상 플레이어 및 편집",
    "News": "뉴스",
    "Reference": "참고",
    "Developer Tools": "개발자 도구",
    "Graphics & Design": "그래픽 및 디자인",
    "Education": "교육",
}

# 위 장르 사전의 역방향 — 한국 스토어에만 있는 앱의 한글 장르를 영문 화면용으로 되돌린다.
APPLE_GENRES_EN = {ko: en for en, ko in APPLE_GENRES_KO.items()}

# 한국 스토어에만 있는 앱의 개발사·퍼블리셔가 한글일 때 영문 화면에 쓸 공식 영문 사명.
# 사전에 없는 회사는 사명을 비워 화면에서 숨긴다(한글 사명을 그대로 두면 EN 화면에 한글이 샌다).
KO_COMPANY_EN = {
    "한국철도공사": "Korea Railroad Corporation (KORAIL)",
    "㈜SR - 새로운 고속열차 SRT": "SR Co., Ltd.",
    "번개장터 주식회사": "Bungaejangter Inc.",
    "주식회사 카카오": "Kakao Corp.",
    "(주)카카오": "Kakao Corp.",
    "네이버 주식회사": "NAVER Corp.",
    "주식회사 우아한형제들": "Woowa Brothers Corp.",
}

# 시리즈·플랫폼 표기 — 사실 확인용
PLATFORM_LABEL_KO = {
    "steam": "Steam", "windows": "Windows", "macos": "macOS", "linux": "Linux",
    "ios": "iOS", "android": "Android", "web": "웹", "console": "콘솔", "other": "기타",
}

# 필터 플래그의 자동 수집 문구(한국어/영어). 값은 항목마다 달라지므로 note 만 여기서 만든다.
FLAG_NOTE_UNKNOWN_KO = "공개 API 로는 확인하지 못했다 — 순차 심층 검수 대상."
FLAG_NOTE_UNKNOWN_EN = "Not verifiable from public APIs yet — queued for the deep review pass."


# ─────────────────────────────────────────────────────────────── HTTP(캐시·병렬)
def cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:40]
    return CACHE_DIR / f"{digest}.gz"



# ── Steam 요청 간격(초) — appdetails·상점 페이지의 IP 기준 요청 제한(약 200회/5분)을 넘지 않게 한다.
STEAM_PACE = float(os.environ.get("PHAROS_STEAM_PACE", "0") or 0)
STEAM_GATE = threading.Lock()
STEAM_LAST = [0.0]


def steam_throttle(url: str) -> None:
    """Steam 호스트 요청을 최소 간격으로 벌린다(PHAROS_STEAM_PACE>0 일 때)."""
    if STEAM_PACE <= 0 or "steampowered.com" not in url:
        return
    with STEAM_GATE:
        wait = STEAM_LAST[0] + STEAM_PACE - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        STEAM_LAST[0] = time.monotonic()

# ── App Store(iTunes) 요청 간격(초) — iTunes Search API 는 짧은 시간에 몰리면 429/403 을 준다.
ITUNES_PACE = float(os.environ.get("PHAROS_ITUNES_PACE", "0") or 0)
ITUNES_GATE = threading.Lock()
ITUNES_LAST = [0.0]


def itunes_throttle(url: str) -> None:
    """itunes.apple.com 요청을 최소 간격으로 벌린다(PHAROS_ITUNES_PACE>0 일 때)."""
    if ITUNES_PACE <= 0 or "itunes.apple.com" not in url:
        return
    with ITUNES_GATE:
        wait = ITUNES_LAST[0] + ITUNES_PACE - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        ITUNES_LAST[0] = time.monotonic()


def http_raw(url: str, headers: dict | None = None, timeout: int = 30, retries: int = 2,
             use_cache: bool = True, label: str = "") -> tuple[bytes, dict]:
    """URL 응답 바이트 — 같은 URL 은 캐시에서 즉시 돌려준다."""
    if use_cache:
        path = cache_path(url)
        if path.exists():
            with LOG_LOCK:
                HTTP_LOG.append({"label": label or "http", "url": url, "status": "cache", "bytes": path.stat().st_size})
            return gzip.decompress(path.read_bytes()), {"status": "cache", "bytes": path.stat().st_size}
    last: Exception | None = None
    started = time.perf_counter()
    for attempt in range(retries + 1):
        steam_throttle(url)
        itunes_throttle(url)
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as res:
                raw = res.read()
                if res.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                info = {"status": res.status, "bytes": len(raw), "ms": round((time.perf_counter() - started) * 1000)}
                with LOG_LOCK:
                    HTTP_LOG.append({"label": label or "http", "url": url, **info})
                if use_cache:
                    with CACHE_LOCK:
                        CACHE_DIR.mkdir(parents=True, exist_ok=True)
                        path = cache_path(url)
                        path.write_bytes(gzip.compress(raw))
                return raw, info
        except urllib.error.HTTPError as exc:
            last = exc
            # iTunes 는 요청이 몰리면 403(Forbidden)으로도 막는다 — 같은 호스트에만 재시도 대상으로 둔다.
            retryable = (429, 500, 502, 503, 504) + ((403,) if "itunes.apple.com" in url else ())
            if exc.code in retryable and attempt < retries:
                time.sleep((2.5 if exc.code == 403 else 1.5) * (attempt + 1))
                continue
            break
        except Exception as exc:  # noqa: BLE001 — 네트워크 오류는 재시도 후 실패로 남긴다
            last = exc
            if attempt < retries:
                time.sleep(1.0)
                continue
            break
    with LOG_LOCK:
        HTTP_LOG.append({"label": label or "http", "url": url, "status": "error",
                         "error": f"{type(last).__name__}: {last}"})
    raise CollectError(f"{label or 'http'} 실패 — {type(last).__name__}: {last} ({url})")


def jget(url: str, headers: dict | None = None, label: str = "") -> dict:
    raw, _ = http_raw(url, headers=headers, label=label)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CollectError(f"{label or 'json'} 응답이 JSON 이 아님 — {exc}") from exc


def tget(url: str, headers: dict | None = None, label: str = "") -> str:
    raw, _ = http_raw(url, headers=headers, label=label)
    return raw.decode("utf-8", "ignore")


class CollectError(Exception):
    """수집 실패 — 그 소스만 건너뛰고 나머지 소스로 항목을 만든다."""


# ─────────────────────────────────────────────────────────────── 텍스트 도우미
TAG_RE = re.compile(r"<[^>]+>")
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]+")


def clean(text: str | None, limit: int = 170) -> str:
    """스토어 소개문 → 한 줄. HTML·중복 공백·줄바꿈을 걷어내고 자른다."""
    if not text:
        return ""
    text = htmllib.unescape(TAG_RE.sub(" ", text))
    text = EMOJI_RE.sub("", text)
    text = re.sub(r"[\s\u00a0]+", " ", text).strip()
    if len(text) > limit:
        cut = text[:limit]
        cut = cut.rsplit(" ", 1)[0] if " " in cut[30:] else cut
        text = cut.rstrip(" ,·-—") + "…"
    return text


def first_sentence(text: str | None, limit: int = 170) -> str:
    text = clean(text, 400)
    if not text:
        return ""
    m = re.match(r"(.{20,}?[.!?。])\s", text)
    out = m.group(1) if m else text
    return clean(out, limit)


def fmt(n) -> str:
    return ac.fmt(n)


def en_safe(text: str | None, fallback: str) -> str:
    """영문 화면에 쓰는 문자열 — 스토어가 한국어 이름만 주면 대체 문구로 바꾼다."""
    text = (text or "").strip()
    return text if text and not KOREAN.search(text) else fallback


def en_name(entry: dict) -> str:
    """스펙이 준 영문 이름(없으면 원래 이름)."""
    return entry.get("name_en") or entry["name"]


def company_en(name: str | None, fallback: str) -> str:
    """영문 화면의 개발사 사명 — 한글이면 공식 영문 사명으로 바꾸고, 모르면 fallback."""
    name = (name or "").strip()
    if not name:
        return fallback
    if not KOREAN.search(name):
        return name
    return KO_COMPANY_EN.get(name, fallback)


def clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def years_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return (date.fromisoformat(TODAY) - date.fromisoformat(iso)).days / 365.25
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────── 1) ID 확정
def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]", "", (text or "").lower())


# ─────────────────────────────────────────────────── 1-1) 중복 방지 가드
# 어떤 배치를 돌려도 기존 210종과 겹쳐 적재되지 않도록, 시작 전에 data/ 전체에서
# id · 정규화 이름 · 스토어 ID(steam appid · App Store trackId · Play 패키지 · GitHub 저장소)를
# 인덱스로 만들고 스펙 항목을 자동 스킵한다. 수집이 끝난 뒤 확정된 스토어 ID 로 한 번 더 본다.
STORE_URL_PATTERNS = {
    "steam": re.compile(r"store\.steampowered\.com/app/(\d+)"),
    "ios": re.compile(r"apps\.apple\.com/[^/\s]+/app/[^/\s]*?/?id(\d+)"),
    "play": re.compile(r"play\.google\.com/store/apps/details\?id=([\w.\-]+)"),
    "github": re.compile(r"github\.com/([\w.\-]+/[\w.\-]+)"),
}
STORE_ID_FIELDS = (("steam", "steam_id"), ("ios", "ios_id"),
                   ("play", "play_package"), ("github", "github_repo"))


def store_ids_of_sources(sources) -> list[tuple[str, str]]:
    """출처 URL 에서 스토어 ID 를 뽑는다(수집기가 남기는 주소 형식 그대로)."""
    found: list[tuple[str, str]] = []
    for src in sources or []:
        url = (src or {}).get("url") or ""
        for kind, pattern in STORE_URL_PATTERNS.items():
            match = pattern.search(url)
            if not match:
                continue
            value = match.group(1)
            if kind == "github":
                value = value[:-4] if value.endswith(".git") else value
                value = value.lower()
            found.append((kind, value))
    return found


def build_dup_index(paths: list[Path]) -> dict:
    """기존 데이터 전체를 중복 판정 인덱스로 만든다(검색 인덱스와 비교군 파일이 겹치면 id 로 한 번만 센다)."""
    index: dict = {"ids": {}, "names": {}, "stores": {}, "items": 0, "files": 0}
    seen_ids: set[str] = set()
    for path in paths:
        try:
            rows = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(rows, dict):
            rows = rows.get("items") or []
        if not isinstance(rows, list):
            continue
        index["files"] += 1
        for row in rows:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            item_id = row["id"]
            index["ids"].setdefault(item_id, Path(path).name)
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                index["items"] += 1
            for name in [row.get("name")] + list(row.get("aliases") or []):
                key = norm(name)
                if key:
                    index["names"].setdefault(key, item_id)
            for kind, value in store_ids_of_sources(row.get("sources")):
                index["stores"].setdefault((kind, value), item_id)
    return index


def load_dup_index() -> dict:
    """data/search-index.json 과 data/{domain}/*.json 을 모두 읽어 가드 인덱스를 만든다."""
    return build_dup_index([DATA_DIR / "search-index.json"] + sorted(DATA_DIR.glob("*/*.json")))


def duplicate_reason(entry: dict, index: dict, raw: dict | None = None) -> str | None:
    """새 스펙 항목이 기존 데이터와 겹치면 사유를, 아니면 None 을 돌려준다."""
    item_id = entry.get("id") or ""
    if item_id in index["ids"]:
        return f"id '{item_id}' 이미 존재({index['ids'][item_id]})"
    for name in [entry.get("name")] + list(entry.get("aliases") or []):
        key = norm(name)
        if key and key in index["names"]:
            return f"이름 '{name}' 이 기존 항목 '{index['names'][key]}' 과 같음"
    for kind, field in STORE_ID_FIELDS:
        value = entry.get(field)
        if not value:
            continue
        value = str(value)
        value = value.lower() if kind == "github" else value
        if (kind, value) in index["stores"]:
            return f"{kind} ID '{value}' 가 기존 항목 '{index['stores'][(kind, value)]}' 과 같음"
    if raw:
        resolved: list[tuple[str, str]] = []
        if raw.get("steam"):
            resolved.append(("steam", str(raw["steam"]["app_id"])))
        for record in (raw.get("ios") or {}).values():
            resolved.append(("ios", str(record.get("trackId"))))
        if ((raw.get("play") or {}).get("en") or {}).get("package"):
            play_rec = raw["play"].get("en") or raw["play"].get("ko") or {}
            if play_rec.get("package"):
                resolved.append(("play", play_rec["package"]))
        if (raw.get("github") or {}).get("repo"):
            resolved.append(("github", raw["github"]["repo"].lower()))
        for kind, value in resolved:
            if (kind, value) in index["stores"]:
                return f"{kind} ID '{value}' 가 기존 항목 '{index['stores'][(kind, value)]}' 과 같음"
    return None


def resolve_steam(term: str, name: str) -> tuple[int, str, str]:
    url = "https://store.steampowered.com/api/storesearch/?" + urllib.parse.urlencode(
        {"term": term, "l": "english", "cc": "kr"})
    data = jget(url, label=f"steam-search:{term}")
    rows = [(int(r["id"]), r.get("name") or "") for r in (data.get("items") or [])]
    if not rows:
        raise CollectError(f"Steam 검색 결과 없음: {term}")
    want = norm(name)
    for app_id, row_name in rows:
        if norm(row_name) == want:
            return app_id, row_name, "exact"
    for app_id, row_name in rows:
        if norm(row_name).startswith(want) or want.startswith(norm(row_name)):
            return app_id, row_name, "prefix"
    raise CollectError(f"Steam 검색에서 '{name}' 확정 실패 — 후보 {rows[:3]}")


def resolve_ios(term: str, name: str) -> dict:
    """한국·미국 스토어에서 같은 앱을 찾아 trackId 를 확정한다(둘 다 저장)."""
    found: dict[str, dict] = {}
    for country in ("kr", "us"):
        url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
            {"term": term, "country": country, "entity": "software", "limit": 8})
        data = jget(url, label=f"itunes-search:{term}:{country}")
        rows = data.get("results") or []
        want = norm(name)
        match = next((r for r in rows if norm(r.get("trackName")) == want), None)
        if match is None:
            match = next((r for r in rows if norm(r.get("trackName")).startswith(want)), None)
        if match is None:
            match = next((r for r in rows if want in norm(r.get("trackName"))), None)
        if match:
            found[country] = match
    if not found:
        raise CollectError(f"App Store 검색 결과에서 '{name}' 을(를) 확정하지 못함")
    return found



def json_unescape(text: str | None) -> str | None:
    """JSON-LD/HTML 에 \\u0026 처럼 남은 유니코드 이스케이프를 실제 문자로 되돌린다."""
    if not text:
        return text
    def repl(m):
        return chr(int(m.group(1), 16))
    return re.sub(r"\\u([0-9a-fA-F]{4})", repl, text).replace("\\/", "/")


def fetch_play(package: str, lang: str) -> dict:
    hl, gl = ("ko", "KR") if lang == "ko" else ("en", "US")
    html = tget(f"https://play.google.com/store/apps/details?id={package}&hl={hl}&gl={gl}",
                headers=STORE_UA, label=f"play:{package}:{lang}")
    title = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    image = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    desc = re.search(r'<meta (?:property|name)="(?:og:)?description" content="([^"]+)"', html)
    rating = count = None
    ld = re.search(r'"aggregateRating":\{([^}]+)\}', html)
    if ld:
        rv = re.search(r'"ratingValue":"?([\d.]+)', ld.group(1))
        rc = re.search(r'"ratingCount":"?(\d+)', ld.group(1))
        rating = float(rv.group(1)) if rv else None
        count = int(rc.group(1)) if rc else None
    dev = re.search(r'"author":\{"@type":"Person","name":"([^"]+)"', html)
    updated = re.search(r"Updated on</div><div[^>]*>([^<]+)", html)
    return {
        "package": package,
        "name": json_unescape(re.sub(r"\s*-\s*Apps on Google Play$", "", title.group(1))) if title else package,
        "description": htmllib.unescape(desc.group(1)) if desc else "",
        "image": image.group(1) if image else None,
        "rating": rating,
        "count": count,
        "developer": json_unescape(dev.group(1)) if dev else None,
        "contains_ads": ("Contains ads" in html),
        "has_iap": ("In-app purchases" in html),
        "updated": updated.group(1).strip() if updated else None,
        "url": f"https://play.google.com/store/apps/details?id={package}",
    }


def parse_play_date(text: str | None) -> str | None:
    if not text:
        return None
    for fmt in ("%b %d, %Y", "%d %b %Y", "%Y년 %m월 %d일", "%b %d， %Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def fetch_github(repo: str) -> dict:
    data = jget(f"https://api.github.com/repos/{repo}", headers={"Accept": "application/vnd.github+json"},
                label=f"github:{repo}")
    license_info = data.get("license") or {}
    return {
        "repo": repo,
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "license": license_info.get("spdx_id"),
        "license_name": license_info.get("name"),
        "archived": bool(data.get("archived")),
        "pushed_at": (data.get("pushed_at") or "")[:10] or None,
        "created_at": (data.get("created_at") or "")[:10] or None,
        "homepage": data.get("homepage"),
        "topics": data.get("topics") or [],
        "avatar": ((data.get("owner") or {}).get("avatar_url")),
        "url": data.get("html_url"),
    }


def fetch_steam(app_id: int) -> dict:
    kr = jget(f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=kr&l=korean"
              f"&filters=basic,price_overview,genres,categories,platforms,release_date,developers,"
              f"publishers,dlc,short_description,header_image,recommendations,metacritic",
              label=f"steam-appdetails:{app_id}:kr").get(str(app_id)) or {}
    us = jget(f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=us&l=english"
              f"&filters=basic,price_overview,genres,platforms,release_date,developers,short_description",
              label=f"steam-appdetails:{app_id}:us").get(str(app_id)) or {}
    if not (kr.get("success") and kr.get("data")) and not (us.get("success") and us.get("data")):
        raise CollectError(f"Steam appdetails 에서 appid {app_id} 를 찾지 못함")
    dk = (kr.get("data") or {}) if kr.get("success") else {}
    du = (us.get("data") or {}) if us.get("success") else {}
    primary = dk or du
    out = {
        "app_id": app_id,
        "name": du.get("name") or primary.get("name"),
        "name_kr": dk.get("name") or primary.get("name"),
        "developers": primary.get("developers") or [],
        "publishers": primary.get("publishers") or [],
        "release_date": ac.parse_release((primary.get("release_date") or {}).get("date", "")),
        "is_free": bool(primary.get("is_free")),
        "genres_ko": [g.get("description") for g in (dk.get("genres") or primary.get("genres") or [])],
        "genres_en": [g.get("description") for g in (du.get("genres") or primary.get("genres") or [])],
        "categories_en": [c.get("description") for c in (du.get("categories") or dk.get("categories") or [])],
        "languages_en": [re.sub(r"<[^>]+>", "", part).strip()
                         for part in (primary.get("supported_languages") or "").split(",")],
        "website": primary.get("website"),
        "platforms": [k for k, v in (primary.get("platforms") or {}).items() if v],
        "short_ko": dk.get("short_description") or primary.get("short_description"),
        "short_en": du.get("short_description") or primary.get("short_description"),
        "header_image": primary.get("header_image"),
        "price_kr": primary.get("price_overview"),
        "price_us": (du.get("price_overview") or {}),
        "dlc_ids": primary.get("dlc") or [],
        "metacritic": (primary.get("metacritic") or {}).get("score"),
        "url": f"https://store.steampowered.com/app/{app_id}/",
        "warnings": [],
    }
    # 평가 요약 — 상점 페이지(data-tooltip-html) 우선, 실패하면 SteamSpy(전체 누적)로 대체
    try:
        page = tget(f"https://store.steampowered.com/app/{app_id}/?cc=kr&l=english",
                    headers=STORE_UA, label=f"steam-reviews:{app_id}")
        if "user_reviews_summary_row" in page:
            rows = []
            for block in re.findall(r'<a class="user_reviews_summary_row".*?</a>', page, re.S):
                tip = re.search(r'data-tooltip-html="([^"]+)"', block)
                if not tip:
                    continue
                text = tip.group(1)
                m = re.search(r"(\d+)% of the ([\d,]+) user reviews in the last 30 days", text)
                if m:
                    rows.append({"kind": "recent", "percent": int(m.group(1)),
                                 "count": int(m.group(2).replace(",", "")), "window": "최근 30일"})
                    continue
                m = re.search(r"(\d+)% of the ([\d,]+) user reviews (?:in your language|for this game)", text)
                if m:
                    rows.append({"kind": "language", "percent": int(m.group(1)),
                                 "count": int(m.group(2).replace(",", "")), "window": "전체(영어 리뷰)"})
            out["reviews"] = rows
        else:
            out["warnings"].append("상점 평가 페이지 접근 차단(연령 확인) — SteamSpy 누적으로 대체")
    except CollectError as exc:
        out["warnings"].append(str(exc))
    try:
        spy = jget(f"https://steamspy.com/api.php?request=appdetails&appid={app_id}", label=f"steamspy:{app_id}")
        pos, neg = int(spy.get("positive") or 0), int(spy.get("negative") or 0)
        if pos:
            out["steamspy"] = {"positive": pos, "negative": neg, "total": pos + neg,
                               "percent": round(pos * 100 / (pos + neg), 1) if pos + neg else None,
                               "owners": spy.get("owners")}
    except CollectError as exc:
        out["warnings"].append(str(exc))
    try:
        news = jget(f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={app_id}&count=100&maxlength=1",
                    label=f"steam-news:{app_id}")
        rows = []
        for row in (news.get("appnews") or {}).get("newsitems") or []:
            if row.get("feedname") != "steam_community_announcements":
                continue
            rows.append({"date": datetime.fromtimestamp(row["date"], timezone.utc).date().isoformat(),
                         "title": clean(row.get("title"), 120), "url": row.get("url")})
        rows.sort(key=lambda r: r["date"], reverse=True)
        out["announcements"] = rows[:12]
    except CollectError as exc:
        out["warnings"].append(str(exc))
        out["announcements"] = []
    return out


def collect_entry(entry: dict) -> dict:
    """한 항목의 소스 수집 — 실패한 소스는 건너뛰고 나머지로 만든다."""
    raw: dict = {"warnings": []}
    if entry.get("steam"):
        try:
            app_id, store_name, how = resolve_steam(entry["steam"], entry["name"])
            raw["steam"] = fetch_steam(app_id)
            raw["steam"]["store_name"] = store_name
            raw["steam"]["match"] = how
        except CollectError as exc:
            raw["warnings"].append(str(exc))
    if entry.get("ios"):
        try:
            raw["ios"] = resolve_ios(entry["ios"], entry["name"])
        except CollectError as exc:
            raw["warnings"].append(str(exc))
    if entry.get("play"):
        # 한국·영어 스토어 페이지를 따로 받는다 — 한쪽 페이지가 없어도(해외 전용·지역 제한) 나머지로 항목을 만든다.
        play_rec: dict = {}
        for lang in ("en", "ko"):
            try:
                play_rec[lang] = fetch_play(entry["play"], lang)
            except CollectError as exc:
                raw["warnings"].append(f"play:{entry['play']}:{lang} — {exc}")
        if play_rec.get("en") or play_rec.get("ko"):
            raw["play"] = play_rec
    if entry.get("github"):
        try:
            raw["github"] = fetch_github(entry["github"])
        except CollectError as exc:
            raw["warnings"].append(str(exc))
    if not any(key in raw for key in ("steam", "ios", "play", "github")):
        raise CollectError("수집된 소스가 없음 — " + "; ".join(raw["warnings"]))
    return raw


# ─────────────────────────────────────────────────────────────── 2) 점수 산정
def license_open(license_id: str | None) -> bool:
    return bool(license_id) and license_id not in {"NOASSERTION", "OTHER", "UNLICENSED"}


def license_label(license_id: str | None) -> str:
    """화면에 쓰는 라이선스 표기 — 자동 확인 실패는 '미확인'으로."""
    if license_id and license_id not in {"NOASSERTION", "OTHER", "UNLICENSED"}:
        return license_id
    return "미확인"


def recency_days(last_update: str | None) -> int | None:
    return ac.days_since(last_update) if last_update else None


def objective_score(f: dict) -> tuple[float, list[str], list[str]]:
    """객관 축 초기 산정 — 라이선스·가격 표기·업데이트 주기·플랫폼·출시 연수. (점수, 한국어 근거, 영어 근거)"""
    score, why, why_en = 62.0, [], []
    if license_open(f.get("license")):
        score += 8
        why.append(f"오픈소스 라이선스 {f['license']}(+8)")
        why_en.append(f"open-source license {f['license']} (+8)")
    elif f.get("license"):
        score += 2
        why.append(f"라이선스 {f['license']}(+2)")
        why_en.append(f"license {f['license']} (+2)")
    if f.get("price_known"):
        score += 4
        why.append("가격·무료 여부를 스토어에서 확인(+4)")
        why_en.append("price or free-to-use confirmed on the store (+4)")
    age = f.get("days_since_update")
    if age is None:
        score -= 4
        why.append("최근 업데이트 확인 실패(-4)")
        why_en.append("recent update not found (-4)")
    elif age <= 90:
        score += 8
        why.append(f"최근 90일 내 업데이트 {f['last_update']}(+8)")
        why_en.append(f"updated within 90 days ({f['last_update']}) (+8)")
    elif age <= 180:
        score += 5
        why.append(f"180일 내 업데이트 {f['last_update']}(+5)")
        why_en.append(f"updated within 180 days ({f['last_update']}) (+5)")
    elif age <= 365:
        score += 2
        why.append(f"1년 내 업데이트 {f['last_update']}(+2)")
        why_en.append(f"updated within a year ({f['last_update']}) (+2)")
    else:
        score -= 14
        why.append(f"12개월 넘게 업데이트 없음 {f['last_update']}(-14)")
        why_en.append(f"no update for over 12 months ({f['last_update']}) (-14)")
    platforms = f.get("platforms") or []
    if len(platforms) >= 4:
        score += 4
        why.append(f"플랫폼 {len(platforms)}종(+4)")
        why_en.append(f"{len(platforms)} platforms (+4)")
    elif len(platforms) >= 2:
        score += 2
        why.append(f"플랫폼 {len(platforms)}종(+2)")
        why_en.append(f"{len(platforms)} platforms (+2)")
    years = years_since(f.get("release_date"))
    if years is not None and years >= 6:
        score += 4
        why.append(f"출시 {int(years)}년(+4)")
        why_en.append(f"{int(years)} years since release (+4)")
    elif years is not None and years >= 3:
        score += 2
        why.append(f"출시 {int(years)}년(+2)")
        why_en.append(f"{int(years)} years since release (+2)")
    return round(clip(score, 35, 95), 1), why, why_en


def ai_review_score(f: dict) -> tuple[float, list[str], list[str]]:
    """AI 검토 축 잠정값 — 본질 검토 전 중립값 60 에서 사실만으로 보정한다."""
    score, why, why_en = 60.0, ["본질 검토 전 중립값 60"], ["neutral 60 before the deep review"]
    rating = f.get("rating100")
    if rating is not None:
        delta = round((rating - 80) * 0.25, 1)
        score += delta
        why.append(f"스토어 평점 {rating}({delta:+})")
        why_en.append(f"store rating {rating} ({delta:+})")
    if license_open(f.get("license")):
        score += 4
        why.append("오픈소스 소스 공개(+4)")
        why_en.append("open-source code (+4)")
    age = f.get("days_since_update")
    if age is not None and age <= 90:
        score += 4
        why.append("90일 내 업데이트(+4)")
        why_en.append("updated within 90 days (+4)")
    elif age is not None and age <= 180:
        score += 2
        why.append("180일 내 업데이트(+2)")
        why_en.append("updated within 180 days (+2)")
    elif age is not None and age > 365:
        score -= 8
        why.append("12개월 방치(-8)")
        why_en.append("idle for over 12 months (-8)")
    sample = f.get("sample_count") or 0
    if sample >= 100_000:
        score += 3
        why.append(f"표본 {fmt(sample)}건(+3)")
        why_en.append(f"{fmt(sample)} ratings (+3)")
    elif sample >= 10_000:
        score += 1
        why.append(f"표본 {fmt(sample)}건(+1)")
        why_en.append(f"{fmt(sample)} ratings (+1)")
    return round(clip(score, 45, 82), 1), why, why_en


# ─────────────────────────────────────────────────────────────── 3) 항목 조립
def build_facts(entry: dict, raw: dict, arena: dict) -> dict:
    """소스 원본 → 항목 공통 사실 묶음(한국어·영어 문장 재료)."""
    steam, ios, play, gh = raw.get("steam"), raw.get("ios"), raw.get("play"), raw.get("github")
    play_en = (play or {}).get("en") or {}
    play_ko = (play or {}).get("ko") or {}
    ios_primary = None
    if ios:
        ios_primary = max(ios.items(), key=lambda kv: (kv[1].get("userRatingCount") or 0))[1]
    f: dict = {
        "name": entry["name"],
        "developer": None,
        "publisher": None,
        "release_date": None,
        "platforms": [],
        "genres_ko": [],
        "genres_en": [],
        "one_liner_ko": "",
        "one_liner_en": "",
        "price_known": False,
        "license": None,
        "last_update": None,
        "last_update_platform": None,
        "days_since_update": None,
        "update_notes": [],
        "rating100": None,
        "sample_count": 0,
        "rating_lines_ko": [],
        "rating_lines_en": [],
        "review_rows": [],
        "review_rows_en": [],
        "tiers": [],
        "warnings": list(raw.get("warnings") or []),
        "store_ads": None,
        "sources": [],
    }

    if steam:
        f["developer"] = (steam["developers"] or [None])[0]
        f["publisher"] = (steam["publishers"] or [None])[0]
        f["release_date"] = steam.get("release_date")
        f["platforms"] = list(dict.fromkeys(
            ["steam"] + [{"windows": "windows", "mac": "macos", "linux": "linux"}.get(p, p) for p in steam["platforms"]]))
        f["genres_ko"] = [g for g in steam.get("genres_ko") or [] if g]
        f["genres_en"] = [g for g in steam.get("genres_en") or [] if g]
        f["one_liner_ko"] = clean(steam.get("short_ko"), 140)
        f["one_liner_en"] = clean(steam.get("short_en"), 140)
        f["price_known"] = True
        price_kr = steam.get("price_kr") or {}
        price_us = steam.get("price_us") or {}
        amount = price_kr.get("initial")
        if steam["is_free"]:
            f["tiers"].append({
                "tier_id": "steam", "kind": "free", "label": "Steam 무료",
                "label_en": "Free on Steam",
                "price": {"amount": 0, "currency": "KRW", "period": "none", "display": "무료"},
                "price_display_en": "Free",
                "limits": ["캐시 상점·확률형 상품 등 선택 과금은 검수 전"],
                "limits_en": ["Cash shop or random-item monetization not reviewed yet"],
                "one_liner": "무료 플레이 — 선택 과금 구조는 검수 전",
                "one_liner_en": "Free to play — optional monetization not reviewed yet",
            })
        else:
            kr_amount = round(amount / 100) if amount else None
            display = f"₩{fmt(kr_amount)}" if kr_amount is not None else "가격 미표기(스토어 응답 없음)"
            if price_kr.get("discount_percent"):
                display += f" (할인 {price_kr['discount_percent']}% ₩{fmt(round((price_kr.get('final') or 0) / 100))})"
            usd = f"${price_us['initial'] / 100:.2f}" if price_us.get("initial") else None
            display_en = usd or ("Price not listed on the store" if kr_amount is None else display)
            limits = ([f"DLC {len(steam['dlc_ids'])}건 별도 판매"] if steam["dlc_ids"] else ["유료 DLC 없음(스토어 목록 기준)"])
            limits_en = ([f"{len(steam['dlc_ids'])} paid DLCs sold separately"] if steam["dlc_ids"]
                         else ["No paid DLC listed"])
            if usd:
                limits.append(f"미국 스토어 {usd}")
                limits_en.append(f"US store {usd}")
            if kr_amount is None:
                limits.append("스토어에 가격이 표시되지 않음 — 무료 전환·판매 중단 여부 확인 필요")
                limits_en.append("No price on the store listing — free-to-play switch or delisting to verify")
            f["tiers"].append({
                "tier_id": "steam", "kind": "one_time", "label": "Steam 1회 구매",
                "label_en": "One-time purchase on Steam",
                "price": {"amount": kr_amount, "currency": "KRW", "period": "one_time", "display": display},
                "price_display_en": display_en,
                "limits": limits, "limits_en": limits_en,
                "one_liner": (f"1회 구매 ₩{fmt(kr_amount)} — DLC {len(steam['dlc_ids'])}건 별도" if kr_amount is not None
                              else "가격 미표기 — 스토어에 구매 가격이 표시되지 않는다"),
                "one_liner_en": (f"One-time ${usd} — {len(steam['dlc_ids'])} DLCs sold separately" if kr_amount is not None
                                 else "No price shown on the store listing"),
            })
        # 평가
        rows = steam.get("reviews") or []
        lang_row = next((r for r in rows if r["kind"] == "language"), None)
        recent_row = next((r for r in rows if r["kind"] == "recent"), None)
        if lang_row:
            f["review_rows"].append({
                "platform": "steam",
                "cumulative": {"metric": "positive_rate", "value": lang_row["percent"], "scale": "percent",
                               "count": lang_row["count"], "window": "전체(영어 리뷰)", "evidence_grade": "A"},
                **(dict(recent={"metric": "positive_rate", "value": recent_row["percent"],
                                "scale": "percent", "count": recent_row["count"], "window": "최근 30일",
                                "evidence_grade": "A"}) if recent_row else {}),
                "note": f"Steam 상점 평가 요약(영어 리뷰 전체 {fmt(lang_row['count'])}건).",
            })
            f["review_rows_en"].append({
                "platform": "steam",
                "cumulative": {"metric": "positive_rate", "value": lang_row["percent"], "scale": "percent",
                               "count": lang_row["count"], "window": "All (English reviews)", "evidence_grade": "A"},
                **(dict(recent={"metric": "positive_rate", "value": recent_row["percent"],
                                "scale": "percent", "count": recent_row["count"], "window": "Last 30 days",
                                "evidence_grade": "A"}) if recent_row else {}),
                "note": f"Steam store review summary ({fmt(lang_row['count'])} English reviews).",
            })
            f["rating_lines_ko"].append(
                f"Steam 누적 {lang_row['percent']}% 긍정({fmt(lang_row['count'])}건)"
                + (f" · 최근 30일 {recent_row['percent']}%({fmt(recent_row['count'])}건)" if recent_row else ""))
            f["rating_lines_en"].append(
                f"{lang_row['percent']}% positive on Steam ({fmt(lang_row['count'])} reviews)"
                + (f", {recent_row['percent']}% in the last 30 days ({fmt(recent_row['count'])})" if recent_row else ""))
        elif steam.get("steamspy"):
            spy = steam["steamspy"]
            f["review_rows"].append({
                "platform": "steam",
                "cumulative": {"metric": "positive_rate", "value": spy["percent"], "scale": "percent",
                               "count": spy["total"], "window": "전체(SteamSpy 집계)", "evidence_grade": "C"},
                "note": f"SteamSpy 전체 누적 {fmt(spy['positive'])}긍정/{fmt(spy['negative'])}부정 · 보유자 {spy.get('owners')}.",
            })
            f["review_rows_en"].append({
                "platform": "steam",
                "cumulative": {"metric": "positive_rate", "value": spy["percent"], "scale": "percent",
                               "count": spy["total"], "window": "All (SteamSpy aggregate)", "evidence_grade": "C"},
                "note": f"SteamSpy lifetime totals: {fmt(spy['positive'])} positive / {fmt(spy['negative'])} negative, "
                        f"owners {spy.get('owners')}.",
            })
            f["rating_lines_ko"].append(f"Steam 전체 누적 {spy['percent']}% 긍정(SteamSpy {fmt(spy['total'])}건)")
            f["rating_lines_en"].append(f"{spy['percent']}% positive overall (SteamSpy, {fmt(spy['total'])} reviews)")
        # 업데이트
        announcements = steam.get("announcements") or []
        if announcements:
            updates = [a for a in announcements if UPDATE_RE.search(a.get("title") or "")]
            pick = (updates or announcements)[0]
            f["last_update"] = pick["date"]
            f["last_update_platform"] = "steam"
            f["update_notes"] = announcements[:2]
            f["update_kind"] = "업데이트 공지" if updates else "개발사 공지(업데이트 공지 아님)"
            f["update_kind_en"] = "update announcement" if updates else "developer announcement (not a patch note)"
            f["update_title"] = pick.get("title")
            f["update_url"] = pick.get("url")
    if ios_primary:
        seller = ios_primary.get("sellerName")
        f["developer"] = f["developer"] or seller
        f["publisher"] = f["publisher"] or seller
        f["release_date"] = f["release_date"] or (ios_primary.get("releaseDate") or "")[:10] or None
        for p in ("ios",):
            if p not in f["platforms"]:
                f["platforms"].append(p)
        genres_ko_src = [g for g in (ios_primary.get("genres") or []) if g]
        us_rec = (ios or {}).get("us") or {}
        genres_en_src = [g for g in (us_rec.get("genres") or genres_ko_src) if g]
        if not f["genres_en"]:
            f["genres_en"] = [APPLE_GENRES_EN.get(g, g) for g in genres_en_src[:3]]
            f["genres_ko"] = ([APPLE_GENRES_KO.get(g, g) for g in genres_ko_src[:3]]
                               or genres_en_src[:3])
        # 한국 스토어에만 있는 앱은 미국 레코드가 없어 장르가 한글로 남는다 — 영문 화면에 새지 않게 영문으로 바꾼다.
        if any(KOREAN.search(g or "") for g in f["genres_en"]):
            translated = [APPLE_GENRES_EN.get(g, "") for g in f["genres_en"]]
            f["genres_en"] = [g for g in translated if g] or ["Software"]
        if not f["one_liner_ko"]:
            f["one_liner_ko"] = first_sentence(ios_primary.get("description"), 140)
        if not f["one_liner_en"]:
            us_rec = (ios or {}).get("us") or ios_primary
            f["one_liner_en"] = first_sentence(us_rec.get("description"), 140)
        stars = ios_primary.get("averageUserRating")
        count = ios_primary.get("userRatingCount") or 0
        price = ios_primary.get("price") or 0
        country = max(ios.items(), key=lambda kv: (kv[1].get("userRatingCount") or 0))[0]
        if stars:
            f["review_rows"].append({
                "platform": "ios",
                "cumulative": {"metric": "stars", "value": round(stars, 2), "scale": "stars5", "count": count,
                               "window": f"전체({country.upper()} 스토어)", "evidence_grade": "A"},
                "note": f"{country.upper()} {stars:.2f}★ · {fmt(count)}건 표본(한국·미국 중 큰 쪽).",
            })
            f["review_rows_en"].append({
                "platform": "ios",
                "cumulative": {"metric": "stars", "value": round(stars, 2), "scale": "stars5", "count": count,
                               "window": f"All ({country.upper()} store)", "evidence_grade": "A"},
                "note": f"{country.upper()} {stars:.2f}★ · {fmt(count)} ratings (the larger of the KR and US stores).",
            })
            f["rating_lines_ko"].append(f"App Store {stars:.2f}★({fmt(count)}건)")
            f["rating_lines_en"].append(f"{stars:.2f}★ on the App Store ({fmt(count)} ratings)")
        version_date = (ios_primary.get("currentVersionReleaseDate") or "")[:10] or None
        if version_date and (not f["last_update"] or version_date > f["last_update"]):
            f["last_update"] = version_date
            f["last_update_platform"] = "ios"
            f["update_kind"] = f"앱 버전 {ios_primary.get('version')} 릴리스"
            f["update_kind_en"] = f"app version {ios_primary.get('version')} release"
            f["update_title"] = f"{ios_primary.get('trackName')} {ios_primary.get('version')}"
            f["update_title_en"] = (f"{en_safe((((ios or {}).get('us') or ios_primary).get('trackName')), en_name(entry))} "
                                    f"{ios_primary.get('version')}")
            f["update_url"] = ios_primary.get("trackViewUrl")
        f["price_known"] = True
        amount = price or 0
        price_en_label = en_safe(((ios or {}).get("us") or {}).get("formattedPrice"), "")
        f["tiers"].append({
            "tier_id": "ios", "kind": "one_time" if amount else "freemium",
            "label": "iOS 1회 구매" if amount else "iOS 무료",
            "label_en": "One-time purchase on iOS" if amount else "Free on iOS",
            "price": {"amount": amount, "currency": ios_primary.get("currency") or "KRW",
                      "period": "one_time" if amount else "none",
                      "display": ios_primary.get("formattedPrice") or ("무료" if not amount else "가격 미확인")},
            "price_display_en": price_en_label or ("Free" if not amount else "Price not listed"),
            "limits": ["앱 내 구입·구독 구조는 검수 전"],
            "limits_en": ["In-app purchases and subscriptions not reviewed yet"],
            "one_liner": (f"{ios_primary.get('formattedPrice')} · 1회 구매" if amount
                          else f"무료 · 평점 {stars:.1f}★" if stars else "무료"),
            "one_liner_en": (f"{price_en_label} one-time" if amount and price_en_label
                             else f"Free · {stars:.1f}★" if stars else "Free"),
        })
    if play_en:
        f["developer"] = f["developer"] or play_en.get("developer")
        f["publisher"] = f["publisher"] or play_en.get("developer")
        if "android" not in f["platforms"]:
            f["platforms"].append("android")
        if not f["one_liner_ko"] and play_ko.get("description"):
            f["one_liner_ko"] = clean(play_ko["description"], 140)
        if not f["one_liner_en"] and play_en.get("description"):
            f["one_liner_en"] = clean(play_en["description"], 140)
        if play_en.get("rating"):
            play_en["rating"] = round(play_en["rating"], 2)
            f["review_rows"].append({
                "platform": "android",
                "cumulative": {"metric": "stars", "value": play_en["rating"], "scale": "stars5",
                               "count": play_en.get("count") or 0, "window": "전체(Play 표시 평가 수)",
                               "evidence_grade": "A"},
                "note": f"Google Play {play_en['rating']:.2f}★ · {fmt(play_en.get('count'))}건.",
            })
            f["review_rows_en"].append({
                "platform": "android",
                "cumulative": {"metric": "stars", "value": play_en["rating"], "scale": "stars5",
                               "count": play_en.get("count") or 0, "window": "All (Play Store rating count)",
                               "evidence_grade": "A"},
                "note": f"Google Play {play_en['rating']:.2f}★ · {fmt(play_en.get('count'))} ratings.",
            })
            f["rating_lines_ko"].append(f"Google Play {play_en['rating']:.2f}★({fmt(play_en.get('count'))}건)")
            f["rating_lines_en"].append(f"{play_en['rating']:.2f}★ on Google Play ({fmt(play_en.get('count'))} ratings)")
        play_updated = parse_play_date(play_en.get("updated"))
        if play_updated and (not f["last_update"] or play_updated > f["last_update"]):
            f["last_update"] = play_updated
            f["last_update_platform"] = "android"
            f["update_kind"] = "Play 스토어 업데이트"
            f["update_kind_en"] = "Play Store update"
            f["update_title"] = play_en.get("name")
            f["update_title_en"] = en_safe(play_en.get("name"), en_name(entry))
            f["update_url"] = play_en.get("url")
        f["store_ads"] = play_en.get("contains_ads")
        if not f["tiers"]:
            f["price_known"] = True
            f["tiers"].append({
                "tier_id": "android", "kind": "freemium" if play_en.get("has_iap") else "free",
                "label": "Google Play 무료", "label_en": "Free on Google Play",
                "price": {"amount": 0, "currency": "KRW", "period": "none", "display": "무료"},
                "price_display_en": "Free",
                "limits": ["앱 내 구입·구독 한도는 검수 전" if play_en.get("has_iap") else "무료 티어 한도는 검수 전"],
                "limits_en": ["In-app purchase limits not reviewed yet" if play_en.get("has_iap")
                              else "Free-tier limits not reviewed yet"],
                "one_liner": "무료 — 앱 내 구입 구조는 검수 전" if play_en.get("has_iap") else "무료",
                "one_liner_en": "Free — in-app purchases not reviewed yet" if play_en.get("has_iap") else "Free",
            })
    if gh:
        f["developer"] = f["developer"] or (gh.get("full_name") or "").split("/")[0]
        f["publisher"] = f["publisher"] or f["developer"]
        f["license"] = (gh.get("license") or "").strip() or None
        f["release_date"] = f["release_date"] or gh.get("created_at")
        if not f["one_liner_ko"]:
            f["one_liner_ko"] = clean(gh.get("description"), 140) or f"{gh['full_name']} 오픈소스 저장소"
        if not f["one_liner_en"]:
            f["one_liner_en"] = clean(gh.get("description"), 140) or f"{gh['full_name']} open-source repository"
        if not f["genres_en"]:
            blocked = {"c", "cpp", "python", "rust", "go", "java", "javascript", "typescript", "shell", "lua",
                       "hacktoberfest", "linux", "windows", "macos", "android", "ios", "cli", "utility",
                       "tool", "tools", "open-source", "opensource", "self-hosted", "docker", "api", "gui", "qt",
                       "gtk", "electron", "nodejs", "react", "ffmpeg", "terminal", "cross-platform"}
            own = {norm(entry["id"]), norm(entry.get("name") or ""), norm((gh.get("full_name") or "").split("/")[-1])}
            topics = [t.replace("-", " ") for t in (gh.get("topics") or [])
                      if t.lower() not in blocked and len(t) > 2 and norm(t) not in own]
            f["genres_en"] = topics[:3] or ["Open-source tool"]
            f["genres_ko"] = [g for g in f["genres_en"]] if topics else ["오픈소스 도구"]
        if not f["tiers"]:
            f["tiers"].append({
                "tier_id": "oss", "kind": "free", "label": "오픈소스 무료",
                "label_en": "Open source, free",
                "price": {"amount": 0, "currency": "KRW", "period": "none", "display": "무료"},
                "price_display_en": "Free",
                "limits": [f"라이선스 {license_label(f['license'])} — 무료로 설치·사용"
                           + (" (복제·수정 조건은 확인 필요)" if license_label(f['license']) == "미확인" else "")],
                "limits_en": [f"License {('not confirmed' if license_label(f['license']) == '미확인' else f['license'])} — "
                              f"free to install and use"
                              + (" (reuse and modification terms to verify)" if license_label(f['license']) == "미확인" else "")],
                "one_liner": f"오픈소스 · 무료(라이선스 {license_label(f['license'])})",
                "one_liner_en": f"Open source, free (license {'not confirmed' if license_label(f['license']) == '미확인' else f['license']})",
            })
        if gh.get("pushed_at") and (not f["last_update"] or gh["pushed_at"] > f["last_update"]):
            f["last_update"] = gh["pushed_at"]
            f["last_update_platform"] = "other"
            f["update_kind"] = "저장소 최근 푸시"
            f["update_kind_en"] = "latest repository push"
            f["update_title"] = f"{gh['full_name']} push"
            f["update_url"] = gh.get("url")
    dev_en = company_en(f["developer"], "")
    if KOREAN.search(f["one_liner_en"] or ""):
        f["one_liner_en"] = f"{dev_en or en_name(entry)} — {arena['label_en']} entry"
    if not f["one_liner_ko"]:
        f["one_liner_ko"] = f"{f['developer'] or entry['name']}의 {arena['label']} 항목"
        f["one_liner_en"] = f"{dev_en or en_name(entry)} — {arena['label_en']} entry"
    if not f["genres_ko"]:
        f["genres_ko"] = ["소프트웨어"]
        f["genres_en"] = f["genres_en"] or ["Software"]
    for platform in entry.get("platforms") or []:
        if platform not in f["platforms"]:
            f["platforms"].append(platform)
    if not f["platforms"]:
        f["platforms"] = ["other"]

    # 사용자 축 — 표본 가중 평균(별점 축은 20배로 100점 환산)
    candidates = []
    for row in f["review_rows"]:
        metric = row["cumulative"]
        count = metric.get("count") or 0
        if metric["scale"] == "stars5":
            candidates.append((round(metric["value"] * 20, 1), count, metric["window"]))
        elif metric["scale"] == "percent":
            candidates.append((metric["value"], count, metric["window"]))
    if candidates:
        total = sum(c for _s, c, _w in candidates)
        f["rating100"] = (round(sum(s * c for s, c, _w in candidates) / total, 1) if total
                          else round(sum(s for s, _c, _w in candidates) / len(candidates), 1))
        f["sample_count"] = max(c for _s, c, _w in candidates)
    # v0.6.0 표본 규모 보정 — 기본 평점은 그대로 두고, 사용자 축 점수만 규모로 보정한다.
    f["scale"] = srules.adjust(f["rating100"], f["sample_count"], "reviews")
    age = recency_days(f["last_update"])
    f["days_since_update"] = age
    return f


def maintenance_of(f: dict) -> tuple[str, str, str]:
    """(maintenance_status, 한국어 메모, 영어 메모)"""
    age = f["days_since_update"]
    if f["last_update"] is None:
        return ("stale_unknown",
                "마지막 업데이트 날짜를 확인하지 못했다 — 완결·방치 여부도 미확인.",
                "Last update date not found — neither feature-complete nor abandoned confirmed.")
    if age is not None and age > 365:
        return ("stale_unknown",
                f"마지막 업데이트 {f['last_update']}({age}일 전) — 완결 선언인지 방치인지 확인 전.",
                f"Last update {f['last_update']} ({age} days ago) — feature-complete or abandoned not confirmed.")
    return ("active", f"마지막 업데이트 {f['last_update']}({age}일 전).",
            f"Last update {f['last_update']} ({age} days ago).")


def flags_for(f: dict, domain: str) -> dict:
    """공개 API 가 직접 증명하는 것만 yes/no, 나머지는 unknown."""
    src_ids = [s["id"] for s in f["sources"]]
    primary = src_ids[:1]
    unknown = {"value": "unknown", "evidence_grade": "unknown", "source_ids": [],
               "note": FLAG_NOTE_UNKNOWN_KO}
    flags: dict = {
        "gacha_random_items": dict(unknown),
        "p2w": dict(unknown),
        "iap_required_to_progress": dict(unknown),
        "subscription_required": dict(unknown),
        "account_required": dict(unknown),
        "data_collected": dict(unknown),
        "data_export": {"value": "unknown", "evidence_grade": "unknown", "source_ids": [],
                        "note": "내보내기·이전 방법은 확인하지 못했다."},
    }
    ads_known = f.get("store_ads")
    if ads_known is False:
        flags["contains_ads"] = {"value": "no", "evidence_grade": "A", "source_ids": primary,
                                 "note": "Google Play 데이터 보안 표기에 '광고 포함'이 없다.", "verification": "direct"}
        flags["forced_ad_before_use"] = {"value": "no", "evidence_grade": "A", "source_ids": primary,
                                         "note": "스토어에 광고 표기가 없고, 실행 전 광고 안내도 없다.", "verification": "direct"}
        flags["bait_ad"] = {"value": "no", "evidence_grade": "C", "source_ids": primary,
                            "note": "미끼형 유입 광고 보도·불만을 확인하지 못했다(부재 근거).", "verification": "absent"}
    elif ads_known is True:
        flags["contains_ads"] = {"value": "yes", "evidence_grade": "A", "source_ids": primary,
                                 "note": "Google Play 데이터 보안 표기에 '광고 포함'이 있다.", "verification": "direct"}
        flags["forced_ad_before_use"] = dict(unknown)
        flags["bait_ad"] = dict(unknown)
    elif "steam" in f["source_kinds"]:
        flags["contains_ads"] = {"value": "no", "evidence_grade": "B", "source_ids": primary,
                                 "note": "Steam 단품 게임 — 스토어에 인게임 광고 표기가 없고 실행 전 광고도 없다.",
                                 "verification": "inferred"}
        flags["forced_ad_before_use"] = {"value": "no", "evidence_grade": "B", "source_ids": primary,
                                         "note": "Steam 단품 게임 — 실행 전 광고가 없다.", "verification": "inferred"}
        flags["bait_ad"] = {"value": "no", "evidence_grade": "C", "source_ids": primary,
                            "note": "미끼형 유입 광고 보도·불만을 확인하지 못했다(부재 근거).", "verification": "absent"}
    else:
        flags["contains_ads"] = dict(unknown)
        flags["forced_ad_before_use"] = dict(unknown)
        flags["bait_ad"] = dict(unknown)
    if "steam" in f["source_kinds"] and f.get("paid_one_time"):
        flags["subscription_required"] = {"value": "no", "evidence_grade": "B", "source_ids": primary,
                                          "note": "1회 구매 단품 — 구독 상품이 없다(스토어 가격 구조).",
                                          "verification": "inferred"}
        flags["iap_required_to_progress"] = dict(unknown)
        flags["account_required"] = dict(unknown)
    ago = f["days_since_update"]
    if ago is None:
        flags["stale_over_12m"] = dict(unknown)
    elif ago > 365:
        flags["stale_over_12m"] = {"value": "yes", "evidence_grade": "A", "source_ids": primary,
                                   "note": f"마지막 업데이트 {f['last_update']} — 12개월({ago}일) 넘게 새 공지·릴리스가 없다.",
                                   "verification": "direct"}
    else:
        flags["stale_over_12m"] = {"value": "no", "evidence_grade": "A", "source_ids": primary,
                                   "note": f"마지막 업데이트 {f['last_update']}({ago}일 전) — 활발.", "verification": "direct"}
    return flags


def add_source(f: dict, sid: str, title: str, url: str, stype: str, grade: str,
               note_ko: str, note_en: str, title_en: str | None = None) -> None:
    f["sources"].append({"id": sid, "title": title, "url": url, "type": stype, "grade": grade,
                         "accessed_at": TODAY, "note": note_ko, "note_en": note_en,
                         "title_en": title_en or title})


def auto_encyclopedia(item: dict, f: dict, raw: dict, entry: dict, arena: dict) -> tuple[dict, dict]:
    """수집 사실만으로 기본 사전 블록을 만든다(수치를 지어내지 않는다).

    제원: 플랫폼 · 한국어(Steam 언어 목록) · 플레이 방식 · 모드(Steam 분류) · 가격 · 평가 ·
          최근 업데이트 · 라이선스(GitHub) — 확인된 것만 넣고 최소 3개를 못 채우면 ValueError.
    """
    domain = item["domain"]
    steam = raw.get("steam") or {}
    gh = raw.get("github") or {}
    tier = (f.get("tiers") or [{}])[0]
    kind_ko = {"free": "무료", "freemium": "무료 + 유료", "demo": "체험판", "one_time": "1회 구매",
               "subscription": "구독", "license": "라이선스", "consumable": "소모품 과금"}.get(tier.get("kind"), tier.get("kind") or "")
    kind_en = {"free": "Free", "freemium": "Free + paid tiers", "demo": "Demo", "one_time": "One-time purchase",
               "subscription": "Subscription", "license": "License", "consumable": "Consumable purchases"}.get(tier.get("kind"), tier.get("kind") or "")
    langs = [x for x in (steam.get("languages_en") or []) if x]
    korean = ("지원" if any("Korean" in x for x in langs) else "미지원") if langs else None
    cats = [c for c in (steam.get("categories_en") or []) if c]
    modes = [c for c in cats if c in ("Single-player", "Multi-player", "Online PvP", "PvP", "Online Co-op", "Co-op",
                                      "Shared/Split Screen Co-op", "Shared/Split Screen", "MMO", "Cross-Platform Multiplayer")]
    license_id = gh.get("license") or ""
    facts = [
        enc.fact("플랫폼", "Platforms", enc.platform_list(item["platforms"], lambda p: enc.PLATFORM_KO.get(p, p)),
                 enc.platform_list(item["platforms"], lambda p: enc.PLATFORM_EN.get(p, p))),
        enc.fact("한국어", "Korean", korean or "", "Supported" if korean == "지원" else ("Not supported" if korean else ""),
                 "Steam 표시 언어 목록", "Steam supported languages") if korean else None,
        enc.fact("플레이 방식", "How it plays", " · ".join(f["genres_ko"][:3]) or arena["label"],
                 " · ".join(f["genres_en"][:3]) or arena.get("label_en", arena["label"])),
        enc.fact("모드", "Modes", " · ".join(modes), " · ".join(modes), "Steam 상점 분류", "Steam store categories") if modes else None,
        enc.fact("가격", "Price", f"{tier.get('price_display_ko') or tier.get('price', {}).get('display') or '미표기'}"
                 + (f" ({kind_ko})" if kind_ko else ""),
                 f"{tier.get('price_display_en') or tier.get('price', {}).get('display') or 'not listed'}"
                 + (f" ({kind_en})" if kind_en else "")),
        enc.fact("평가", "Rating", " · ".join(f.get("rating_lines_ko") or []) or "표본 없음",
                 " · ".join(f.get("rating_lines_en") or []) or "no sample"),
        enc.fact("최근 업데이트", "Latest update", f.get("last_update") or "기록 없음",
                 f.get("last_update") or "no record", "수집 시점 스토어·저장소 표기", "As listed when collected"),
        enc.fact("라이선스", "License", license_id or "", license_id, "GitHub 저장소", "GitHub repository") if license_id else None,
        enc.fact("출시", "Released", item.get("release_date") or "미표기", item.get("release_date") or "not listed") if item.get("release_date") else None,
    ]
    facts = [row for row in facts if row]

    name_ko, name_en = item["name"], entry.get("en") or item["name"]
    head_ko, head_en = enc.summary_line(domain, name_ko=name_ko, name_en=name_en,
                                        developer_ko=item["developer"], developer_en=item["developer"],
                                        release=item.get("release_date"),
                                        genres_ko=item["genres"], genres_en=f.get("genres_en") or item["genres"])
    rating_ko = " · ".join(f.get("rating_lines_ko") or []) or "공개 표본 없음"
    rating_en = " · ".join(f.get("rating_lines_en") or []) or "no public sample"
    summary_ko = f"{head_ko} {item['one_liner']} 평가 표본은 {rating_ko}"
    summary_en = f"{head_en} {f.get('one_liner_en') or item['one_liner']} Rating sample: {rating_en}."

    high_ko, high_en = [], []
    if korean:
        high_ko.append(f"한국어 {korean} — Steam 표시 언어 목록 기준.")
        high_en.append(f"Korean: {'supported' if korean == '지원' else 'not supported'} in Steam's language list.")
    if modes:
        high_ko.append(f"Steam 분류: {' · '.join(modes)}.")
        high_en.append(f"Steam categories: {', '.join(modes)}.")
    if f.get("rating_lines_ko"):
        high_ko.append(f"공개 평가 {rating_ko}.")
        high_en.append(f"Public ratings: {rating_en}.")
    high_ko.append(f"가격은 {tier.get('price_display_ko') or tier.get('price', {}).get('display') or '미표기'}"
                   f"{' (' + kind_ko + ')' if kind_ko else ''}.")
    high_en.append(f"Price: {tier.get('price_display_en') or tier.get('price', {}).get('display') or 'not listed'}"
                   f"{' (' + kind_en + ')' if kind_en else ''}.")
    if f.get("last_update"):
        high_ko.append(f"최근 업데이트 {f['last_update']}.")
        high_en.append(f"Latest update {f['last_update']}.")

    links = []
    if steam.get("website"):
        links.append(enc.link("공식 홈페이지", "Official site", steam["website"]))
    if gh.get("url"):
        links.append(enc.link("공식 저장소", "Official repository", gh["url"]))
    return enc.compose(summary_ko=summary_ko, summary_en=summary_en, facts=facts,
                       highlights_ko=high_ko, highlights_en=high_en, official_links=links)


def build_item(entry: dict, arena: dict, meta: dict, raw: dict) -> tuple[dict, dict, dict]:
    """수집 원본 → (한국어 item, 영어 오버레이, 아이콘 후보)."""
    f = build_facts(entry, raw, arena)
    dev_en = company_en(f["developer"], "")
    f["source_kinds"] = {k for k in ("steam", "ios", "play", "github") if k in raw}
    steam, ios, gh = raw.get("steam"), raw.get("ios"), raw.get("github")
    f["paid_one_time"] = bool(steam) and not steam.get("is_free")

    # ── 출처
    if steam:
        price_kr = steam.get("price_kr") or {}
        price_txt = ("무료" if steam["is_free"] else
                     f"정가 {price_kr.get('initial_formatted') or '미표기'}")
        add_source(f, f"steam-{entry['id']}", f"Steam — {steam.get('name')}", steam["url"], "store", "A",
                   f"{price_txt}, 출시 {steam.get('release_date') or '미표기'}, 개발사 {', '.join(steam['developers']) or '미표기'}. "
                   f"평가 {' · '.join(f['rating_lines_ko']) or '표본 미확인'}.",
                   f"{'Free' if steam['is_free'] else 'List price ' + (price_kr.get('initial_formatted') or 'not listed')}, "
                   f"released {steam.get('release_date') or 'not listed'}, developer {', '.join(steam['developers']) or 'not listed'}. "
                   f"Reviews: {' · '.join(f['rating_lines_en']) or 'not found'}.",
                   title_en=f"Steam — {steam.get('name')}")
    if ios:
        rec = max(ios.items(), key=lambda kv: (kv[1].get("userRatingCount") or 0))[1]
        rec_en = (ios or {}).get("us") or rec
        add_source(f, f"itunes-{entry['id']}", f"Apple App Store — {rec.get('trackName')}",
                   rec.get("trackViewUrl") or f"https://apps.apple.com/app/id{rec.get('trackId')}", "store", "A",
                   f"가격 {rec.get('formattedPrice')}, {rec.get('averageUserRating') and round(rec['averageUserRating'], 2)}★"
                   f"({fmt(rec.get('userRatingCount'))}건), 버전 {rec.get('version')}, "
                   f"최근 릴리스 {(rec.get('currentVersionReleaseDate') or '')[:10]}.",
                   f"Price {en_safe(rec_en.get('formattedPrice'), 'free or in-app')}, "
                   f"{rec_en.get('averageUserRating') and round(rec_en['averageUserRating'], 2)}★ "
                   f"({fmt(rec_en.get('userRatingCount'))} ratings), version {rec_en.get('version')}, "
                   f"released {(rec_en.get('currentVersionReleaseDate') or '')[:10]}.",
                   title_en=f"Apple App Store — {en_safe(rec_en.get('trackName'), en_name(entry))}")
    if raw.get("play"):
        en = raw["play"].get("en") or raw["play"].get("ko") or {}
        add_source(f, f"play-{entry['id']}", f"Google Play — {en.get('name')}", en["url"], "store", "A",
                   f"평점 {en.get('rating')}★({fmt(en.get('count'))}) · 무료 · 최근 업데이트 {parse_play_date(en.get('updated')) or '미표기'}.",
                   f"{en.get('rating')}★ ({fmt(en.get('count'))}) · free · last updated "
                   f"{parse_play_date(en.get('updated')) or 'not listed'}.",
                   title_en=f"Google Play — {en_safe(en.get('name'), en_name(entry))}")
    if raw.get("github"):
        gh = raw["github"]
        add_source(f, f"github-{entry['id']}", f"GitHub — {gh['full_name']}", gh["url"], "official", "A",
                   f"스타 {fmt(gh['stars'])} · 라이선스 {license_label(gh.get('license'))} · 최근 푸시 {gh.get('pushed_at')} "
                   f"· 아카이브 {str(gh['archived']).lower()}.",
                   f"{fmt(gh['stars'])} stars · license {('not confirmed' if license_label(gh.get('license')) == '미확인' else gh.get('license'))} "
                   f"· last push {gh.get('pushed_at')} · archived {str(gh['archived']).lower()}.",
                   title_en=f"GitHub — {gh['full_name']}")
    if steam and steam.get("steamspy"):
        spy = steam["steamspy"]
        add_source(f, f"steamspy-{entry['id']}", f"SteamSpy — {steam.get('name')}",
                   f"https://steamspy.com/app/{steam['app_id']}", "aggregator", "C",
                   f"전체 언어 누적 긍정 {fmt(spy['positive'])} / 부정 {fmt(spy['negative'])} (긍정률 {spy['percent']}%). "
                   f"보유자 규모 {spy.get('owners')}.",
                   f"{fmt(spy['positive'])} positive / {fmt(spy['negative'])} negative across all languages "
                   f"({spy['percent']}% positive). Owners {spy.get('owners')}.",
                   title_en=f"SteamSpy — {steam.get('name')}")
    if steam and f.get("update_url"):
        add_source(f, f"steam-news-{entry['id']}", f"Steam — {steam.get('name')} 개발사 공지",
                   f["update_url"], "official", "A",
                   f"최근 {f.get('update_kind')} '{clean(f.get('update_title'), 90)}' ({f['last_update']}).",
                   f"Latest {f.get('update_kind_en')} '{clean(f.get('update_title'), 90)}' ({f['last_update']}).",
                   title_en=f"Steam — {steam.get('name')} developer announcements")

    if not f["sources"]:
        raise CollectError("출처를 하나도 만들지 못함")

    # ── 도메인·상태
    maintenance, mnote_ko, mnote_en = maintenance_of(f)
    flags = flags_for(f, meta["domain"])
    obj_score, obj_why, obj_why_en = objective_score(f)
    ai_score, ai_why, ai_why_en = ai_review_score(f)
    rating_ko = " · ".join(f["rating_lines_ko"]) or "스토어 평점 표본 없음"
    rating_en = " · ".join(f["rating_lines_en"]) or "no store rating sample"
    price_ko = ("무료" if any(t["price"]["amount"] == 0 for t in f["tiers"]) else
                f"{f['tiers'][0]['price']['display']}")
    rating_short_ko = (f"{f['rating100']}점" if f["rating100"] is not None else "표본 없음")
    scale = f.get("scale") or srules.adjust(None, None)
    user_score = scale["final_score"]
    scale_ko = "v0.6.0 " + srules.reason_ko(scale)
    scale_en = "v0.6.0 " + srules.reason_en(scale)
    scale_brief_ko = (f" · v0.6.0 규모 보정 {scale['applied']:+.2f}(표본 {srules.fmt_count(scale['sample_count'])}) → {user_score}"
                      if scale["base_score"] is not None else "")
    scale_brief_en = (f" · v0.6.0 sample-scale adjustment {scale['applied']:+.2f} "
                      f"({srules.fmt_count(scale['sample_count'])} samples) → {user_score}"
                      if scale["base_score"] is not None else "")

    arena_short = arena["label"]
    arena_note_ko = (f"{rating_ko}. {price_ko} · 마지막 업데이트 {f['last_update'] or '미확인'}. "
                     f"「{arena_short}」 안에서 {f['developer'] or entry['name']}의 자리는 이 수치로 잡았다.")
    arena_note_en = (f"{rating_en}. {('Free' if price_ko == '무료' else f['tiers'][0]['price_display_en'])} · "
                     f"last update {f['last_update'] or 'not found'}. "
                     f"This is where {dev_en or en_name(entry)} sits in {arena['label_en']}.")

    reasons_ko = [rating_ko + ".",
                  f"{price_ko} · 마지막 업데이트 {f['last_update'] or '미확인'}"
                  + (f"({f['days_since_update']}일 전)" if f["days_since_update"] is not None else "") + ".",
                  "공개 스토어·저장소 API 값만으로 만든 1차 판정 — 확률형 상품·구독·약관은 아직 검수하지 않았다."]
    reasons_en = [rating_en + ".",
                  f"{('Free' if price_ko == '무료' else f['tiers'][0]['price_display_en'])} · last update "
                  f"{f['last_update'] or 'not found'}"
                  + (f" ({f['days_since_update']} days ago)" if f["days_since_update"] is not None else "") + ".",
                  "First-pass verdict from public store and repository APIs only — gacha, subscriptions and terms "
                  "are not reviewed yet."]

    item = {
        "schema_version": "0.4.0",
        "id": entry["id"],
        "name": entry["name"],
        "aliases": entry.get("aliases") or [],
        "domain": meta["domain"],
        "category": meta["category"],
        "arenas": [arena["id"]],
        "arena_notes": {arena["id"]: arena_note_ko},
        "genres": f["genres_ko"][:3],
        "platforms": f["platforms"],
        "developer": f["developer"] or entry["name"],
        "publisher": f["publisher"],
        "release_date": f["release_date"],
        "one_liner": f["one_liner_ko"],
        "taste_tags": [],
        "keywords": entry.get("keywords") or [],
        "assessed_at": TODAY,
        "method": "desk_research",
        "review_tier": "auto_fact",
        "maintenance_status": maintenance,
        "maintenance_note": mnote_ko,
        "sources": f["sources"],
        "flags": flags,
        "tiers": f["tiers"],
        "axes": {
            "user_rating": {
                "score": user_score, "signal": ac.signal_for(user_score),
                "signal_basis": "score",
                "evidence_grade": "A" if f["review_rows"] else "unknown",
                "confidence": ("high" if (f["sample_count"] or 0) >= 10000
                               else "medium" if (f["sample_count"] or 0) >= 1000 else "low"),
                "summary": (f"자동 수집: {rating_ko} — 표본 가중 평균 {f['rating100']}{scale_brief_ko}."
                            if f["rating100"] is not None
                            else "공개 스토어 평점 표본을 찾지 못해 사용자 축을 비웠다(판정에서 제외)."),
                # 표본이 없어 사용자 축을 비운 항목에는 규모 보정 기록을 붙이지 않는다(v0.6.0 계약).
                **({"scale_adjustment": scale} if user_score is not None else {}),
                "source_ids": [s["id"] for s in f["sources"] if s["type"] in ("store", "aggregator")],
            },
            "objective": {
                "score": obj_score, "signal": ac.signal_for(obj_score), "signal_basis": "score",
                "evidence_grade": "A/C", "confidence": "low",
                "summary": f"자동 산정 {obj_score}: " + " · ".join(obj_why) + ".",
                "source_ids": [s["id"] for s in f["sources"] if s["type"] == "official"] or
                              [s["id"] for s in f["sources"]][:1],
            },
            "ai_review": {
                "score": ai_score, "signal": ac.signal_for(ai_score), "signal_basis": "score",
                "evidence_grade": "C", "confidence": "low",
                "summary": (f"자동 추정 {ai_score}: " + " · ".join(ai_why)
                            + ". 본질 검토는 순차 심층 검수에서 이 값을 대체한다."),
                "source_ids": [s["id"] for s in f["sources"]][:1],
            },
        },
        "verdict": {
            "overall": "conditional",
            "tier_of_record": f["tiers"][0]["tier_id"],
            "signals": {"user_rating": "unknown", "objective": "unknown", "ai_review": "unknown"},
            "one_liner": "",
            "reasons": reasons_ko,
            "reasons_en": reasons_en,
            "hard_filter_blocked": False,
            "condition_notes": ([
                "자동 수집 항목 — 세부 약관·과금 함정은 순차 심층 검수에서 확정한다.",
                f"가격은 {TODAY} 스토어 표기 기준이다.",
            ] + ([f"마지막 업데이트가 {f['last_update']} 인데 12개월이 넘었다 — 완결작으로 선언된 작품이면 면제 대상이라 "
                  "심층 검수에서 maintenance_status 를 확정한다."] if (f["days_since_update"] or 0) > 365 else [])),
        },
        "review_snapshot": {
            "min_sample": 100,
            "platforms": f["review_rows"] or [{
                "platform": "other",
                "cumulative": {"metric": "stars", "value": 0, "scale": "stars5", "count": 0,
                               "window": "표본 없음", "evidence_grade": "unknown"},
                "note": "공개 API 에서 평점 표본을 찾지 못했다.",
            }],
            "sample_sufficient": (f["sample_count"] or 0) >= 100,
            "downgrade_applied": False,
            "summary": (f"자동 수집 표본: {rating_ko}. 표본 규칙(100건) "
                        f"{'충족' if (f['sample_count'] or 0) >= 100 else '미달'} — 최근 구간 해석은 검수 전이다."
                        if f["review_rows"] else "공개 API 에 평점 표본이 없어 사용자 축을 판정에서 제외했다."),
        },
        "update_profile": {
            "latest_update": f["last_update"],
            **({"latest_update_platform": f["last_update_platform"]} if f.get("last_update_platform") else {}),
            "cadence": ("unknown" if f["days_since_update"] is None else
                        "active" if f["days_since_update"] <= 180 else
                        "irregular" if f["days_since_update"] <= 365 else "dormant"),
            "entries": ([{
                "date": f["last_update"], "type": "other", "platform": f.get("last_update_platform") or "other",
                "promise_status": "not_applicable", "evidence_grade": "A",
                "source_ids": [f"steam-news-{entry['id']}"] if steam else
                              [s["id"] for s in f["sources"] if s["id"].endswith(entry["id"])][:1],
                "note": f"{f.get('update_kind') or '최근 업데이트'} '{clean(f.get('update_title'), 90)}'.",
            }] if f["last_update"] else []),
            "maintenance_quality": ("healthy" if maintenance == "active" else "unknown"),
            "assessment": (f"마지막 업데이트 {f['last_update']}({f['days_since_update']}일 전). "
                           f"자동 수집은 업데이트 시점만 보고, 과금·약관 변경과의 관계는 검수하지 않았다."
                           if f["last_update"] else
                           "최근 업데이트 기록을 찾지 못했다 — 완결·방치 여부도 검수 전이다."),
        },
        "monetization": {
            "ads": {
                "in_app_exposure": ("none" if flags["contains_ads"]["value"] == "no" else "unknown"),
                "ad_types": (["none"] if flags["contains_ads"]["value"] == "no" else ["unknown"]),
                "store_declares_ads": (True if f.get("store_ads") is True else
                                       False if f.get("store_ads") is False else None),
                "inflow_ad": {"present": flags["bait_ad"]["value"], "honesty": "not_assessed",
                              "evidence_grade": flags["bait_ad"]["evidence_grade"],
                              "source_ids": flags["bait_ad"]["source_ids"],
                              "note": flags["bait_ad"]["note"]},
            },
            "iap": {
                "present": ("no" if f["paid_one_time"] and not raw.get("play") else "unknown"),
                "random_items": flags["gacha_random_items"]["value"],
                "first_purchase_prompt": "unknown",
                "p2w": flags["p2w"]["value"],
                "required_to_progress": flags["iap_required_to_progress"]["value"],
                "evidence_grade": "B" if f["paid_one_time"] else "unknown",
                "source_ids": [s["id"] for s in f["sources"] if s["type"] == "store"],
            },
            "subscription": {"present": ("no" if flags["subscription_required"]["value"] == "no" else "unknown"),
                             "display": ("구독 상품 없음(1회 구매)" if flags["subscription_required"]["value"] == "no"
                                         else "구독 여부는 검수 전")},
            "free_play": {"value": "unknown", "evidence_grade": "unknown", "source_ids": [],
                          "note": "무과금으로 어디까지 쓸 수 있는지는 아직 확인하지 않았다."},
            "summary": (f"{price_ko}. " +
                        (f"DLC {len(steam['dlc_ids'])}건 별도. " if steam and steam["dlc_ids"] else "") +
                        "확률형 상품·구독·앱 내 구입 구조는 검수 전이다."),
        },
        "data_quality": {
            "overall_grade": "A/C",
            "unverified": ["확률형 상품·과금 함정", "구독·계정 필수 여부", "개인정보 수집·내보내기 범위",
                           "본질 완성도(AI 검토)"],
            "conflicts": [],
            "limitations": (f"자동 수집(auto_fact) — {TODAY} 공개 API 값만으로 만든 1차 기록. 세부 약관·과금 구조·문장은 "
                            f"순차 심층 검수에서 대체된다. 한 줄 소개는 스토어 표기를 다듬어 썼다."),
        },
        "score_notes": {
            "user_rating": ((f"{rating_ko} → 표본 가중 평균 {f['rating100']}. 표본 {fmt(f['sample_count'])}건. "
                             + scale_ko) if f["rating100"] is not None else scale_ko),
            "objective": f"자동 산정 {obj_score}: " + " · ".join(obj_why) + ".",
            "ai_review": f"자동 추정 {ai_score}: " + " · ".join(ai_why) + ".",
        },
    }
    if f.get("warnings"):
        item["data_quality"]["unverified"].append("일부 소스 수집 실패: " + "; ".join(f["warnings"])[:180])

    # 영어 오버레이 — 검증기가 요구하는 항목을 전부 채운다(한글 잔존 0)
    en = {
        "name": en_name(entry),
        "developer": dev_en,
        "publisher": company_en(f["publisher"], dev_en),
        "one_liner": f["one_liner_en"],
        "tagline": f["tiers"][0]["one_liner_en"],
        "arena_notes": {arena["id"]: arena_note_en},
        "genres": f["genres_en"][:3],
        "maintenance_note": mnote_en,
        "axes": {
            "user_rating": {"summary": (f"Auto-collected: {rating_en} — sample-weighted {f['rating100']}{scale_brief_en}."
                                        if f["rating100"] is not None else
                                        "No public store rating sample, so the user axis is left empty and excluded "
                                        "from the verdict.")},
            "objective": {"summary": f"Auto-estimate {obj_score}: " + " · ".join(obj_why_en) + "."},
            "ai_review": {"summary": (f"Provisional {ai_score}: " + " · ".join(ai_why_en)
                                      + ". The deep review pass replaces this value.")},
        },
        "verdict": {
            "one_liner": "",
            "reasons": reasons_en,
            "condition_notes": ([
                "Auto-collected entry — terms and monetization traps are confirmed in the sequential deep review.",
                f"Prices as listed on the store on {TODAY}.",
            ] + ([f"The last update was {f['last_update']}, more than 12 months ago — a title declared feature-complete "
                  "would be exempt, so the deep review confirms maintenance_status."]
                 if (f["days_since_update"] or 0) > 365 else [])),
        },
        "tiers": [{
            "tier_id": t["tier_id"],
            "label": t["label_en"],
            "price": {"display": t["price_display_en"]},
            "one_liner": t["one_liner_en"],
            "limits": t["limits_en"],
            "hard_filters": {filter_key: {"note": _flag_note_en(filter_key, flags[flag_key])}
                             for filter_key, flag_key in vlib.FILTER_TO_FLAG.items()},
        } for t in f["tiers"]],
        "flags": {key: {"note": _flag_note_en(key, node)} for key, node in flags.items()},
        "sources": [{"id": s["id"], "title": s["title_en"], "note": s["note_en"]} for s in f["sources"]],
        "review_snapshot": {"platforms": f["review_rows_en"] or [{
            "platform": "other",
            "cumulative": {"metric": "stars", "value": 0, "scale": "stars5", "count": 0,
                           "window": "No sample", "evidence_grade": "unknown"},
            "note": "No rating sample from public APIs.",
        }], "summary": (
            f"Auto-collected sample: {rating_en}. Sample rule (100 ratings) "
            f"{'met' if (f['sample_count'] or 0) >= 100 else 'not met'} — recent-window reading not reviewed yet."
            if f["review_rows"] else
            "No rating sample from public APIs, so the user axis is excluded from the verdict.")},
        "update_profile": {"entries": ([{
            "date": f["last_update"], "type": "other", "platform": f.get("last_update_platform") or "other",
            "promise_status": "not_applicable", "evidence_grade": "A",
            "source_ids": ([f"steam-news-{entry['id']}"] if steam else
                           [src["id"] for src in f["sources"] if src["id"].endswith(entry["id"])][:1]),
            "note": f"{f.get('update_kind_en') or 'latest update'} '{clean(f.get('update_title_en') or f.get('update_title'), 90)}'.",
        }] if f["last_update"] else []),
            "assessment": (
            f"Last update {f['last_update']} ({f['days_since_update']} days ago). Auto-collection only checks the "
            f"date; links to pricing or terms changes are not reviewed." if f["last_update"] else
            "No recent update record found — feature-complete or abandoned status not reviewed yet.")},
        "monetization": {"ads": {"inflow_ad": {"note": _flag_note_en("bait_ad", flags["bait_ad"])}},
                         "subscription": {"display": (
                             "No subscription product (one-time purchase)"
                             if flags["subscription_required"]["value"] == "no"
                             else "Subscription not reviewed yet")},
                         "free_play": {"note": "How far the free tier goes is not reviewed yet."},
                         "summary": (
            f"{('Free' if price_ko == '무료' else f['tiers'][0]['price_display_en'])}. "
            + (f"{len(steam['dlc_ids'])} DLCs sold separately. " if steam and steam["dlc_ids"] else "")
            + "Gacha, subscription and in-app purchase structure not reviewed yet.")},
        "data_quality": {"unverified": ["Gacha and monetization traps", "Subscription or account requirements",
                                        "Data collection and export scope", "Core quality (AI review)"],
                         "limitations": (
            f"Auto-collected (auto_fact) — a first-pass record built from public APIs on {TODAY}. Terms, monetization "
            f"and copy are replaced in the sequential deep review. The one-liner is condensed from the store listing.")},
        "score_notes": {
            "user_rating": ((f"{rating_en} → sample-weighted {f['rating100']}. Sample {fmt(f['sample_count'])} ratings. "
                             + scale_en) if f["rating100"] is not None else scale_en),
            "objective": f"Auto-estimate {obj_score}: " + " · ".join(obj_why_en) + ".",
            "ai_review": f"Provisional {ai_score}: " + " · ".join(ai_why_en) + ".",
        },
    }
    icon = None
    if ios:
        rec = max(ios.items(), key=lambda kv: (kv[1].get("userRatingCount") or 0))[1]
        if rec.get("artworkUrl512") or rec.get("artworkUrl100"):
            icon = {"url": rec.get("artworkUrl512") or rec.get("artworkUrl100"),
                    "provider": "Apple App Store 공식 아트워크", "crop": "center", "note": "artworkUrl512"}
    if icon is None and raw.get("play") and (raw["play"].get("en") or raw["play"].get("ko") or {}).get("image"):
        icon = {"url": (raw["play"].get("en") or raw["play"].get("ko"))["image"], "provider": "Google Play 공식 아이콘",
                "crop": "center", "note": "og:image 512px"}
    if icon is None and raw.get("github") and raw["github"].get("avatar"):
        icon = {"url": raw["github"]["avatar"],
                "provider": f"GitHub 조직 아바타 ({(raw['github']['full_name'] or '').split('/')[0]})",
                "crop": "center", "note": "공식 저장소 조직 아바타"}
    if icon is None and steam:
        icon = {"url": f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{steam['app_id']}/library_600x900.jpg",
                "provider": "Steam 공식 라이브러리 캡슐 아트", "crop": "center", "note": "300×450 원본에서 정사각 크롭",
                "fallback_url": steam.get("header_image")}

    # ── 사전(encyclopedia) — 수집한 사실만으로 기본 블록을 만든다. 대표작은 backfill 이 문장을 덮어쓴다.
    try:
        enc_ko, enc_en = auto_encyclopedia(item, f, raw, entry, arena)
        item["encyclopedia"] = enc_ko
        en["encyclopedia"] = enc_en
    except ValueError:
        pass  # 재원 3개를 채울 수 없는 항목(주로 표본 없는 GitHub 도구)은 사전 없이 둔다 — UI 폴백 뷰가 보여 준다.
    return _strip_en(item), en, icon


def _strip_en(node):
    """item 에는 한국어 원본만 남긴다(영어 조각 `*_en`·내부 표시는 오버레이로만 간다)."""
    if isinstance(node, dict):
        return {key: _strip_en(value) for key, value in node.items()
                if not key.endswith("_en") and key != "source_kinds"}
    if isinstance(node, list):
        return [_strip_en(value) for value in node]
    return node


def _flag_note_en(key: str, node: dict) -> str:
    value = node.get("value")
    if value == "unknown":
        return FLAG_NOTE_UNKNOWN_EN
    if key == "contains_ads":
        return ("The store's data-safety section declares ads." if value == "yes"
                else "No ad disclosure on the store page; no pre-launch ads.")
    if key == "forced_ad_before_use":
        return "No ads before or during use."
    if key == "bait_ad":
        return "No reports or complaints of bait-style inflow ads (absence of evidence)."
    if key == "subscription_required":
        return "One-time purchase — no subscription product."
    if key == "stale_over_12m":
        return ("No new release, patch or announcement for more than 12 months." if value == "yes"
                else "A release or announcement within the last 12 months.")
    if key == "data_export":
        return "Export and migration paths not checked."
    return FLAG_NOTE_UNKNOWN_EN


def finalize(item: dict, en: dict | None = None) -> dict:
    """하드 필터·신호·티어·대표 판정을 검증기와 같은 규칙으로 계산한다."""
    for tier in item["tiers"]:
        tier["hard_filters"] = ac.derive_hard_filters(item)
    for key, axis in item["axes"].items():
        if axis.get("score") is not None and axis.get("signal_basis", "score") == "score":
            axis["signal"] = ac.signal_for(axis["score"])
    for tier in item["tiers"]:
        tier["verdict"] = vlib.compute_verdict(item, tier)[0]
    usable = [t for t in item["tiers"] if t["verdict"] != "avoid"]
    for tier in item["tiers"]:
        tier["recommended_path"] = False
    if usable:
        cheapest = min(usable, key=lambda t: (t["price"].get("amount") if t["price"].get("amount") is not None else 0))
        cheapest["recommended_path"] = True
        record = cheapest
    else:
        record = item["tiers"][0]
    overall, why = vlib.compute_verdict(item, record)
    item["verdict"]["overall"] = overall
    item["verdict"]["tier_of_record"] = record["tier_id"]
    item["verdict"]["hard_filter_blocked"] = overall == "avoid"
    for key in ("user_rating", "objective", "ai_review"):
        item["verdict"]["signals"][key] = item["axes"][key].get("signal", "unknown")
    label_ko = {"recommend": "추천", "conditional": "조건부", "avoid": "거름"}[overall]
    label_en = {"recommend": "Recommended", "conditional": "Conditional", "avoid": "Filtered out"}[overall]
    rating_ko = " · ".join(_rating_lines(item)) or "스토어 평점 표본 없음"
    rating_en = " · ".join(_rating_lines(item, "en")) or "no store rating sample"
    last = item["update_profile"]["latest_update"]
    item["verdict"]["one_liner"] = (f"{label_ko} — {rating_ko}, "
                                   f"{'최근 업데이트 ' + last if last else '업데이트 기록 없음'}. 자동 수집 1차 판정.")
    if en is not None:
        en["verdict"]["one_liner"] = (f"{label_en} — {rating_en}, "
                                      f"{'last update ' + last if last else 'no update record'}. "
                                      f"First-pass auto assessment.")
    return item


def _rating_lines(item: dict, lang: str = "ko") -> list[str]:
    lines = []
    for row in item["review_snapshot"]["platforms"]:
        metric = row.get("cumulative") or {}
        value, count = metric.get("value"), metric.get("count")
        if not value or not count:
            continue
        platform = {"steam": "Steam", "ios": "App Store", "android": "Google Play"}.get(row.get("platform"), row.get("platform"))
        if metric.get("scale") == "percent":
            lines.append(f"{platform} {value}% 긍정({fmt(count)}건)" if lang == "ko"
                         else f"{value}% positive on {platform} ({fmt(count)})")
        else:
            lines.append(f"{platform} {value}★({fmt(count)}건)" if lang == "ko"
                         else f"{value}★ on {platform} ({fmt(count)})")
    return lines


# ─────────────────────────────────────────────────────────────── 4) 기록
def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def apply_catalog(spec: dict) -> tuple[list[str], list[str]]:
    catalog = load_json(CATALOG_PATH)
    known_cats = {c["id"] for c in catalog["categories"]}
    known_arenas = {a["id"] for a in catalog["arenas"]}
    new_cats, new_arenas = [], []
    for cat in spec["categories"]:
        if cat["id"] in known_cats:
            continue
        catalog["categories"].append({k: cat[k] for k in ("id", "domain", "label", "description")})
        new_cats.append(cat["id"])
    for arena in spec["arenas"]:
        if arena["id"] in known_arenas:
            continue
        catalog["arenas"].append({k: arena[k] for k in ("id", "domain", "category", "label", "description", "data_file")})
        new_arenas.append(arena["id"])
    featured = catalog["home"]["featured_arenas"]
    for arena_id in reversed(new_arenas):
        if arena_id not in featured:
            featured.insert(0, arena_id)
    # 카탈로그 note 는 stamp_catalog_note() 가 배치별로 한 번만 덧붙인다(여기서 덮어쓰지 않는다).
    write_json(CATALOG_PATH, catalog)
    return new_cats, new_arenas


def count_items() -> int:
    """카탈로그에 등록된 비교군 파일의 항목 수 합계."""
    catalog = load_json(CATALOG_PATH)
    total = 0
    for arena in catalog["arenas"]:
        path = DATA_DIR / arena["data_file"]
        if path.exists():
            total += len(load_json(path))
    return total


def stamp_catalog_note(spec: dict) -> None:
    """배치 요약 문장을 카탈로그 note 에 한 번만 붙인다(총 종수는 기록된 데이터에서 센다)."""
    tail = spec.get("catalog_note")
    if not tail:
        return
    catalog = load_json(CATALOG_PATH)
    marker = spec.get("catalog_note_marker") or tail.split("로 ")[0]
    base = catalog["note"].split(marker)[0].rstrip()
    catalog["note"] = base + " " + tail.format(total=count_items())
    write_json(CATALOG_PATH, catalog)


def apply_en(spec: dict, en_items: dict) -> None:
    bundle = load_json(EN_PATH)
    for cat in spec["categories"]:
        bundle.setdefault("categories", {})[cat["id"]] = {"label": cat["label_en"], "description": cat["description_en"]}
    for arena in spec["arenas"]:
        bundle.setdefault("arenas", {})[arena["id"]] = {"label": arena["label_en"], "description": arena["description_en"]}
    # 장르 사전 — 한국어 표기 → 영어(신규 항목이 쓴 표기만 채운다)
    genres = bundle.setdefault("genres", {})
    for item_id, (ko_item, en) in en_items.items():
        for ko, eng in zip(ko_item["genres"], en["genres"]):
            if ko and eng:
                genres.setdefault(ko, eng)
    bundle.setdefault("items", {}).update({iid: en for iid, (_ko, en) in en_items.items()})
    write_json(EN_PATH, bundle)


def write_arenas(spec: dict, items: dict[str, dict]) -> dict:
    """비교군 파일 기록 — 새 비교군은 새 파일, 기존 비교군은 뒤에 덧붙인다."""
    arena_by_id = {a["id"]: a for a in spec["arenas"]}
    catalog = load_json(CATALOG_PATH)
    existing_files = {a["id"]: a["data_file"] for a in catalog["arenas"]}
    written = {}
    for arena_id, rows in items.items():
        arena = arena_by_id.get(arena_id)
        data_file = existing_files.get(arena_id) or (arena or {}).get("data_file")
        if not data_file:
            raise SystemExit(f"비교군 {arena_id} 의 data_file 을 찾을 수 없음")
        path = DATA_DIR / data_file
        current = load_json(path) if path.exists() else []
        current = [row for row in current if row["id"] not in {r["id"] for r in rows}]
        merged = current + rows
        write_json(path, merged)
        written[arena_id] = (str(path.relative_to(ROOT)), len(current), len(rows))
    return written


def save_icons(pairs: list[tuple[str, dict]]) -> list[dict]:
    saved = []
    for item_id, icon in pairs:
        if not icon or not icon.get("url"):
            continue
        try:
            info = ac.save_icon(item_id, icon["url"], icon["provider"], icon.get("crop", "center"),
                                icon.get("note", ""), force=False)
            saved.append({"id": item_id, "ok": True, **{k: info.get(k) for k in ("provider", "bytes", "skipped")}})
        except Exception as exc:  # noqa: BLE001 — 아이콘 실패는 항목 기록을 막지 않는다
            if icon.get("fallback_url"):
                try:
                    info = ac.save_icon(item_id, icon["fallback_url"], "Steam 공식 헤더 아트(캡슐 404 대체)",
                                        "center", "460×215 헤더에서 정사각 크롭", force=True)
                    saved.append({"id": item_id, "ok": True, **{k: info.get(k) for k in ("provider", "bytes", "skipped")}})
                    continue
                except Exception as exc2:  # noqa: BLE001
                    exc = exc2
            saved.append({"id": item_id, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return saved


# ─────────────────────────────────────────────────────────────── main
def main() -> int:
    global CACHE_DIR
    parser = argparse.ArgumentParser(description="파로스 대량 팩트 적재(auto_fact)")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--ids", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--resolve-only", action="store_true")
    parser.add_argument("--no-icon", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="이미 적재된 항목도 다시 만들어 덮어쓴다(스크립트 수정 후 특정 id 재생성용)")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    spec = load_json(spec_path)
    CACHE_DIR = spec_path.parent / "cache"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    items = spec["items"]
    only = {part.strip() for part in args.ids.split(",") if part.strip()}
    if only:
        items = [row for row in items if row["id"] in only]
    if args.limit:
        items = items[: args.limit]

    # 0) 중복 방지 가드 — 스펙 단계에서 기존 데이터와 겹치는 항목을 먼저 걸러낸다
    dup_index = load_dup_index()
    skipped: list[dict] = []
    kept: list[dict] = []
    for entry in items:
        reason = None if args.force else duplicate_reason(entry, dup_index)
        if reason:
            skipped.append({"id": entry["id"], "reason": reason})
        else:
            kept.append(entry)
    items = kept

    catalog = load_json(CATALOG_PATH)
    bundle = load_json(EN_PATH)
    arena_by_id = {a["id"]: dict(a) for a in catalog["arenas"]}
    for arena in arena_by_id.values():
        en_meta = (bundle.get("arenas") or {}).get(arena["id"]) or {}
        arena["label_en"] = en_meta.get("label") or arena["label"]
        arena["description_en"] = en_meta.get("description") or ""
    for arena in spec["arenas"]:
        arena_by_id[arena["id"]] = arena
    meta_by_arena = {a["id"]: a for a in catalog["arenas"]}
    for arena in spec["arenas"]:
        meta_by_arena[arena["id"]] = arena
    cat_by_id = {c["id"]: c for c in catalog["categories"]}
    for cat in spec["categories"]:
        cat_by_id[cat["id"]] = cat

    started = time.perf_counter()
    print("=" * 80)
    print(f"Pharos bulk_ingest — {len(items)}종 · {TODAY} · 워커 {args.workers}")
    print(f"중복 가드: 기존 {dup_index['items']}건 인덱스(파일 {dup_index['files']} · id {len(dup_index['ids'])} · "
          f"이름 {len(dup_index['names'])} · 스토어 ID {len(dup_index['stores'])}) — "
          f"스펙 {len(items) + len(skipped)}종 중 {len(skipped)}종 스킵")
    for row in skipped:
        print(f"  ↷ 스킵 {row['id']}: {row['reason']}")
    print("=" * 80)

    # 1) 병렬 수집
    raw_by_id: dict[str, dict] = {}
    failures: list[dict] = []
    with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(collect_entry, entry): entry for entry in items}
        for job in futures.as_completed(jobs):
            entry = jobs[job]
            try:
                raw_by_id[entry["id"]] = job.result()
                src = " + ".join(k for k in ("steam", "ios", "play", "github") if k in raw_by_id[entry["id"]])
                print(f"  ✓ {entry['id']:<38} {src}")
            except Exception as exc:  # noqa: BLE001
                failures.append({"id": entry["id"], "error": f"{type(exc).__name__}: {exc}"})
                print(f"  × {entry['id']:<38} {exc}")

    # 1-1) 수집으로 확정된 스토어 ID 로 한 번 더 가드(이름은 달라도 같은 앱·게임이면 스킵)
    for entry in list(items):
        reason = None if args.force else duplicate_reason(entry, dup_index, raw_by_id.get(entry["id"]))
        if not reason:
            continue
        skipped.append({"id": entry["id"], "reason": reason})
        items.remove(entry)
        raw_by_id.pop(entry["id"], None)
        print(f"  ↷ 스킵 {entry['id']}: {reason}")
    collect_s = round(time.perf_counter() - started, 2)

    # 2) 항목 조립
    built: dict[str, tuple[dict, dict, dict]] = {}
    for entry in items:
        raw = raw_by_id.get(entry["id"])
        if not raw:
            continue
        arena_meta = arena_by_id.get(entry["arena"])
        if not arena_meta:
            failures.append({"id": entry["id"], "error": f"스펙에 없는 비교군 {entry['arena']}"})
            continue
        meta = {"domain": arena_meta["domain"], "category": arena_meta["category"]}
        try:
            ko, en, icon = build_item(entry, arena_meta, meta, raw)
            ko = finalize(ko, en)
            built[entry["id"]] = (ko, en, icon)
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": entry["id"], "error": f"build: {type(exc).__name__}: {exc}"})
            print(f"  × build {entry['id']}: {exc}")
    build_s = round(time.perf_counter() - started - collect_s, 2)

    # 3) 아이콘
    icons: list[dict] = []
    if not args.no_icon:
        icons = save_icons([(iid, built[iid][2]) for iid in built])
        for row in icons:
            if row.get("ok") and not row.get("skipped"):
                built[row["id"]][0]["icon"] = f"assets/icons/{row['id']}.webp"
            elif row.get("ok"):
                if (ROOT / "web" / "assets" / "icons" / f"{row['id']}.webp").exists():
                    built[row["id"]][0]["icon"] = f"assets/icons/{row['id']}.webp"
            else:
                print(f"  ! 아이콘 실패 {row['id']}: {row.get('error')}")
    icon_s = round(time.perf_counter() - started - collect_s - build_s, 2)

    # 4) 기록
    written = {}
    if not args.no_write and built:
        by_arena: dict[str, list[dict]] = {}
        for entry in items:
            if entry["id"] in built:
                by_arena.setdefault(entry["arena"], []).append(built[entry["id"]][0])
        new_cats, new_arenas = apply_catalog(spec)
        apply_en(spec, {iid: (built[iid][0], built[iid][1]) for iid in built})
        written = write_arenas(spec, by_arena)
        stamp_catalog_note(spec)
        print(f"\n  카탈로그: 신규 대분류 {len(new_cats)} · 신규 비교군 {len(new_arenas)}")
        for arena_id, (path, before, added) in written.items():
            print(f"  → {path}: {before} + {added}")

    total_s = round(time.perf_counter() - started, 2)
    ok = len(built)
    summary = {
        "batch": spec.get("batch"),
        "date": TODAY,
        "items_in_spec": len(items) + len(skipped),
        "items_built": ok,
        "failed": len(failures),
        "failures": failures,
        "skipped_count": len(skipped),
        "skipped": skipped,
        "timing": {"collect_s": collect_s, "build_s": build_s, "icons_s": icon_s, "total_s": total_s,
                   "seconds_per_item": round(total_s / max(ok, 1), 2)},
        "http_requests": len([r for r in HTTP_LOG if r.get("status") != "cache"]),
        "http_cache_hits": len([r for r in HTTP_LOG if r.get("status") == "cache"]),
        "icons": {"saved": sum(1 for r in icons if r.get("ok") and not r.get("skipped")),
                  "skipped": sum(1 for r in icons if r.get("skipped")),
                  "failed": [r for r in icons if not r.get("ok")]},
        "encyclopedia": {
            "items": sum(1 for _iid, (ko, _en, _ic) in built.items() if ko.get("encyclopedia")),
            "facts": sum(len((ko.get("encyclopedia") or {}).get("key_facts") or [])
                         for ko, _en, _ic in built.values()),
            "highlights": sum(len((ko.get("encyclopedia") or {}).get("highlights") or [])
                              for ko, _en, _ic in built.values()),
        },
        "arenas": written,
        "verdicts": {},
    }
    for item_id, (ko, _en, _icon) in built.items():
        summary["verdicts"][item_id] = {"verdict": ko["verdict"]["overall"],
                                        "score": round(vlib.weighted_score(ko, next(
                                            t for t in ko["tiers"] if t["tier_id"] == ko["verdict"]["tier_of_record"])), 2)
                                        if True else None}
    log_path = spec_path.parent / f"bulk-{TODAY}-run.json"
    write_json(log_path, summary)

    print("\n" + "=" * 80)
    print(f"결과: {ok}/{len(items)}종 생성 · 실패 {len(failures)} · 중복 스킵 {len(skipped)} · 총 {total_s}s "
          f"(수집 {collect_s}s · 조립 {build_s}s · 아이콘 {icon_s}s · 항목당 {summary['timing']['seconds_per_item']}s)")
    print(f"HTTP {summary['http_requests']}회 · 캐시 {summary['http_cache_hits']}회 · "
          f"아이콘 저장 {summary['icons']['saved']}건 · "
          f"사전 {summary['encyclopedia']['items']}/{ok}종(제원 {summary['encyclopedia']['facts']})")
    print(f"로그: {Path(os.path.relpath(log_path, ROOT.parent.parent))}")
    print("=" * 80)
    if failures:
        for row in failures[:10]:
            print(f"  × {row['id']}: {row['error']}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
