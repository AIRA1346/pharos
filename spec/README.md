# 파로스 Pharos — 정적 웹 v2 (4단 탐색 · 스키마 v0.4.0)

빌드 도구 없이 **순수 HTML/CSS/ES Module** 만으로 동작하는 파로스 프론트엔드입니다.
서버는 파일만 배포하고, 점수·신호·판정은 전부 브라우저에서 `schema/item.schema.json` 의
`x-pharos.client` 계약대로 실시간 재계산합니다.

v2 는 `plan.md` v2.0 의 2단계(사이트 구조 개편·배포) 결과물입니다.
**도메인 → 대분류 → 비교군 → 항목** 4단 탐색, 비교군별 분할 데이터 지연 로딩,
홈 요약 뷰(비교군 바로가기·별점-판정 갭 리포트·통합 검색), 1:1 비교 표,
미세조정 드로어, 사실/의견 분리, 대체제 연결, URL 딥링크, 북마크, 방법론 모달을 담았습니다.

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
| 홈 | 서비스 요약 · 비교군 바로가기 · '별점은 높은데 거름 판정' 리포트 · 통합 검색 · 보관함 | `catalog.json` + `search-index.json` (경량) |
| 1 도메인 | 홈 / 앱 / 게임 전환 | `catalog.domains` |
| 2 대분류 | 생산성·지식관리, 전략·카드, RPG·수집, 액션·인디, RPG·MMORPG, 모바일 전략·디펜스 | `catalog.categories` |
| 3 비교군 | 노트·지식관리, 덱빌딩 게임, 모바일 수집형 RPG, 액션 로그라이크, PC MMORPG, 모바일 전략·디펜스 | `catalog.arenas[].data_file` |
| 4 항목·티어 | 카드 목록 · 1:1 비교 · 상세 모달 | `data/{domain}/{arena}.json` (그 비교군만 지연 로딩) |

- 홈은 비교군 파일을 **내려받지 않습니다.** 통합 검색·홈 리포트는 경량 인덱스만 읽고,
  비교군을 열 때 해당 `data_file` 하나만 `fetch` 해 캐시합니다.
- 점수 평균·순위·요약은 **오직 같은 비교군 안에서만** 계산합니다. 도메인이나 분야가 다른 항목의 평균을 섞지 않습니다.
- 홈의 수치(비교군 평균·1위 점수)는 **균형 기본 가중치 기준**으로 인덱스에 미리 계산되어 있습니다.
  내 가중치로 바꾸면 비교군·비교·상세 화면이 그 기준으로 즉시 다시 계산됩니다.

## 파일

