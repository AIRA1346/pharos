# 파로스 Pharos — 정적 웹 v3.4 (4단 탐색 · 장르 추천 중심 · KO/EN 다국어 · 화면·UX·모바일 마감 · 기준표 v0.5.0 · 스키마 v0.4.0)

빌드 도구 없이 **순수 HTML/CSS/ES Module** 만으로 동작하는 파로스 프론트엔드입니다.
서버는 파일만 배포하고, 점수·신호·판정은 전부 브라우저에서 `schema/item.schema.json` 의
`x-pharos.client` 계약대로 실시간 재계산합니다.

v2 는 `plan.md` v2.0 의 2단계(사이트 구조 개편·배포) 결과물이고, v3 는 그 위의 **정보 계층 개편**, v3.1 은 **분야 확장**(앱 할 일·비밀번호, AI 도구)입니다.
**도메인 → 대분류 → 비교군 → 항목** 4단 탐색, 비교군별 분할 데이터 지연 로딩,
1:1 비교 표, 미세조정 드로어, 사실/의견 분리, 대체제 연결, URL 딥링크, 북마크, 방법론 모달을 담았습니다.

v3.4 는 **한국어 + 영어(`KO / EN`)** 를 더했습니다. 헤더 오른쪽 토글로 언어를 바꾸고, 해외 방문자는
브라우저 언어만으로 영어 화면을 봅니다(우선순위: URL `?lang=` → `localStorage` → 브라우저 언어).

v3.5 는 **2단계 발행 구조**를 드러냅니다. 항목에는 선택 필드 `review_tier`(`verified` 기본값 | `auto_fact`)가 있고,
`auto_fact`(공개 스토어·저장소 API 로 대량 적재한 1차 판정)는 카드에 점선 **`자동 수집` 배지**,
상세 모달 상단에 "공개 스토어·저장소 API 데이터 기반 1차 판정이며, 세부 약관·과금 함정은 순차 검수 중" 안내가 붙습니다.
확인하지 못한 값은 지어내지 않고 ⚪(`unknown`)로 두며, 배지·안내 문자열은 `js/i18n.js`(`reviewTier.badge`·`reviewTier.notice`)에 있습니다.

v3 의 원칙 — **"처음엔 장르와 그 장르의 추천, 들어가면 자세한 내용"**:

1. **홈·도메인(앱/게임/AI 도구)** — 장르(비교군) 이름과 함께 그 장르의 추천 항목 3~4개가
   공식 아이콘(44px) · 이름 · 판정 배지(🟢 추천 / 🟡 조건부) · 가중 점수 타일로 바로 보입니다.
   타일을 누르면 상세 모달, 장르 헤더나 `전체 N종 비교 →` 를 누르면 비교군 화면으로 갑니다.
2. **비교군 목록 카드** — 아이콘 · 이름 · 개발사/장르 · 판정 · 가중 점수, 한 줄 요약, 핵심 태그 최대 2개
   (`선택 과금 · 무과금 가능`, `핵심 과금 · 성장 벽`, `완결작` 등)만 남겼습니다.
3. **상세 모달** — 3축 점수·축별 근거·티어별 가격/필터 통과 목록·사실(Fact)/의견(Opinion)은 여기에만 둡니다.

## 실행

```bash
cd projects/pharos/web          # 배포 폴더 그대로
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000/ 접속
```

- `file://` 로 `index.html` 을 직접 열면 `fetch` 가 차단되어 안내 문구가 뜹니다. 반드시 HTTP 로 열어 주세요.
- **이 폴더 하나가 배포 단위입니다.** GitHub Pages 루트에 `web/` 의 내용을 그대로 올리면
  `index.html` → `./js/app.js` → `./data/catalog.json` · `./data/search-index.json` · `./schema/item.schema.json`
  로 모두 해결됩니다. 상위 폴더(`../data`)를 참조하지 않습니다.

