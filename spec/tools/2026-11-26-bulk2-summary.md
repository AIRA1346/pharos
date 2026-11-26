# 파로스 2차 대량 적재(330종+) — 실측·판단 기록 (2026-11-26, v13)

## 규모
- 도메인 3 · 대분류 **34**(+12) · 비교군 **45**(+12) · **352종**(210 → 352, **+142**)
  - `verified` 107종(사람이 약관·과금·문장까지 검토) · `auto_fact` **245종**(공개 API 사실만)
- 이번 배치: 신규 비교군 12개의 **124종** + 기존 7개 비교군 보강 **18종** = **142종**
- 신규 대분류 12: `open-world-adventure` · `sandbox-creative` · `action-fighting` · `rhythm-music`
  · `casual-puzzle` · `competitive-online`(게임) · `social-community` · `streaming-ott` · `health-fitness`
  · `learning-languages` · `music-audio` · `office-docs`(앱)

| 신규 비교군 | 종수 | 추천 | 조건부 | 거름 | 대표 |
| :--- | ---: | ---: | ---: | ---: | :--- |
| 오픈월드 RPG · 어드벤처 | 13 | 6 | 3 | 4 | The Witcher 3 (86.2) |
| 샌드박스 · 크리에이티브 | 12 | 10 | 1 | 1 | Satisfactory (85.8) |
| 격투 · 콤보 액션 | 10 | 4 | 4 | 2 | Devil May Cry 5 (85.2) |
| 리듬 · 음악 게임 | 10 | 6 | 3 | 1 | Beat Saber (85.2) |
| 모바일 캐주얼 · 퍼즐 | 11 | 8 | 2 | 1 | Monument Valley (86.4) |
| 스포츠 · MOBA · 경쟁 | 11 | 1 | 6 | 4 | Dota 2 (81.2) |
| 소셜 · 커뮤니티 | 11 | 4 | 7 | 0 | X (84.9) |
| OTT · 영상 스트리밍 | 9 | 6 | 3 | 0 | Netflix (86.1) |
| 건강 · 운동 · 러닝 | 10 | 8 | 2 | 0 | Headspace (84.5) |
| 언어 · 학습 · 플래시카드 | 9 | 9 | 0 | 0 | Anki (85.9) |
| 음악 스트리밍 · 오디오 · DAW | 9 | 5 | 4 | 0 | SoundCloud (84.8) |
| 오피스 · 문서 · 화이트보드 | 9 | 5 | 4 | 0 | Microsoft Word (86.1) |

기존 비교군 보강 18종 — `fps-shooters`(+4: Team Fortress 2 · Rainbow Six Siege · Battlefield 2042 · THE FINALS)
· `survival-crafting`(+4: Rust · ARK · DayZ · The Forest) · `action-roguelike`(+2: Binding of Isaac: Rebirth · Gunfire Reborn)
· `metroidvania-platformer`(+2: Ori and the Blind Forest · Super Meat Boy) · `turn-based-strategy`(+2: Crusader Kings III · Total War: WARHAMMER III)
· `pc-mmorpg`(+2: ESO · SWTOR) · `mobile-gacha-rpg`(+2: Fate/Grand Order · Azur Lane)

## 1단계 — 자동 중복 방지 가드 (`scripts/bulk_ingest.py`)
- 적재 시작 전 `data/search-index.json` 과 `data/{domain}/*.json` **전체**를 읽어 인덱스를 만든다
  (`load_dup_index` → `build_dup_index`).
  - `ids` — 항목 id → 발견 파일
  - `names` — 이름·별칭을 **소문자·특수문자 제거**로 정규화(norm)한 키 → 항목 id
  - `stores` — 출처 URL 에서 뽑은 스토어 ID 4종: **Steam AppID**(`store.steampowered.com/app/{id}`),
    **App Store trackId**(`apps.apple.com/…/id{trackId}`), **Play 패키지**(`…details?id={pkg}`),
    **GitHub 저장소**(`github.com/{owner}/{repo}` — 소문자·`.git` 제거)
  - 스펙에 `steam_id`·`ios_id`·`play_package`·`github_repo` 가 직접 적혀 있으면 그것도 함께 본다.
  - 검색 인덱스와 비교군 파일이 같은 항목을 두 번 세지 않도록 id 로 중복 제거(기존 352건 = 352 id).
