# 파로스 5차 대량 적재(1,000종 돌파, 1,189종) — 실측·판단 기록 (2026-11-26, v16)

## 규모
- 도메인 3 · 대분류 **61**(+7) · 비교군 **73**(+7) · **1,189종**(867 → 1,189, **+322**)
  - `verified` 107종(사람이 약관·과금·문장까지 검토, 변동 없음) · `auto_fact` **1,082종**(+322)
- 이번 배치: **신규 비교군 7개의 90종** + **기존 40여 개 비교군 보강 232종** = 322종
- 신규 대분류 7: `visual-novel` · `management-automation` · `arcade-retro`(게임)
  · `streaming-capture` · `audio-production` · `travel-mobility` · `ai-writing-research`(앱)

| 신규 비교군 | 종수 | 추천 | 조건부 | 거름 |
| :--- | ---: | ---: | ---: | ---: |
| 비주얼 노벨 · 인터랙티브 스토리 | 13 | 3 | 10 | 0 |
| 경영 · 자동화 · 공장 건설 | 13 | 6 | 6 | 1 |
| 아케이드 · 리듬 · 클래식 | 15 | 4 | 9 | 2 |
| 화면 녹화 · 방송 · 스트리밍 | 10 | 2 | 7 | 1 |
| 음악 제작 · DAW · 팟캐스트 | 13 | 4 | 8 | 1 |
| 교통 · 숙박 · 항공 · 모빌리티 | 14 | 1 | 13 | 0 |
| AI 글쓰기 · 리서치 · 전사 | 12 | 1 | 11 | 0 |

이번 322종 판정: 추천 **65** · 조건부 **230** · 거름 **27**.
전체 1,189종: 추천 **344** 🟢 · 조건부 **748** 🟡 · 거름 **97** 🔴 (직전 237건에서 140건 감소 — 2단계 완결작 정리 효과).

---

## 1단계 — 신규 적재와 중복 가드
- 스펙 후보 **322종** → 최종 생성 **322종**, **실패 0**.
- 중복 가드 스킵 **2건**(첫 실행) — 둘 다 손으로 해결했다.
  - `vaultwarden`: 기존 `bitwarden` 이 별칭으로 `Vaultwarden` 을 이미 갖고 있어 스킵 → **스펙에서 제외**(Bitwarden 호환 서버라 중복 판단이 타당).
  - `firefly-iii`: 별칭 `파이어플라이` 가 `adobe-firefly` 의 별칭과 같아 스킵 → 별칭을 `파이어플라이 III` 로 바꿔 적재.
- 수집 뒤 확정 스토어 ID 2단계 가드에서 추가 스킵 0건. `validate.py` 전체 중복 검사 1,189건 · 0건.

### 처음부터 다시 고른 항목(수집 레코드가 의도한 앱이 아니었던 것)
| 스펙 id | 문제 | 조치 |
| :--- | :--- | :--- |
| `postman` | App Store 검색이 다른 개발자의 `API Inspector for Postman` 을 집음 | **Hoppscotch**(GitHub `hoppscotch/hoppscotch`)로 교체 |
| `notebooklm` · `consensus` · `jenni-ai` · `jasper-ai` | 공식 앱이 없거나 동명의 서드파티 앱이 잡힘 | **SciSpace** · **Kimi** · **alphaXiv** · **Sudowrite** 로 교체 |
| `castro` · `snipd` | `Castro Model LTD.`(의류) · `Snipd - Hairstyle Try On` 이 잡힘 | 실제 앱 표기(`Castro: Podcast App & Player` · `Snipd | AI Podcast Player`)로 교체 |
| `n-plus-plus` | Steam 검색이 `N++` → **NBA 2K27**(appid 4356430)을 확정 | **VVVVVV** · **Hotline Miami** 로 교체 |
| `urbackup` | GitHub 조직 아바타가 334B 빈 이미지 → 아이콘 검사 실패 | **Pika Backup** · **Timeshift** 로 교체 |
| `camtasia` | iOS 에 Camtasia 앱이 없음(동일 개발사 `TechSmith Capture` 만 존재) | `TechSmith Capture` 로 표기 |
| `snowbreak` · `whiteout-survival` 등 13종 | Play 패키지 오기(404) | Play 스토어 검색으로 실제 패키지 확인 후 수정 (`com.seasun.snowbreak.google` · `com.gof.global` · `com.my.defense` · `com.prism.live` · `kr.co.nowcom.mobile.afreeca` · `com.hcom.android` · `com.fiton.android` · `com.lumiunited.aqarahome.play` · `com.frograms.watcha` · `com.coupang.mobile.play` · `tv.plex.labs.plexamp` · `com.dci.magzter` · `com.scribd.app.reader0` · `com.coupang.mobile.eats`) |
| `okami-hd` | Steam 표기가 `Okami HD`(장음 없음)라 `ŌKAMI HD` 로 확정 실패 | 이름을 `Okami HD` 로(별칭에 `ŌKAMI HD`) |

