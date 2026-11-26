# 파로스 4차 대량 적재(830종+) — 실측·판단 기록 (2026-11-26, v15)

## 규모
- 도메인 3 · 대분류 **54**(+10) · 비교군 **66**(+10) · **867종**(607 → 867, **+260**)
  - `verified` 107종(사람이 약관·과금·문장까지 검토, 변동 없음) · `auto_fact` **760종**(+260)
- 이번 배치: **신규 비교군 10개의 126종** + **기존 39개 비교군 보강 134종** = 260종
- 신규 대분류 10: `puzzle-logic` · `stealth-tactical` · `space-flight` · `jrpg-anime` · `subculture-mobile`(게임)
  · `translation-study` · `design-3d` · `system-utils` · `shopping-life` · `weather-smarthome`(앱)

| 신규 비교군 | 종수 | 추천 | 조건부 | 거름 |
| :--- | ---: | ---: | ---: | ---: |
| 퍼즐 · 두뇌 · 공간 논리 | 14 | 4 | 1 | 9 |
| 애니메이션 · JRPG | 14 | 6 | 3 | 5 |
| 시스템 · 압축 · 파일 · 런처 | 14 | 0 | 14 | 0 |
| 모바일 서브컬처 · 방치형 · 수집 RPG | 13 | 0 | 13 | 0 |
| 잠입 · 전술 액션 | 12 | 2 | 2 | 8 |
| 우주 · 비행 · SF 시뮬 | 12 | 2 | 5 | 5 |
| 3D · CAD · 모델링 · 벡터 | 12 | 3 | 7 | 2 |
| 쇼핑 · 배달 · 중고 · 예약 | 12 | 1 | 11 | 0 |
| 날씨 · 스마트홈 · IoT | 12 | 1 | 10 | 1 |
| 번역 · 필기 · 학습 도구 | 11 | 3 | 8 | 0 |

기존 비교군 보강 134종(39개 비교군) — `web-browsers`(+7: Waterfox · Samsung Internet · Naver Whale 포함) ·
`fps-shooters`(+6) · `action-roguelike`(+6) · `task-managers`(+5) · `metroidvania-platformer`(+5) ·
`dev-terminals-git`(+5) · `open-world-rpg`(+5) · `sandbox-creative`(+5) · `cloud-storage`(+4) ·
`survival-crafting`(+4) · `turn-based-strategy`(+4) · `arpg-hack-slash`(+4) · `soulslike`(+4) ·
`racing-sim`(+4) · `office-suite`(+4) · `horror-thriller`(+4) · `story-narrative-vn`(+4) ·
`password-managers`(+3) · `mobile-gacha-rpg`(+3) · `email-clients`(+3) · `city-builder-management`(+3) ·
`co-op-party`(+3) · `messaging-team`(+3) · `media-players`(+3) · `fighting-action`(+3) ·
`mobile-casual-puzzle`(+3) · `remote-desktop-network`(+3) · 2종씩 보강 12개 비교군.

## 1단계 — 중복 방지 가드
- 스펙 후보 **261종** → 가드 스킵 **1건**: `ankidroid`(Play `com.ichi2.anki` 가 기존 `anki` 와 같은 앱).
- 적재 전 id·정규화 이름·스토어 ID, 수집 후 확정 스토어 ID 2단계 가드 모두 통과. 스펙 내부 id 중복 0.
- 손으로 고친 가드 오탐 1건: `Warp`(터미널)가 Cloudflare WARP 와 이름이 같아 스킵되던 것을 `Warp Terminal` 로 표기해 통과시켰다.
- `validate.py` 전체 중복 검사: **867건 · id/이름/스토어 ID 중복 0건**.

## 2단계 — 실측 수집
| 단계 | 실측 |
| :--- | :--- |
| 콜드 수집(워커 8) | 258종 중 236종 성공 **127.5초** · HTTP **819회**(캐시 60회) |
| 429 복구(워커 2~3, 재시도 3회) | 24종 **48초**(5 + 1 + 18종) — 18/18 회복 |
| 한글 사명 재생성(`--force`) | 한국 전용 앱 5종 **0.8초** |
| 아이콘 260건 192×192 webp | 본배치 83.6초 + 재시도 5.1초 |
| 합계 | **260종 약 178초**(항목당 0.68초) |

- 소스 분포(스펙 261종): Steam **118** · Google Play **94** · GitHub **36** · App Store **13**
- GitHub 37개 저장소는 `gh`(인증, 시간당 5,000회)로 `prime_github.py` 가 캐시를 미리 채워 무인증 60회 한도를 피했다(35/37 캐시).
- Steam 429: 첫 배치에서 17종이 요청 제한에 걸렸고, 약 15분 뒤 워커 2로 재시도해 **18/18 전량 회복**(캐시 덕분에 재시도는 15초).