```
web/
  index.html            화면 골격 (도메인 탭 · 경로 · 홈/탐색/비교 뷰 · 상세·방법론 모달 · 드로어)
  styles.css            등대 테마 (다크 기본 / 라이트 토글), 반응형
  js/data.js            카탈로그·인덱스 로드, 비교군 파일 지연 로딩/캐시, 통합 검색
  js/engine.js          계산 엔진 — x-pharos.client 계약 (DOM 비의존 순수 함수, 신선도·대체제·완결작 면제)
  js/app.js             상태·라우팅(URL 딥링크)·렌더링·이벤트
  data/catalog.json     도메인·대분류·비교군 정의 + 필터 팩 + 홈 리포트 규칙
  data/search-index.json 경량 인덱스 (자동 생성 — 통합 검색·홈 리포트)
  data/app/pkm-notes.json              노트·지식관리 5건
  data/game/roguelike-deckbuilder.json 덱빌딩 게임 4건
  data/game/mobile-gacha-rpg.json      모바일 수집형 RPG 3건
  data/game/action-roguelike.json      액션 로그라이크 4건
  data/game/pc-mmorpg.json             PC MMORPG 4건
  data/game/mobile-strategy-defense.json 모바일 전략·디펜스 4건
  schema/item.schema.json  배포용 스키마 사본 (v0.4.0)
  tests/verify_ui.py    Playwright 검증 스크립트
  preview-v2-home.png        홈 요약 뷰 (1440px)
  preview-v2-arena.png       비교군 목록 (덱빌딩 게임)
  preview-v2-compare.png     1:1 비교 표 (Balatro vs Slay the Spire)
  preview-v2-mobile.png      모바일 비교군 화면 (390px)
  preview-v2-method.png      방법론 모달
  preview-v2-mobile-tune.png 모바일 미세조정 드로어
  preview-v2-mobile-detail.png 모바일 상세 모달
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

`arena` 만 있어도 카탈로그에서 도메인·대분류를 찾아 해석합니다.

## 기능 요약

- **홈 요약 뷰**: 비교군 바로가기 카드(건수·평균·1위), `별점은 높은데 거름 판정` 리포트
  (예: Hero Wars 4.6★ vs 34.6점 — 스토어 별점과 걸린 필터 공개), 통합 검색(이름·별칭·키워드·비교군 라벨),
  보관함(localStorage).
- **첫 화면 경량화**: 기본 `균형 기본` 프리셋. 가중치 슬라이더·하드 필터·엄격 모드는 `내 기준 미세조정` 드로어 안.
  선택한 도메인의 필터 팩(게임 팩 / 앱 팩)을 먼저 펼칩니다.
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

## 계약 ↔ 구현 대응

| 스키마 `x-pharos.client` | 구현 |
| :--- | :--- |
| `catalog.file` · `search_index` | `data.js` 가 `./data/catalog.json`·`./data/search-index.json` 로드, 비교군 `data_file` 만 지연 로딩 |
| `navigation.levels` | 홈 → 도메인 → 대분류 → 비교군 → 항목 라우터(`app.js`) |
| `freshness.review_after_days` (180) | `engine.freshness` — `재검토 필요` 배지·상세 경고 |
| `axes[]` (라벨·기본 가중치) | 슬라이더·프리셋을 스키마에서 생성(기본 0.40/0.35/0.25) |
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
  카드에 '완결작' 배지와 '면제 · 완결작' 사유 칩을 보입니다(점수는 바꾸지 않음 — Inscryption 80.15).
- `abandoned`·`stale_unknown`, 서비스형 앱·라이브 게임의 12개월 이상 중단은 그대로 `fail`(거름)입니다.
- `flags.compat_risk.value == "yes"` 면 추천 대신 **조건부 경고**(규칙 ⑦)입니다.

### 확률형·P2W 강도 3단계 (v0.4.0)

- `hard_filters.gacha_random_items`·`p2w` 에 `impact`(`none`/`optional`/`core`)를 적습니다. 값이 없으면 상태에서
  추론합니다(pass→none, fail→core — 보수적 기본값).
- `optional` 은 필터 상태를 `fail` 로 **남긴 채**(상품이 있다는 사실 유지) 거름으로 잡지 않고, 카드·상세에
  「선택 과금 · 무과금 가능」 배지를 답니다. 점수·신호 규칙으로 추천/조건부가 갈립니다(검은사막 80.1 · Bloons TD 6 81.3 → 🟢).
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

## 검증

```bash
pip install playwright
python3 -m playwright install chromium      # 또는 CHROME_PATH=<chromium 실행 파일>
python3 projects/pharos/web/tests/verify_ui.py
```

- 스크립트가 `web/` 폴더를 임시 HTTP 서버 루트로 띄우고(포트 자동 할당) 종료 시 정리합니다.
  따라서 **web/ 폴더 단독 배포** 조건 그대로 검증됩니다(모든 요청이 배포 루트 안에서 해결되는지 확인).
- 331개 항목 통과: 로드·콘솔/네트워크 에러 0, 홈에서 비교군 파일 미로딩(지연 로딩), 홈 리포트(Hero Wars 4.6★/34.6),
  통합 검색(한글 별칭·비교군 라벨), 4단 탐색과 비교군별 요약 재계산, 필터 팩 우선 노출, 프리셋·슬라이더 재계산,
  비교 2~3개 표(4개째 차단), 상세 Fact/Opinion·대체제·공유 복사·정정 링크, URL 딥링크 5종, 북마크 지속,
  방법론 모달, 모바일 레이아웃·드로어, 엔진 단위 테스트(가중 평균·6단 규칙·면제·신선도·대체제·impact 3단계), 선택 과금 배지·`strict_monetization` 토글·상세 강도 블록,
  본질 경험 기준 재평가(니케 81.2 🟢 · 160벽 카드 표기 유지 · strict ON 시 거름).
- `--shots-dir` 로 스크린샷 저장 위치를 바꿀 수 있습니다(기본: `web/`).
- 데이터 쪽은 `python3 projects/pharos/schema/validate.py` 로 별도 검증합니다
  (스키마·카탈로그 계층·의미 규칙·판정 재계산·인덱스 신선도·음성 테스트·완결작 면제·impact 3단계·웹 사본 일치).

## 계산 외 원칙

- 카드/모달의 수치는 모두 분할 데이터와 현재 설정에서 계산됩니다. 점수·판정 하드코딩 없음.
- 확인하지 못한 값은 ⚪/'미확인'으로 표시하고 추정으로 채우지 않습니다.
- 화면은 데이터의 `verdict`(기록값)와 현재 설정 재계산값을 나란히 보여 줍니다. 다르면 설정 때문이며,
  상세의 '계산 과정'에서 어느 규칙이 적용됐는지 확인할 수 있습니다.
- 파로스는 어필리에이트·유료 광고·협찬 배치를 쓰지 않습니다. 이의제기·정정은 GitHub Issue 로 받습니다.