## 4단 탐색과 데이터 로딩

| 단계 | 화면 | 데이터 |
| :--- | :--- | :--- |
| 홈 | 컴팩트 히어로 + 검색 · **장르별 추천 타일** · '별점은 높은데 거름 판정' 리포트 · 보관함 | `catalog.json` + `search-index.json` (경량) |
| 1 도메인 | 홈 / 앱 / 게임 / AI 도구 전환 — 도메인 화면도 **장르별 추천 타일**로 시작 | `catalog.domains` |
| 2 대분류 | 생산성·지식관리, 보안·유틸리티, 전략·카드, RPG·수집, 액션·인디, RPG·MMORPG, 모바일 전략·디펜스, 개발·코딩 (칩으로 이동) | `catalog.categories` |
| 3 비교군 | 노트·지식관리, 할 일·일정 관리, 비밀번호 관리, 덱빌딩 게임, 모바일 수집형 RPG, 액션 로그라이크, PC MMORPG, 모바일 전략·디펜스, AI 코딩 에디터·에이전트 — 핵심만 남긴 카드 목록 | `catalog.arenas[].data_file` |
| 4 항목·티어 | 1:1 비교 · 상세 모달(3축·티어·필터·Fact/Opinion) | `data/{domain}/{arena}.json` (그 비교군만 지연 로딩) |

- 홈은 비교군 파일을 **내려받지 않습니다.** 통합 검색·홈 리포트는 경량 인덱스만 읽고,
  비교군을 열 때 해당 `data_file` 하나만 `fetch` 해 캐시합니다.
- 점수 평균·순위·요약은 **오직 같은 비교군 안에서만** 계산합니다. 도메인이나 분야가 다른 항목의 평균을 섞지 않습니다.
- 홈·도메인의 장르 추천 타일(판정·점수)은 `search-index.json` 의 **균형 기본 가중치·기본 필터** 값입니다.
  내 가중치로 바꾸면 비교군·비교·상세 화면이 그 기준으로 즉시 다시 계산됩니다(타일은 기본 기준을 보여 주고, 상세에서 내 기준 판정을 봅니다).
- 타일 한 줄 소개는 `search-index.json` 의 `tagline`(대표 티어의 한 줄)을 씁니다. 타일 이름은 좁은 폭에서
  영어 원어 괄호를 떼고 보여 주며, 전체 이름은 title·상세에 남습니다.

## 파일

```
web/
  index.html            화면 골격 (도메인 탭 · 경로 · 홈/탐색/비교 뷰 · 상세·방법론 모달 · 드로어 · KO|EN 토글)
  styles.css            등대 테마 (다크 기본 / 라이트 토글), 반응형
  js/i18n.js            UI 문자열 사전 KO/EN · 언어 감지·저장 · 숫자·일수 표기 · 정적 마크업 번역
  js/data.js            카탈로그·인덱스 로드, en.json 오버레이 병합, 비교군 파일 지연 로딩/캐시, 통합 검색
  js/engine.js          계산 엔진 — x-pharos.client 계약 (DOM 비의존 순수 함수, 신선도·대체제·완결작 면제)
  js/app.js             상태·라우팅(URL 딥링크)·렌더링·이벤트
  data/catalog.json     도메인·대분류·비교군 정의 + 필터 팩 + 홈 리포트 규칙
  data/search-index.json 경량 인덱스 (자동 생성 — 통합 검색·홈 리포트)
  data/en.json          영문 번들 — 3도메인·10대분류·14비교군·67종 표시 문자열(영어 모드에서만 로드)
  data/app/pkm-notes.json              노트·지식관리 5건
  data/app/task-managers.json          할 일·일정 관리 5건
  data/app/password-managers.json      비밀번호 관리 4건
  data/app/web-browsers.json           웹 브라우저 5건
  data/app/cloud-storage.json          클라우드 스토리지 5건
  data/game/roguelike-deckbuilder.json 덱빌딩 게임 4건
  data/game/mobile-gacha-rpg.json      모바일 수집형 RPG 6건
  data/game/action-roguelike.json      액션 로그라이크 4건
  data/game/pc-mmorpg.json             PC MMORPG 4건
  data/game/mobile-strategy-defense.json 모바일 전략·디펜스 6건
  data/ai/ai-assistants.json           AI 어시스턴트·검색 5건
  data/ai/ai-coding-tools.json         AI 코딩 에디터·에이전트 4건
  assets/icons/        57종 공식 아이콘 192×192 webp + manifest.json(출처·확보 방법)
  schema/item.schema.json  배포용 스키마 사본 (v0.4.0)
  tests/verify_ui.py    Playwright 검증 스크립트
  preview-v3-home.png        홈 — 장르별 추천 타일 (1440px)
  preview-v3-game.png        게임 도메인 — 장르별 추천 타일
  preview-v3-arena.png       비교군 목록 — 핵심만 남긴 카드 (덱빌딩 게임)
  preview-v3-compare.png     1:1 비교 표 (Balatro vs Slay the Spire)
  preview-v3-mobile.png      모바일 비교군 화면 (390px)
  preview-v3-method.png      방법론 모달
  preview-v3-mobile-tune.png 모바일 미세조정 드로어
  preview-v3-mobile-detail.png 모바일 상세 모달
```