## 3단계 — 검증·배포
- `sync_web_data.py`: `search-index.json` 재생성(867건 · 비교군 66) + `web/` 사본 동기화 + 검증
- `validate.py`: **PASS** — 867건 스키마 100% · 의미 규칙 0 · 계층 3/54/66 · 판정 재계산 일치 · 음성 테스트 27/27 · 완결작 면제 9/9 · 강도 3단계 10/10 · 아이콘 **867/867** · 영문 **867/867** · web 사본 일치
- `check_en_leaks.py --all`: **867건 · 한글 남은 경로 0개**
- `smoke_v15.py`(신규): **72/72 PASS** — 홈 867건·비교군 66·featured 블록, 이번 배치 18개 비교군 카드 수·`자동 수집` 배지·192px 아이콘, auto_fact 상세 안내(검증 완료엔 없음), EN 8개 비교군+상세 한글 0·빈 개발사 표기 깨짐 없음, 390px 넘침 0, 콘솔·HTTP 오류 0
- 배포: `web/` → `AIRA1346/pharos` `main` 루트, 스크립트·문서 → `spec/tools/`. 커밋 `cadbb3e`(316파일: 신규 비교군 10개 데이터 파일 + 아이콘 260장 + 카탈로그·인덱스·영문 번들).
- 라이브 검증: 푸시 후 라이브 인덱스 **867/66** 확인 → `smoke_v15.py --live` **72/72 PASS**(첫 회차 `fallout-4.webp` 503 일시 오류 1건 → CDN 재조회 200 확인 후 재실행 72/72).
  스크린샷 `live/live-v15-bulk4-home.png`(867건 · 66비교군 · 신규 4블록) `live/live-v15-bulk4-arena.png`(퍼즐 · 두뇌 · 공간 논리 14종).


## 판정 (v0.5.0 · 0.50/0.25/0.25)
- 전체 **867종: 추천 279 🟢 · 조건부 444 🟡 · 거름 144 🔴**
- 이번 260종만: 추천 **36** · 조건부 **163** · 거름 **61**

## 이번에 내린 판단
- **`bulk_ingest.py` 버그 3건 수정**
  1. Play 스토어 페이지를 영어·한국어 따로 받도록 바꿨다. 한쪽 페이지가 없으면(해외 전용·지역 제한) 항목 전체가 실패하던 문제 — 우마무스메(한국 페이지 404)가 이 때문에 실패했다.
  2. 영문 화면에 한글 사명이 새던 경로를 막았다. `developer`·`publisher`·`one_liner`·`arena_notes`·`sources` 제목·업데이트 메모가 한국 스토어의 한글 사명을 그대로 쓰고 있었다(배달의민족·올리브영·코레일톡·SRT·번개장터). 영문 오버레이에 `developer`/`publisher` 를 추가하고, 널리 쓰이는 공식 영문 사명 7개는 사전(`KO_COMPANY_EN`)으로 옮겼다(한국철도공사 → Korea Railroad Corporation (KORAIL), ㈜SR → SR Co., Ltd., 번개장터 주식회사 → Bungaejangter Inc. 등). 사전에 없는 회사는 영문 화면에서 사명을 비워 한글이 새지 않게 했다.
  3. `--force` 플래그를 넣어, 스크립트를 고친 뒤 특정 id만 다시 만들어 덮어쓸 수 있게 했다(가드가 이미 적재된 항목을 스킵해 재생성이 불가능했다).
- **소스가 사라지거나 바뀐 항목은 실제 스토어 표기로 교체**
  - LibraWolf(GitHub 저장소 404) → Waterfox(GitHub `BrowserWorks/waterfox`) + 삼성 인터넷 · 네이버 웨일 추가
  - Pixelmator Pro(iOS 레코드 없음, Mac App Store 전용) → `Pixelmator Classic iOS`
  - 우마무스메 → 글로벌 Play 패키지 `com.cygames.umamusume`
  - Weather Underground → Play 패키지 404, App Store 레코드로 수집
  - 궤적 1st Chapter → 스토어 표기명 `Trails in the Sky 1st Chapter`(풀네임은 별칭으로)
- **구조적 문제(그대로 남김)**: 완결형 싱글플레이 게임은 "최근 1년 패치 없음"이 정상인데도 검증기 규칙상 거름이 된다.
  이번 61건 중 62%(약 38건)가 `stale_over_12m` + `maintenance_status=stale_unknown` 때문이며,
  Portal(98% 긍정) · The Witness · Superliminal · Cocoon · Chants of Sennaar 같은 작품이 여기 들어간다.
  자동 단계에서 근거 없이 완결작으로 단정하지 않는다는 원칙은 유지했고, 심층 검수에서 `feature_complete` 를 기록하면 면제된다.

## 확인하지 못한 것(순차 심층 검수 대상)
- 확률형 상품·배틀패스·구독 구조와 무과금 한도(이번 260종 전부 `unknown`) — 모바일 서브컬처 13종이 특히 중요
- 계정 필수 여부, 데이터 수집·내보내기 범위(쇼핑·배달 12종, 배달앱 위치·결제 정보)
- `feature_complete` 선언 원문 — 위 거름 38건
- 한국 전용 앱(배민·올리브영·코레일톡·SRT·번개장터·당근)의 글로벌 기능 차이
