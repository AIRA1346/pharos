# 2026-11-27 미디어 도메인(영화 · 애니 · 만화) 90종 적재 — 배치 요약

## 결과

| 도메인 | 대분류 | 비교군 | 종수 | 추천 | 조건부 | 거름 |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| media 🎬 | anime · manga · movie | anime-tv · manga-volumes · feature-films | 90 | 62 | 26 | 2 |

- 애니메이션 30종 — 🟢 18 · 🟡 11 · 🔴 1(헌터×헌터 2011, 장기 휴재)
- 만화 30종 — 🟢 15 · 🟡 14 · 🔴 1(베가본드, 30년 넘은 미완)
- 영화 30종 — 🟢 29 · 🟡 1(괴물 3.76/5)

카탈로그 전체: **도메인 4 · 대분류 67 · 비교군 83 · 1,557종**(아이콘 1,557/1,557 · 영문 1,557/1,557).

## 수집 소스 (무료 공개 API, 키 없음)

- **애니·만화 — AniList GraphQL** `https://graphql.anilist.co`
  - `averageScore`(0~100) · `stats.scoreDistribution` 합(채점 표본) · `popularity`/`favourites` · 표지(`coverImage.extraLarge`)
  - 방영·연재 기간(`startDate`/`endDate`/`status`) · 화수·권수 · 스튜디오·작가 · 장르
- **영화 — Letterboxd 영화 페이지 JSON-LD** `https://letterboxd.com/film/{slug}/`
  - `aggregateRating.ratingValue`(5점) · `ratingCount`(평가 수) · 감독 · 장르 · 개봉일(`dateCreated`) · 포스터
- 한 작품당 요청 1~2회, 응답은 `drafts/media-2026-11-27/cache/` 에 캐시(재실행 시 재요청 없음).
- AniList 는 30요청/분 제한 → 검색 4개 묶음(별칭) + 2.6초 간격, 429/403 은 지수 백오프로 재시도.

## 점수 산정 (기준표 v0.7.0)

- 사용자 축 = 원점수(AniList 0~100 / Letterboxd 5점×20) + **v0.6.0 표본 규모 보정**(`validate.scale_expected` 그대로 호출)
- 객관 축 = 62 + 완결성(완결 +12 · 연재 중 −10 · 휴재 −14) + 접근 경로 수(+8/+2) + 작품 수명(+8/+5/+2)
- AI 검토 축 = 60 + (사용자 평균−80)×0.7 + min(6, log10 표본) + 완결성(+6/0/−6) — **잠정값(auto_fact)**
- 판정 = `validate.compute_verdict` (검증기와 같은 함수) — 손으로 쓴 판정 없음

## 아이콘

포스터는 2:3 이라 46px 정사각 틀에서 세로로 앉히면 읽히지 않는다. 그래서 **정사각 크롭(위쪽 45% 초점) 320×320 WebP**(quality 84)로 만들어
`web/assets/icons/{id}.webp` 에 저장한다(기존 1,467종은 그대로).

## 확인하지 못한 것 (지어내지 않고 남김)

- 한국에서 시청·열람 가능한 플랫폼과 작품 단위 가격 → `data_quality.unverified`, `tier.price.amount: null`(통화 `none`)
- 연재·방영 중 작품의 최근 화 공개일 → `update_profile.latest_update: null`
- 작품성(연출·구성)에 대한 사람 검토 → AI 축은 잠정값, `review_tier: auto_fact`
- 영화 사용자 축은 Letterboxd 단일 표본(서구·시네필 편중)

## 재현

```bash
python3 projects/pharos/scripts/media_ingest.py        # 수집·생성·기록(90종)
python3 projects/pharos/scripts/sync_web_data.py       # 인덱스·웹 사본 동기화 + validate
python3 projects/pharos/scripts/check_en_leaks.py      # EN 누출 0
python3 projects/pharos/scripts/smoke_v26_media.py     # 미디어 도메인 스모크 30항목
python3 projects/pharos/scripts/smoke_v26_media.py --live --shots-dir projects/pharos/live
```

스펙·훅: `spec.json`(작품·ID·슬러그) · `hooks.json`(한 줄 소개·수명 단계·작가) · `cache/`(API 응답)