- **두 번 검사한다.**
  1. 수집 전 — id·이름·명시된 스토어 ID 로 스펙 항목을 걸러 **수집 자체를 하지 않는다**.
  2. 수집 후 — 검색어로 확정된 실제 스토어 ID(AppID·trackId·패키지·저장소)로 한 번 더 본다.
     이름이 달라도 같은 제품이면(예: 이름만 다른 리마스터) 여기서 걸린다.
- 스킵은 `↷ 스킵 {id}: {사유}` 로 콘솔에 남고, 실행 로그 JSON 의 `skipped_count`·`skipped[]` 에 사유와 함께 기록된다.
  스킵은 실패가 아니므로 종료 코드에 영향을 주지 않는다.
- 이번 배치 스킵: **0건**(142종 모두 신규).
- 가드 동작 확인(픽스처 `drafts/bulk2-2026-11-26/guard-probe.json`):
  - `witcher-steam-probe`(이름 "The Witcher 3") → `steam ID '292030' 가 기존 항목 'the-witcher-3' 과 같음` **스킵**
  - `spotify-play-probe`(이름 "Music Probe") → `play ID 'com.spotify.music' 가 기존 항목 'spotify' 과 같음` **스킵**
  - `anki-dupe-probe` → `github ID 'ankitects/anki' 가 기존 항목 'anki' 과 같음` **스킵**
  - 이미 적재된 배치를 다시 돌리면 **142종 전량 스킵**(id 중복) — 같은 배치를 여러 번 돌려도 중복이 생기지 않는다.
- `schema/validate.py` 보강 — `duplicate_item_errors()` 로 **비교군 파일 전체**에서
  ① 항목 id, ② 정규화 이름(이름+별칭), ③ 스토어 ID(steam·appstore·play·github) 중복을 검사하고 1건이라도 있으면 FAIL.
  음성 테스트(이름·스토어 ID 가 같은 항목을 복제하면 차단)도 매 실행에 포함. 현재 352건 중복 0건.

## 2단계 — 실측 수집
| 단계 | 실측 |
| :--- | :--- |
| 콜드 수집(워커 8, 캐시 없음) | 142종 **56.0초** · HTTP **642회**(항목당 0.39초) |
| 재수집(캐시) | 142종 **8.9초**(HTTP 18회 · 캐시 658회) |
| 아이콘 142건 192×192 webp | **26.8초** |
| 기록 포함 합계(캐시 상태) | **36.9초** |

- 소스 분포(항목 수, 중복 포함): Steam **71**(SteamSpy 67 보조) · Google Play **60** · App Store **51** · GitHub **7**
- 캐시: `drafts/bulk2-2026-11-26/cache/` (URL 해시 gzip) — iTunes 검색 API 는 분당 요청이 몰리면
  429/403 을 돌려주므로 첫 실행에서 8종이 실패했고, 재실행에서 7종이 회복됐다(1종은 Steam 목록에서 내려간 게임).

## 3단계 — 검증·배포
- `sync_web_data.py`: `search-index.json` 재생성(352건 · gap 4건) + `web/` 사본 동기화 + 검증
- `validate.py`: **PASS** — 352건 스키마 100% · 의미 규칙 0 · 계층 3/34/45 · id·이름·스토어 ID 중복 0
  · 판정 재계산 일치 · 음성 27/27 · 완결작 9/9 · 강도 3단계 10/10 · 아이콘 **352/352** · 영문 **352/352** · web/ 사본 일치
- `check_en_leaks.py --all`: **352건 · 한글 남은 경로 0개**
- `smoke_v13.py`(신규, 배치용): **59/59 PASS** — 홈 352건·비교군 45·featured 블록, 이번 배치 19개 비교군
  카드 수·`자동 수집` 배지·192px 아이콘, auto_fact 상세 안내(검증 완료엔 없음), EN 한글 0, 390px 넘침 0,
  콘솔·HTTP 오류 0. 건수는 카탈로그·인덱스에서 계산하므로 다음 배치에도 낡지 않는다.