### 스크립트 수정 2건
1. **Play 메타데이터의 `\u0026` 이스케이프** — Google Play JSON-LD 가 `&` 를 `\u0026` 로 남겨 개발사가 `Castbox.FM - Radio \u0026 Podcast …` 처럼 저장됐다. `json_unescape()` 를 넣어 실제 문자로 되돌린다(castbox·podbean·podcast-addict 재생성 확인).
2. **Steam 요청 간격** — `PHAROS_STEAM_PACE` 환경변수(초)로 `store.steampowered.com` 요청을 최소 간격만큼 벌린다. 기본 0(기존 동작 유지). 이번 배치는 1.0~1.1초로 돌려 429 없이 163종을 끝냈다.

## 2단계 — 완결형 싱글플레이 `stale_over_12m` 정리(140건)
- 남아 있던 `stale_unknown` 거름 게임 189종 중, **Steam 상점 분류가 `Single-player` 단독**(멀티플레이·협동·PvP·MMO 분류 없음)인 **138종**과, 온라인 협동이 선택 모드인 완결작 **2종**(Dark Souls III · Dark Souls II: SotFS)에 `maintenance_status=feature_complete` 를 기록했다.
- 근거는 `check_steam_categories.py` 가 Steam appdetails(`filters=basic,categories`)로 받아 `steam-categories.json` 에 남긴 **상점 분류(등급 A)** 다. 온라인 요소가 있는 2종만 등급 B.
- 원자료 `flags.stale_over_12m` 은 **사실 그대로**(`yes`) 두고, 티어 기록만 `exempt` + 사유로 바꿨다. 축 점수는 기준표 4.1절대로 올리지 않았다(객관 축의 12개월 공백 감점 유지).
- 결과: 거름 **237 → 97**, 140종이 **조건부**로 올라왔다(자동 단계의 AI 검토 축이 잠정값 56.5라 2개 노란불 → 추천까지는 가지 않는다).
  - 대표: Portal 77.88 · Half-Life 2 77.3 · Undertale 77.75 · Persona 4 Golden 77.3 · Sekiro 75.05 · God of War 76.75 · Dark Souls III 76.12 · Outer Wilds 76.2 · Spiritfarer 76.12
- **일부러 남긴 것**(온라인·협동·PvP 분류가 있는 작품): `Superliminal`(Steam 이 Multi-player·PvP 로 분류 — 최근 협동 업데이트), `Stardew Valley`(협동), `Cuphead`(협동), `Spiritfarer`(협동), `Halo: MCC`·`Titanfall 2`·`DOOM Eternal`(온라인 PvP), `Assetto Corsa` 계열·`EA SPORTS WRC`·`NFS Heat`(온라인 레이싱), `WWE 2K24`·`Golf With Your Friends`(온라인 대전), `GTFO`·`It Takes Two`·`Gang Beasts`(싱글 플레이 없음), `Nioh 2`·`CODE VEIN`·`Remnant II`(온라인 협동 중심) 등 69종.
  - `Superliminal` 은 지시서 예시에 있었지만, Steam 분류가 PvP·협동을 표기하고 있어 "완전 오프라인 완결작"으로 단정하지 않았다(심층 검수 대상으로 남김).
- 모바일 전용 항목(`The Room` · `BADLAND 2` · `Little Alchemy 2` · `Neural Cloud`)은 12개월 이상 업데이트가 없는 **OS 호환성 위험**이 있어 면제하지 않았다.

