#!/usr/bin/env python3
"""파로스 무료 공개 API 반자동 수집 파이프라인 — auto_collect.py (v1.0)

이름·스토어 ID·저장소만 주면 **사실(Fact) 약 70% + 공식 아이콘 + 스키마 v0.4.0 초안 JSON**을
자동으로 만든다. 사람(배치 리뷰어)은 AI 검토·과금 구조·한 줄 평 같은 나머지 30%만 채운다.

지원 소스 (모두 무료 공개 API, API 키 불필요)
  1) Apple App Store — itunes.apple.com/lookup (한국·미국 스토어)
     앱명·개발사·가격·평점·평가 수·최근 버전/릴리스 날짜·번들 ID·스토어 URL·공식 아트워크(512px),
     그리고 apps.apple.com 페이지의 '앱 내 구입' 항목(이름·가격)까지.
  2) Steam — store.steampowered.com/api/appdetails + 상점 페이지 평가 요약 + ISteamNews + SteamSpy
     게임명·개발사·가격(KRW/USD)·무료 여부·출시일·누적/최근 30일 긍정률·표본 수·헤더/캡슐 아트·
     DLC 목록·개발사 공지(마지막 업데이트 근거).
  3) GitHub — api.github.com/repos/{owner}/{repo} + /releases/latest (+ /license)
     라이선스·최근 릴리스·최근 푸시·스타 수·아카이브 여부·오픈소스 여부.
  4) Google Play (보조) — play.google.com 페이지의 JSON-LD(평점·평가 수)·공식 아이콘.

만드는 것
  · `drafts/{id}.draft.json`  — item.schema.json v0.4.0 을 만족하는 초안(스키마 검사 PASS)
  · `drafts/{id}.review.json` — 남은 TODO 목록 + 수집 로그(요청 수·소요 시간)
  · `web/assets/icons/{id}.webp` (192×192) + `web/assets/icons/manifest.json` 갱신
  · `drafts/logs/{날짜}-auto-collect.json` — 배치 실행 기록(항목별 소요 시간·커버리지)

TODO 표시 규칙
  사람이 판단해야 하는 값은 문자열 앞에 `TODO(리뷰):` 를 붙인다. 커버리지(%)는 전체 문자열
  리프 중 TODO 가 아닌 비율로 계산한다(리뷰어가 채워야 할 몫 = 100 − 커버리지).

사용
  python3 projects/pharos/scripts/auto_collect.py --spec projects/pharos/drafts/spec-2026-11-25.json
  python3 projects/pharos/scripts/auto_collect.py --id celeste --name Celeste \
      --domain game --category action-indie --arena metroidvania-platformer --steam-id 504230
  python3 projects/pharos/scripts/auto_collect.py --spec ... --no-icon --force   # 아이콘 건너뛰기/덮어쓰기

스펙 파일(JSON) 형식
  {"items": [
     {"id": "celeste", "name": "Celeste", "domain": "game", "category": "action-indie",
      "arena": "metroidvania-platformer", "steam_id": 504230,
      "ios_bundle": "com.example.app",     # 또는 "ios_id": 123456789, "ios_search": "Name"
      "github_repo": "owner/repo", "play_package": "com.example",
      "aliases": ["셀레스트"], "keywords": ["Celeste 1"],
      "platforms": ["console"],            # API 로 알 수 없는 플랫폼 보충
      "icon_url": "...", "icon_crop": "center|top|bottom|left|right", "icon_provider": "..."}
  ]}
  필수: id, name, domain, category, arena (또는 arenas 배열) · 소스는 1개 이상.

종료 코드 0 = 모든 초안 생성·스키마 검증 통과, 1 = 일부 실패.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]            # projects/pharos
SCHEMA_DIR = ROOT / "schema"
sys.path.insert(0, str(SCHEMA_DIR))

import validate as vlib  # noqa: E402  — 판정 규칙·가중 점수를 검증기와 한 곳에서 쓴다

DRAFTS_DIR = ROOT / "drafts"
ICON_DIR = ROOT / "web" / "assets" / "icons"
MANIFEST = ICON_DIR / "manifest.json"
SCHEMA_PATH = SCHEMA_DIR / "item.schema.json"
ICON_SIZE = 192
TODAY = date.today().isoformat()
TODO = "TODO(리뷰): "
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
STORE_UA = {**UA, "Accept-Language": "en-US,en;q=0.9"}

# 요청 로그 — 소요 시간·건수를 배치 리포트에 그대로 남긴다.
HTTP_LOG: list[dict] = []

# 개발사 공지 중 '업데이트'로 볼 수 있는 제목 — 상품·굿즈·행사 공지는 업데이트 근거가 아니다.
UPDATE_RE = re.compile(r"(patch|hotfix|changelog|change log|update now|now live|version\s*\d|ver\.?\s*\d|업데이트|패치|핫픽스)", re.I)

KR_MONTHS = {m: i for i, m in enumerate(
    ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"], start=1)}


class CollectError(Exception):
    """소스 수집 실패(로그를 남기고 넘어간다)."""


# ─────────────────────────────────────────────────────────────────── HTTP
def http(url: str, headers: dict | None = None, timeout: int = 40, retries: int = 2,
         label: str = "") -> tuple[bytes, dict]:
    last: Exception | None = None
    for attempt in range(retries + 1):
        started = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as res:
                raw = res.read()
                if res.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
                info = {
                    "label": label or "http",
                    "url": url,
                    "status": res.status,
                    "bytes": len(raw),
                    "ms": round((time.perf_counter() - started) * 1000),
                }
                HTTP_LOG.append(info)
                return raw, info
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        except Exception as exc:  # noqa: BLE001 — 네트워크 오류는 재시도 후 실패로 남긴다
            last = exc
            if attempt < retries:
                time.sleep(1.0)
                continue
            break
    HTTP_LOG.append({"label": label or "http", "url": url, "status": "error", "bytes": 0, "ms": 0,
                     "error": f"{type(last).__name__}: {last}"})
    raise CollectError(f"{label or 'http'} 실패 — {type(last).__name__}: {last} ({url})")


def get_json(url: str, headers: dict | None = None, label: str = "") -> dict:
    raw, _info = http(url, headers=headers, label=label)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CollectError(f"{label or 'json'} 응답이 JSON 이 아님 — {exc}") from exc


def get_text(url: str, headers: dict | None = None, label: str = "") -> str:
    raw, _info = http(url, headers=headers, label=label)
    return raw.decode("utf-8", "ignore")


# ─────────────────────────────────────────────────────────── 공통 변환 도우미
def fact(value: str, grade: str, source_ids: list[str], note: str, verification: str | None = None) -> dict:
    node = {"value": value, "evidence_grade": grade, "source_ids": source_ids, "note": note}
    if verification:
        node["verification"] = verification
    return node


def parse_money(text: str) -> tuple[float | None, str | None]:
    """'₩ 16,500' · '$7.99' · '￦11,500' · '무료' → (금액, 통화)."""
    if not text:
        return None, None
    text = text.replace("\u00a0", " ").strip()
    symbol = None
    for sym, cur in (("₩", "KRW"), ("￦", "KRW"), ("$", "USD"), ("€", "EUR"), ("£", "GBP"), ("¥", "JPY")):
        if sym in text:
            symbol = cur
            break
    digits = re.sub(r"[^\d.,]", "", text)
    if not digits:
        return None, symbol
    digits = digits.replace(",", "")
    try:
        return float(digits), symbol
    except ValueError:
        return None, symbol


def parse_release(text: str) -> str | None:
    """Steam '2017년 2월 24일' / '24 Feb, 2017' → '2017-02-24'."""
    if not text:
        return None
    m = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", text)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*,?\s+(\d{4})", text)
    if m:
        months = {name: idx for idx, name in enumerate(
            ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
        mon = months.get(m.group(2).lower())
        if mon:
            return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(1)):02d}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return m.group(0)
    return None


def days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        return (date.fromisoformat(iso) - date.fromisoformat(TODAY)).days * -1
    except ValueError:
        return None


def signal_for(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= vlib.THRESHOLDS["green_min"]:
        return "green"
    if score >= vlib.THRESHOLDS["yellow_min"]:
        return "yellow"
    return "red"


def fmt(n: float | int | None) -> str:
    if n is None:
        return "—"
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    return f"{n:,}" if isinstance(n, int) else f"{n:,.2f}".rstrip("0").rstrip(".")


# ─────────────────────────────────────────────────────────── Apple App Store
def itunes_lookup(params: dict, label: str) -> list[dict]:
    url = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(params)
    data = get_json(url, label=label)
    return data.get("results") or []


def itunes_search(term: str, country: str, entity: str, limit: int = 8) -> list[dict]:
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": term, "country": country, "entity": entity, "limit": limit})
    data = get_json(url, label=f"itunes-search:{term}")
    return data.get("results") or []


def _name_key(text: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]", "", (text or "").lower())


def parse_app_store_iap(html: str, lang: str = "ko") -> dict | None:
    """apps.apple.com 페이지의 '앱 내 구입' 항목 — (가능 여부, 항목 목록)."""
    marker = "앱 내 구입</dt>" if lang == "ko" else "In-App Purchases</dt>"
    idx = html.find(marker)
    if idx < 0:
        return None
    seg = html[idx:idx + 4000]
    available = ("사용 가능" in seg) or ("\nYes" in seg) or (">Yes" in seg)
    items = re.findall(r"<span>([^<]{1,60})</span>\s*<span>([^<]{1,20})</span>", seg)
    return {"available": available, "items": items[:14]}


def collect_ios(spec: dict) -> dict:
    """App Store 사실 수집 — 한국·미국 스토어 lookup + 앱 내 구입 페이지."""
    out: dict = {"kind": "ios", "countries": {}, "warnings": []}
    entity = spec.get("ios_entity", "software")
    countries = spec.get("ios_countries") or ["kr", "us"]

    target = None
    if spec.get("ios_id"):
        for country in countries:
            rows = itunes_lookup({"id": spec["ios_id"], "country": country}, f"itunes-lookup:{country}")
            if rows:
                out["countries"][country] = rows[0]
    elif spec.get("ios_bundle"):
        for country in countries:
            rows = itunes_lookup({"bundleId": spec["ios_bundle"], "country": country},
                                 f"itunes-lookup:{country}")
            match = next((r for r in rows if r.get("bundleId") == spec["ios_bundle"]), None)
            if match:
                out["countries"][country] = match
    elif spec.get("ios_search"):
        for country in countries:
            rows = itunes_search(spec["ios_search"], country, entity)
            want = _name_key(spec.get("name") or spec["ios_search"])
            match = next((r for r in rows if _name_key(r.get("trackName", "")) == want), None)
            if match is None:
                close = [r for r in rows if want and want in _name_key(r.get("trackName", ""))]
                match = close[0] if len(close) == 1 else None
            if match:
                out["countries"][country] = match
        if not out["countries"]:
            raise CollectError(f"App Store 검색 결과에서 '{spec.get('name')}' 을(를) 확정하지 못함 — "
                               f"ios_bundle·ios_id 를 직접 지정하세요")
    else:
        raise CollectError("ios 소스에는 ios_id·ios_bundle·ios_search 중 하나가 필요함")

    if not out["countries"]:
        raise CollectError(f"App Store 에서 {spec.get('ios_bundle') or spec.get('ios_id')} 를 찾지 못함")

    primary_country = "kr" if "kr" in out["countries"] else sorted(out["countries"])[0]
    primary = out["countries"][primary_country]
    out.update({
        "primary": primary,
        "primary_country": primary_country,
        "track_id": primary.get("trackId"),
        "name": primary.get("trackName"),
        "seller": primary.get("sellerName"),
        "artwork": primary.get("artworkUrl512") or primary.get("artworkUrl100"),
        "url": primary.get("trackViewUrl"),
        "genres": primary.get("genres") or [],
        "bundle": primary.get("bundleId"),
        "version_date": (primary.get("currentVersionReleaseDate") or "")[:10] or None,
        "release_date": (primary.get("releaseDate") or "")[:10] or None,
        "min_os": primary.get("minimumOsVersion"),
        "available_in_kr": "kr" in out["countries"],
    })

    iap = None
    for country in ([primary_country] + [c for c in out["countries"] if c != primary_country]):
        try:
            html = get_text(f"https://apps.apple.com/{country}/app/id{out['track_id']}",
                            headers=STORE_UA, label=f"appstore-page:{country}")
        except CollectError as exc:
            out["warnings"].append(str(exc))
            continue
        parsed = parse_app_store_iap(html, "ko" if country == "kr" else "en")
        if parsed:
            iap = {**parsed, "country": country}
            break
    out["iap"] = iap
    return out


# ─────────────────────────────────────────────────────────────────── Steam
def steam_appdetails(app_id: int, cc: str, lang: str) -> dict | None:
    url = (f"https://store.steampowered.com/api/appdetails?appids={app_id}"
           f"&cc={cc}&l={lang}&filters=basic,price_overview,genres,categories,platforms,"
           f"release_date,developers,publishers,dlc,short_description,website,metacritic,"
           f"recommendations,screenshots,header_image,capsule_image")
    data = get_json(url, label=f"steam-appdetails:{app_id}:{cc}")
    node = data.get(str(app_id)) or {}
    return node.get("data") if node.get("success") else None


def steam_review_rows(app_id: int) -> list[dict]:
    """상점 페이지의 평가 요약(최근 30일 + 언어별) — data-tooltip-html 이 가장 정확하다."""
    html = get_text(f"https://store.steampowered.com/app/{app_id}/?cc=kr&l=english",
                    headers=STORE_UA, label=f"steam-reviews:{app_id}")
    rows = []
    for block in re.findall(r'<a class="user_reviews_summary_row".*?</a>', html, re.S):
        label = re.search(r'<div class="subtitle column[^"]*">\s*([^<]+?)\s*</div>', block)
        tip = re.search(r'data-tooltip-html="([^"]+)"', block)
        if not tip:
            continue
        text = tip.group(1)
        m = re.search(r"(\d+)% of the ([\d,]+) user reviews in the last 30 days", text)
        if m:
            rows.append({"kind": "recent", "percent": int(m.group(1)),
                         "count": int(m.group(2).replace(",", "")), "window": "최근 30일",
                         "label": (label.group(1) if label else "Recent Reviews").strip()})
            continue
        m = re.search(r"(\d+)% of the ([\d,]+) user reviews (?:in your language|for this game)", text)
        if m:
            rows.append({"kind": "language", "percent": int(m.group(1)),
                         "count": int(m.group(2).replace(",", "")),
                         "window": "전체(영어 리뷰)", "language": "english",
                         "label": (label.group(1) if label else "English Reviews").strip()})
    return rows


def steam_spy(app_id: int) -> dict | None:
    try:
        data = get_json(f"https://steamspy.com/api.php?request=appdetails&appid={app_id}",
                        label=f"steamspy:{app_id}")
    except CollectError:
        return None
    if not data or not data.get("positive"):
        return None
    pos, neg = int(data.get("positive", 0)), int(data.get("negative", 0))
    total = pos + neg
    return {
        "positive": pos,
        "negative": neg,
        "total": total,
        "percent": round(pos * 100 / total, 1) if total else None,
        "owners": data.get("owners"),
    }


def steam_news(app_id: int) -> list[dict]:
    data = get_json(
        f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={app_id}&count=100&maxlength=1",
        label=f"steam-news:{app_id}")
    items = []
    for row in (data.get("appnews") or {}).get("newsitems") or []:
        items.append({
            "date": datetime.fromtimestamp(row["date"], timezone.utc).date().isoformat(),
            "feed": row.get("feedname"),
            "title": row.get("title"),
            "url": row.get("url"),
        })
    return items


def collect_steam(spec: dict) -> dict:
    app_id = int(spec["steam_id"])
    kr = steam_appdetails(app_id, "kr", "korean")
    us = steam_appdetails(app_id, "us", "english")
    if not kr and not us:
        raise CollectError(f"Steam appdetails 에서 appid {app_id} 를 찾지 못함")
    primary = kr or us
    name_en = (us or {}).get("name") or primary.get("name")
    out = {
        "kind": "steam",
        "app_id": app_id,
        "name": name_en,
        "name_kr": (kr or {}).get("name"),
        "developers": primary.get("developers") or [],
        "publishers": primary.get("publishers") or [],
        "release_date": parse_release((primary.get("release_date") or {}).get("date", "")),
        "release_date_raw": (primary.get("release_date") or {}).get("date"),
        "is_free": bool(primary.get("is_free")),
        "genres": [g.get("description") for g in primary.get("genres") or []],
        "categories": [c.get("description") for c in primary.get("categories") or []],
        "platforms": [k for k, v in (primary.get("platforms") or {}).items() if v],
        "website": primary.get("website"),
        "metacritic": (primary.get("metacritic") or {}).get("score"),
        "recommendations": (primary.get("recommendations") or {}).get("total"),
        "short_description": primary.get("short_description"),
        "header_image": primary.get("header_image"),
        "price_kr": primary.get("price_overview"),
        "price_us": (us or {}).get("price_overview"),
        "dlc_ids": primary.get("dlc") or [],
        "reviews": [],
        "warnings": [],
        "url": f"https://store.steampowered.com/app/{app_id}/",
    }
    try:
        out["reviews"] = steam_review_rows(app_id)
    except CollectError as exc:
        out["warnings"].append(str(exc))
    out["steamspy"] = steam_spy(app_id)
    try:
        out["news"] = steam_news(app_id)
    except CollectError as exc:
        out["warnings"].append(str(exc))
        out["news"] = []

    dlc = []
    for dlc_id in out["dlc_ids"][:6]:
        try:
            node = steam_appdetails(int(dlc_id), "kr", "korean")
        except CollectError:
            node = None
        if node:
            price = node.get("price_overview") or {}
            dlc.append({
                "app_id": int(dlc_id),
                "name": node.get("name"),
                "is_free": bool(node.get("is_free")),
                "price": price.get("initial"),
                "currency": price.get("currency"),
            })
    out["dlc"] = dlc
    announcements = [n for n in out.get("news") or [] if n.get("feed") == "steam_community_announcements"]
    out["announcements"] = announcements[:8]
    out["update_posts"] = sorted(
        [n for n in announcements if UPDATE_RE.search(n.get("title") or "")],
        key=lambda n: n["date"], reverse=True)[:6]
    return out


# ────────────────────────────────────────────────────────────────── GitHub
def gh_api(path: str) -> dict:
    """`gh`(로그인된 CLI)가 있으면 그것을, 없으면 공개 API(시간당 60회)를 쓴다."""
    if shutil.which("gh"):
        started = time.perf_counter()
        proc = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=60)
        HTTP_LOG.append({"label": f"gh:{path}", "url": f"https://api.github.com/{path}",
                         "status": 200 if proc.returncode == 0 else "error",
                         "bytes": len(proc.stdout), "ms": round((time.perf_counter() - started) * 1000)})
        if proc.returncode == 0:
            return json.loads(proc.stdout)
    data = get_json(f"https://api.github.com/{path}", headers={"Accept": "application/vnd.github+json"},
                    label=f"github:{path}")
    return data


def collect_github(spec: dict) -> dict:
    repo = spec["github_repo"].strip().strip("/")
    out: dict = {"kind": "github", "repo": repo, "warnings": []}
    data = gh_api(f"repos/{repo}")
    out.update({
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "license": ((data.get("license") or {}).get("spdx_id")),
        "license_name": ((data.get("license") or {}).get("name")),
        "archived": bool(data.get("archived")),
        "pushed_at": (data.get("pushed_at") or "")[:10] or None,
        "created_at": (data.get("created_at") or "")[:10] or None,
        "homepage": data.get("homepage"),
        "topics": data.get("topics") or [],
        "avatar": ((data.get("owner") or {}).get("avatar_url")),
        "url": data.get("html_url"),
    })
    if not out["license"] or out["license"] == "NOASSERTION":
        try:
            lic = gh_api(f"repos/{repo}/license")
            out["license"] = (lic.get("license") or {}).get("spdx_id") or out["license"]
            out["license_name"] = (lic.get("license") or {}).get("name") or out["license_name"]
        except CollectError as exc:
            out["warnings"].append(str(exc))
    try:
        rel = gh_api(f"repos/{repo}/releases/latest")
        out["latest_release"] = {
            "tag": rel.get("tag_name"),
            "name": rel.get("name"),
            "published_at": (rel.get("published_at") or "")[:10] or None,
            "url": rel.get("html_url"),
        }
    except CollectError:
        out["latest_release"] = None
    return out


# ────────────────────────────────────────────────────────────── Google Play
def collect_play(spec: dict) -> dict:
    package = spec["play_package"]
    html = get_text(f"https://play.google.com/store/apps/details?id={package}&hl=en&gl=US",
                    headers=STORE_UA, label=f"play:{package}")
    title = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    image = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    ld = re.search(r'"aggregateRating":\{([^}]+)\}', html)
    rating = count = None
    developer = None
    if ld:
        rv = re.search(r'"ratingValue":"?([\d.]+)', ld.group(1))
        rc = re.search(r'"ratingCount":"?(\d+)', ld.group(1))
        rating = float(rv.group(1)) if rv else None
        count = int(rc.group(1)) if rc else None
    dev = re.search(r'"author":\{"@type":"Person","name":"([^"]+)"', html)
    if dev:
        developer = dev.group(1)
    price = re.search(r'"offers":\[\{[^}]*"price":"([\d.]+)"', html)
    return {
        "kind": "play",
        "package": package,
        "name": re.sub(r"\s*-\s*Apps on Google Play$", "", title.group(1)) if title else package,
        "developer": developer,
        "rating": rating,
        "count": count,
        "price": float(price.group(1)) if price else None,
        "image": image.group(1) if image else None,
        "url": f"https://play.google.com/store/apps/details?id={package}",
    }


# ─────────────────────────────────────────────────────────────────── 아이콘
def fetch_image_bytes(url: str) -> tuple[bytes, list[int]]:
    raw, _info = http(url, label="icon-download")
    img = Image.open(io.BytesIO(raw))
    img.load()
    return raw, list(img.size)


def square_crop(img: Image.Image, mode: str = "center") -> Image.Image:
    """정사각 크롭 — mode 로 어느 쪽을 남길지 고른다(top/bottom/left/right/center)."""
    w, h = img.size
    side = min(w, h)
    if mode == "top":
        box = (0, 0, side, side)
    elif mode == "bottom":
        box = (0, h - side, side, h)
    elif mode == "left":
        box = (0, 0, side, side)
    elif mode == "right":
        box = (w - side, 0, w, side)
    else:
        left, top = (w - side) // 2, (h - side) // 2
        box = (left, top, left + side, top + side)
    return img.crop(box)


def save_icon(item_id: str, url: str, provider: str, crop: str = "center",
              note: str = "", force: bool = False) -> dict:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    out = ICON_DIR / f"{item_id}.webp"
    if out.exists() and not force:
        existing = {}
        if MANIFEST.exists():
            for row in json.loads(MANIFEST.read_text(encoding="utf-8")).get("items", []):
                if row.get("id") == item_id:
                    existing = row
        return {"id": item_id, "file": f"assets/icons/{out.name}", "skipped": True,
                "provider": existing.get("provider", provider), "source_url": existing.get("source_url", url)}

    raw, size = fetch_image_bytes(url)
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    img = square_crop(img, crop).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    img.save(out, "WEBP", quality=90, method=6)
    record = {
        "id": item_id,
        "provider": provider,
        "source_url": url,
        "file": f"assets/icons/{out.name}",
        "bytes": out.stat().st_size,
        "source_size": size,
        "crop": crop,
        "note": note,
        "retrieved_at": TODAY,
    }
    manifest = {"items": []}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["items"] = [row for row in manifest.get("items", []) if row.get("id") != item_id]
    manifest.setdefault("note", "파로스 카드·상세·비교표에 쓰는 공식 아이콘 목록. "
                               "fetch_icons.py · auto_collect.py 가 기록한다.")
    manifest.setdefault("size", [ICON_SIZE, ICON_SIZE])
    manifest.setdefault("format", "webp/q90")
    manifest["items"].append(record)
    manifest["items"].sort(key=lambda row: row["id"])
    manifest["count"] = len(manifest["items"])
    manifest["retrieved_at"] = TODAY
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**record, "skipped": False}


def choose_icon(spec: dict, sources: dict) -> dict | None:
    """아이콘 우선순위 — 지정 URL → iOS 아트워크 → Play 아이콘 → GitHub 조직 아바타 → Steam 아트."""
    if spec.get("icon_url"):
        return {"url": spec["icon_url"], "provider": spec.get("icon_provider", "지정 URL"),
                "crop": spec.get("icon_crop", "center"), "note": spec.get("icon_note", "")}
    ios = sources.get("ios")
    if ios and ios.get("artwork"):
        return {"url": ios["artwork"], "provider": f"Apple App Store 공식 아트워크 ({ios['primary_country']})",
                "crop": spec.get("icon_crop", "center"), "note": "artworkUrl512"}
    play = sources.get("play")
    if play and play.get("image"):
        return {"url": play["image"], "provider": "Google Play 공식 아이콘",
                "crop": spec.get("icon_crop", "center"), "note": "og:image 512px"}
    gh = sources.get("github")
    if gh and gh.get("avatar"):
        return {"url": gh["avatar"], "provider": f"GitHub 조직 아바타 ({gh['full_name'].split('/')[0]})",
                "crop": spec.get("icon_crop", "center"), "note": "공식 저장소 조직 아바타"}
    steam = sources.get("steam")
    if steam:
        if spec.get("icon_url"):
            return None
        url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{steam['app_id']}/library_600x900.jpg"
        return {"url": url, "provider": "Steam 공식 라이브러리 캡슐 아트",
                "crop": spec.get("icon_crop", "center"), "note": "300×450 원본에서 정사각 크롭"}
    return None


# ─────────────────────────────────────────────────────── 초안(item) 조립
def derive_hard_filters(item: dict) -> dict:
    """flags 원자료 → 티어 하드 필터(검증기와 같은 규칙). 완결작 면제까지 반영한다."""
    out = {}
    for key, flag_key in vlib.FILTER_TO_FLAG.items():
        node = (item["flags"].get(flag_key) or {})
        value = node.get("value", "unknown")
        if key == "stale_over_12m" and value == "yes" and item.get("maintenance_status") == "feature_complete":
            status = "exempt"
        else:
            status = {"yes": "fail", "no": "pass"}.get(value, "unknown")
        out[key] = {
            "status": status,
            "evidence_grade": node.get("evidence_grade", "unknown"),
            "note": node.get("note", "미확인"),
            "source_ids": node.get("source_ids", []),
        }
    return out


def finalize_item(item: dict) -> dict:
    """하드 필터·축 신호·티어 판정·대표 판정을 계산 규칙으로 다시 맞춘다."""
    for tier in item["tiers"]:
        recorded = {k: v.get("impact") for k, v in (tier.get("hard_filters") or {}).items()}
        filters = derive_hard_filters(item)
        for key, impact in recorded.items():
            if impact and key in filters:
                filters[key]["impact"] = impact
        tier["hard_filters"] = filters

    for key, axis in item["axes"].items():
        if axis.get("score") is not None and axis.get("signal_basis", "score") == "score":
            axis["signal"] = signal_for(axis["score"])

    for tier in item["tiers"]:
        verdict, _why = vlib.compute_verdict(item, tier)
        tier["verdict"] = verdict

    usable = [t for t in item["tiers"] if t["verdict"] != "avoid"]
    if usable and not any(t.get("recommended_path") for t in item["tiers"]):
        cheapest = min(usable, key=lambda t: (t["price"].get("amount") or 0))
        for tier in item["tiers"]:
            tier["recommended_path"] = tier is cheapest

    record = next((t for t in item["tiers"] if t.get("recommended_path")), item["tiers"][0])
    overall, _why = vlib.compute_verdict(item, record)
    item["verdict"]["overall"] = overall
    item["verdict"]["tier_of_record"] = record["tier_id"]
    item["verdict"]["hard_filter_blocked"] = overall == "avoid"
    for key in ("user_rating", "objective", "ai_review"):
        axis = item["axes"].get(key) or {}
        item["verdict"]["signals"][key] = axis.get("signal", "unknown")
    return item


def build_draft(spec: dict, sources: dict, started: float) -> tuple[dict, dict]:
    """수집한 사실 → 스키마 v0.4.0 초안 + 리뷰 체크리스트."""
    ios, steam, gh, play = sources.get("ios"), sources.get("steam"), sources.get("github"), sources.get("play")
    arenas = spec.get("arenas") or [spec["arena"]]
    item_id = spec["id"]
    todos: list[dict] = []

    def todo(path: str, hint: str, suggestion: str | None = None) -> None:
        todos.append({"field": path, "hint": hint, "suggestion": suggestion})

    # ── 기본 신원 정보
    name = spec.get("name") or (ios or {}).get("name") or (steam or {}).get("name") or (gh or {}).get("full_name")
    developer = spec.get("developer")
    if not developer:
        if steam and steam["developers"]:
            developer = steam["developers"][0]
        elif ios and ios.get("seller"):
            developer = ios["seller"]
        elif play and play.get("developer"):
            developer = play["developer"]
        elif gh:
            developer = gh["full_name"].split("/")[0]
    publisher = spec.get("publisher")
    if publisher is None:
        if steam and steam["publishers"]:
            publisher = steam["publishers"][0]
        elif ios:
            publisher = ios.get("seller")

    release_date = spec.get("release_date") or (steam or {}).get("release_date") or (ios or {}).get("release_date")

    platforms: list[str] = []
    if steam:
        for p in steam["platforms"]:
            platforms.append({"windows": "windows", "mac": "macos", "linux": "linux"}.get(p, p))
        platforms.insert(0, "steam")
    if ios:
        platforms.append("ios")
    if play:
        platforms.append("android")
    for p in spec.get("platforms") or []:
        if p not in platforms:
            platforms.append(p)
    if not platforms:
        platforms = ["web"]
        todo("platforms", "소스에서 플랫폼을 알 수 없음 — 실제 배포 플랫폼을 적으세요")

    genres = spec.get("genres")
    if not genres:
        genres = []
        if steam:
            genres.extend(steam["genres"])
        if ios:
            for g in ios["genres"]:
                if g not in genres and g not in {"게임", "생산성", "비즈니스", "유틸리티"}:
                    genres.append(g)
        if gh:
            genres.extend([t for t in gh["topics"][:4]])

    # ── 출처(sources) — 실제 요청 URL 과 그 응답에서 읽은 값을 note 에 남긴다
    sources_out: list[dict] = []

    def add_source(sid: str, title: str, url: str, stype: str, grade: str, note: str) -> str:
        sources_out.append({"id": sid, "title": title, "url": url, "type": stype, "grade": grade,
                            "accessed_at": TODAY, "note": note})
        return sid

    if steam:
        price_kr = steam.get("price_kr") or {}
        review_bits = []
        for row in steam.get("reviews") or []:
            review_bits.append(f"{row['window']} {row['percent']}%({fmt(row['count'])}건)")
        price_text = (f"정가 {price_kr.get('initial_formatted')} ({price_kr.get('currency')})"
                      if price_kr else ("무료" if steam["is_free"] else "가격 미표기"))
        note = (f"{price_text}, "
                f"출시 {steam.get('release_date') or steam.get('release_date_raw')}, "
                f"개발사 {', '.join(steam['developers'])}. 평가: {' · '.join(review_bits) or '요약 미확인'}.")
        add_source(f"steam-{item_id}", f"Steam — {steam['name']}", steam["url"], "store", "A", note)
        add_source(f"steam-api-{item_id}", f"Steam 상점 API — {steam['name']} 앱 정보",
                   f"https://store.steampowered.com/api/appdetails?appids={steam['app_id']}&cc=kr",
                   "store", "A",
                   f"is_free={str(steam['is_free']).lower()}, DLC {len(steam['dlc'])}건"
                   + (f"({', '.join(d['name'] for d in steam['dlc'][:3])})" if steam['dlc'] else "")
                   + f", 장르 {', '.join(steam['genres'])}.")
        if steam.get("steamspy"):
            sp = steam["steamspy"]
            add_source(f"steamspy-{item_id}", f"SteamSpy — {steam['name']} 전체 평가 집계",
                       f"https://steamspy.com/app/367520" if steam['app_id'] == 367520
                       else f"https://steamspy.com/app/{steam['app_id']}",
                       "aggregator", "C",
                       f"전체 언어 누적 긍정 {fmt(sp['positive'])} / 부정 {fmt(sp['negative'])} "
                       f"(긍정률 {sp['percent']}%). 보유자 규모 {sp['owners']}.")
        announcements = steam.get("announcements") or []
        if announcements:
            latest = announcements[0]
            updates = steam.get("update_posts") or []
            if updates:
                note = (f"최근 업데이트 공지 {updates[0]['date']} '{updates[0]['title']}' · "
                        f"최근 개발사 공지 {latest['date']} '{latest['title']}' "
                        f"(공지 {len(announcements)}건 확인).")
            else:
                note = (f"최근 개발사 공지 {latest['date']} '{latest['title']}' — 게임 업데이트 공지는 "
                        f"최근 {len(announcements)}건 안에 없다.")
            add_source(f"steam-news-{item_id}", f"Steam 공지 — {steam['name']} 개발사 업데이트",
                       latest["url"], "official", "A", note)

    if ios:
        rating_rows = []
        for cc, rec in ios["countries"].items():
            rating_rows.append(f"{cc.upper()} {rec.get('averageUserRating'):.2f}★"
                               f"({fmt(rec.get('userRatingCount'))})" if rec.get("averageUserRating") else "")
        iap = ios.get("iap") or {}
        iap_text = ("앱 내 구입 있음 — " + ", ".join(f"{n} {p}" for n, p in iap.get("items", [])[:4])) \
            if iap.get("available") else ("앱 내 구입 없음" if iap else "앱 내 구입 정보 미확인")
        add_source(f"itunes-{item_id}", f"Apple App Store — {ios.get('name')}",
                   f"https://apps.apple.com/{ios['primary_country']}/app/id{ios['track_id']}",
                   "store", "A",
                   f"가격 {ios['primary'].get('formattedPrice')}, "
                   f"{' · '.join(r for r in rating_rows if r)}, "
                   f"버전 {ios['primary'].get('version')}({ios['version_date']}), "
                   f"{iap_text}."
                   + ("" if ios.get("available_in_kr") else " 한국 스토어에는 없음."))

    if play:
        add_source(f"play-{item_id}", f"Google Play — {play['name']}", play["url"], "store", "A",
                   f"평점 {play['rating']}★({fmt(play['count'])}) · 무료.")

    if gh:
        add_source(f"github-{item_id}", f"GitHub — {gh['full_name']}", gh["url"], "official", "A",
                   f"스타 {fmt(gh['stars'])} · 라이선스 {gh.get('license') or '미탐지'}"
                   f" · 최근 푸시 {gh['pushed_at']} · 아카이브 {str(gh['archived']).lower()}.")
        if gh.get("latest_release"):
            rel = gh["latest_release"]
            add_source(f"github-release-{item_id}", f"GitHub 릴리스 — {rel['tag']}",
                       rel["url"], "official", "A",
                       f"최근 릴리스 {rel['published_at']} ({rel.get('name') or rel['tag']}).")

    src_ids = [s["id"] for s in sources_out]
    primary_source = src_ids[:1]

    # ── flags — API 가 직접 증명하는 사실만 yes/no, 나머지는 unknown + 리뷰 TODO
    flags: dict = {}

    def set_flag(key: str, value: str, grade: str, note: str, verification: str | None = None,
                 sids: list[str] | None = None, review_hint: str | None = None) -> None:
        flags[key] = fact(value, grade, sids if sids is not None else primary_source, note, verification)
        if review_hint and value in {"unknown", "not_assessed"}:
            todo(f"flags.{key}", review_hint)

    paid_steam = bool(steam) and not steam["is_free"]
    free_app = bool(ios or play) and not (ios and (ios["primary"].get("price") or 0) > 0)

    if steam:
        set_flag("contains_ads", "no", "A", "Steam 유료 단품 — 스토어에 광고 표기가 없다.", "direct")
        set_flag("gacha_random_items", "no", "A",
                 "인앱 결제·확률형 상품 항목이 스토어에 없다(가격은 1회 구매).", "direct")
        set_flag("forced_ad_before_use", "no", "A", "실행 전 광고 없음(단품 게임).", "direct")
        set_flag("bait_ad", "no" if not free_app else "unknown", "B",
                 "미끼형 유입 광고 보도·불만 없음(부재 근거).", "absent")
        set_flag("p2w", "no", "A", "과금 재화가 없어 게임 내 재화로만 성장한다.", "direct")
        set_flag("iap_required_to_progress", "no", "A", "1회 구매로 전편.", "direct")
        set_flag("subscription_required", "no", "A", "구독 상품 없음.", "direct")
        set_flag("account_required", "no", "A", "게임 자체 계정 없음(Steam 계정은 플랫폼 요건).", "direct")
    else:
        set_flag("contains_ads", "unknown", "unknown",
                 "App Store·Play 페이지에는 광고 표기가 별도 항목으로 없다 — 실제 노출은 확인 필요.",
                 review_hint="앱 화면·정책 문서에서 광고 노출을 확인해 yes/no 로 확정")
        set_flag("gacha_random_items", "unknown", "unknown", "확률형 상품 여부는 스토어 데이터로 알 수 없다.",
                 review_hint="상점 구성(확률형 뽑기·랜덤 박스) 확인")
        set_flag("forced_ad_before_use", "unknown", "unknown", "실행 전 광고 여부 미확인.",
                 review_hint="첫 실행 화면에서 확인")
        set_flag("bait_ad", "unknown", "unknown", "미끼형 유입 광고 여부 미확인.",
                 review_hint="SNS·검색 광고의 약속과 실제 기능 비교")
        set_flag("p2w", "unknown", "unknown", "경쟁·성장 구조가 과금에 기대는지 미확인.",
                 review_hint="무료 한도와 유료 전환 지점 확인")
        set_flag("iap_required_to_progress", "unknown", "unknown", "핵심 기능이 유료 전용인지 미확인.",
                 review_hint="무료로 쓸 수 있는 범위 확인")

    iap_available = bool((ios or {}).get("iap", {}) and (ios or {})["iap"].get("available"))
    if not steam:
        sub_hint = "앱 내 구입 목록에 'Monthly/Annual' 상품이 있으면 구독 구조 확인"
        set_flag("subscription_required", "unknown", "unknown",
                 ("앱 내 구입 목록 확인 — 구독 상품 존재 여부는 리뷰에서 판정."
                  if iap_available else "구독 여부 미확인."),
                 review_hint=sub_hint)
        set_flag("account_required", "unknown", "unknown",
                 "앱 자체 계정이 필수인지, 메일 계정만 있으면 되는지 리뷰에서 판정.",
                 review_hint="설치 직후 계정 없이 쓸 수 있는지 확인")

    last_update = None
    if ios and ios.get("version_date"):
        last_update = ios["version_date"]
    if gh and gh.get("latest_release") and gh["latest_release"].get("published_at"):
        candidate = gh["latest_release"]["published_at"]
        last_update = max(filter(None, [last_update, candidate]), default=candidate)
    steam_updates = (steam or {}).get("update_posts") or []
    if steam and steam_updates:
        candidate = steam_updates[0]["date"]
        last_update = max(filter(None, [last_update, candidate]), default=candidate)
    if gh and gh.get("pushed_at"):
        last_update = max(filter(None, [last_update, gh["pushed_at"]]), default=gh["pushed_at"])

    age = days_since(last_update) if last_update else None
    if last_update is None:
        set_flag("stale_over_12m", "unknown", "unknown", "최근 업데이트 날짜를 확인하지 못했다.",
                 review_hint="공식 사이트·스토어 버전 이력에서 마지막 업데이트 날짜 확인")
        maintenance = "stale_unknown"
        maintenance_note = TODO + "최근 업데이트 날짜를 확인해 active/완결작/방치를 정하세요."
    elif age is not None and age > 365:
        set_flag("stale_over_12m", "yes", "A",
                 f"마지막 업데이트 {last_update} — 12개월({age}일) 넘게 새 버전·공지가 없다.", "direct")
        maintenance = "stale_unknown"
        maintenance_note = (f"마지막 업데이트 {last_update}({age}일 전). 완결 선언인지 방치인지 "
                            f"리뷰에서 확인해야 한다.")
    else:
        set_flag("stale_over_12m", "no", "A", f"마지막 업데이트 {last_update}({age}일 전) — 활발.", "direct")
        maintenance = "active"
        maintenance_note = f"마지막 업데이트 {last_update}({age}일 전)."

    set_flag("data_collected", "unknown", "unknown", "개인정보 처리방침의 수집 항목을 확인해야 한다.",
             review_hint="개인정보 처리방침·스토어 데이터 보안 항목 확인")
    flags["data_export"] = {"value": "unknown", "evidence_grade": "unknown", "source_ids": [],
                            "note": "내보내기·이전 방법 미확인."}
    todo("flags.data_export", "내보내기 형식·표준(예: mbox·IMAP·CSV) 확인")

    # ── 가격 티어
    tiers: list[dict] = []
    if steam:
        price = steam.get("price_kr") or {}
        if steam["is_free"]:
            tiers.append({"tier_id": "steam", "label": "Steam 무료", "kind": "free",
                          "price": {"amount": 0, "currency": "KRW", "period": "none", "display": "무료"},
                          "limits": [], "hard_filters": {}, "verdict": "conditional",
                          "one_liner": TODO + "무료로 어디까지 즐길 수 있는지", "recommended_path": True})
        else:
            amount = price.get("initial")
            final = price.get("final")
            discount = price.get("discount_percent") or 0
            display = f"₩{fmt(round(amount / 100) if amount else 0)}"
            if discount and final and final != amount:
                display += f" (2026-11-25 기준 {discount}% 할인 ₩{fmt(round(final / 100))})"
            limits = ["유료 DLC·시즌패스 여부는 상세 확인" if not steam["dlc"] else
                      f"DLC {len(steam['dlc'])}건 별도: " + ", ".join(d["name"] for d in steam["dlc"][:3])]
            if (steam.get("price_us") or {}).get("initial"):
                limits.append(f"미국 스토어 ${steam['price_us']['initial'] / 100:.2f}")
            tiers.append({"tier_id": "steam", "label": "Steam 1회 구매", "kind": "one_time",
                          "price": {"amount": round((amount or 0) / 100), "currency": "KRW",
                                    "period": "one_time", "display": display},
                          "limits": limits, "hard_filters": {}, "verdict": "conditional",
                          "one_liner": TODO + "이 티어의 값을 한 줄로", "recommended_path": True})
    if ios:
        rec = ios["primary"]
        amount = rec.get("price") or 0
        iap_items = ((ios.get("iap") or {}).get("items") or [])
        limits = []
        if iap_items:
            limits.append("앱 내 구입: " + ", ".join(f"{n} {p}" for n, p in iap_items[:4]))
        if not ios.get("available_in_kr"):
            limits.append("한국 스토어에는 없다 — 미국·일본 등 일부 스토어에서만 판매")
        tiers.append({
            "tier_id": "ios",
            "label": ("iOS 1회 구매" if amount else ("iOS 무료 + 앱 내 구입" if iap_items else "iOS 무료")),
            "kind": ("one_time" if amount else ("freemium" if iap_items else "free")),
            "price": {"amount": amount, "currency": rec.get("currency") or "KRW",
                      "period": "one_time" if amount else "none",
                      "display": rec.get("formattedPrice") or ("무료" if not amount else "가격 미확인")},
            "limits": limits or [TODO + "무료 한도"],
            "hard_filters": {}, "verdict": "conditional",
            "one_liner": TODO + "이 티어의 값을 한 줄로", "recommended_path": not tiers,
        })
    if play:
        tiers.append({"tier_id": "android", "label": "Google Play 무료", "kind": "free",
                      "price": {"amount": 0, "currency": "KRW", "period": "none", "display": "무료"},
                      "limits": [TODO + "무료 한도"], "hard_filters": {}, "verdict": "conditional",
                      "one_liner": TODO + "이 티어의 값을 한 줄로", "recommended_path": not tiers})
    if not tiers:
        tiers.append({"tier_id": "default", "label": "기본", "kind": "free",
                      "price": {"amount": 0, "currency": "KRW", "period": "none", "display": "무료"},
                      "limits": [], "hard_filters": {}, "verdict": "conditional",
                      "one_liner": TODO + "가격·이용 조건", "recommended_path": True})
        todo("tiers[].price", "가격·과금 구조를 확인해 티어를 나누세요")

    # ── 리뷰 스냅샷 + 사용자 축
    platform_rows: list[dict] = []
    score_candidates: list[tuple[float, int, str]] = []  # (점수, 표본, 출처)
    if steam:
        for row in steam["reviews"]:
            if row["kind"] == "language":
                platform_rows.append({
                    "platform": "steam",
                    "cumulative": {"metric": "positive_rate", "value": row["percent"], "scale": "percent",
                                   "count": row["count"], "window": row["window"], "evidence_grade": "A"},
                })
                score_candidates.append((float(row["percent"]), row["count"], "steam"))
        recent = next((r for r in steam["reviews"] if r["kind"] == "recent"), None)
        if recent and platform_rows:
            platform_rows[0]["recent"] = {"metric": "positive_rate", "value": recent["percent"],
                                          "scale": "percent", "count": recent["count"],
                                          "window": recent["window"], "evidence_grade": "A"}
        if steam.get("steamspy") and platform_rows:
            sp = steam["steamspy"]
            platform_rows[0]["note"] = (f"전체 언어 누적 {fmt(sp['positive'])}긍정/{fmt(sp['negative'])}부정"
                                        f" (긍정률 {sp['percent']}%, SteamSpy 등급 C 교차 확인).")
    if ios:
        best = max(ios["countries"].items(), key=lambda kv: kv[1].get("userRatingCount") or 0)
        cc, rec = best
        stars = rec.get("averageUserRating")
        count = rec.get("userRatingCount")
        if stars is not None:
            platform_rows.append({
                "platform": "ios",
                "cumulative": {"metric": "stars", "value": round(stars, 2), "scale": "stars5",
                               "count": count, "window": f"전체({cc.upper()} 스토어)", "evidence_grade": "A"},
                "note": f"{cc.upper()} {stars:.2f}★ · {fmt(count)}건.",
            })
            score_candidates.append((round(stars * 20, 1), count or 0, "ios"))
    if play:
        platform_rows.append({
            "platform": "android",
            "cumulative": {"metric": "stars", "value": play["rating"], "scale": "stars5",
                           "count": play["count"], "window": "전체(Play 표시 평가 수)", "evidence_grade": "A"},
            "note": f"Play {play['rating']}★ · {fmt(play['count'])}건.",
        })
        if play.get("rating"):
            score_candidates.append((round(play["rating"] * 20, 1), play["count"] or 0, "android"))

    if score_candidates:
        total_count = sum(c for _s, c, _p in score_candidates)
        user_score = round(sum(s * c for s, c, _p in score_candidates) / total_count, 1) if total_count else \
            round(sum(s for s, _c, _p in score_candidates) / len(score_candidates), 1)
        basis = " · ".join(f"{p} {s}점({fmt(c)}건)" for s, c, p in score_candidates)
        user_summary = (f"자동 수집 기준 {basis} — 표본 가중 평균 {user_score}. "
                        f"최근 구간·불만 내용은 리뷰에서 확인해야 한다.")
        todo("axes.user_rating.summary", "누적과 최근 구간의 괴리·반복되는 불만을 한 줄로 정리",
             user_summary)
    else:
        user_score = None
        user_summary = TODO + "사용자 평가 표본을 찾지 못함 — 스토어 평점을 직접 확인하세요."
        todo("axes.user_rating.score", "평점·평가 수 확인 후 0~100 점수 산정")

    if not platform_rows:
        platform_rows.append({
            "platform": (ios and "ios") or (gh and "web") or "other",
            "cumulative": {"metric": "stars", "value": 0, "scale": "stars5", "count": 0,
                           "window": "표본 없음", "evidence_grade": "unknown"},
            "note": "스토어 평점 표본을 찾지 못했다.",
        })
        todo("review_snapshot", "리뷰 표본(스토어 평점·평가 수)을 직접 확인해 채우세요")

    sufficient = any((row.get("cumulative") or {}).get("count", 0) >= 100 for row in platform_rows)
    downgrade = any(((row.get("recent") or {}).get("count") or 999) < 100 for row in platform_rows if row.get("recent"))

    axes = {
        "user_rating": {
            "score": user_score,
            "signal": signal_for(user_score),
            "signal_basis": "score",
            "evidence_grade": "A" if score_candidates else "unknown",
            "confidence": "high" if sufficient and (max(c for _s, c, _p in score_candidates) if score_candidates else 0) >= 10000 else ("medium" if sufficient else "low"),
            "summary": user_summary,
            "source_ids": [s["id"] for s in sources_out if s["type"] == "store"],
        },
        "objective": {
            "score": None,
            "signal": "unknown",
            "signal_basis": "score",
            "evidence_grade": "unknown",
            "confidence": "low",
            "summary": TODO + "가격 투명성·유지보수·정직성을 확인해 0~100 점수를 매기세요.",
        },
        "ai_review": {
            "score": None,
            "signal": "unknown",
            "signal_basis": "score",
            "evidence_grade": "unknown",
            "confidence": "low",
            "summary": TODO + "본질 완성도·함정 구조·강점/약점을 검토해 0~100 점수를 매기세요.",
        },
    }

    # ── update_profile
    entries = []
    if ios and ios.get("version_date"):
        entries.append({"date": ios["version_date"], "type": "other", "platform": "ios",
                        "promise_status": "not_applicable", "evidence_grade": "A",
                        "source_ids": [f"itunes-{item_id}"],
                        "note": f"최근 버전 {ios['primary'].get('version')} 릴리스(스토어 표기)."})
    for post in ((steam or {}).get("update_posts") or [])[:2]:
        entries.append({"date": post["date"], "type": "content", "platform": "steam",
                        "promise_status": "not_applicable", "evidence_grade": "A",
                        "source_ids": [f"steam-news-{item_id}"],
                        "note": f"개발사 업데이트 공지 '{post['title'][:90]}'."})
    if not ((steam or {}).get("update_posts")) and (steam or {}).get("announcements"):
        post = steam["announcements"][0]
        entries.append({"date": post["date"], "type": "other", "platform": "steam",
                        "promise_status": "not_applicable", "evidence_grade": "A",
                        "source_ids": [f"steam-news-{item_id}"],
                        "note": f"개발사 공지 '{post['title'][:80]}' — 게임 업데이트 공지는 아니다."})
    if gh and gh.get("latest_release"):
        entries.append({"date": gh["latest_release"]["published_at"], "type": "other", "platform": "other",
                        "promise_status": "not_applicable", "evidence_grade": "A",
                        "source_ids": [f"github-release-{item_id}"],
                        "note": f"GitHub 최근 릴리스 {gh['latest_release']['tag']}."})
    if not entries:
        entries.append({"date": None, "type": "unknown", "platform": "other",
                        "promise_status": "not_applicable", "evidence_grade": "unknown",
                        "note": TODO + "최근 업데이트·릴리스 기록을 찾지 못했다."})
        todo("update_profile.entries", "공식 사이트·스토어 버전 이력으로 업데이트 기록 채우기")
    cadence = "unknown"
    if age is not None:
        cadence = "active" if age <= 180 else ("irregular" if age <= 365 else "dormant")

    # ── monetization
    iap_present = "no"
    if steam and not steam["is_free"]:
        iap_present = "no"
    elif iap_available or (ios and (ios["primary"].get("price") or 0) == 0 and ios.get("iap") is None):
        iap_present = "unknown" if not iap_available else "yes"
    prices = []
    for _n, p in ((ios or {}).get("iap", {}) or {}).get("items", []):
        amount, currency = parse_money(p)
        if amount is not None and currency:
            prices.append((amount, currency))
    price_range = None
    if prices:
        lo, hi = min(p[0] for p in prices), max(p[0] for p in prices)
        price_range = {"min": {"amount": lo, "currency": prices[0][1]},
                       "max": {"amount": hi, "currency": prices[0][1]},
                       "evidence_grade": "A",
                       "note": "App Store '앱 내 구입' 목록의 최저·최고 표시가."}

    monetization = {
        "ads": {
            "in_app_exposure": ("none" if flags["contains_ads"]["value"] == "no" else "unknown"),
            "ad_types": ["none"] if flags["contains_ads"]["value"] == "no" else ["unknown"],
            "store_declares_ads": (False if steam else None),
            "inflow_ad": {"present": flags["bait_ad"]["value"], "honesty": "not_assessed",
                          "evidence_grade": flags["bait_ad"]["evidence_grade"],
                          "source_ids": flags["bait_ad"]["source_ids"],
                          "note": flags["bait_ad"]["note"]},
        },
        "iap": {
            "present": iap_present,
            "random_items": flags["gacha_random_items"]["value"],
            **({"price_range": price_range} if price_range else {}),
            "first_purchase_prompt": "unknown",
            "p2w": flags["p2w"]["value"],
            "required_to_progress": flags["iap_required_to_progress"]["value"],
            "evidence_grade": "A" if steam else "unknown",
            "source_ids": [s["id"] for s in sources_out if s["type"] == "store"],
        },
        "subscription": {"present": "unknown" if iap_present != "no" else "no",
                         "display": ("구독 상품 없음" if iap_present == "no" else
                                     TODO + "앱 내 구입 목록에서 구독 여부 확인")},
        "free_play": {"value": "unknown", "evidence_grade": "unknown", "source_ids": [],
                      "note": TODO + "무과금으로 본편·핵심 기능을 어디까지 쓸 수 있는지"},
        "summary": TODO + "광고·앱 내 구입·구독 구조를 한두 문장으로 정리",
    }
    todo("monetization.summary", "요금 구조 요약(무료 한도·구독 가격·총비용)")

    # ── 판정 텍스트(사실 기반 초안) — 리뷰에서 문장 다듬기
    reasons = []
    if steam and steam["reviews"]:
        for row in steam["reviews"]:
            if row["kind"] == "language":
                reasons.append(f"Steam {row['window']} {row['percent']}% 긍정({fmt(row['count'])}건).")
            if row["kind"] == "recent":
                reasons.append(f"최근 30일 {row['percent']}% 긍정({fmt(row['count'])}건).")
    if ios and ios["countries"]:
        cc, rec = max(ios["countries"].items(), key=lambda kv: kv[1].get("userRatingCount") or 0)
        if rec.get("averageUserRating"):
            reasons.append(f"App Store {cc.upper()} {rec['averageUserRating']:.2f}★({fmt(rec.get('userRatingCount'))}건).")
    if gh:
        reasons.append(f"오픈소스({gh.get('license') or '라이선스 미탐지'}) · 스타 {fmt(gh['stars'])} · 최근 푸시 {gh['pushed_at']}.")
    reasons.append(TODO + "이 항목을 추천/조건부/거름으로 가르는 핵심 근거 1~2개를 채우세요.")
    todo("verdict.reasons", "판정 근거 문장 완성")

    item = {
        "schema_version": "0.4.0",
        "id": item_id,
        "name": name,
        "icon": f"assets/icons/{item_id}.webp",
        "aliases": spec.get("aliases") or [],
        "domain": spec["domain"],
        "category": spec["category"],
        "arenas": arenas,
        "arena_notes": {arena: TODO + "이 비교군에서 이 항목의 비교 포인트" for arena in arenas},
        "genres": genres,
        "platforms": platforms or ["other"],
        "developer": developer or TODO + "개발사",
        "publisher": publisher,
        "release_date": release_date,
        "one_liner": TODO + "스토어 소개를 걷어낸 한 줄 정의",
        "taste_tags": spec.get("taste_tags") or [],
        "keywords": spec.get("keywords") or [],
        "assessed_at": TODAY,
        "method": "desk_research",
        "maintenance_status": maintenance,
        "maintenance_note": maintenance_note,
        "sources": sources_out,
        "flags": flags,
        "tiers": tiers,
        "axes": axes,
        "verdict": {
            "overall": "conditional",
            "tier_of_record": tiers[0]["tier_id"],
            "signals": {"user_rating": "unknown", "objective": "unknown", "ai_review": "unknown"},
            "one_liner": TODO + "판정 한 줄",
            "reasons": reasons,
            "hard_filter_blocked": False,
            "condition_notes": [],
        },
        "review_snapshot": {
            "min_sample": 100,
            "platforms": platform_rows,
            "sample_sufficient": sufficient,
            "downgrade_applied": downgrade,
            "summary": (f"자동 수집: " + " · ".join(
                f"{r['platform']} {(r.get('cumulative') or {}).get('value')}"
                f"({fmt((r.get('cumulative') or {}).get('count'))}건)" for r in platform_rows)
                + f". 표본 규칙(100건) {'충족' if sufficient else '미달'} — 최근 구간 해석은 리뷰에서 보완."),
        },
        "update_profile": {
            "latest_update": last_update,
            **({"latest_update_platform": "ios"} if ios and ios.get("version_date") == last_update
               else ({"latest_update_platform": "steam"} if steam_updates and steam_updates[0]["date"] == last_update
                     else ({"latest_update_platform": "other"} if last_update else {}))),
            "cadence": cadence,
            "entries": entries,
            "maintenance_quality": ("healthy" if cadence == "active" else
                                    ("unknown" if cadence == "unknown" else "stalled_but_trusted")),
            "assessment": TODO + "업데이트 흐름과 과금·약관 변경의 관계를 한 줄로",
        },
        "monetization": monetization,
        "data_quality": {
            "overall_grade": "A" if (steam or ios) and not (ios and not ios.get("available_in_kr")) else "A/C",
            "unverified": [
                "AI 검토 점수(본질 완성도)",
                "무과금으로 즐길 수 있는 범위",
                "개인정보 수집·내보내기 범위",
            ],
            "conflicts": [],
            "limitations": (f"반자동 수집(auto_collect.py) 초안 — {TODAY} 공개 API 값만 채웠다. "
                            f"사람이 나머지 판단(객관·AI 축, 과금 구조, 문장)을 채워야 최종 데이터가 된다."),
        },
    }
    if ios and ios.get("iap") is not None:
        todo("monetization.iap.present", "앱 내 구입 목록의 상품 성격(구독/1회/소모품) 확인")

    # TODO 성격의 필수 문장은 별도 목록으로도 남긴다
    todo("one_liner", "한 줄 정의")
    todo("verdict.one_liner", "판정 한 줄")
    todo("axes.objective", "객관·신뢰 지표 점수·요약")
    todo("axes.ai_review", "AI 검토 점수·요약")
    todo("data_quality.unverified", "확인하지 못한 항목 정리")
    todo("arena_notes", "비교군별 비교 포인트")

    item = finalize_item(item)
    review = {
        "id": item_id,
        "generated_at": TODAY,
        "elapsed_s": round(time.perf_counter() - started, 2),
        "sources_used": sorted(sources),
        "todos": todos,
        "warnings": [w for src in sources.values() for w in (src.get("warnings") or [])],
    }
    return item, review


# 무료 API 만으로 채워지는 사실 필드 — 커버리지 분모에 함께 넣어 '전체 기록의 몇 %가 자동인가'를 센다.
FACT_FIELDS = [
    "name",
    "platforms",
    "developer",
    "publisher",
    "release_date",
    "genres",
    "maintenance_status",
    "sources",
    "tiers.price",
    "tiers.kind",
    "axes.user_rating.score",
    "axes.user_rating.summary",
    "review_snapshot.platforms",
    "review_snapshot.summary",
    "update_profile.latest_update",
    "update_profile.entries",
    "monetization.ads.in_app_exposure",
    "monetization.iap.present",
    "data_quality.overall_grade",
]

# 사람이 판단해야 하는 필드 — 이 목록의 '채워짐/남음'이 리뷰 체크리스트와 같다.
REVIEW_FIELDS = [
    "one_liner",
    "arena_notes",
    "taste_tags",
    "axes.objective.score",
    "axes.objective.summary",
    "axes.ai_review.score",
    "axes.ai_review.summary",
    "verdict.one_liner",
    "verdict.reasons",
    "verdict.condition_notes",
    "flags.contains_ads",
    "flags.forced_ad_before_use",
    "flags.gacha_random_items",
    "flags.bait_ad",
    "flags.p2w",
    "flags.iap_required_to_progress",
    "flags.subscription_required",
    "flags.account_required",
    "flags.stale_over_12m",
    "flags.data_collected",
    "flags.data_export",
    "tiers.one_liner",
    "tiers.limits",
    "tiers.verdict",
    "monetization.summary",
    "monetization.free_play",
    "update_profile.assessment",
    "data_quality.unverified",
    "data_quality.limitations",
]


def _dig(node, path: str):
    """'tiers.one_liner' 처럼 리스트를 지나가는 경로에서 값 목록을 모은다."""
    parts = path.split(".")
    current = [node]
    for part in parts:
        nxt = []
        for cur in current:
            if isinstance(cur, list):
                for element in cur:
                    if isinstance(element, dict) and part in element:
                        nxt.append(element[part])
            elif isinstance(cur, dict) and part in cur:
                nxt.append(cur[part])
        current = nxt
    return current


def _is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and not value.startswith(TODO)
    if isinstance(value, (list, dict)):
        if not value:
            return False
        if isinstance(value, list):
            return all(_is_filled(v) for v in value)
        return any(_is_filled(v) for v in value.values())
    return True


def coverage(item: dict) -> dict:
    """자동 채움 커버리지 — (1) 판단 필드 기준, (2) 문자열 기준 두 가지로 센다."""
    total = todo_n = 0

    def walk(node):
        nonlocal total, todo_n
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            total += 1
            if node.startswith(TODO):
                todo_n += 1

    walk(item)
    def count(paths):
        filled, pending = [], []
        for path in paths:
            values = _dig(item, path)
            (filled if values and all(_is_filled(v) for v in values) else pending).append(path)
        return filled, pending

    facts_ok, facts_pending = count(FACT_FIELDS)
    rev_ok, rev_pending = count(REVIEW_FIELDS)
    field_total = len(FACT_FIELDS) + len(REVIEW_FIELDS)
    auto_total = len(facts_ok) + len(rev_ok)
    return {
        "fields_total": field_total,
        "fields_auto": auto_total,
        "coverage": round(auto_total * 100 / field_total, 1) if field_total else 0.0,
        "fact_fields_auto": f"{len(facts_ok)}/{len(FACT_FIELDS)}",
        "review_fields_auto": f"{len(rev_ok)}/{len(REVIEW_FIELDS)}",
        "review_pending": rev_pending,
        "fact_pending": facts_pending,
        "string_coverage": round((total - todo_n) * 100 / total, 1) if total else 0.0,
        "todo_strings": f"{todo_n}/{total}",
    }


# ─────────────────────────────────────────────────────────────────── 실행
def collect_one(spec: dict, args) -> tuple[dict | None, dict, dict]:
    started = time.perf_counter()
    for key in ("id", "name", "domain", "category"):
        if not spec.get(key):
            raise CollectError(f"스펙 필수 키 누락: {key}")
    if not (spec.get("arena") or spec.get("arenas")):
        raise CollectError("스펙에 arena(또는 arenas)가 필요함")

    sources: dict = {}
    errors: list[str] = []
    for name, collector, key in (("steam", collect_steam, "steam_id"),
                                 ("ios", collect_ios, "ios"),
                                 ("github", collect_github, "github_repo"),
                                 ("play", collect_play, "play_package")):
        if name == "ios":
            wanted = spec.get("ios_id") or spec.get("ios_bundle") or spec.get("ios_search")
        else:
            wanted = spec.get(key)
        if not wanted:
            continue
        try:
            sources[name] = collector(spec)
        except CollectError as exc:
            errors.append(str(exc))
    if not sources:
        raise CollectError("수집된 소스가 없음 — " + ("; ".join(errors) or "소스 옵션을 지정하세요"))

    item, review = build_draft(spec, sources, started)

    icon_info = None
    if not args.no_icon:
        choice = choose_icon(spec, sources)
        if choice:
            try:
                icon_info = save_icon(item["id"], choice["url"], choice["provider"], choice.get("crop", "center"),
                                      choice.get("note", ""), force=args.force)
                item["icon"] = icon_info["file"]
            except Exception as exc:  # noqa: BLE001 — 아이콘 실패는 초안 생성을 막지 않는다
                errors.append(f"아이콘 저장 실패: {type(exc).__name__}: {exc}")
                item["icon"] = item.get("icon")
                review["todos"].append({"field": "icon", "hint": "아이콘을 직접 받아 web/assets/icons/ 에 두세요",
                                        "suggestion": choice["url"]})
        else:
            review["todos"].append({"field": "icon", "hint": "공식 아이콘 URL 을 찾지 못함", "suggestion": None})
            item.pop("icon", None)
    else:
        item.pop("icon", None)

    cov = coverage(item)
    review["coverage"] = cov
    review["errors"] = errors
    review["http_requests"] = len(HTTP_LOG)
    review["elapsed_s"] = round(time.perf_counter() - started, 2)
    if icon_info:
        review["icon"] = {k: icon_info.get(k) for k in ("provider", "source_url", "bytes", "crop", "skipped")}
    return item, review, {"spec": spec["id"], "coverage": cov, "errors": errors}


def validate_draft(item: dict) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    from jsonschema import Draft202012Validator, FormatChecker
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [f"{'/'.join(str(p) for p in err.path) or '(root)'}: {err.message}"
            for err in sorted(validator.iter_errors(item), key=lambda e: list(e.path))]


def main() -> int:
    parser = argparse.ArgumentParser(description="파로스 무료 API 반자동 수집 파이프라인")
    parser.add_argument("--spec", help="배치 스펙 JSON 경로")
    parser.add_argument("--id")
    parser.add_argument("--name")
    parser.add_argument("--domain")
    parser.add_argument("--category")
    parser.add_argument("--arena")
    parser.add_argument("--steam-id", type=int)
    parser.add_argument("--ios-id", type=int)
    parser.add_argument("--ios-bundle")
    parser.add_argument("--ios-search")
    parser.add_argument("--github", dest="github_repo")
    parser.add_argument("--play", dest="play_package")
    parser.add_argument("--out", default=str(DRAFTS_DIR), help="초안 출력 폴더(기본 projects/pharos/drafts)")
    parser.add_argument("--no-icon", action="store_true", help="아이콘 수집을 건너뛴다")
    parser.add_argument("--force", action="store_true", help="아이콘 파일이 있어도 다시 받는다")
    parser.add_argument("--list-todos", action="store_true", help="항목별 TODO 목록을 함께 출력")
    parser.add_argument("--ids", default="", help="쉼표로 구분한 id 만 수집(배치 스펙에서 골라 다시 돌릴 때)")
    args = parser.parse_args()

    if args.spec:
        spec_data = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        specs = spec_data.get("items") if isinstance(spec_data, dict) else spec_data
    else:
        specs = [{
            "id": args.id, "name": args.name, "domain": args.domain, "category": args.category,
            "arena": args.arena, "steam_id": args.steam_id, "ios_id": args.ios_id,
            "ios_bundle": args.ios_bundle, "ios_search": args.ios_search,
            "github_repo": args.github_repo, "play_package": args.play_package,
        }]
        if not args.id:
            parser.error("--spec 또는 --id 가 필요합니다")

    only = {part.strip() for part in (args.ids or "").split(",") if part.strip()}
    if only:
        specs = [spec for spec in specs if spec.get("id") in only]

    out_dir = Path(args.out)
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    batch, failures = [], 0

    print("=" * 78)
    print(f"Pharos auto_collect — 항목 {len(specs)}건 · {TODAY}")
    print("=" * 78)
    for spec in specs:
        before = len(HTTP_LOG)
        print(f"\n▸ {spec.get('id')} — {spec.get('name')}")
        try:
            item, review, _info = collect_one(spec, args)
        except CollectError as exc:
            failures += 1
            print(f"  × 실패: {exc}")
            batch.append({"id": spec.get("id"), "ok": False, "error": str(exc)})
            continue

        draft_path = out_dir / f"{item['id']}.draft.json"
        review_path = out_dir / f"{item['id']}.review.json"
        draft_path.write_text(json.dumps(item, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        review_path.write_text(json.dumps(review, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

        schema_errors = validate_draft(item)
        requests = len(HTTP_LOG) - before
        cov = review["coverage"]
        print(f"  ✓ 초안 {draft_path.relative_to(ROOT.parent.parent)} · 리뷰 {review_path.relative_to(ROOT.parent.parent)}")
        print(f"    소스 {', '.join(review['sources_used'])} · 요청 {requests}건 · "
              f"{review['elapsed_s']}s · 자동 채움 {cov['coverage']}% "
              f"(사실 {cov['fact_fields_auto']} · 판단 {cov['review_fields_auto']} · "
              f"TODO 문자열 {cov['todo_strings']})")
        if review.get("icon"):
            size = review['icon'].get('bytes')
            print(f"    아이콘 {review['icon']['provider']} · "
                  + (f"{size}B (저장)" if size else "(기존 파일 유지)"))
        if review["errors"]:
            for err in review["errors"]:
                print(f"    ! {err}")
        if schema_errors:
            failures += 1
            print(f"    × 스키마 불일치 {len(schema_errors)}건")
            for err in schema_errors[:6]:
                print(f"       · {err}")
        else:
            print("    · 스키마 v0.4.0 검사 PASS")
        if args.list_todos:
            for entry in review["todos"]:
                print(f"       TODO {entry['field']}: {entry['hint']}")
        batch.append({"id": item["id"], "ok": not schema_errors, "coverage": cov,
                      "sources": review["sources_used"], "requests": requests,
                      "elapsed_s": review["elapsed_s"], "schema_errors": schema_errors,
                      "todos": len(review["todos"]), "warnings": review["warnings"]})

    total_s = round(time.perf_counter() - started, 2)
    ok = [row for row in batch if row.get("ok")]
    avg_cov = round(sum(row["coverage"]["coverage"] for row in ok) / len(ok), 1) if ok else 0.0
    log = {
        "date": TODAY,
        "items": batch,
        "summary": {
            "items": len(specs), "ok": len(ok), "failed": len(batch) - len(ok),
            "requests": len(HTTP_LOG), "elapsed_s": total_s,
            "avg_seconds_per_item": round(total_s / max(len(batch), 1), 2),
            "avg_coverage": avg_cov,
        },
    }
    log_path = out_dir / "logs" / f"{TODAY}-auto-collect.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n" + "=" * 78)
    print(f"결과: {len(ok)}/{len(specs)}건 초안 생성 · 평균 자동 채움 {avg_cov}% · "
          f"요청 {len(HTTP_LOG)}건 · 총 {total_s}s (항목당 {log['summary']['avg_seconds_per_item']}s)")
    print(f"배치 로그: {log_path.relative_to(ROOT.parent.parent)}")
    print("=" * 78)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