원본은 `../data`·`../schema` 이고 `web/data`·`web/schema` 는 배포용 사본입니다(아래 동기화 참고).

## 데이터 동기화 (단일 소스)

```bash
python3 projects/pharos/scripts/sync_web_data.py          # 인덱스 재생성 + 원본 → web/ 복사 + 전체 검증
python3 projects/pharos/scripts/sync_web_data.py --check  # 쓰지 않고 최신 여부만 확인(다르면 종료 코드 1)
```

- `data/search-index.json` 은 **분할 데이터에서 자동 생성**됩니다. 손으로 고치지 않습니다.
- `sync_web_data.py` 는 마지막에 `schema/validate.py` 전체 검증(스키마·카탈로그·의미 규칙·판정 재계산·인덱스 신선도·웹 사본 해시)을 실행합니다.

## URL 딥링크

| 파라미터 | 뜻 | 예 |
| :--- | :--- | :--- |
| `domain` | 도메인 id | `?domain=app` |
| `category` | 대분류 id | `?domain=game&category=strategy-card` |
| `arena` | 비교군 id | `?domain=game&arena=roguelike-deckbuilder` |
| `item` | 항목 id (상세 모달) | `?domain=app&arena=pkm-notes&item=evernote` |
| `compare` | 같은 비교군 2~3개 | `?arena=pkm-notes&compare=joplin,obsidian` |
| `preset` | 가중치 프리셋 | `?preset=ai` |
| `w` | 직접 설정한 가중치(쉼표) | `?w=60,25,15` |
| `filters` | 켠 하드 필터(쉼표) | `?filters=forced_ads,p2w` |
| `strict` | 엄격 모드 끄기 | `?strict=0` |
| `strictmon` | 선택 과금(impact: optional)도 거름 | `?strictmon=1` |
| `lang` | 화면 언어 | `?lang=en` (미지정 시 저장값 → 브라우저 언어) |

`arena` 만 있어도 카탈로그에서 도메인·대분류를 찾아 해석합니다.

## 기능 요약

- **홈 요약 뷰**: 비교군 바로가기 카드(건수·평균·1위), `별점은 높은데 거름 판정` 리포트
  (예: Hero Wars 4.6★ vs 34.6점 — 스토어 별점과 걸린 필터 공개), 통합 검색(이름·별칭·키워드·비교군 라벨),
  보관함(localStorage).
