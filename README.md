# 파로스 Pharos — 별점 대신, 내 기준으로 거르는 앱·게임 선별

사용자 평가·객관 신뢰 지표·AI 검토를 **내 가중치로 합치고**, 강제 광고·확률형 아이템 같은
**절대 거름 조건**을 적용해 앱과 게임을 선별하는 정적 웹 앱입니다.
빌드 도구 없이 HTML/CSS/ES Module만으로 동작하며, 점수·신호·판정 계산은 전부 브라우저에서
`schema/item.schema.json`의 `x-pharos.client` 계약대로 실시간으로 이뤄집니다. 서버는 파일만 전달합니다.

**라이브:** https://aira1346.github.io/pharos/

**기준표 v0.4.0 (2026-11-25):** 확률형·P2W 상품의 **강제성을 3단계**(`impact`: none·optional·core)로 나눴습니다. 상품이 있어도
무과금으로 본편을 충분히 즐길 수 있으면(`optional`) 「선택 과금 · 무과금 가능」 배지로만 알리고 거르지 않으며, 상품 존재 자체로
거르고 싶으면 미세조정의 `strict_monetization`(기본 OFF)을 켭니다. Black Desert 54.15→**80.1 🟢**, Guild Wars 2 →**77.2 🟡**,
Bloons TD 6 →**81.3 🟢**, Limbus Company →**78.7 🟡** 로 재적용하고, Lost Ark·Clash Royale·Plants vs. Zombies 2·Archero·Hero Wars·Genshin Impact 는 `core`(🔴)로 남겼습니다.

**기준표 v0.4.1 (2026-11-25) — 본질 경험 기준(`core_experience`):** `impact`·`free_play` 를 가르는 기준을 "최상위 경쟁·풀돌파까지
과금 없이 가는가"가 아니라 **"그 게임의 본질적 재미를 무과금으로 온전히 누릴 수 있는가"** 로 바로잡았습니다(기준표 5.2).
엔드 경쟁 구간의 돌파 벽·아레나 순위·스킨 가격은 `limits`·`condition_notes` 에 사실 그대로 남깁니다.
이 기준으로 **승리의 여신: 니케를 69.65 🔴 → 81.2 🟢 추천**으로 재평가했습니다(사용자 86·객관 68·AI 92) — 본질인 메인 스토리·연출은
과금 없이 끝까지 감상할 수 있고, 160벽·챔피언 아레나·스킨은 엔드 수집·경쟁의 선택 구간이라는 근거입니다.

**모바일 게임 3차 확장 (2026-11-25):** 전체 **29건**. `모바일 수집형 RPG` 에 승리의 여신: 니케(**81.2 🟢**)·블루 아카이브(75.5 🟡)·붕괴: 스타레일(70.1 🔴), `모바일 전략·디펜스` 에 Clash of Clans(78.5 🟡)·Arknights(80.2 🟢)를 더했습니다. 같은 확률형이라도 마일리지 교환·확정 천장 이월·90연 천장으로 강도가 갈리고, 무료+시간 게이트(CoC)와 타워디펜스+확률형 수집(Arknights)이 한 표에 놓입니다.

**공식 아이콘 (2026-11-25):** 29종 모두 카드·상세·비교 표에 공식 아이콘을 붙였습니다. App Store 아트워크 → 공식 사이트
아이콘 → 공식 브랜드 마크 순으로 내려받아 192×192 webp 로 저장하고(`assets/icons/`), 출처는 `assets/icons/manifest.json` 에
남깁니다. 아이콘은 각 권리자의 상표·아트워크이며 **식별 목적**으로만 씁니다.

## v2 — 4단 탐색으로 개편

`spec/plan.md` v2.0 의 2단계 결과물입니다. 비교군 → 앱/게임 역전 구조와 `전체` 평균 혼합을 폐기하고,
분야가 늘어나도 무너지지 않는 계층으로 바꿨습니다.

| 단계 | 예 |
| :--- | :--- |
| 1 도메인 | 앱 · 게임 (추후 콘텐츠·AI 툴·제품) |
| 2 대분류 | 생산성·지식관리 / 전략·카드 / RPG·수집 / 액션·인디 / RPG·MMORPG / 모바일 전략·디펜스 |
| 3 비교군 | 노트·지식관리 · 덱빌딩 게임 · 모바일 수집형 RPG · 액션 로그라이크 · PC MMORPG · 모바일 전략·디펜스 |
| 4 항목·티어 | Obsidian(무료/Sync), Balatro(1회 구매) |

- **데이터 분리**: `data/catalog.json`(도메인·대분류·비교군 정의) + 비교군별 파일 `data/{domain}/{arena}.json`
  (웹은 선택한 파일만 지연 로딩) + 자동 생성 경량 인덱스 `data/search-index.json`(통합 검색·홈 리포트).
- **홈 요약 뷰**: 비교군 바로가기, `별점은 높은데 거름 판정` 리포트(예: Hero Wars 4.6★ vs 34.6점),
  통합 검색(이름·별칭·키워드), 보관함(localStorage).
- **첫 화면 경량화**: 기본 `균형 기본` 프리셋. 가중치·하드 필터·엄격 모드는 `내 기준 미세조정` 드로어 안으로,
  선택한 도메인의 필터 팩(게임 팩 / 앱 팩)을 먼저 노출.
- **1:1 비교**: 같은 비교군 2~3개를 체크해 점수·축·필터·별점·수명 단계·신선도를 한 표에.
- **상세 강화**: `assessed_at` 180일 초과 시 `재검토 필요`, **사실(Fact)과 의견(Opinion) 분리**,
  거름·조건부 항목의 **같은 비교군 상위 대체제**, **공유 요약 복사**, **정정 제보**(GitHub Issue 양식).
