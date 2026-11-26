# 파로스 3차 대량 적재(500종+) — 실측·판단 기록 (2026-11-26, v14)

## 규모
- 도메인 3 · 대분류 **44**(+10) · 비교군 **56**(+11) · **607종**(352 → 607, **+255**)
  - `verified` 107종(사람이 약관·과금·문장까지 검토, 변동 없음) · `auto_fact` **500종**(+255)
- 이번 배치: **신규 비교군 11개의 신규 169종** + **기존 26개 비교군 보강 86종**
- 신규 대분류 10: `horror-thriller` · `story-narrative` · `life-sim` · `tabletop-card` · `mobile-arcade`(게임)
  · `maps-travel` · `photo-camera` · `finance-money` · `reading-news`(앱) · `ai-media-gen`(AI 도구)

| 신규 비교군 | 종수 | 추천 | 조건부 | 거름 | 대표(가중 점수) |
| :--- | ---: | ---: | ---: | ---: | :--- |
| 공포 · 서바이벌 호러 | 17 | 6 | 4 | 7 | Resident Evil 2 (84.0) |
| 스토리 · 내러티브 · 추리 | 18 | 5 | 2 | 11 | Phoenix Wright: Ace Attorney Trilogy (85.8) |
| 생활 · 농장 · 타이쿤 시뮬 | 18 | 9 | 5 | 4 | Fields of Mistria (84.8) |
| 디지털 보드 · 카드 · 체스 | 17 | 2 | 10 | 5 | Tabletop Simulator (85.75) |
| 모바일 액션 · 아케이드 · 러너 | 15 | 0 | 14 | 1 | Stick War: Legacy (84.47) |
| 지도 · 내비게이션 · 여행 | 14 | 1 | 13 | 0 | Booking.com (84.25) |
| 사진 편집 · 카메라 · 스캔 | 14 | 3 | 11 | 0 | Darkroom (84.53) |
| 가계부 · 금융 · 자산 관리 | 13 | 1 | 12 | 0 | YNAB (84.62) |
| 원격 제어 · 네트워크 · 유틸 | 12 | 1 | 11 | 0 | Shazam (84.7) |
| 전자책 · 만화 · 뉴스 · 팟캐스트 | 16 | 3 | 13 | 0 | AntennaPod (84.7) |
| AI 영상 · 음성 · 음악 생성 | 15 | 1 | 8 | 6 | Suno (85.15) |

