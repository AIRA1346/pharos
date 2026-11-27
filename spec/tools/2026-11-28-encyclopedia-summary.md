# 2026-11-28 사전(encyclopedia) 기반 — 대표작 168종 백필 배치 요약

## 결과

| 도메인 | 종수 | 사전 제원 평균 | 관련작 |
| :--- | ---: | ---: | ---: |
| game 🎮 | 64 | 7.4개 | — |
| media 🎬 (애니 25 · 만화 25 · 영화 25) | 75 | 7.8개 | — |
| app 📱 | 22 | 5.1개 | — |
| ai 🤖 | 7 | 5.3개 | — |
| **합계** | **168** | **7.2개**(최소 3 · 최대 8) | **233개** |

- 카탈로그 전체 2,072종 중 168종에 사전 원고. 나머지 1,904종은 사전 없이도 상세 모달의 **기본 제원 폴백 뷰**
  (`one_liner` · 개발사 · 출시 · 장르 · 플랫폼 · 수집 출처)로 같은 자리에서 보인다.
- 관련작 233개 관계: 같은 자리의 대안 160 · 같은 시리즈 45 · 원작·매체화 13 · 후속작 8 · 전편 7.
- 공식·참고 링크 42개(큐레이션 링크 + `steam_enrich.json` 의 Steam 공식 사이트).

## 구성

- **사람이 쓴 원고** — `curated.py` (애니 25 · 만화 25 · 영화 25 · 게임 64 · 앱 22 · AI 7). 개요 2~3문장,
  핵심 특징 3줄, 도메인별 추가 제원(원작·연재처 등), 관련작, 공식 링크.
- **수집 사실** — 게임·앱·AI는 플랫폼 · 한국어 지원 · 모드 · 가격 · 평가 · 출시 · 최근 업데이트,
  미디어는 제작 · 분량 · 방영·출간 · 장르 · 감상 경로 · 평가. 값은 `data/{domain}/{arena}.json` 과
  `steam_enrich.json`(Steam 49종 재확인: 표시 언어 · 상점 분류 · 공식 사이트)에서만 가져온다.
- **미디어 분량** — `arena_notes` 의 형식 구간(`TV 25화 (2013)` · `만화 224화·29권` · `영화 148분`)을 그대로 읽는다.
  75종 중 62종이 분량 표기 보유(나머지 13종은 원본에 분량 표기가 없다 — 지어내지 않음).
- **KO/EN** — 같은 구조를 `data/en.json` 오버레이에 함께 쓴다. 영어 장르·개발사·가격은 영문 번역본 값,
  분량은 영문 `arena_notes` 표기(`TV, 25 episodes (2013)` · `169 min`)를 옮긴다.

## 확인하지 못한 것

- 미디어 13종의 화수·권수·상영 시간 → 원본 수집값 없음(분량 행 생략).
- 한국에서 시청·열람 가능한 플랫폼과 작품 단위 가격 → `unverified` 유지(기존 미디어 배치와 동일).
- 1,904종의 사전 원고 미작성 → 폴백 뷰로 표시.

## 재현

```bash
python3 projects/pharos/scripts/enrich_encyclopedia_facts.py     # Steam 언어·분류·사이트 49종
python3 projects/pharos/scripts/backfill_encyclopedia.py --dry-run
python3 projects/pharos/scripts/backfill_encyclopedia.py
python3 projects/pharos/scripts/sync_web_data.py
python3 projects/pharos/scripts/check_en_leaks.py --all
python3 projects/pharos/scripts/smoke_v30_encyclopedia.py --live --shots-dir projects/pharos/live
```