## 3단계 — 실측 수집
| 단계 | 실측 |
| :--- | :--- |
| 비 Steam 157종(Play·App Store·GitHub) | 56.3초(아이콘 49.5초 포함) · 실패 19 → 원인 수정 후 26종 재수집 17.1초 · 실패 0 |
| Steam 163종(1차, 워커 6) | 1차 시도에서 appdetails **429** 로 112종 실패 |
| Steam 재수집(청크 30종 · `PHAROS_STEAM_PACE=1.1`) | 18.9 + 8.1 + 8.0 + 88.3 + 141.9 + 56.6초 · 429 0건 |
| 나머지 재생성(Okami HD · Pika/Timeshift · castbox 3종 · VVVVVV/Hotline Miami) | 6.2 + 2.6 + 1.3 + 11.7초 |
| 합계 | **322종 약 417초**(항목당 1.3초), Steam 요청은 간격을 두고 429 없이 완료 |

- 소스 분포(스펙 322종): Steam **164** · Google Play **58** · App Store **42** · GitHub **58**
- GitHub 57개 저장소는 `gh`(인증, 시간당 15,000회)로 `prime_github.py` 가 캐시를 미리 채워 무인증 60회 한도를 피했다(58/58 캐시, briar·revolt 저장소 표기는 실패 후 `briar/briar`·`revoltchat/desktop` 으로 정정).

## 4단계 — 검증·배포
- `sync_web_data.py`: `search-index.json` 재생성(1,189건 · 비교군 73) + `web/` 사본 동기화 + 검증
- `validate.py`: **PASS** — 1,189건 스키마 100% · 의미 규칙 0 · 계층 3/61/73 · 판정 재계산 일치 · 음성 테스트 27/27 · 완결작 면제 9/9 · 강도 3단계 10/10 · 아이콘 **1,189/1,189** · 영문 **1,189/1,189** · web 사본 일치
- `check_en_leaks.py --all`: **1,189건 · 한글 남은 경로 0개**
- `smoke_v16.py`(신규): 로컬 **68/68 PASS**, 라이브 **68/68 PASS**
  - 홈 1,189건·비교군 73·featured 블록, 이번 배치 15개 비교군(신규 7 + 보강 8) 카드 수·`자동 수집` 배지·192px 아이콘, auto_fact 상세 안내(검증 완료엔 없음), **완결작 면제 항목(Portal)이 거름이 아니고 상세에 '면제' 사유 표시**, EN 8개 비교군 한글 0·빈 개발사 깨짐 없음, 390px 넘침 0, 콘솔·HTTP 오류 0
- 배포: `web/` → `AIRA1346/pharos` `main` 루트, 스크립트·문서 → `spec/tools/`. 커밋 `7256ce6`(389파일: 신규 비교군 7개 데이터 파일 + 아이콘 322장 + 카탈로그·인덱스·영문 번들).
- 라이브 확인: 푸시 후 라이브 인덱스 **1,189건 · 73비교군**(2회 폴링 만에 반영) → `smoke_v16.py --live` **68/68 PASS**
  스크린샷 `live/live-v16-1000-home.png`(1,189건 · 73비교군 · 신규 3블록) · `live/live-v16-1000-arena.png`(아케이드 · 리듬 · 클래식 15종, 완결작 배지)

## 남은 것(심층 검수 대상)
- **온라인 분류가 있는 완결작 69종** — Steam 분류만으로 단정하지 않았다. 개별 확인 후 `feature_complete` 여부를 정할 수 있다.
- **모바일 전용 4종**(The Room · BADLAND 2 · Little Alchemy 2 · Neural Cloud) — 최신 OS 호환성 확인 필요.
- 교통·숙박 비교군 14종 전부 조건부 — 예약 수수료·취소 규정·위치/결제 정보 수집 범위가 아직 `unknown`.
- 확률형 상품·구독 구조, AI 도구의 학습 이용·출처 표시(이번 322종 전부 `unknown`).
- `camtasia` id 로 적재된 `TechSmith Capture` — id 와 표기가 다르다(화면에는 표기만 노출). 다음 정리 때 id 변경 후보.
