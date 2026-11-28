# 2026-11-28 8차 대량 적재 367종 — 배치 요약

## 결과

| 도메인 | 이전 | 이후 | 순증 | 추천 | 조건부 | 거름 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 영화 movie | 175 | 269 | +94 | 219 | 49 | 1 |
| 애니 anime | 175 | 262 | +87 | 138 | 123 | 1 |
| 만화 manga | 175 | 257 | +82 | 89 | 164 | 4 |
| 게임 game | 835 | 892 | +57 | 252 | 530 | 110 |
| 앱 app | 664 | 695 | +31 | 128 | 548 | 19 |
| AI ai | 48 | 64 | +16 | 10 | 46 | 8 |
| **합계** | **2,072** | **2,439** | **+367** | **836** | **1,460** | **143** |

- 사전(encyclopedia) 168 → **188종**(신규 20종) · 관련작 233 → **256개**
- 등대 139종 · 271목표(변동 없음) · 아이콘 2,439/2,439 · 영문 2,439/2,439

## 수집 소스

- **애니·만화** — AniList GraphQL: `averageScore`·`stats.scoreDistribution` 합(채점 표본)·`status`·`format`·`episodes`/`chapters`/`volumes`·`studios`/`staff`·`coverImage.extraLarge`·`genres`. 30요청/분 제한 → 4개 묶음 + 2.6초 간격, 429/403 지수 백오프.
- **영화** — Letterboxd 영화 페이지 JSON-LD: `aggregateRating.ratingValue`(5점)·`ratingCount`·`director`·`genre`·`dateCreated`·포스터.
- **게임** — Steam storesearch→appdetails(ko/en)·상점 평가 요약·ISteamNews·SteamSpy. `PHAROS_STEAM_PACE` 로 요청 간격 조절.
- **앱** — Google Play JSON-LD(평점·평가 수·업데이트·광고 표기·og:image) · App Store iTunes search/lookup.
- **AI** — GitHub 저장소(라이선스·스타·최근 푸시·아카이브) · 스토어 레코드가 있는 도구는 Play/iTunes.

## 이번 배치에서 고친 것

1. **`media_ingest.py` v1.3 — 스펙 `arena` 우선** : 장르 태그가 여러 비교군에 걸치는 작품(코미디 태그가 붙은 소년 액션, 전쟁 태그가 붙은 로맨스 드라마)을 사람이 제자리에 둘 수 있게 했다. 263종은 `drafts/media-2026-11-28-batch4/arena_map.py` 에서 하나씩 지정.
2. **`smoke_v26`·`smoke_v31` 건수 단언을 데이터 계산식으로** : `175`·`2,072` 같은 고정 수치를 카탈로그·비교군 파일 합계로 바꿔 다음 배치에서도 낡지 않게 했다.
3. **완결형 패키지 게임의 stale 거름 해소** — 이번 배치 게임 28종이 '12개월 새 소식 없음'으로 거름이 됐는데, 그중 Steam 상점 분류가 Single-player 단독인 12종과 본편이 끝난 1회 구매작(온라인은 선택 모드) 11종을 `maintenance_status=feature_complete` 로 면제해 조건부로 올렸다(Half-Life · TEKKEN 7 · Far Cry 3 · Nioh · BattleTech 등). 거름 32 → 9(조커 2 · 불새 · SD WebUI Forge · Overcooked AYCE · KeyWe · PICO PARK 2 · Sniper Elite: Resistance · Samsung Notes · nPlayer).
4. **자동 조립 사전 블록 정리** : `은(는)`·`A animated` 같은 조립 문구가 남는 자동 블록을 신규 334종에서 걷어내고, 대표작 20종만 사람이 쓴 블록을 남겼다. 나머지는 상세 모달의 기본 제원 폴백 뷰.

## 확인하지 못한 것 (지어내지 않고 남김)

- 연재·방영 중 작품의 최근 화 공개일 · 한국 시청 가능 플랫폼 · 작품 단위 가격 → `data_quality.unverified`, `tier.price.amount: null`
- 이번 367종의 확률형·구독·계정·데이터 수집 판단 → `unknown` (심층 검수 대기)
- 영화 사용자 축은 Letterboxd 단일 표본(서구·시네필 편중)

## 재현

```bash
python3 projects/pharos/scripts/media_ingest.py --merge \
    --spec projects/pharos/drafts/media-2026-11-28-batch4/spec.json \
    --hooks projects/pharos/drafts/media-2026-11-28-batch4/hooks.json
python3 projects/pharos/scripts/media_ingest.py --icons-only --spec ... --hooks ...
python3 projects/pharos/scripts/bulk_ingest.py --spec projects/pharos/drafts/bulk-2026-11-28-batch8/spec.json
python3 projects/pharos/drafts/encyclopedia-2026-11-28-batch8/apply.py
python3 projects/pharos/scripts/sync_web_data.py
python3 projects/pharos/scripts/check_en_leaks.py --all
```

스펙·훅: `drafts/media-2026-11-28-batch4/`(spec · hooks · arena_map · works · films.json) ·
`drafts/bulk-2026-11-28-batch8{,b,c}/spec.json` · `drafts/encyclopedia-2026-11-28-batch8/curated.py`