- **첫 화면 경량화**: 기본 `균형 기본` 프리셋. 가중치 슬라이더·하드 필터·엄격 모드는 `내 기준 미세조정` 드로어 안.
  선택한 도메인의 필터 팩(게임 팩 / 앱 팩 / AI 도구 팩)을 먼저 펼칩니다. AI 도구 팩은 같은 9개 필터를
  도메인 문법으로 다시 부르며(`catalog.domains[].filter_labels` — 예: `iap_required_to_progress` → 「불투명 크레딧·한도 함정 제외」),
  스키마·엔진은 그대로 둡니다.
- **1:1 비교**: 같은 비교군 2~3개를 체크 → 점수·축·걸린 필터·스토어 별점·최근 리뷰·수명 단계·신선도를 한 표에.
- **선택 과금 배지(v0.4.0 · v0.4.1)**: 확률형·P2W 상품이 있어도 무과금으로 본편을 즐길 수 있으면(`impact: optional`)
  카드·상세에 「선택 과금 · 무과금 가능」 배지를 붙이고 거르지 않습니다. optional 인지는 **본질 경험 기준**
  (`core_experience`, 기준표 5.2)으로 판단합니다 — 최상위 경쟁·풀돌파가 아니라 그 게임의 본질(예: 니케=스토리)이
  무과금으로 열려 있는지를 봅니다. 상세 08번에 무과금 충분성(`monetization.free_play`)과 근거 등급을 함께 보여 주며,
  미세조정의 `strict_monetization` 을 켜면 상품 존재만으로 거릅니다.
- **상세**: 신선도(`assessed_at` +180일 → `재검토 필요`), **사실(Fact)과 의견(Opinion) 분리**,
  거름·조건부 항목의 **같은 비교군 상위 추천 대체제**, **공유용 요약 복사**, **정정 제보**(GitHub Issue
  `correction.yml`), 보관함 담기.
- **방법론 모달**: 4단 구조·4축·A/B/C 등급·판정 규칙·독립성(어필리에이트·유료 광고 배제) 선언·용어 도움말.
- **공식 아이콘(v2.1)**: 57종 모두 `assets/icons/{id}.webp`(192×192) 공식 아이콘을 가집니다 — 카드 46px,
  상세 모달 54px, 1:1 비교표 32px, 홈 검색·갭 리포트·보관함 26px. 파일은 `scripts/fetch_icons.py` 가
  App Store 아트워크 → 공식 사이트 아이콘/파비콘 → 공식 브랜드 마크 순으로 내려받아 정규화하며,
  출처는 `assets/icons/manifest.json` 에 남깁니다. 파일이 없거나 로드에 실패하면 img 가 숨고
  같은 자리에 이름 첫 글자 이니셜 배지가 남습니다(깨진 이미지 없음).

## 계약 ↔ 구현 대응

| 스키마 `x-pharos.client` | 구현 |
| :--- | :--- |
| `catalog.file` · `search_index` | `data.js` 가 `./data/catalog.json`·`./data/search-index.json` 로드, 비교군 `data_file` 만 지연 로딩 |
| `navigation.levels` | 홈 → 도메인 → 대분류 → 비교군 → 항목 라우터(`app.js`) |
| `freshness.review_after_days` (180) | `engine.freshness` — `재검토 필요` 배지·상세 경고 |
| `axes[]` (라벨·기본 가중치) | 슬라이더·프리셋을 스키마에서 생성(기본 0.50/0.25/0.25 — v0.5.0) |
| `hard_filters[]` + `default_enabled_filters` | 도메인 필터 팩 우선 노출, 켜진 필터 `fail` → 거름, `unknown` ⚪ 주의, `exempt` 면제. `impact: optional` 은 배지로만 |
| `monetization_impact` (levels·inference·strict_toggle·badge) | `engine.tierImpact`·`evaluateTier` 의 optionalFails, 미세조정 `strict_monetization` 토글(기본 OFF), 배지 문구 |
| `verdict_rules` 1~7 | `evaluateTier` — 순서대로 먼저 맞는 규칙, 적용 규칙을 상세에 표시 |
| `score_formula` · `signal_thresholds` | `Σ(w·s)/Σw`(점수 없는 축 제외), 🟢≥75 · 🟡≥50 · 🔴<50 |
| `stale_exemption` · `maintenance_statuses` | 완결작은 `stale_over_12m` → `exempt`, `compat_risk` 시 조건부 경고 |
| `display.alternatives` · `fact_vs_opinion` | 상세 06번 대체제, 02 Fact / 03 Opinion 섹션 |
| `evidence_rules.sample_downgrade` | 최근 표본 < 100 이면 하향 필요 표시 |

