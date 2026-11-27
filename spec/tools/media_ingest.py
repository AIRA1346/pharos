#!/usr/bin/env python3
"""파로스 미디어 도메인(애니·만화·영화) 적재 — media_ingest.py (v1.0)

새 도메인 `media`(🎬 영화 · 애니 · 만화)를 3개 대분류·3개 비교군으로 만들고,
대표 명작 90종을 **공개 API 사실**로 스키마 100% 채워 `data/media/{arena}.json` ·
`data/en.json` · `data/catalog.json` 에 기록한다.

수집 소스 (무료 공개 API, 키 불필요)
  · 애니·만화 — AniList GraphQL (평균 점수·채점 분포·인기·즐겨찾기·표지·장르·방영/연재 기간·스튜디오/작가)
  · 영화      — Letterboxd 영화 페이지 (JSON-LD: 평점·평가 수·감독·장르·개봉일·포스터)

자동 산정 규칙 (사실 → 점수, 요약에 근거를 그대로 적는다)
  · 사용자 축   : AniList 평균 점수(0~100)·Letterboxd 평점(5점)×20, 표본 수는 채점 분포 합/평가 수.
                  v0.6.0 표본 규모 보정을 검증기와 같은 계약(validate.scale_expected)으로 계산한다.
  · 객관 축     : 62 에서 완결성(+12/−10/−14)·접근 경로 수(+8/+2)·출시 연수(+8/+5/+2)
  · AI 검토 축  : 본질 검토 전 중립값 60 에서 사용자 평균·표본 규모·완결성만으로 보정한 잠정값
  · 판정        : 검증기와 같은 규칙(validate.compute_verdict)으로 계산 — 손으로 쓴 판정이 아니다.

확인하지 못한 것(한국 시청 가능 플랫폼·작품 단위 가격·최근 화 공개일)은 지어내지 않고 `unknown`·`unverified` 로 남긴다.

사용
  python3 projects/pharos/scripts/media_ingest.py                # 수집·생성·기록(아이콘 포함)
  python3 projects/pharos/scripts/media_ingest.py --no-icon      # 포스터 아이콘 생략
  python3 projects/pharos/scripts/media_ingest.py --only anime   # 한 비교군만
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]          # projects/pharos
sys.path.insert(0, str(ROOT / "schema"))
import validate as vlib  # noqa: E402 — 판정·표본 보정 규칙을 검증기와 한 곳에서 쓴다

DATA = ROOT / "data"
WEB = ROOT / "web"
DRAFT = ROOT / "drafts" / "media-2026-11-27"
CACHE = DRAFT / "cache"
TODAY = date.today().isoformat()
NOW_YEAR = date.today().year
UA = {"User-Agent": "PharosBot/1.0 (Pharos catalog; contact: none)"}
ACCESSED = TODAY

ARENA = {
    "anime": {"category": "anime", "arena": "anime-tv", "file": "media/anime.json",
              "label": "TV · 극장 애니메이션", "label_en": "TV & Film Animation"},
    "manga": {"category": "manga", "arena": "manga-volumes", "file": "media/manga.json",
              "label": "만화 · 단행본", "label_en": "Manga & Volumes"},
    "movie": {"category": "movie", "arena": "feature-films", "file": "media/movie.json",
              "label": "실사 영화", "label_en": "Feature Films"},
}

GENRE_KO = {
    "Action": "액션", "Adventure": "모험", "Comedy": "코미디", "Drama": "드라마", "Fantasy": "판타지",
    "Horror": "공포", "Mystery": "미스터리", "Psychological": "심리", "Romance": "로맨스", "Sci-Fi": "SF",
    "Slice of Life": "일상", "Sports": "스포츠", "Supernatural": "초자연", "Thriller": "스릴러",
    "Music": "음악", "Mecha": "메카", "Military": "밀리터리", "School": "학원", "Ecchi": "에치",
    "Mahou Shoujo": "마법소녀", "Science Fiction": "SF", "Animation": "애니메이션", "Family": "가족",
    "Crime": "범죄", "History": "역사", "War": "전쟁", "Western": "서부", "Documentary": "다큐멘터리",
}
GENRE_EN = {v: k for k, v in GENRE_KO.items()}
GENRE_EN["SF"] = "Sci-Fi"
GENRE_EN["애니메이션"] = "Animation"
GENRE_EN["가족"] = "Family"

ANILIST_FIELDS = """
  id title { romaji english native } synonyms averageScore meanScore popularity favourites
  stats { scoreDistribution { score amount } }
  coverImage { extraLarge large color } genres
  startDate { year month day } endDate { year month day } status format source countryOfOrigin
  episodes duration chapters volumes studios { nodes { name isAnimationStudio } }
  staff(perPage: 3) { nodes { name { full } } } description(asHtml: false)
  externalLinks { site url }
