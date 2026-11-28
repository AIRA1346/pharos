# 2026-11-28 9차 대량 적재 587종 — 배치 요약

## 결과

| 도메인 | 이전 | 이후 | 순증 | 추천 | 조건부 | 거름 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 영화 movie | 269 | 410 | +141 | 83 | 58 | 0 |
| 애니 anime | 262 | 422 | +160 | 33 | 127 | 0 |
| 만화 manga | 257 | 385 | +128 | 19 | 110 | 0 |
| 게임 game | 892 | 991 | +99 | 12 | 85 | 3 |
| 앱 app | 695 | 738 | +43 | 13 | 28 | 2 |
| AI ai | 64 | 80 | +16 | 6 | 19 | 2 |
| **합계** | **2,439** | **3,026** | **+587** | **166** | **427** | **7** |

(추천·조건부·거름은 이번 배치로 새로 들어온 항목 기준입니다.)

- 사전(encyclopedia) 188 → **208종**(신규 20종) · 관련작 256 → **310개**
- 등대 139종 · 271목표(변동 없음) · 아이콘 3,026/3,026 · 영문 3,026/3,026
- 신규 600종 판정: 추천 166 · 조건부 427 · 거름 7(완결작 면제 적용 후)

## 수집 소스

- **애니·만화** — AniList GraphQL: `averageScore`·`stats.scoreDistribution` 합(채점 표본)·`status`·`format`·`episodes`/`chapters`/`volumes`·`studios`/`staff`·`coverImage.extraLarge`·`genres`.
- **영화** — Letterboxd 영화 페이지 JSON-LD: `aggregateRating.ratingValue`(5점)·`ratingCount`·`director`·`genre`·`dateCreated`·포스터.
- **게임** — Steam storesearch→appdetails(ko/en)·상점 평가 요약·ISteamNews·SteamSpy. `PHAROS_STEAM_PACE` 로 요청 간격 조절.
- **앱** — Google Play JSON-LD(평점·평가 수·업데이트·광고 표기·og:image) · App Store iTunes search/lookup(패키지명이 틀리거나 내려간 항목은 이름 검색으로 전환).
- **AI** — GitHub 저장소(라이선스·스타·최근 푸시·아카이브) · 스토어 레코드가 있는 도구는 Play/iTunes.

## 이번 배치에서 새로 만든 것

1. **후보를 인기순 풀에서 고르는 절차** (`probe.py` → `probe2.py`) — 장르별 AniList 인기순 상위에서 이미 적재된 id 를 빼고 후보를 만들고, 고른 작품의 id·연도를 AniList 응답으로 먼저 확정했다(`resolved.json`). 적재는 확정된 id 로만 하므로 '검색 1순위가 다른 작품'인 사고가 구조적으로 없다.
2. **이름 충돌 처리 규칙** — 같은 작품이 이미 카탈로그에 있으면 애니메이션은 `(애니메이션)`, 만화는 `(만화)`, 극장판은 `(극장판)` 접미사로 구분하고, 이미 있는 작품 자체는 넣지 않았다(케이쿠라·샤먼 킹 만화 등).
3. **완결형 패키지 게임 면제** — 신규 게임 54종에 `maintenance_status=feature_complete` 를 적용. Steam 상점 분류 Single-player 단독 39종(등급 A)과 본편 완결·온라인 선택 15종(등급 B). 거름 61 → 7.

## 확인하지 못한 것 (지어내지 않고 남김)

- 연재·방영 중 작품의 최근 화 공개일 · 한국 시청 가능 플랫폼 · 작품 단위 가격 → `data_quality.unverified`, `tier.price.amount: null`
- 이번 587종의 확률형·구독·계정·데이터 수집 판단 → `unknown` (심층 검수 대기)
- 영화 사용자 축은 Letterboxd 단일 표본(서구·시네필 편중)

## 재현

```bash
python3 projects/pharos/drafts/media-2026-11-28-batch5/probe.py
python3 projects/pharos/drafts/media-2026-11-28-batch5/probe2.py
python3 projects/pharos/drafts/media-2026-11-28-batch5/resolve_movies.py
python3 projects/pharos/drafts/media-2026-11-28-batch5/build_spec.py
python3 projects/pharos/drafts/media-2026-11-28-batch5/prefetch.py
python3 projects/pharos/scripts/media_ingest.py --merge --no-icon \
  --spec projects/pharos/drafts/media-2026-11-28-batch5/spec.json \
  --hooks projects/pharos/drafts/media-2026-11-28-batch5/hooks.json
python3 projects/pharos/scripts/media_ingest.py --icons-only \
  --spec projects/pharos/drafts/media-2026-11-28-batch5/spec.json \
  --hooks projects/pharos/drafts/media-2026-11-28-batch5/hooks.json
python3 projects/pharos/scripts/bulk_ingest.py --spec projects/pharos/drafts/bulk-2026-11-28-batch9/spec.json
python3 projects/pharos/scripts/bulk_ingest.py --spec projects/pharos/drafts/bulk-2026-11-28-batch9c/spec.json
python3 projects/pharos/drafts/encyclopedia-2026-11-28-batch9/apply.py
python3 projects/pharos/drafts/bulk-2026-11-28-batch9/check_steam_categories.py
python3 projects/pharos/drafts/bulk-2026-11-28-batch9/patch_feature_complete.py --write
python3 projects/pharos/scripts/sync_web_data.py
python3 projects/pharos/scripts/check_en_leaks.py --all
```

스펙·훅: `drafts/media-2026-11-28-batch5/`(picks_* · hooks_* · resolved.json · films.json · spec.json · hooks.json · final.py) · `drafts/bulk-2026-11-28-batch9{,b,c}/spec.json` · `drafts/encyclopedia-2026-11-28-batch9/curated.py`
