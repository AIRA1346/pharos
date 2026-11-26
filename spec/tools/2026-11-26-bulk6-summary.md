# 파로스 6차 대량 적재(1,400종 돌파, 1,467종) — 실측·판단 기록 (2026-11-26, v17)

## 규모
- 도메인 3 · 대분류 **64**(+3) · 비교군 **80**(+7) · **1,467종**(1,189 → 1,467, **+278 순증**)
  - `verified` 107종(변동 없음) · `auto_fact` **1,360종**(+278)
- 이번 배치: **신규 비교군 7개의 81종** + **기존 30여 비교군 보강 197종** = **278종**
- 신규 대분류 3: `reading-comics` · `habit-focus`(앱) · `sports-management`(게임)

| 신규 비교군 | 종수 | 추천 | 조건부 | 거름 |
| :--- | ---: | ---: | ---: | ---: |
| 웹툰 · 만화 · 전자책 서비스 | 13 | 1 | 12 | 0 |
| 습관 · 집중 · 타이머 | 12 | 4 | 8 | 0 |
| 2단계 인증 · OTP · 인증기 | 10 | 0 | 10 | 0 |
| 마인드맵 · 다이어그램 · 화이트보드 | 10 | 0 | 10 | 0 |
| 커뮤니티 · RSS · 뉴스레터 | 12 | 0 | 12 | 0 |
| 모바일 · 크로스플랫폼 MMORPG | 12 | 0 | 11 | 1 |
| 스포츠 매니저 · 구단 운영 | 12 | 0 | 11 | 1 |

이번 278종 판정: 추천 **21** · 조건부 **229** · 거름 **28**.
전체 1,467종: 추천 **365** 🟢 · 조건부 **977** 🟡 · 거름 **125** 🔴(직전 97 → 125, 이번 배치의 12개월 공백 게임이 더해졌고 2단계에서 34건을 면제로 되돌렸다).

## 계획서와 다르게 판단한 것 — 'TCG'·'리듬'은 기존 비교군 보강으로
계획서는 `digital-tcg-card` · `rhythm-music-games` 를 신규 비교군으로 적었지만, 이미 `card-board-digital`(22종: Hearthstone·MTG Arena·Yu-Gi-Oh! Master Duel·MARVEL SNAP·Shadowverse·Legends of Runeterra…)과 `rhythm-music`(17종: DJMAX RESPECT V·Muse Dash·osu!·Arcaea·Cytus II·Phigros·Taiko…)이 같은 장르를 담고 있었다. 같은 이름의 비교군을 하나 더 만들면 중복 가드가 계획서가 든 후보 대부분을 스킵해 **빈 껍데기 비교군**이 되므로, 이 두 갈래는 **기존 비교군 보강**으로 넣었다(TCG 6종 · 리듬 6종). 신규 비교군은 실제로 비어 있던 7개(앱 5 · 게임 2)로 세웠다.

## 1단계 — 신규 적재와 중복 가드
- 스펙 280종 → 최종 반영 **278종**. 실패 0(교체·재시도 후) · 중복 스킵 3건
  - `trails-through-daybreak`: 이름 별칭 `궤적 시리즈` 가 기존 `trails-in-the-sky-1st-chapter` 와 겹쳐 스킵 → **다른 작품으로 바꾸지 않고 제외**(시리즈 전체를 대표하는 이름이라 단일 작품에 붙이지 않았다).
  - `life-is-strange`: Steam 검색이 준 appid(532210)가 기존 `life-is-strange-2` 와 같아 스킵 → 시리즈 1편의 Steam 등록명이 달라 확인 후 별도 적재 대상으로 남김.
  - `session-focus`: 처음 이름 `Session` 이 메신저 `session` 과 겹쳐 스킵 → 표기 `Session Pomodoro Focus Timer` 로 바꿔 적재.

### 처음부터 다시 고른 항목(수집 레코드가 없거나 다른 제품이던 것)
| 스펙 id | 문제 | 조치 |
| :--- | :--- | :--- |
| `ootp-25` · `pro-cycling-manager-2025` | Steam 검색에 없음(시리즈 최신작만 노출) | **Pro Basketball Manager 2025** · **Cricket Captain 2024** 로 교체 |
| `starsector` · `heaven-burns-red` · `ash-echoes` | Steam 미입점 | **Terra Invicta** · **Duet Night Abyss** · **Persona5: The Phantom X** 로 교체 |
| `nba-2k25` · `tony-hawk-1-2` | Steam 검색에서 내려감(2K26·리메이크 이후) | **EA SPORTS Madden NFL 26** · **skate.** 로 교체 |
| `anno-1404` | 상점 표기가 `Anno 1404 - History Edition` | 검색어를 `Anno 1404` 로 |
| `man-of-medan` | 표기가 `The Dark Pictures Anthology: Man of Medan` | 정식 표기로 |
| `hot-wheels-unleashed-2` | 표기에 `™` 포함 | 검색어 `HOT WHEELS UNLEASHED 2` |
| `ragnarok-x` | iOS 검색 차단 → Play 패키지 `global.thedream.and.rox` 확인 | Play 로 전환 |
| `amie` · `busycal` · `vimcal` | iOS 전용 + App Store API 403 | **TimeTree · Calendly · GroupCal** 로 교체(Play) |
| `moment-pro-camera` · `affinity-photo-2` · `affinity-designer-2` · `marginnote` | iOS 전용 + App Store API 403 | **Blackmagic Camera · Adobe Express · Fotor · Squid** 로 교체(Play) |