"""


# ------------------------------------------------------------------ HTTP + 캐시

def _cache_path(kind: str, key: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"{kind}-{re.sub(r'[^a-zA-Z0-9_-]', '_', key)}.json"


def _http(url: str, body: bytes | None = None, headers: dict | None = None, tries: int = 5):
    h = dict(UA)
    if headers:
        h.update(headers)
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=h)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (403, 429, 500, 502, 503, 504):
                time.sleep(6 * (attempt + 1))
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"요청 실패: {url} — {last}")


def _anilist(query: str) -> dict:
    raw = _http("https://graphql.anilist.co", json.dumps({"query": query}).encode(),
                {"Content-Type": "application/json", "Accept": "application/json"})
    return json.loads(raw.decode())


def _year_of(media: dict | None) -> int:
    return int(((media or {}).get("startDate") or {}).get("year") or 0)


def anilist_resolve(works: list[dict]) -> dict[str, dict]:
    """작품별 AniList 항목 — 제목 검색으로 찾고, 연도가 어긋나면 지정 id 로 다시 확인한다.

    AniList 는 30요청/분 제한이 있어 5개씩 별칭(alias)으로 묶어 보낸다. 응답은 작품 id 기준으로 캐시한다.
    """
    out: dict[str, dict] = {}
    todo: list[dict] = []
    for work in works:
        path = _cache_path("anilist", work["id"])
        if path.exists():
            out[work["id"]] = json.loads(path.read_text(encoding="utf-8"))
        else:
            todo.append(work)

    step = 4
    for i in range(0, len(todo), step):
        chunk = todo[i:i + step]
        parts = []
        for j, work in enumerate(chunk):
            media_type = "MANGA" if work["type"] == "manga" else "ANIME"
            term = work["search"].replace('"', "")
            parts.append(f'm{j}: Media(search: "{term}", type: {media_type}) {{ {ANILIST_FIELDS} }}')
        data = _anilist("query {\n" + "\n".join(parts) + "\n}")
        wait = 2.6
        for j, work in enumerate(chunk):
            media = None
            if work.get("anilist_id"):
                # id 를 지정한 작품은 그 항목이 정본이다(검색 1순위가 다른 작품일 수 있다).
                try:
                    exact = _anilist(f'query {{ Media(id: {work["anilist_id"]}) {{ {ANILIST_FIELDS} }} }}')
                    media = (exact.get("data") or {}).get("Media")
                    time.sleep(2.6)
                except Exception:  # noqa: BLE001
                    media = None
            if media is None:
                media = (data.get("data") or {}).get(f"m{j}")
            if not media:
                raise RuntimeError(f"AniList 검색 실패: {work['id']} ({work['search']})")
            if abs(_year_of(media) - work["year"]) > 1:
                print(f"  ! {work['id']}: 연도 {_year_of(media)} ≠ {work['year']} — {media['title']}", flush=True)
            _cache_path("anilist", work["id"]).write_text(json.dumps(media, ensure_ascii=False, indent=1), encoding="utf-8")
            out[work["id"]] = media
        print(f"  · AniList {i + len(chunk)}/{len(todo)}", flush=True)
        time.sleep(wait)
    return out


LD = re.compile(r"/\* <!\[CDATA\[ \*/\s*(\{.*?\})\s*/\* \]\]> \*/", re.S)


def letterboxd_film(slug: str) -> dict:
    path = _cache_path("letterboxd", slug)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    html = _http(f"https://letterboxd.com/film/{slug}/",
                 headers={"Accept-Language": "en-US,en;q=0.9"}).decode("utf-8", "replace")
    match = LD.search(html)
    if not match:
        raise RuntimeError(f"Letterboxd JSON-LD 없음: {slug}")
    data = json.loads(match.group(1))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    time.sleep(1.2)
    return data


# ------------------------------------------------------------------ 표시 도우미

def iso_date(d: dict | None) -> str | None:
    if not d or not d.get("year"):
        return None
    month = d.get("month") or 1
    day = d.get("day") or 1
    return f"{d['year']:04d}-{month:02d}-{day:02d}"


def minutes_from_duration(text: str | None) -> int | None:
    if not text:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", text)
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def signal_of(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 50:
        return "red"
    if score < 75:
        return "yellow"
    return "green"


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


# ------------------------------------------------------------------ 항목 생성

def build_item(work: dict, hook: dict, media: dict | None, film: dict | None, scale: dict) -> tuple[dict, dict]:
    kind = work["type"]
    meta = ARENA[kind]
    arena_id = meta["arena"]

    if kind in ("anime", "manga"):
        m = media
        title_en = work["en"]
        src_label = "AniList"
        src_url = f"https://anilist.co/{'manga' if kind == 'manga' else 'anime'}/{m['id']}"
        base = float(m.get("averageScore") or 0)
        sample = sum(int(row["amount"]) for row in ((m.get("stats") or {}).get("scoreDistribution") or []))
        unit_ko, unit_en = "/100", "/100"
        score_txt = f"{base:.0f}/100"
        poster_url = (m.get("coverImage") or {}).get("extraLarge")
        genres_raw = [g for g in (m.get("genres") or [])]
        start = iso_date(m.get("startDate"))
        end = iso_date(m.get("endDate"))
        fmt = (m.get("format") or "").upper()
        eps = m.get("episodes")
        chapters, volumes = m.get("chapters"), m.get("volumes")
        studio = next((s["name"] for s in ((m.get("studios") or {}).get("nodes") or []) if s.get("isAnimationStudio")), None)
        credit_ko = credit_en = hook.get("author_ko") or studio or ""
        if kind == "manga":
            credit_ko, credit_en = hook.get("author_ko", ""), hook.get("author_en", "")
        if kind == "anime":
            credit_en = studio or ""
        credit_ko = credit_ko.replace("bones", "Bones")
        release = start
    else:
        f = film
        title_en = work["en"]
        src_label = "Letterboxd"
        src_url = f.get("url") or f"https://letterboxd.com/film/{work['slug']}/"
        rating = float((f.get("aggregateRating") or {}).get("ratingValue") or 0)
        base = round(rating * 20, 1)
        sample = int((f.get("aggregateRating") or {}).get("ratingCount") or 0)
        unit_ko, unit_en = "★/5", "★/5"
        score_txt = f"{rating:.2f}/5"
        poster_url = f.get("image")
        genres_raw = [g for g in (f.get("genre") or [])]
        start = f.get("dateCreated")
        end = None
        runtime = minutes_from_duration(f.get("duration"))
        eps = chapters = volumes = None
        fmt = "MOVIE"
        credit_ko = credit_en = (f.get("director") or [{}])[0].get("name", "")
        release = start

    year = int((start or work.get("year") or NOW_YEAR)[:4]) if start else work["year"]
    life = hook["life"]
    life_ko = {"complete": "완결", "ongoing": "연재·방영 중", "hiatus": "장기 휴재"}[life]
    life_en = {"complete": "complete", "ongoing": "still running", "hiatus": "on long hiatus"}[life]

    # ---------- 형식 표기
    def fmt_line(lang: str) -> str:
        if kind == "anime":
            base_label = {"TV": "TV", "OVA": "OVA", "ONA": "ONA", "MOVIE": "극장판", "SPECIAL": "특별편"}.get(fmt, fmt or "TV")
            if lang == "en":
                base_label = {"TV": "TV", "OVA": "OVA", "ONA": "ONA", "MOVIE": "film", "SPECIAL": "special"}.get(fmt, fmt or "TV")
            if fmt == "MOVIE":
                head = base_label
            else:
                head = f"{base_label} {eps}화" if eps and lang == "ko" else (f"{base_label}, {eps} episodes" if eps else base_label)
            span = f"{year}~{end[:4]}" if end and end[:4] != str(year) else str(year)
            return f"{head} ({span})"
        if kind == "manga":
            if chapters and volumes:
                head = f"만화 {chapters}화·{volumes}권" if lang == "ko" else f"{chapters} chapters in {volumes} volumes"
            elif chapters:
                head = f"만화 {chapters}화 연재 중" if lang == "ko" else f"{chapters} chapters so far"
            else:
                head = "연재 중" if lang == "ko" else "serialised"
            span = f"{year}~{end[:4]}" if end and end[:4] != str(year) else (f"{year}~" if life != "complete" else str(year))
            return f"{head} ({span})"
        head = f"영화 {runtime}분" if runtime and lang == "ko" else (f"{runtime} min" if runtime else "feature film")
        return f"{head} ({year})"

    fmt_ko, fmt_en = fmt_line("ko"), fmt_line("en")

    # ---------- 표본 보정 (v0.6.0)
    raw_delta, gate, applied, final_user = vlib.scale_expected(scale, base, sample)
    user_score = final_user if final_user is not None else None

    # ---------- 객관
    comp_pts = {"complete": 12, "ongoing": -10, "hiatus": -14}[life]
    platforms = (["tv", "streaming"] if kind == "anime" else ["print", "web"] if kind == "manga" else ["cinema", "streaming"])
    if kind == "anime" and fmt == "MOVIE":
        platforms = ["cinema", "streaming"]
    access_pts = 8 if len(platforms) >= 2 else 2
    age = NOW_YEAR - year
    age_pts = 8 if age >= 20 else 5 if age >= 10 else 2 if age >= 3 else 0
    objective = round(clamp(62 + comp_pts + access_pts + age_pts), 1)

    # ---------- AI 검토(잠정)
    sample_pts = round(min(6.0, math.log10(max(sample, 1))), 1)
    ai_life = {"complete": 6, "ongoing": 0, "hiatus": -6}[life]
    ai_review = round(clamp(60 + (base - 80) * 0.7 + sample_pts + ai_life), 1)

    user_sig, obj_sig, ai_sig = signal_of(user_score), signal_of(objective), signal_of(ai_review)

    # ---------- 하드 필터·플래그
    if kind == "anime":
        sub_value, sub_status = "yes", "fail"
        acc_value, acc_status = "yes", "fail"
    elif kind == "manga":
        sub_value, sub_status = "no", "pass"
        acc_value, acc_status = "no", "pass"
    else:
        sub_value, sub_status = "unknown", "unknown"
        acc_value, acc_status = "unknown", "unknown"

    stale_value = "no" if life == "ongoing" else "yes"
    maintenance_status = {"complete": "feature_complete", "ongoing": "active", "hiatus": "stale_unknown"}[life]

    flag_note = {
        "forced_ads": ("작품 자체에 실행 전 광고가 없다 — 서비스 화면의 광고는 플랫폼의 몫으로 본다.",
                       "No pre-roll ads inside the work itself — platform ads belong to the service."),
        "gacha_random_items": ("작품 단위 확률형 상품이 없다.", "No random-item purchases attached to the work."),
        "bait_ad": ("미끼형 유입 광고 보도·불만을 확인하지 못했다(부재 근거).",
                    "No reports or complaints of bait-style promotional ads (absence of evidence)."),
        "p2w": ("작품 감상에 과금 우위 요소가 없다.", "No pay-to-win element in experiencing the work."),
        "iap_required_to_progress": ("작품 감상에 추가 결제가 필요하지 않다.", "No extra purchase is required to finish the work."),
        "data_collected": ("시청·열람에 필요한 개인정보 수집 범위는 확인하지 않았다.",
                           "The personal data a platform collects to serve the work is not verified."),
    }
    sub_note = {
        "yes": ("시청은 스트리밍 구독을 전제로 한다 — 작품 단위 구매 경로는 확인하지 않았다.",
                "Watching assumes a streaming subscription; per-title purchase routes are not verified."),
        "no": ("단행본 구매로 읽는다 — 구독 상품이 작품의 전제가 아니다.",
               "Read through volume purchases; a subscription is not a precondition."),
        "unknown": ("극장 관람과 스트리밍이 모두 가능해 구독 필수 여부를 단정하지 않는다.",
                    "Both cinema and streaming routes exist, so subscription dependence is left unknown."),
    }[sub_value]
    acc_note = {
        "yes": ("스트리밍·전자책 서비스 계정이 필요하다.", "A streaming or e-book account is required."),
        "no": ("종이책 구매만으로 읽을 수 있어 계정이 필수는 아니다.", "A paper volume can be read without an account."),
        "unknown": ("플랫폼에 따라 계정이 필요하지만 작품 단위로 확인하지 않았다.",
                    "Some platforms require an account; not verified per title."),
    }[acc_value]
    stale_note = {
        "complete": ("연재·방영이 끝난 작품 — 12개월 이상 새 화·판이 없다(완결작 면제).",
                     "Serialisation or broadcast has ended — no new instalment for over 12 months (completed work, exempt)."),
        "ongoing": ("원작·후속 시즌이 이어지는 작품 — 12개월 공백으로 보지 않는다.",
                    "Original work or new seasons continue, so this is not a 12-month gap."),
        "hiatus": ("장기 휴재로 새 화가 나오지 않고 있다(방치 여부 미확인).",
                   "On a long hiatus with no new instalment (abandonment not confirmed)."),
    }[life]
    stale_status = {"complete": "exempt", "ongoing": "pass", "hiatus": "fail"}[life]

    def hf(status: str, grade: str, note_ko: str, note_en: str, impact: str | None = None):
        node = {"status": status, "evidence_grade": grade, "note": note_ko}
        if impact:
            node["impact"] = impact
        return node, {"status": status, "evidence_grade": grade, "note": note_en, **({"impact": impact} if impact else {})}

    ko_filters, en_filters = {}, {}
    for key, (nko, nen), st, gr, imp in (
        ("forced_ads", flag_note["forced_ads"], "pass", "B", None),
        ("gacha_random_items", flag_note["gacha_random_items"], "pass", "B", "none"),
        ("bait_ad", flag_note["bait_ad"], "pass", "C", None),
        ("p2w", flag_note["p2w"], "pass", "B", "none"),
        ("iap_required_to_progress", flag_note["iap_required_to_progress"], "pass", "B", None),
        ("stale_over_12m", stale_note, stale_status, "A" if life != "hiatus" else "C", None),
        ("subscription_required", sub_note, sub_status, "B" if sub_value != "unknown" else "unknown", None),
        ("account_required", acc_note, acc_status, "B" if acc_value != "unknown" else "unknown", None),
        ("data_collection", flag_note["data_collected"], "unknown", "unknown", None),
    ):
        a, b = hf(st, gr, nko, nen, imp)
        ko_filters[key] = a
        en_filters[key] = b

    def flag(value: str, grade: str, nko: str, nen: str, verification: str | None = None):
        node = {"value": value, "evidence_grade": grade, "source_ids": [src_id], "note": nko}
        if verification:
            node["verification"] = verification
        en_node = {"note": nen}
        return node, en_node

    src_id = f"anilist-{m['id']}" if kind in ("anime", "manga") else f"letterboxd-{work['slug']}"
    src_title = f"AniList — {title_en}" if kind in ("anime", "manga") else f"Letterboxd — {title_en}"
    src_note_ko = (f"평균 {base:.0f}/100 · 채점 {sample:,}건 · {fmt_ko} · {life_ko}." if kind in ("anime", "manga")
                   else f"평점 {score_txt} · 평가 {sample:,}건 · {fmt_ko} · 감독 {credit_ko}.")
    src_note_en = (f"Average {base:.0f}/100 from {sample:,} ratings · {fmt_en} · {life_en}." if kind in ("anime", "manga")
                   else f"Rating {score_txt} from {sample:,} ratings · {fmt_en} · directed by {credit_en}.")

    flags, en_flags = {}, {}
    pairs = [
        ("contains_ads", "no", "B", "작품 안에 광고가 삽입되어 있지 않다.", "No ads are embedded in the work.", "inferred"),
        ("gacha_random_items", "no", "B", flag_note["gacha_random_items"][0], flag_note["gacha_random_items"][1], "direct"),
        ("forced_ad_before_use", "no", "B", flag_note["forced_ads"][0], flag_note["forced_ads"][1], "inferred"),
        ("bait_ad", "no", "C", flag_note["bait_ad"][0], flag_note["bait_ad"][1], "absent"),
        ("p2w", "no", "B", flag_note["p2w"][0], flag_note["p2w"][1], "direct"),
        ("iap_required_to_progress", "no", "B", flag_note["iap_required_to_progress"][0], flag_note["iap_required_to_progress"][1], "direct"),
        ("subscription_required", sub_value, "B" if sub_value != "unknown" else "unknown", sub_note[0], sub_note[1], None),
        ("account_required", acc_value, "B" if acc_value != "unknown" else "unknown", acc_note[0], acc_note[1], None),
        ("data_collected", "unknown", "unknown", flag_note["data_collected"][0], flag_note["data_collected"][1], None),
        ("stale_over_12m", stale_value, "A" if life != "hiatus" else "C", stale_note[0], stale_note[1], "direct" if life != "hiatus" else "direct"),
    ]
    for key, value, grade, nko, nen, ver in pairs:
        a, b = flag(value, grade, nko, nen, ver)
        flags[key] = a
        en_flags[key] = b

    # ---------- 티어
    if kind == "anime":
        tier_id = "stream"
        tier_label_ko, tier_label_en = "스트리밍 시청", "Streaming"
        price_display_ko = "작품 단위 결제 없음 — 스트리밍 구독에 포함"
        price_display_en = "No per-title charge — included in a streaming subscription"
        if fmt == "MOVIE":
            tier_line_ko = "구독 서비스로 시청 — 극장판"
            tier_line_en = "Watch on a subscription service — film"
        else:
            tier_line_ko = (f"구독 서비스로 시청 — {eps}화" if eps else "구독 서비스로 시청")
            tier_line_en = (f"Watch on a subscription service — {eps} episodes" if eps else "Watch on a subscription service")
        limits_ko = ["한국 시청 가능 플랫폼은 확인하지 않았다", "블루레이·디지털 구매가는 작품별로 다르다"]
        limits_en = ["Streaming platforms available in Korea are not verified", "Blu-ray and digital prices differ per release"]
    elif kind == "manga":
        tier_id = "volumes"
        tier_label_ko, tier_label_en = "단행본 구매", "Volume purchase"
        price_display_ko = "권당 정가 미확인 — 판매처별 상이"
        price_display_en = "Per-volume price not verified — varies by retailer"
        tier_line_ko = f"단행본 구매 — {volumes}권" if volumes else "단행본·전자책으로 읽기"
        tier_line_en = f"Volume purchase — {volumes} volumes" if volumes else "Read as volumes or e-books"
        limits_ko = ["전자책·종이책 판매처별 가격이 다르다", "연재 중이면 최신 권까지 따로 산다" if life == "ongoing" else "절판·품절 여부는 확인하지 않았다"]
        limits_en = ["Prices differ between print and e-book retailers", "Ongoing series means buying each new volume" if life == "ongoing" else "Out-of-print or out-of-stock status is not verified"]
    else:
        tier_id = "watch"
        tier_label_ko, tier_label_en = "극장 관람 · 스트리밍", "Cinema or streaming"
        price_display_ko = "작품 단위 가격 미확인 — 극장 관람권·스트리밍 구독"
        price_display_en = "Per-title price not verified — cinema ticket or streaming subscription"
        tier_line_ko = f"극장 개봉 · 스트리밍 — {runtime}분" if runtime else "극장 개봉 · 스트리밍"
        tier_line_en = f"Released in cinemas and on streaming — {runtime} min" if runtime else "Released in cinemas and on streaming"
        limits_ko = ["극장 관람권 가격은 지역·관 종별로 다르다", "스트리밍 포함 여부는 서비스별로 다르다"]
        limits_en = ["Cinema ticket prices vary by region and venue", "Streaming availability differs by service"]

    # ---------- 축 요약
    user_summary_ko = (f"자동 수집: {src_label} 평균 {score_txt} · 채점 {sample:,}건 — 표본 가중 평균 {base:.1f}. "
                       f"v0.6.0 표본 규모 보정 {applied:+.2f} → {user_score}.")
    user_summary_en = (f"Auto-collected: {score_txt} on {src_label} across {sample:,} ratings — sample-weighted {base:.1f}. "
                       f"v0.6.0 scale adjustment {applied:+.2f} → {user_score}.")
    obj_summary_ko = (f"자동 산정 {objective}: {life_ko} ({comp_pts:+d}) · 접근 경로 {len(platforms)}개 ({access_pts:+d}) · "
                      f"출시 {age}년 ({age_pts:+d}).")
    obj_summary_en = (f"Auto-estimate {objective}: {life_en} ({comp_pts:+d}) · {len(platforms)} access routes ({access_pts:+d}) · "
                      f"{age} years since release ({age_pts:+d}).")
    ai_summary_ko = (f"자동 추정 {ai_review}: 본질 검토 전 중립값 60 · 사용자 평균 {base:.1f} ({(base - 80) * 0.7:+.1f}) · "
                     f"표본 {sample:,}건 (+{sample_pts}) · {life_ko} ({ai_life:+d}). 본질 검토는 순차 심층 검수에서 이 값을 대체한다.")
    ai_summary_en = (f"Provisional {ai_review}: neutral 60 before the deep review · user average {base:.1f} ({(base - 80) * 0.7:+.1f}) · "
                     f"{sample:,} ratings (+{sample_pts}) · {life_en} ({ai_life:+d}). The deep review pass replaces this value.")

    # ---------- 수명·갱신
    if life == "complete":
        maintenance_note_ko = (f"완결 — AniList 종료일 {end or release} 기준으로 연재·방영이 끝난 작품이다. "
                               "후속 시즌·외전은 이 항목에서 다루지 않는다.")
        maintenance_note_en = (f"Complete — serialisation or broadcast ended on {end or release} (AniList end date). "
                               "Sequels and spin-offs are outside this entry.")
        cadence = "dormant"
        latest_update = end or release
        upd_note_ko = f"최종화·최종권 공개({end or release}) — AniList 종료일."
        upd_note_en = f"Final episode or volume released ({end or release}) — AniList end date."
    elif life == "ongoing":
        maintenance_note_ko = ("연재·방영 중 — 원작이나 후속 시즌이 이어지는 작품이다. 최근 화 공개일은 확인하지 않았다.")
        maintenance_note_en = ("Still running — the source work or new seasons continue. The date of the latest instalment is not verified.")
        cadence = "active"
        latest_update = None
        upd_note_ko = "연재·방영이 이어지는 작품 — 최근 화 공개일은 확인하지 않았다."
        upd_note_en = "Still publishing or airing — latest instalment date not verified."
    else:
        maintenance_note_ko = ("장기 휴재 — 마지막 화 이후 새 화가 나오지 않은 상태다. 최근 연재일은 확인하지 못했다.")
        maintenance_note_en = ("Long hiatus — no new instalment since the last chapter. The latest release date is not verified.")
        cadence = "irregular"
        latest_update = None
        upd_note_ko = "장기 휴재 — 최근 연재일 미확인."
        upd_note_en = "Long hiatus — latest chapter date unverified."

    quality = "stalled_but_trusted" if life == "hiatus" else "healthy"
    verdict_ko = {"recommend": "추천", "conditional": "조건부", "avoid": "거름"}
    verdict_en = {"recommend": "Recommended", "conditional": "Conditional", "avoid": "Skip"}

    # ---------- 판정용 임시 티어
    tier_ko = {
        "tier_id": tier_id, "kind": "subscription" if kind == "anime" else "one_time",
        "label": tier_label_ko,
        "price": {"amount": None, "currency": "none", "period": "none", "display": price_display_ko},
        "limits": limits_ko,
        "hard_filters": ko_filters,
        "one_liner": tier_line_ko,
        "recommended_path": True,
    }
    item = {
        "schema_version": "0.4.0",
        "id": work["id"],
        "name": work["ko"] + (" (애니메이션)" if work.get("suffix") else ""),
        "aliases": [title_en + (" (anime)" if work.get("suffix") else "")],
        "domain": "media",
        "category": meta["category"],
        "arenas": [arena_id],
        "arena_notes": {},
        "genres": [GENRE_KO.get(g, g) for g in genres_raw[:3]],
        "platforms": platforms,
        "developer": credit_ko,
        "release_date": release,
        "one_liner": hook["ko"],
        "taste_tags": [("completed" if life == "complete" else "ongoing")] + (["classic"] if age >= 20 else []),
        "keywords": [work["ko"], title_en, life_ko],
        "assessed_at": TODAY,
        "method": "desk_research",
        "review_tier": "auto_fact",
        "maintenance_status": maintenance_status,
        "maintenance_note": maintenance_note_ko,
        "sources": [{"id": src_id, "title": src_title, "url": src_url, "type": "aggregator",
                     "grade": "A", "accessed_at": ACCESSED, "note": src_note_ko}],
        "flags": flags,
        "tiers": [tier_ko],
        "axes": {
            "user_rating": {
                "score": user_score, "signal": user_sig, "signal_basis": "score", "evidence_grade": "A",
                "confidence": "high",
                "summary": user_summary_ko, "source_ids": [src_id],
                "scale_adjustment": {
                    "rule": "v0.6.0", "sample_count": sample, "sample_source": "reviews",
                    "base_score": base, "log_delta": round(raw_delta, 3), "gate": round(gate, 3),
                    "applied": applied, "final_score": user_score, "applied_flag": True,
                },
            },
            "objective": {"score": objective, "signal": obj_sig, "signal_basis": "score", "evidence_grade": "A",
                          "confidence": "medium", "summary": obj_summary_ko, "source_ids": [src_id]},
            "ai_review": {"score": ai_review, "signal": ai_sig, "signal_basis": "score", "evidence_grade": "C",
                          "confidence": "low", "summary": ai_summary_ko, "source_ids": [src_id]},
        },
        "verdict": {
            "overall": "conditional", "tier_of_record": tier_id,
            "signals": {"user_rating": user_sig, "objective": obj_sig, "ai_review": ai_sig},
            "one_liner": "", "reasons": [], "hard_filter_blocked": False, "condition_notes": [],
        },
        "review_snapshot": {
            "min_sample": 100,
            "platforms": [{
                "platform": "anilist" if kind in ("anime", "manga") else "letterboxd",
                "cumulative": {"metric": "score", "value": base, "scale": "out_of_100" if kind in ("anime", "manga") else "stars5",
                               "count": sample, "window": "전체 누적", "evidence_grade": "A"},
                "note": f"{score_txt} · {sample:,}건 (전체 누적)",
            }],
            "sample_sufficient": sample >= 100,
            "downgrade_applied": False,
            "summary": f"자동 수집 표본: {src_label} {score_txt} · 채점 {sample:,}건. 표본 규칙(100건) 충족.",
        },
        "update_profile": {
            "latest_update": latest_update,
            "latest_update_platform": platforms[0],
            "cadence": cadence,
            "entries": [{"date": latest_update, "type": "content", "platform": platforms[0],
                         "promise_status": "not_applicable", "evidence_grade": "A",
                         "source_ids": [src_id], "note": upd_note_ko}],
            "maintenance_quality": quality,
            "assessment": maintenance_note_ko,
        },
        "monetization": {
            "ads": {"in_app_exposure": "none", "ad_types": ["none"], "store_declares_ads": None,
                    "inflow_ad": {"present": "no", "honesty": "not_assessed", "evidence_grade": "C",
                                  "source_ids": [src_id], "note": flag_note["bait_ad"][0]}},
            "iap": {"present": "no", "random_items": "no", "first_purchase_prompt": "unknown",
                    "p2w": "no", "required_to_progress": "no", "evidence_grade": "B", "source_ids": [src_id]},
            "subscription": {"present": sub_value, "display": price_display_ko},
            "summary": (f"작품 단위 인앱 결제·확률형 요소 없음. "
                        + ("시청은 스트리밍 구독이 전제다." if kind == "anime" else
                           "열람은 단행본 구매가 기본이다." if kind == "manga" else
                           "극장 관람 또는 스트리밍 구독으로 본다.")),
        },
        "data_quality": {
            "overall_grade": "A/C",
            "unverified": ["한국 시청·열람 가능 플랫폼", "작품 단위 가격", "최근 화·판 공개일", "본질 완성도(AI 검토)"],
            "conflicts": [],
            "limitations": (f"{src_label} 공개 API 값만으로 만든 1차 기록(auto_fact) — 작품성·완성도 판단과 "
                            "시청 가능 경로·가격은 순차 심층 검수에서 확정한다. 한 줄 소개는 작품 소재를 요약해 직접 썼다."),
        },
        "score_notes": {
            "user_rating": (f"{src_label} {score_txt} · 채점 {sample:,}건 → 표본 가중 평균 {base:.1f}. 표본 {sample:,}건. "
                            f"v0.6.0 표본 규모 보정: 누적 표본 {sample:,}건 → 로그 보정 {raw_delta:+.2f} × 평점 게이트 {gate:.2f} "
                            f"= {applied:+.2f} ({base:.1f} → {user_score})."),
            "objective": obj_summary_ko,
            "ai_review": ai_summary_ko,
        },
        "icon": f"assets/icons/{work['id']}.webp",
    }
    item["arena_notes"][arena_id] = (f"{src_label} {score_txt} · 채점 {sample:,}건 · {fmt_ko} · {credit_ko}. "
                                     f"'{meta['label']}' 안에서 이 작품의 자리는 이 수치로 잡았다.")

    # 판정 계산(검증기와 같은 함수)
    overall, why = vlib.compute_verdict(item, tier_ko)
    item["tiers"][0]["verdict"] = overall
    item["verdict"]["overall"] = overall
    item["tiers"][0]["recommended_path"] = overall != "avoid"
    item["verdict"]["one_liner"] = (f"{verdict_ko[overall]} — {src_label} {score_txt} · 채점 {sample:,}건 · {fmt_ko}. 자동 수집 1차 판정.")
    item["verdict"]["reasons"] = [
        f"{src_label} {score_txt} · 채점 {sample:,}건 (표본 보정 {applied:+.2f} → {user_score}).",
        f"{fmt_ko} · {credit_ko}.",
        (f"{life_ko} — AniList 종료일 {end or release}." if life == "complete"
         else f"{life_ko} — 후속 시즌·연재가 이어지고 있다." if life == "ongoing"
         else "장기 휴재 — 최근 연재일은 확인하지 못했다."),
    ]
    item["verdict"]["condition_notes"] = [
        "자동 수집 항목 — 본질·완성도 판단은 순차 심층 검수에서 확정한다.",
        "한국 기준 시청·열람 가능 플랫폼과 작품 단위 가격은 확인하지 않았다.",
        (f"완결작 면제는 AniList 종료일({end or release})에 근거한 자동 판단이다." if life == "complete"
         else "연재·방영이 이어지는 작품 — 최근 화 공개일은 확인하지 않았다." if life == "ongoing"
         else "장기 휴재 상태 — 최근 연재일을 확인하지 못해 12개월 공백으로 남겼다."),
    ]
    item["verdict"]["_why"] = why
    item["verdict"].pop("_why", None)

    # ---------- EN 오버레이
    en_genres = [GENRE_EN.get(GENRE_KO.get(g, g), g) for g in genres_raw[:3]]
    en = {
        "name": title_en,
        "developer": credit_en,
        "one_liner": hook["en"],
        "tagline": tier_line_en,
        "arena_notes": {arena_id: (f"{score_txt} on {src_label} across {sample:,} ratings · {fmt_en} · {credit_en}. "
                                   f"This is where it sits in “{meta['label_en']}”.")},
        "genres": en_genres,
        "maintenance_note": maintenance_note_en,
        "axes": {
            "user_rating": {"summary": user_summary_en},
            "objective": {"summary": obj_summary_en},
            "ai_review": {"summary": ai_summary_en},
        },
        "verdict": {
            "one_liner": f"{verdict_en[overall]} — {score_txt} on {src_label} across {sample:,} ratings · {fmt_en}. First-pass auto assessment.",
            "reasons": [
                f"{score_txt} on {src_label} across {sample:,} ratings (scale adjustment {applied:+.2f} → {user_score}).",
                f"{fmt_en} · {credit_en}.",
                (f"{life_en.capitalize()} — AniList end date {end or release}." if life == "complete"
                 else "Still running — sequels or the source serialisation continue." if life == "ongoing"
                 else "On a long hiatus; the latest chapter date is not verified."),
            ],
            "condition_notes": [
                "Auto-collected entry — core quality is confirmed in the sequential deep review.",
                "Streaming or reading platforms available in Korea, and per-title prices, are not verified.",
                (f"The completed-work exemption rests on the AniList end date ({end or release}) and is an automated judgement." if life == "complete"
                 else "The work is still running; the latest instalment date is not verified." if life == "ongoing"
                 else "The work is on a long hiatus, and the latest chapter date could not be verified."),
            ],
        },
        "tiers": [{
            "tier_id": tier_id, "label": tier_label_en,
            "price": {"display": price_display_en},
            "one_liner": tier_line_en,
            "limits": limits_en,
            "hard_filters": en_filters,
        }],
        "review_snapshot": {
            "platforms": [{
                "platform": "anilist" if kind in ("anime", "manga") else "letterboxd",
                "cumulative": {"metric": "score", "value": base, "scale": "out_of_100" if kind in ("anime", "manga") else "stars5",
                               "count": sample, "window": "All-time", "evidence_grade": "A"},
                "note": f"{score_txt} · {sample:,} ratings (all-time)",
            }],
            "summary": f"Auto-collected sample: {score_txt} on {src_label} across {sample:,} ratings. Sample rule (100 ratings) met.",
        },
        "score_notes": {
            "user_rating": (f"{score_txt} on {src_label} across {sample:,} ratings → sample-weighted {base:.1f}. Sample {sample:,}. "
                            f"v0.6.0 scale adjustment: {sample:,} cumulative ratings → log adjustment {raw_delta:+.2f} × rating gate {gate:.2f} "
                            f"= {applied:+.2f} ({base:.1f} → {user_score})."),
            "objective": obj_summary_en,
            "ai_review": ai_summary_en,
        },
        "data_quality": {
            "unverified": ["Streaming or reading platforms available in Korea", "Per-title price",
                           "Date of the latest instalment", "Core quality (AI review)"],
            "limitations": (f"Auto-collected (auto_fact) — a first-pass record built from {src_label} public API data on {TODAY}. "
                            "Core quality, viewing routes and prices are replaced in the sequential deep review. "
                            "The one-liner is a summary of the work's premise written for this catalog."),
        },
        "monetization": {
            "summary": ("No per-title in-app purchase or random items. "
                        + ("Watching assumes a streaming subscription." if kind == "anime" else
                           "Reading is based on volume purchases." if kind == "manga" else
                           "Seen in cinemas or on a streaming subscription.")),
            "ads": {"inflow_ad": {"note": flag_note["bait_ad"][1]}},
            "subscription": {"display": price_display_en},
        },
        "update_profile": {
            "assessment": maintenance_note_en,
            "entries": [{"date": latest_update, "type": "content", "platform": platforms[0],
                         "promise_status": "not_applicable", "evidence_grade": "A",
                         "source_ids": [src_id], "note": upd_note_en}],
        },
        "flags": en_flags,
        "sources": [{"title": src_title, "note": src_note_en}],
    }
    return item, en


# ------------------------------------------------------------------ 포스터 아이콘

def make_icon(data: bytes, out: Path) -> None:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    size = 320
    # 배경: 꽉 채워 흐리게
    bg_scale = max(size / img.width, size / img.height)
    bg = img.resize((max(1, int(img.width * bg_scale)), max(1, int(img.height * bg_scale))), Image.LANCZOS)
    left, top = (bg.width - size) // 2, (bg.height - size) // 2
    bg = bg.crop((left, top, left + size, top + size)).filter(ImageFilter.GaussianBlur(14))
    bg = Image.blend(bg, Image.new("RGB", (size, size), (12, 13, 18)), 0.35)
    # 전경: 높이 맞춤
    fg_h = size - 16
    fg_w = max(1, int(img.width * fg_h / img.height))
    fg = img.resize((fg_w, fg_h), Image.LANCZOS)
    if fg_w > size - 16:
        fg = fg.crop(((fg_w - (size - 16)) // 2, 0, (fg_w - (size - 16)) // 2 + size - 16, fg_h))
        fg_w = fg.width
    canvas = bg.copy()
    canvas.paste(fg, ((size - fg_w) // 2, (size - fg_height(fg)) // 2))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "WEBP", quality=84, method=6)


def fg_height(img: Image.Image) -> int:
    return img.height


# ------------------------------------------------------------------ 카탈로그·EN 병합

def update_catalog(catalog: dict) -> None:
    catalog["domains"] = [d for d in catalog["domains"] if d["id"] != "media"]
    catalog["categories"] = [c for c in catalog["categories"] if c["domain"] != "media"]
    catalog["arenas"] = [a for a in catalog["arenas"] if a["domain"] != "media"]
    catalog["filter_packs"]["media"] = {
        "label": "미디어 팩",
        "description": "작품 자체보다 감상 경로를 먼저 본다 — 구독·계정·지역 잠금, 완결 여부, 광고 삽입.",
        "filters": ["forced_ads", "gacha_random_items", "p2w", "stale_over_12m",
                    "subscription_required", "account_required", "data_collection"],
    }
    catalog["domains"].append({
        "id": "media", "label": "영화 · 애니 · 만화", "icon": "🎬",
        "description": "보고 읽는 작품 — 완결 여부와 감상 경로(구독·구매·지역)가 판정을 가른다.",
        "filter_pack": "media", "default_preset": "balanced",
        "filter_labels": {
            "forced_ads": "작품 내 광고·홍보 삽입 제외",
            "gacha_random_items": "확률형 수집 요소 제외",
            "p2w": "과금 우위 요소 제외",
            "stale_over_12m": "휴재·중단 작품 제외",
            "subscription_required": "구독 필수 작품 제외",
            "account_required": "계정·지역 잠금 제외",
            "data_collection": "과도한 개인정보 요구 제외",
        },
    })
    catalog["categories"] += [
        {"id": "anime", "domain": "media", "label": "애니메이션",
         "description": "TV·극장 애니메이션 — 원작 진행도와 후속 시즌, 스튜디오가 판정을 가른다."},
        {"id": "manga", "domain": "media", "label": "만화",
         "description": "만화·단행본 — 완결 여부와 권수, 작가의 필력이 판정을 가른다."},
        {"id": "movie", "domain": "media", "label": "영화",
         "description": "실사 영화 — 한 편으로 완결되는 작품성과 재감상 가치를 본다."},
    ]
    catalog["arenas"] += [
        {"id": "anime-tv", "domain": "media", "category": "anime", "label": "TV · 극장 애니메이션",
         "description": "같은 자리에서 겨루는 애니메이션 — AniList 평균 점수와 채점 수, 원작 진행도와 후속 시즌으로 비교한다.",
         "data_file": "media/anime.json"},
        {"id": "manga-volumes", "domain": "media", "category": "manga", "label": "만화 · 단행본",
         "description": "같은 자리에서 겨루는 만화 — AniList 평균 점수와 채점 수, 완결 여부와 권수로 비교한다.",
         "data_file": "media/manga.json"},
        {"id": "feature-films", "domain": "media", "category": "movie", "label": "실사 영화",
         "description": "같은 자리에서 겨루는 영화 — Letterboxd 평점과 평가 수, 개봉 연도로 비교한다.",
         "data_file": "media/movie.json"},
    ]
    featured = catalog["home"]["featured_arenas"]
    for aid in ("anime-tv", "manga-volumes", "feature-films"):
        if aid not in featured:
            featured.insert(0, aid)
    catalog["planned_domains"] = [d for d in catalog.get("planned_domains") or [] if d["id"] != "content"]
    note = catalog.get("note") or ""
    tag = " 2026-11-27 미디어 도메인(v26)으로 영화·애니·만화 3개 비교군 90종이 들어왔다(도메인 4 · 대분류 13 · 비교군 83)."
    if "미디어 도메인(v26)" not in note:
        catalog["note"] = note.rstrip() + tag


def update_en(bundle: dict, items_en: dict[str, dict]) -> None:
    bundle.setdefault("domains", {})["media"] = {
        "label": "Film · Anime · Manga",
        "description": "Works you watch and read — completion and the route to them (subscription, purchase, region) decide the verdict.",
        "filter_labels": {
            "forced_ads": "Ads or promos inside the work",
            "gacha_random_items": "Random-collectible mechanics",
            "p2w": "Pay-to-win elements",
            "stale_over_12m": "On hiatus or abandoned",
            "subscription_required": "Subscription-only",
            "account_required": "Account or region lock",
            "data_collection": "Heavy personal data demands",
        },
    }
    for key, label, desc in (
        ("anime", "Anime", "TV and film animation — how far the source has come, sequel seasons and the studio decide the verdict."),
        ("manga", "Manga", "Manga and volumes — completion, length and the author's craft decide the verdict."),
        ("movie", "Film", "Live-action film — a single sitting's craft and rewatch value."),
    ):
        bundle.setdefault("categories", {})[key] = {"label": label, "description": desc}
    for key, label, desc in (
        ("anime-tv", "TV & Film Animation",
         "Animation works side by side — AniList average score and rating count, progress of the source, sequel seasons."),
        ("manga-volumes", "Manga & Volumes",
         "Manga side by side — AniList average score and rating count, completion and volume count."),
        ("feature-films", "Feature Films",
         "Films side by side — Letterboxd rating and rating count, release year."),
    ):
        bundle.setdefault("arenas", {})[key] = {"label": label, "description": desc}
    bundle.setdefault("filter_packs", {})["media"] = {
        "label": "Media pack",
        "description": "Look at how the work is reached before the work itself — subscription, account and region locks, completion, ads.",
    }
    genres = bundle.setdefault("genres", {})
    for ko, en in GENRE_EN.items():
        genres.setdefault(ko, en)
    bundle.setdefault("items", {}).update(items_en)


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(ARENA), help="한 비교군만 적재")
    ap.add_argument("--no-icon", action="store_true")
    args = ap.parse_args()

    spec = json.loads((DRAFT / "spec.json").read_text(encoding="utf-8"))
    hooks = json.loads((DRAFT / "hooks.json").read_text(encoding="utf-8"))
    if args.only:
        spec = [w for w in spec if w["type"] == args.only]

    missing_hooks = [w["id"] for w in spec if w["id"] not in hooks]
    if missing_hooks:
        print(f"× hooks.json 에 없는 항목: {missing_hooks}")
        return 1

    catalog = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schema" / "item.schema.json").read_text(encoding="utf-8"))
    scale = (schema.get("x-pharos") or {}).get("client", {}).get("scale_adjustment") or {}

    print("=" * 78)
    print(f"미디어 도메인 적재 — {len(spec)}종")
    print("=" * 78)

    anilist_works = [w for w in spec if w["type"] in ("anime", "manga")]
    media_map = anilist_resolve(anilist_works) if anilist_works else {}
    films = {}
    for w in spec:
        if w["type"] == "movie":
            films[w["id"]] = letterboxd_film(w["slug"])

    # 제목·연도 재확인 — 다른 작품을 가져왔으면 멈춘다.
    bad = []
    for w in spec:
        if w["type"] in ("anime", "manga"):
            m = media_map[w["id"]]
            year = _year_of(m)
            if abs(year - w["year"]) > 1:
                bad.append((w["id"], "연도", w["year"], year, m["title"]))
        else:
            f = films[w["id"]]
            year = int((f.get("dateCreated") or "0000")[:4] or 0)
            if abs(year - w["year"]) > 1:
                bad.append((w["id"], "연도", w["year"], year, f.get("name")))
    if bad:
        print("× 연도가 맞지 않는 항목 — 확인 필요")
        for row in bad:
            print("   ", row)
        return 1

    by_type: dict[str, list[tuple[dict, dict]]] = {k: [] for k in ARENA}
    en_items: dict[str, dict] = {}
    icon_done = 0
    for w in spec:
        media = media_map.get(w["id"]) if w["type"] in ("anime", "manga") else None
        film = films.get(w["id"]) if w["type"] == "movie" else None
        item, en = build_item(w, hooks[w["id"]], media, film, scale)
        by_type[w["type"]].append((item, en))
        en_items[w["id"]] = en
        icon_path = WEB / "assets" / "icons" / f"{w['id']}.webp"
        if not args.no_icon and not icon_path.exists():
            poster = ((media or {}).get("coverImage") or {}).get("extraLarge") if media else (film or {}).get("image")
            if not poster:
                print(f"  ! {w['id']}: 포스터 URL 없음")
                continue
            try:
                data = _http(poster, headers={"Accept": "image/webp,image/*,*/*"})
                make_icon(data, WEB / "assets" / "icons" / f"{w['id']}.webp")
                icon_done += 1
                time.sleep(0.5)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {w['id']}: 포스터 실패 {exc}")

    # 파일 기록
    for kind, rows in by_type.items():
        if not rows:
            continue
        path = DATA / ARENA[kind]["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([item for item, _en in rows], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        verdicts = {}
        for item, _en in rows:
            verdicts[item["verdict"]["overall"]] = verdicts.get(item["verdict"]["overall"], 0) + 1
        print(f"→ {path.relative_to(ROOT)} · {len(rows)}건 · {verdicts}")

    update_catalog(catalog)
    (DATA / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"→ data/catalog.json (도메인 {len(catalog['domains'])} · 대분류 {len(catalog['categories'])} · 비교군 {len(catalog['arenas'])})")

    en_path = DATA / "en.json"
    bundle = json.loads(en_path.read_text(encoding="utf-8"))
    update_en(bundle, en_items)
    en_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"→ data/en.json (항목 {len(bundle['items'])}건) · 아이콘 {icon_done}개")

    # 스키마 검사(항목 단위) — 기록 직후 바로 확인
    from jsonschema import Draft202012Validator, FormatChecker
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    fails = 0
    for kind, rows in by_type.items():
        for item, _en in rows:
            errs = sorted(validator.iter_errors(item), key=lambda e: list(e.path))
            if errs:
                fails += 1
                print(f"  × {item['id']}: {len(errs)}건 — {errs[0].message[:120]}")
    print(f"스키마 검사: {sum(len(r) for r in by_type.values()) - fails}통과 / {fails}실패")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