- 배포: `web/` → `AIRA1346/pharos` `main` 루트, 스크립트·문서 → `spec/tools/`. 라이브 확인 + 스크린샷 2장
  (`live/live-v13-bulk2-home.png`, `live/live-v13-bulk2-arena.png`).

## 판정 (v0.5.0 · 0.50/0.25/0.25 · 이번 배치 142종)
- 추천 **80** 🟢 · 조건부 **47** 🟡 · 거름 **15** 🔴
- 거름 15건은 전부 `stale_over_12m` + `maintenance_status=stale_unknown`(12개월 넘게 새 공지·릴리스 없음):
  Ori and the Blind Forest · Project DIVA Mega Mix+ · Call of Duty: Warzone · Football Manager 2024 · WWE 2K24
  · Pro Cycling Manager 2024 · Horizon Zero Dawn · Ghost of Tsushima · God of War · AC Odyssey · Mini Metro
  · KOF XV · Granblue Fantasy: Versus · Kerbal Space Program · The Forest.
  완결작 선언 원문을 확인하지 못해 심층 리뷰 전까지는 거름으로 둔다(기존 배치와 같은 규칙).
- 스포츠·경쟁(추천 1)은 연간 시리즈라 최근 공지가 끊긴 항목이 많고, Warzone(Steam 28% 긍정)·Football Manager 2024(23%)
  처럼 사용자 축이 낮은 항목이 섞여 있다.

## 이번에 내린 판단
- **Rocket League 제외 → Call of Duty: Warzone**: Rocket League 는 Epic 이전 이후 Steam 검색에 잡히지 않는다
  (공개 스토어 API 소스 없음). 경쟁 슈터·배틀로얄 대표작으로 Warzone 을 넣었다.
- **NBA 2K25 → NBA 2K26**: 2K25 는 새 시즌판 출시 후 Steam 목록에서 내려가 검색되지 않는다(2K26 AppID 3472040 로 확정).
- **치지직(CHZZK)**: Play 패키지가 `com.navercorp.game.android.community`(NAVER Corp.)임을 확인해 적재.
  App Store 검색은 한국어 앱명("치지직")만 잡혀 영문 이름으로 확정되지 않아 **Play 단일 소스**로 두었다.
- **영문 오버레이 한글 누출 3건 수정**: 카카오톡·치지직·스픽은 스토어 레코드가 한국어(장르·가격 표기·앱 이름)라
  영문 화면에 한글이 남았다. `bulk_ingest.py` 가 iOS 항목에서 **미국 스토어 레코드를 영문 표기에 우선 사용**하고
  (`en_safe()` — 한글이면 항목 이름으로 대체), 장르·가격 표기·출처 제목·업데이트 제목을 모두 영문으로 만든다.
  세 항목을 지우고 해당 코드로 다시 적재해 `check_en_leaks.py --all` 0건을 확인했다.
- **DaVinci Resolve·League of Legends·Fortnite 제외**: Steam·App Store·Play·GitHub 어디에도 공개 API 소스가 없다.
- **Anki 가격 표기**: iOS(AnkiMobile) $24.99 가 대표 티어로 잡히고 데스크톱·안드로이드는 무료다.
  자동 단계는 iOS 티어를 먼저 기록하는 기존 구조를 그대로 쓴다 — 심층 리뷰에서 무료 경로를 티어로 추가한다.

## 확인하지 못한 것(순차 심층 검수 대상)
- 확률형 상품·배틀패스·구독 구조와 무과금 한도(이번 142종 전부 `unknown`)
- 계정 필수 여부(특히 소셜·스트리밍·오피스 앱), 데이터 수집·내보내기 범위
- OTT 지역 카탈로그·광고 요금제, 피트니스 구독 뒤에 잠긴 기능
- `feature_complete` 선언 원문(거름 15건), 최근 업데이트의 성격(패치인지 공지인지) — Steam 공지 제목 기반 추정