### App Store(iTunes) API 차단 — 스크립트 수정 1건
- 이번 배치 중 iTunes Search API 가 **429 → 403(Forbidden)** 으로 IP 를 막았다. 8워커 동시 요청 뒤로는 간격을 1.2~2.5초로 벌려도 403 이 계속돼 iOS 전용 항목 8종이 실패했다.
- `bulk_ingest.py` 에 **`PHAROS_ITUNES_PACE`**(itunes.apple.com 요청 최소 간격)와 **itunes 한정 403 재시도**(2.5초·5초 백오프)를 넣었다(Steam 의 `PHAROS_STEAM_PACE` 와 같은 방식). 그래도 이번에는 차단이 풀리지 않아, iOS 전용 8종은 **Play 스토어에 있는 동등 앱으로 교체**했다(위 표). 다음 배치에서 앱 스토어 항목은 간격을 두고 소량씩 넣는 편이 안전하다.

## 2단계 — 신규 Steam 완결작 `stale_over_12m` 면제(34건)
- `check_steam_categories.py` 로 12개월 공백 게임 **260종**의 Steam 상점 분류를 다시 받아 `steam-categories.json` 에 남겼다(이번 신규 확인 71종 포함).
- 그중 **Single-player 단독** 171종 가운데, 하드 필터가 `stale_over_12m` 하나뿐인 **34종**에 `maintenance_status=feature_complete` 를 기록하고 티어 기록을 `exempt` 로 바꿨다(원자료 `flags.stale_over_12m=yes` 는 사실 그대로, 축 점수도 올리지 않았다).
- 대표: The Wolf Among Us 77.3 · Cobalt Core 76.0 · Snakebird 75.88 · Islets 75.45 · Luck be a Landlord 75.38 · Rise of the Tomb Raider 75.0 · Shin Megami Tensei V: Vengeance 74.38 · My Time at Portia 73.95 · The Mortuary Assistant · Tales of Berseria · Dicey Dungeons · AC Origins · Heavy Rain · F1 Manager 2024 · Anno 2070 …
- **일부러 남긴 것**: Steam 이 Co-op·PvP·멀티 분류를 표기한 85종(Wreckfest · Hot Wheels Unleashed 2 · Just Shapes & Beats · Divinity: Original Sin 2 · Nightingale · Sons of the Forest · Man of Medan(PvP 표기) 등)과 멀티 전용 4종(It Takes Two · GTFO · Gang Beasts · We Were Here).
- **버그 수정**: 면제 항목의 영문 `verdict.one_liner` 가 할인가 표기(`₩47,000 (할인 75% ₩11,750)`)를 그대로 써서 영문 화면에 한글이 새던 문제를 고쳤다(영문 티어의 `price.display` 사용). 12건 재작성.

## 3단계 — 검증
| 항목 | 결과 |
| :--- | :--- |
| `validate.py` | **PASS** — 1,467건 스키마 100% · 의미 규칙 0 · 계층 3/64/80 · 판정 재계산 일치 · 음성 27/27 · 완결작 면제 9/9 · 강도 3단계 10/10 · 아이콘 **1,467/1,467** · 영문 **1,467/1,467** · web 사본 일치 |
| `check_en_leaks.py --all` | **1,467건 · 한글 남은 경로 0** |
| `smoke_v17.py` (신규) | 로컬 **68/68 PASS** |
| 라이브 | (배포 후 기록) |

`smoke_v17.py` 가 확인하는 것: 홈 데이터 칩(1,467건 · 비교군 80 · v0.4.0) · 1,400종 돌파 · 홈 장르 블록에 이번 배치 15개 비교군 노출 · 신규 7개 비교군 카드 수/자동 수집 배지/192px 아이콘 · auto_fact 상세 안내(검증 완료엔 없음) · EN 8개 비교군 한글 0 · EN 자동 수집 배지 · 390px 넘침 0 · 완결작 면제(The Wolf Among Us)가 거름이 아니고 상세에 '면제' 사유 표시 · 콘솔·HTTP 오류 0.

## 실측 시간
| 단계 | 실측 |
| :--- | :--- |
| 청크 1(신규 앱 5비교군 57종) | 27.7초(수집 0.7 · 아이콘 25.7) — 사전 확인으로 캐시 97회 재사용 |
| 청크 2·3(신규 게임 24 + 앱 보강 78 = 102종) | 71.9초(수집 27.8 · 아이콘 41.5) |
| 청크 4(게임 보강 62종) | 15.6초 |
| 청크 5(게임 보강 58종) | 23.5초 |
| 교체·보정 적재(11 + 10 + 9종) | 8.1 + 7.7 + (iOS 재시도 151.7초는 실패) |
| 검증·배포 | `sync_web_data.py` 약 20초 · `smoke_v17.py` 로컬/라이브 각 약 60초 |

## 남은 것(심층 검수 대상)
- iOS 전용 8종은 이번에 Play 대체작으로 바꿨다 — App Store 평점이 있는 원래 앱(Affinity Photo/Designer 2 · MarginNote 4 · Amie · BusyCal · Vimcal · Moment Camera · Ragnarok X iOS)은 차단이 풀린 뒤 별도 배치로 넣을 수 있다.
- 온라인 분류가 있는 완결작 85종 · 모바일 전용 4종(The Room · BADLAND 2 · Little Alchemy 2 · Neural Cloud)은 그대로 심층 검수 대상.
- 이번 278종의 확률형 상품·구독 구조·데이터 수집 범위는 모두 `unknown` — 순차 검수 필요.
- `life-is-strange`(1편)는 Steam 등록명 확인 후 별도 적재.