### 완결작 면제 규칙

- 원자료 `flags.stale_over_12m` 은 "12개월 넘게 업데이트 없음"이라는 **사실**이고, 필터 **판정**에서만 면제합니다.
- `maintenance_status == "feature_complete"` → `hard_filters.stale_over_12m.status` 를 `exempt` 로 계산·기록하고
  카드에 '완결작' 배지와 '면제 · 완결작' 사유 칩을 보입니다(점수는 바꾸지 않음 — v0.5.0 기준 Inscryption 84.25).
- `abandoned`·`stale_unknown`, 서비스형 앱·라이브 게임의 12개월 이상 중단은 그대로 `fail`(거름)입니다.
- `flags.compat_risk.value == "yes"` 면 추천 대신 **조건부 경고**(규칙 ⑦)입니다.


## v0.5.0 — 평가 배분·표본 규모 검증 (2026-11-25)

- **기본 배분 50/25/25**: 사용자 평가 50% · 객관 25% · AI 25%. 프리셋은 `균형 기본`·`대중 평가 중심`(65/20/15)·
  `쾌적성·노과금 중심`(20/60/20)·**`프라이버시·로컬 중시`**(25/55/20 + `account_required`·`data_collection` 자동)·
  `AI 완성도 중심`(20/25/55) 다섯 가지입니다.
- **표본 규모 검증**: 스키마 계약 `x-pharos.client.sample_scale`. 최근 구간이 등급 C·1,000건 미만인데 스토어 누적이
  등급 A/B·1만 건 이상·최근의 100배 이상·4.4★ 이상이면 최근 값은 방향 신호로만 쓰고 (누적+최근)÷2 로 둡니다(Notion 64→82, Obsidian 82→85).
  과금·약관 변경이 급락과 겹치면(risky_terms) 완화하지 않습니다(Evernote 30 유지). 규칙 대상 항목은
  `score_notes.user_rating` 에 계산 근거를 남기고, 검증기가 메모 없는 항목을 차단합니다.
- **객관 축 비편향**: 클라우드·비공개 소스라는 이유의 감점을 없앴습니다. 객관은 기능 완성도·생태계/연동성·안정성·보안·
  정책/과금 투명성으로 매기고, 로컬·계정·데이터 수집은 `flags` 사실과 필터·프리셋으로만 가릅니다. 같은 사실을
  객관·AI 두 축에서 두 번 깎지 않습니다(Drive AI 72→80, OneDrive 70→77).
- **가중치 0 축은 판정에 세지 않음**: 프로필 전용 `personal_fit` 은 기본 가중치 0이므로 🔴·🟡 개수에 포함하지 않습니다.
  그래서 P1(local-first) 프로필이 기본 화면의 판정을 몰래 끌어내리지 않습니다(Obsidian·Limbus Company 🟢 전환).
- **갭 리포트는 거름(avoid)만**: 제목('별점은 높은데 거름 판정')과 내용을 맞췄습니다. v0.5.0에서 조건부로 올라온
  Gemini·Notion·Drive 는 홈 리포트가 아니라 상세의 조건·한도에 남습니다.

### 확률형·P2W 강도 3단계 (v0.4.0)