기존 비교군 보강 86종(26개 비교군) — `fps-shooters`(+8: Destiny 2 · Warframe · Halo Infinite · Call of Duty: Black Ops 6 ·
Hunt: Showdown 1896 · Ready or Not · Insurgency: Sandstorm · Squad) · `survival-crafting`(+9: Palworld · Enshrouded ·
Sons of the Forest · No Man's Sky · V Rising · Grounded · Green Hell · The Long Dark · Abiotic Factor) ·
`co-op-party`(+5: PAYDAY 3 · Vermintide 2 · GTFO · Human Fall Flat · Pummel Party) · `city-builder-management`(+5: Against the Storm ·
Timberborn · Farthest Frontier · Dyson Sphere Program · The Wandering Village) · `soulslike`(+5: Wo Long · Jedi: Survivor ·
Another Crab's Treasure · CODE VEIN · Thymesia) · `open-world-rpg`(+3: Hogwarts Legacy · Starfield · Days Gone) ·
`turn-based-strategy`(+4: Age of Empires IV · Stellaris · Hearts of Iron IV · Company of Heroes 3) · `pc-mmorpg`(+3) ·
`racing-sim`(+2) · `fighting-action`(+3) · `arpg-hack-slash`(+2) · `sports-competitive`(+1: Marvel Rivals) · `rhythm-music`(+2) ·
`metroidvania-platformer`(+3) · 앱 `web-browsers`(+3) · `messaging-team`(+4: WhatsApp · Zoom · Element · Wire) · `pkm-notes`(+3: Logseq ·
Bear · Anytype) · `task-managers`(+2) · `dev-terminals-git`(+3: kitty · Windows Terminal · Tabby) · `streaming-video`(+4: HBO Max ·
Paramount+ · TVING · Wavve→제외) · `media-players`(+2) · `office-suite`(+2) · `image-editors`(+2) · `pdf-tools`(+2) · `health-fitness`(+1)

## 1단계 — 중복 방지 가드
- `bulk_ingest.py` 의 가드(적재 전 id·정규화 이름·스토어 ID, 수집 후 확정 스토어 ID)가 기존 352종과 겹치는 항목을 자동 스킵.
- 이번 스펙 **255종 전량 신규 → 스킵 0건**. 스펙 내부 id 중복 0(빌더에서 assert).
- `validate.py` 전체 중복 검사: **607건 · id/이름/스토어 ID 중복 0건**.

## 2단계 — 실측 수집
| 단계 | 실측 |
| :--- | :--- |
| 콜드 수집(워커 8) | 255종 중 231종 성공 **106.3초** · HTTP **514회**(캐시 365회) |
| 429 재시도(워커 1, 4~5종씩 5회) | 24종 **39초** · HTTP **118회** — 24/24 회복 |
| 아이콘 255건 192×192 webp | **74.4초**(본배치 68.3 + 재시도 6.1) |
| 합계 | **255종 약 147초**(항목당 0.58초) |

- 소스 분포: Steam **~200** · Google Play **~35** · App Store **~17** · GitHub **14**(AI 음성·영상 오픈소스)
- 사전 확인(`probe3.py`)으로 스펙 255종의 스토어 확정 이름을 먼저 뽑아 잘못된 매칭을 걸러냈다.

## 3단계 — 검증·배포
- `sync_web_data.py`: `search-index.json` 재생성(607건 · 비교군 56 · gap 5건) + `web/` 사본 동기화 + 검증
- `validate.py`: **PASS** — 607건 스키마 100% · 의미 규칙 0 · 계층 3/44/56 · 판정 재계산 일치 · 음성 27/27 · 완결작 9/9 · 강도 3단계 10/10 · 아이콘 **607/607** · 영문 **607/607** · web 사본 일치
- `check_en_leaks.py --all`: **607건 · 한글 남은 경로 0개**
- `smoke_v14.py`(신규): **65/65 PASS** — 홈 607건·비교군 56·featured 블록, 이번 배치 19개 비교군 카드 수·`자동 수집` 배지·192px 아이콘, auto_fact 상세 안내(검증 완료엔 없음), EN 8개 비교군+상세 한글 0, 390px 넘침 0, 콘솔·HTTP 오류 0
- 배포: `web/` → `AIRA1346/pharos` `main` 루트, 스크립트·문서 → `spec/tools/`

## 판정 (v0.5.0 · 0.50/0.25/0.25)
- 전체 **607종: 추천 243 🟢 · 조건부 281 🟡 · 거름 83 🔴**
- 이번 255종만: 추천 **55** · 조건부 **155** · 거름 **45**
  - 신규 비교군 169종(추천 32·조건부 103·거름 34), 보강 86종(추천 23·조건부 52·거름 11)
- 거름 45건의 대부분은 **`stale_over_12m` + `maintenance_status=stale_unknown`**(12개월 넘게 개발사 공지·릴리스 없음 + 완결작 선언 미확인):
  Outer Wilds · Return of the Obra Dinn · The Walking Dead · Danganronpa · Detroit: Become Human · What Remains of Edith Finch ·
  Outer Wilds 계열 스토리 게임 다수, 그리고 GitHub 만 있는 AI 음성 도구(Bark·Coqui TTS·Wav2Lip·SadTalker·Tortoise TTS — 스토어 평점 표본 없음).
- **이번에 드러난 구조적 문제**: 완결형 싱글플레이 내러티브 게임은 "최근 1년 패치 없음"이 정상인데도 검증기 규칙상 거름이 된다.
  이전 배치(15건)보다 비중이 커졌고(169종 중 34종), 심층 검수에서 `feature_complete` 를 기록하면 면제된다.
  자동 단계에서 근거 없이 완결작으로 단정하지 않는다는 원칙은 유지했다.

## 이번에 내린 판단
- **스토어에서 사라졌거나 공개 API 소스가 없는 작품은 대체작으로 교체**
  - MultiVersus(2025 서비스 종료) → Rivals of Aether II · PC Building Simulator 2(Steam 검색 불가) → PC Building Simulator
  - THRONE AND LIBERTY(한국 스토어 검색 결과 없음) → Star Trek Online · Devotion(사운드트랙만 검색) → Layers of Fear
  - Pokemon TCG Live(한국 레코드가 사칭 앱)·Wallet by BudgetBakers·Microsoft Lens·Affinity Photo·Wavve(미국 레코드가 다른 앱) → 각각 Shadowverse·Photoroom·Prisma·WEBTOON·KakaoBank·Money Manager(편한가계부)·PocketBook 으로 대체
- **실제 스토어 표기 반영**: Procreate 는 스토어에 iPhone판만 있어 `Procreate Pocket`, Max→`HBO Max`(2025년 브랜드 복귀),
  Asphalt 9: Legends→`Asphalt Legends`, Halide Mark II→`Halide Mark III`, DaVinci·LoL·Fortnite 는 공개 API 소스가 없어 제외.
- **KakaoMap 패키지 정정**: `com.locnall.KimGiSa` 는 카카오내비였다 → `net.daum.android.map`(카카오맵)으로 바꿔 적재.
- **한글 장르 누출 수정**: TVING(한국 스토어에만 존재)의 장르가 `엔터테인먼트 · 사진 및 비디오`로 영문 화면에 새던 것을
  `bulk_ingest.py` 에 **한글 장르 → 영문 역매핑**(`APPLE_GENRES_EN`)을 넣어 고쳤다. EN 번들 607/607 한글 0 재확인.
- **EPIK 아이콘**: App Store 아트워크가 검정 단색(306B)이라 `validate.py` 아이콘 하한(512B)에 걸렸다 → Play 공식 아이콘으로 대체.
- **Apple Maps 제외**: 독립 앱 스토어 레코드가 없어(내장 앱) 공개 API 로 사실을 만들 수 없다. 지도 비교군은 14종으로 채웠다.

## 확인하지 못한 것(순차 심층 검수 대상)
- 확률형 상품·배틀패스·구독 구조와 무과금 한도(이번 255종 전부 `unknown`)
- 계정 필수 여부, 데이터 수집·내보내기 범위(금융·사진·지도 앱이 특히 중요)
- `feature_complete` 선언 원문 — 위 45건 거름의 대부분
- TVING·티맵처럼 한국 스토어 전용인 앱의 글로벌 기능 차이