- **URL 딥링크·방법론**: `?domain=app&arena=pkm-notes&item=evernote` 같은 링크로 같은 화면이 열리고,
  `파로스가 점수를 매기는 법` 모달에 4축·A/B/C 등급·판정 규칙·독립성(어필리에이트·유료 광고 배제) 선언을 공개합니다.

## 실행

```bash
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000/ 접속
```

`file://`로 `index.html`을 직접 열면 `fetch`가 차단됩니다. 반드시 HTTP로 열어 주세요.

## 저장소 구조

```
index.html                 화면 골격 (도메인 탭 · 홈/탐색/비교 뷰 · 상세·방법론 모달 · 미세조정 드로어)
styles.css                 등대 테마 (다크 기본 / 라이트 토글), 반응형
js/data.js                 카탈로그·인덱스 로드, 비교군 파일 지연 로딩/캐시, 통합 검색
js/engine.js               계산 엔진 — x-pharos.client 계약 (DOM 비의존 순수 함수)
js/app.js                  상태·라우팅(URL 딥링크)·렌더링·이벤트
data/catalog.json          도메인·대분류·비교군 정의 + 도메인 필터 팩 + 홈 리포트 규칙
data/search-index.json     경량 인덱스 (분할 데이터에서 자동 생성)
data/app/pkm-notes.json    노트·지식관리 5건
data/game/roguelike-deckbuilder.json  덱빌딩 4건
data/game/mobile-gacha-rpg.json       모바일 수집형 RPG 6건
data/game/action-roguelike.json       액션 로그라이크 4건
data/game/pc-mmorpg.json              PC MMORPG 4건
data/game/mobile-strategy-defense.json 모바일 전략·디펜스 6건
schema/item.schema.json    스키마 v0.4.0 + 클라이언트 계산 계약(x-pharos.client)
.github/ISSUE_TEMPLATE/correction.yml  정정·이의제기 양식
spec/                      설계 문서 (vision · criteria · plan · pilot-test)와 검증 도구
.nojekyll                  GitHub Pages의 Jekyll 처리 비활성화
```

`index.html` → `./js/app.js` → `./data/catalog.json` · `./data/search-index.json` · `./schema/item.schema.json`
로 이어지는 상대 경로만 쓰고, 비교군 데이터는 선택할 때만 `./data/{domain}/{arena}.json` 으로 읽습니다
(상위 폴더 참조 없음). 이 저장소 루트가 그대로 배포 단위입니다.

## 무엇을 보여주나

- **세 축 가중치** — 사용자 평가 / 객관 신뢰 지표 / AI 검토. 슬라이더로 비중을 바꾸면 카드 점수와 판정이 즉시 재계산됩니다(합계 100% 정규화).
- **하드 필터 9종** — 강제 광고·확률형 아이템·P2W·과금 없이 진행 불가·미끼형 광고·12개월 방치·구독 필수·계정 필수·과도한 데이터 수집. 켜진 필터에 걸리면 점수와 무관하게 **거름**이고, 왜 걸렸는지 사유를 함께 보여줍니다.
- **선택 과금 3단계** — 확률형·P2W는 `impact`(none·optional·core)로 강도를 나눕니다. `optional`(무과금으로 충분)은 「선택 과금 · 무과금 가능」 배지와 무과금 충분성(`monetization.free_play`, 근거 등급)으로 표시하고, `core`(성장 벽)만 기본 모드에서 거릅니다.
- **근거 엄격 모드** — 끄면 근거 등급 C뿐인 필터 적중은 '근거 약함' 조건부 경고로 완화됩니다.
- **수명 단계** — 완결작(`feature_complete`)과 방치(`abandoned`)를 구분해, 완결작은 '업데이트 없음' 필터에서 면제합니다(점수는 그대로). 보안·OS 호환성 신호가 있으면 조건부 경고로 내립니다.
- **비교군 안에서만 비교** — 점수 평균·순위·요약은 오직 같은 비교군에서만 계산합니다. 노트 앱과 카드 게임을 한 줄에 섞어 평균 내지 않습니다.

## 설계 문서

| 문서 | 내용 |
| --- | --- |
| [spec/vision.md](spec/vision.md) | 제품 비전과 문제 정의 |
| [spec/criteria.md](spec/criteria.md) | 선별 기준표 — 축·가중치·산식·하드 필터·확률형·P2W 강도·판정 규칙 (v0.4.0) |
| [spec/plan.md](spec/plan.md) | 개발 계획과 단계 (v2.0) |
| [spec/pilot-test.md](spec/pilot-test.md) | 파일럿 검증 기록 |
| [spec/README.md](spec/README.md) | 문서 읽는 순서와 검증 도구 안내 |

## 계산 원칙

- 카드·상세의 수치는 모두 분할 데이터와 현재 설정에서 계산됩니다. 점수·판정 하드코딩은 없습니다.
- 비교군은 화면 상태가 아니라 데이터(`catalog.json` 의 `arenas`)에서 옵니다.
- 확인하지 못한 값은 ⚪/'미확인'으로 표시하고 추정으로 채우지 않습니다.
- 화면은 데이터에 기록된 `verdict`와 현재 설정 재계산값을 나란히 보여 주며, 값이 다르면 상세의 '계산 과정'에서 적용된 규칙을 확인할 수 있습니다.
- 파로스는 어필리에이트·유료 광고·협찬 배치를 쓰지 않습니다. 정정·이의제기는 GitHub Issue(`correction.yml`)로 받습니다.
