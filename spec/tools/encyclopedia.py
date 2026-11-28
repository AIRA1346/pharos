#!/usr/bin/env python3
"""파로스 사전(encyclopedia) 블록 — 자동 생성 + 큐레이션 병합 도우미.

평가(점수·티어·판정)와 분리된 '작품·앱 자체'의 설명을 만든다.

  summary      여러 줄 개요
  key_facts    도메인별 핵심 제원 [{key, value, note?}]
  highlights   핵심 특징 3~4줄
  related      파로스 내 관련작 [{id, relation, note?}] — 실제 id 만(검증기가 무결성 검사)
  official_links 공식·참고 링크 [{label, url, note?}]

여기서 만드는 자동 블록은 **수집한 사실만** 쓴다(수치를 지어내지 않는다).
수집 파이프라인(bulk_ingest·media_ingest)이 신규 항목에 붙이고,
`scripts/backfill_encyclopedia.py` 가 대표작에 사람이 쓴 문장(큐레이션)을 덮어쓴다.

사용:
  from encyclopedia import compose, fact, link
  enc_ko, enc_en = compose(summary_ko=..., summary_en=..., facts=[...], ...)
"""

from __future__ import annotations

RELATIONS = ("sequel", "prequel", "adaptation", "series", "alternative")
# v31 — 작품 도메인(영화·애니·만화). 개요 문장이 제작사·작품 문법을 쓴다.
WORK_DOMAINS = {"movie", "anime", "manga"}
MAX_FACTS = 12
MIN_FACTS = 3


def fact(key_ko: str, key_en: str, value_ko: str, value_en: str,
         note_ko: str | None = None, note_en: str | None = None) -> dict:
    """제원 1행 — 한국어/영어를 함께 적는다."""
    return {"key_ko": key_ko, "key_en": key_en, "value_ko": value_ko, "value_en": value_en,
            "note_ko": note_ko, "note_en": note_en}


def link(label_ko: str, label_en: str, url: str, note_ko: str | None = None,
         note_en: str | None = None) -> dict:
    return {"label_ko": label_ko, "label_en": label_en, "url": url,
            "note_ko": note_ko, "note_en": note_en}


def _clean(value) -> str:
    return " ".join(str(value or "").split()).strip()


def compose(*, summary_ko: str, summary_en: str, facts: list[dict], highlights_ko: list[str],
            highlights_en: list[str], related: list[dict] | None = None,
            official_links: list[dict] | None = None,
            min_facts: int = MIN_FACTS) -> tuple[dict, dict]:
    """KO/EN 사전 블록 쌍을 만든다. 비어 있는 행은 버리고, 최소 제원 수를 채우지 못하면 예외."""
    ko_facts, en_facts, seen = [], [], set()
    for row in facts:
        key_ko, value_ko = _clean(row.get("key_ko")), _clean(row.get("value_ko"))
        key_en, value_en = _clean(row.get("key_en")), _clean(row.get("value_en"))
        if not (key_ko and value_ko and key_en and value_en) or key_ko in seen:
            continue
        seen.add(key_ko)
        ko_fact = {"key": key_ko, "value": value_ko}
        en_fact = {"key": key_en, "value": value_en}
        if _clean(row.get("note_ko")) and _clean(row.get("note_en")):
            ko_fact["note"] = _clean(row["note_ko"])
            en_fact["note"] = _clean(row["note_en"])
        ko_facts.append(ko_fact)
        en_facts.append(en_fact)
        if len(ko_facts) >= MAX_FACTS:
            break
    if len(ko_facts) < min_facts:
        raise ValueError(f"사전 제원이 {len(ko_facts)}개 — 최소 {min_facts}개 필요")

    ko_high = [_clean(x) for x in highlights_ko if _clean(x)][:5]
    en_high = [_clean(x) for x in highlights_en if _clean(x)][:5]
    if len(ko_high) < 3 or len(en_high) < 3:
        raise ValueError("사전 핵심 특징은 KO/EN 각각 3줄 이상 필요")

    ko = {"summary": " ".join(_clean(summary_ko).split("  ")).strip(),
          "key_facts": ko_facts, "highlights": ko_high}
    en = {"summary": _clean(summary_en), "key_facts": en_facts, "highlights": en_high}

    rel = []
    for row in related or []:
        if row.get("relation") not in RELATIONS or not row.get("id"):
            continue
        rel.append(row)
    if rel:
        ko["related"] = []
        for row in rel:
            out = {"id": row["id"], "relation": row["relation"]}
            if row.get("note_ko") or row.get("note_en"):
                out["note"] = _clean(row.get("note_ko") or row.get("note_en"))
            ko["related"].append(out)
        en["related"] = []
        for row in rel:
            out = {"id": row["id"], "relation": row["relation"]}
            if row.get("note_ko") or row.get("note_en"):
                out["note"] = _clean(row.get("note_en") or row.get("note_ko"))
            en["related"].append(out)

    links = [row for row in official_links or [] if row.get("url")]
    if links:
        ko["official_links"] = [{"label": _clean(r["label_ko"]), "url": r["url"],
                                 **({"note": _clean(r["note_ko"])} if r.get("note_ko") else {})}
                                for r in links]
        en["official_links"] = [{"label": _clean(r["label_en"]), "url": r["url"],
                                 **({"note": _clean(r["note_en"])} if r.get("note_en") else {})}
                                for r in links]
    return ko, en


def platform_list(platforms: list[str], label_of) -> str:
    return " · ".join(label_of(p) for p in platforms if label_of(p))


PLATFORM_KO = {
    "steam": "Steam", "android": "Android", "ios": "iOS", "windows": "Windows", "macos": "macOS",
    "linux": "Linux", "web": "웹", "console": "콘솔", "other": "기타", "cinema": "극장",
    "streaming": "스트리밍", "tv": "TV", "print": "종이책", "anilist": "AniList", "letterboxd": "Letterboxd",
}
PLATFORM_EN = {
    "steam": "Steam", "android": "Android", "ios": "iOS", "windows": "Windows", "macos": "macOS",
    "linux": "Linux", "web": "Web", "console": "Console", "other": "Other", "cinema": "Cinema",
    "streaming": "Streaming", "tv": "TV", "print": "Print", "anilist": "AniList", "letterboxd": "Letterboxd",
}


def summary_line(domain: str, *, name_ko: str, name_en: str, developer_ko: str, developer_en: str,
                 release: str | None, genres_ko: list[str], genres_en: list[str]) -> tuple[str, str]:
    """개요 첫 문장 — 누가 언제 어떤 장르로 냈는가(수집값만)."""
    year = (release or "")[:4]
    gen_ko = " · ".join(genres_ko[:3]) or "작품"
    gen_en = " · ".join(genres_en[:3]) or "work"
    if domain in WORK_DOMAINS:
        return (f"『{name_ko}』은(는) {developer_ko or '제작사 미상'}의 {year or '연도 미상'} {gen_ko} 작품이다."
                if year else f"『{name_ko}』은(는) {developer_ko or '제작사 미상'}의 {gen_ko} 작품이다.",
                f"{name_en} is a {gen_en} work by {developer_en or 'an unlisted studio'}"
                + (f" ({year})." if year else "."))
    return (f"『{name_ko}』은(는) {developer_ko or '개발사 미상'}가 {year or '출시 연도 미상'}에 내놓은 {gen_ko} 제품이다."
            if year else
            f"『{name_ko}』은(는) {developer_ko or '개발사 미상'}의 {gen_ko} 제품이다.",
            f"{name_en} is a {gen_en} product from {developer_en or 'an unlisted developer'}"
            + (f", released in {year}." if year else "."))