- `hard_filters.gacha_random_items`·`p2w` 에 `impact`(`none`/`optional`/`core`)를 적습니다. 값이 없으면 상태에서
  추론합니다(pass→none, fail→core — 보수적 기본값).
- `optional` 은 필터 상태를 `fail` 로 **남긴 채**(상품이 있다는 사실 유지) 거름으로 잡지 않고, 카드·상세에
  「선택 과금 · 무과금 가능」 배지를 답니다. 점수·신호 규칙으로 추천/조건부가 갈립니다(v0.5.0 기준 검은사막 79.5 🟡 · Bloons TD 6 84.5 🟢).
- `optional` 의 근거로 `monetization.free_play.value == "sufficient"`(무과금 충분성)를 요구하고, 검증기가
  `optional` ↔ `sufficient`, `core` ↔ `constrained`·`blocked` 의 일관성을 검사합니다.
- `strict_monetization`(기본 OFF)을 켜면 `optional` 도 상품 존재만으로 거름 — v0.3.1 과 같은 동작입니다.
- **본질 경험 기준(v0.4.1)**: `optional`/`core` 를 가르는 것은 "최상위 경쟁·풀돌파까지 무과금으로 가는가"가 아니라
  "그 게임의 본질적 재미를 무과금으로 온전히 누릴 수 있는가"입니다(기준표 5.2 `core_experience`).
  엔드 경쟁 구간의 돌파 벽·아레나 순위·스킨 가격은 `limits`·`condition_notes` 에 **사실 그대로** 남기고 판정만 본질로 합니다.
  승리의 여신: 니케를 이 기준으로 다시 채점했습니다 — 69.65 🔴 → **81.2 🟢**(사용자 86·객관 68·AI 92, 160벽·아레나 사실 유지).

### 등급 C 필터의 완화 모드

- **엄격 모드(기본)**: 켜진 필터의 `fail` 은 등급과 무관하게 거름 → Evernote 무료 = 🔴.
- **완화 모드(OFF)**: `fail` 근거가 등급 C(또는 미확인)뿐이면 '근거 약함' **조건부 경고**로 내립니다.
  등급 A/B 근거의 `fail` 은 완화 모드에서도 거름입니다 → Hero Wars 는 두 모드 모두 🔴.

## v3.3 — 화면·UX·모바일 마감 (2026-11-25)

첫인상과 탐색 피로, 비교 화면의 가독성, 390px 모바일을 한 번에 다듬었습니다.

- **홈 도메인 필터(점프 바)**: `장르별 추천` 위에 `전체 12 · 앱 5 · 게임 5 · AI 도구 2` 칩을 두고,
  누른 도메인의 장르 블록만 남깁니다. 바는 스크롤해도 상단에 붙어 있어 목록 어디서든 도메인을 바꿀 수 있고,
  뒤로 지나가는 카드는 배경 띠가 가립니다. 홈에서는 의미 없던 `홈` 빵가루 한 글자도 감췄습니다.
- **플로팅 비교 바**: 비교군에서 항목을 체크하면 스크롤 위치와 무관하게 하단에 `N개 선택됨 · 나란히 비교하기 → · 선택 초기화`
  바가 뜨고, 바가 떠 있는 동안 본문 아래 여백과 토스트 위치가 함께 밀립니다. 모바일에서는 2행 그리드(라벨/칩 · 버튼)로 접힙니다.
- **비교 표 가독성**: 첫 열(기준)을 가로 스크롤에도 고정하고, 행마다 우세한 값을 `최고` 배지와 초록 셀로, 점수 차이는 `−2.3`처럼
  표시합니다. 표 위에는 `최고/최저/차이` 한 줄 요약과 모바일용 `↔ 옆으로 밀어 보기` 안내가 붙습니다.
- **🔗 링크 복사**: 비교군 헤더·비교 화면·상세 모달에서 현재 딥링크를 복사하고 `링크를 복사했어요` 토스트로 알립니다.
  (상세 모달은 링크 복사·공유 요약 복사·정정 제보·☆ 보관·닫기 순으로 정리하고, 닫기는 머리 오른쪽 위에 고정했습니다.)
- **모바일 390×844**: 상세·방법론 모달이 화면 폭을 넘지 않도록 backdrop 여백을 없애고, 헤더·도메인 탭·필터 바·
  카드 비교 체크·비교 바 버튼의 터치 영역을 34~40px로 올렸으며, 장르 블록 머리(제목 + 전체 링크 / 건수)의 줄바꿈을 정리했습니다.
- **라이트 테마 대비**: 강조색(빔·바다·초록·노랑·빨강·회색)을 라이트 배경에서 4.2:1 이상으로 다시 잡고,
  기본 버튼은 흰 글자 + 진한 호박색으로, 패널·보더는 조금 진하게 조정했습니다.
- **거름 0건 정리**: 지금 설정에서 거름 항목이 없으면 빨간 점이 붙은 빈 섹션을 숨깁니다(요약 칩의 `거름 0`으로 충분).

## v3.4 — KO / EN 다국어 (2026-11-25)

- **헤더 토글 `KO | EN`**: 테마 토글 옆 세그먼트. 390px에서도 한 줄에 들어가고(가로 넘침 0), 버튼 터치 영역은 34~38px.
- **언어 결정 순서**: ① URL `?lang=ko|en` ② `localStorage`(`pharos-lang`) ③ `navigator.language` — `ko`로 시작하면 한국어, 그 외 모든 해외 브라우저는 영어.
- **전환 시 함께 바뀌는 것**: `<html lang>`, `<title>`, 메타 설명·OG, URL의 `lang`, 🔗 링크 복사 딥링크. 도메인·비교군·비교·프리셋·필터 등 화면 상태는 URL로 유지된 채 다시 열린다.
- **UI 사전 `js/i18n.js`**: 헤더·히어로·검색·도메인/대분류/비교군·필터 칩·미세조정 드로어(프리셋·가중치·하드 필터·용어 도움말)·판정 배지(`Recommended`/`Conditional`/`Filtered`)·3축(`User Rating`/`Objective Trust`/`AI Review`)·상세 모달(`Facts`/`Opinion`/`Verdict by tier`/`Signals`/`Alternatives`/`Reviews`/`Monetization`/`Updates`/`Sources`)·비교 표(`Best` 배지·`Basis` 열)·방법론 모달·토스트·오류 화면·푸터까지 100% 영문.
- **영문 데이터 `data/en.json`**: 카탈로그(3도메인·10대분류·14비교군·필터 팩·갭 리포트) + 67종의 `one_liner`·`tagline`·`verdict.one_liner/reasons/condition_notes`·`arena_notes`·3축 서술·티어 라벨·가격 표기·`limits`·`notes`·`facts`·리뷰 서술·과금·업데이트·한계·`score_notes`·출처·flags 메모. 영어 모드에서만 내려받고, `data.js` 가 원본 항목에 오버레이로 병합한다(원본 한국어 데이터는 그대로 단일 소스).
- **카드·타일 헤드라인은 직접 쓴 영어**: 대표 티어 한 줄과 판정 한 줄은 기계 번역이 아니라 문맥을 살려 다시 썼다(`Start free and the files stay yours`, `High stars, filtered out` 등).
- **검증**: `validate.py` 가 67/67·14/14·10/10·3/3 커버리지와 한글 잔존 0을 검사(누락 시 FAIL), `verify_ui.py` 가 EN 전 화면을 한국어 없이 통과하는지 확인(690/690).

## 검증

```bash
pip install playwright
python3 -m playwright install chromium      # 또는 CHROME_PATH=<chromium 실행 파일>
python3 projects/pharos/web/tests/verify_ui.py
```

- 스크립트가 `web/` 폴더를 임시 HTTP 서버 루트로 띄우고(포트 자동 할당) 종료 시 정리합니다.
  따라서 **web/ 폴더 단독 배포** 조건 그대로 검증됩니다(모든 요청이 배포 루트 안에서 해결되는지 확인).
- 690개 항목 통과: 로드·콘솔/네트워크 에러 0, 홈에서 비교군 파일 미로딩(지연 로딩), 홈 리포트(Hero Wars 4.6★/34.6 · MS To Do 4.6★/60.45),
  통합 검색(한글 별칭·비교군 라벨), 4단 탐색과 비교군별 요약 재계산, 필터 팩 우선 노출, 프리셋·슬라이더 재계산,
  비교 2~3개 표(4개째 차단), 상세 Fact/Opinion·대체제·공유 복사·정정 링크, URL 딥링크 5종, 북마크 지속,
  방법론 모달, 모바일 레이아웃·드로어, 엔진 단위 테스트(가중 평균·6단 규칙·면제·신선도·대체제·impact 3단계), 선택 과금 배지·`strict_monetization` 토글·상세 강도 블록,
  본질 경험 기준 재평가(니케 81.2 🟢 · 160벽 카드 표기 유지 · strict ON 시 거름),
  분야 확장(할 일 5건·비밀번호 4건·AI 코딩 4건, AI 도구 탭·장르 블록·필터 표시 이름, 구독 필수 필터로 1Password·Dashlane 거름, 신규 아이콘 42종),
  2차 분야 확장(v0.4.3: 웹 브라우저 5건·클라우드 5건·AI 어시스턴트 5건 = 57건·12비교군, 새 대분류 `인터넷 · 프라이버시`·`대화 · 리서치`, AI 탭의 두 비교군 전환, 신규 아이콘 15종 192×192),
  **v3.4 KO/EN 다국어**(EN 홈·도메인·비교군·상세·비교·방법론·드로어 한글 잔존 0건, 390px 넘침 0, `?lang=en` 링크 복사·언어 전환 딥링크·브라우저 언어 감지·URL 우선순위, KO 회귀),
  **v3.3 화면·UX 마감**(홈 도메인 필터 4칩 = 12/5/5/2 와 필터링·상단 고정, 플로팅 비교 바 문구·fixed 위치·스크롤 후 동일 위치,
  비교 표 첫 열 sticky·`최고` 셀·점수 차이·최고/최저/차이 요약, 링크 복사 클립보드 값과 토스트, 390px 홈/도메인/목록/비교/상세·방법론·드로어
  가로 넘침 0과 터치 영역 34px, 라이트 테마 텍스트 대비 4.2:1 이상과 가로 넘침 0).
- `--shots-dir` 로 스크린샷 저장 위치를 바꿀 수 있습니다(기본: `web/`).
- 데이터 쪽은 `python3 projects/pharos/schema/validate.py` 로 별도 검증합니다
  (스키마·카탈로그 계층·의미 규칙·판정 재계산·인덱스 신선도·음성 테스트·완결작 면제·impact 3단계·아이콘·**영문 번들 커버리지 67/67**·웹 사본 일치).

## 계산 외 원칙

- 카드/모달의 수치는 모두 분할 데이터와 현재 설정에서 계산됩니다. 점수·판정 하드코딩 없음.
- 확인하지 못한 값은 ⚪/'미확인'으로 표시하고 추정으로 채우지 않습니다.
- 화면은 데이터의 `verdict`(기록값)와 현재 설정 재계산값을 나란히 보여 줍니다. 다르면 설정 때문이며,
  상세의 '계산 과정'에서 어느 규칙이 적용됐는지 확인할 수 있습니다.
- 파로스는 어필리에이트·유료 광고·협찬 배치를 쓰지 않습니다. 이의제기·정정은 GitHub Issue 로 받습니다.
