# 파로스 설계 문서

| 문서 | 내용 |
| --- | --- |
| `vision.md` | 제품 비전 — 왜 별점 대신 '내 기준'인가, 무엇을 대체하는가 |
| `criteria.md` | 선별 기준표 v0.3.1 — 세 축·가중치·산식, 하드 필터, 판정 규칙 1~7, 근거 등급, 수명 단계 (데이터 구조 v0.4.0) |
| `plan.md` | 개발 계획과 단계별 범위 (v2.0 — 4단 계층·분할 로딩·사이트 개편) |
| `pilot-test.md` | 파일럿 아이템으로 기준을 검증한 기록 |

처음 읽는다면 `vision.md` → `criteria.md` 순서를 권합니다. `criteria.md`가 실제 계산 규칙의
단일 근거이고, `schema/item.schema.json`의 `x-pharos.client`가 그 규칙을 기계가 읽을 수 있는
형태로 옮긴 계약입니다. 화면 동작은 이 둘에서만 나옵니다.

## 데이터 구조 (v0.4.0)

| 파일 | 역할 |
| --- | --- |
| `data/catalog.json` | 도메인 → 대분류 → 비교군 정의, 도메인 필터 팩, 홈 리포트 규칙, 각 비교군의 `data_file` |
| `data/{domain}/{arena}.json` | 비교군별 항목 데이터 (웹은 선택한 파일만 지연 로딩) |
| `data/search-index.json` | 통합 검색·홈 리포트용 경량 인덱스 (분할 데이터에서 자동 생성) |
| `schema/item.schema.json` | 아이템 스키마 v0.4.0 — `domain`·`category`(대분류 id) 명시, `x-pharos.client` 계산 계약 |

저장소 루트의 `data/`·`schema/` 가 그대로 배포 사본입니다. 원본 개발 프로젝트(`projects/pharos/`)에서는
`scripts/sync_web_data.py` 가 인덱스를 재생성하고 `web/` 사본을 원본과 맞춘 뒤 `validate.py` 전체 검증을 실행합니다.

## 검증 도구 (`tools/`)

`tools/sync_web_data.py`와 `tools/validate.py`는 원본 개발 프로젝트(`projects/pharos/`)의
레이아웃을 전제로 경로를 계산합니다(`../data`, `../web` 등). 이 저장소에서는 참고용 사본이며,
실행하려면 원본 프로젝트에서 `python3 projects/pharos/schema/validate.py`처럼 호출하세요.

`validate.py`가 검사하는 항목: 스키마 자체의 유효성(Draft 2020-12), 카탈로그 계층(도메인·대분류·비교군·
`data_file` 존재·중복), 모든 아이템의 스키마 적합성과 `domain`·`category` 일치, 의미 규칙(출처 참조·티어·
플래그↔필터 일치·비교군·`maintenance_status` 관계), 산식으로 재계산한 판정 대조, 경량 인덱스 신선도,
음성 테스트, 완결작 면제 규칙의 양성/음성 테스트, 웹 사본과 원본의 해시 일치.

웹 UI 는 원본 프로젝트의 `web/tests/verify_ui.py`(Playwright)가 홈·4단 탐색·통합 검색·미세조정 드로어·
1:1 비교·상세 대체제·URL 딥링크·북마크·방법론 모달·모바일 레이아웃까지 검증합니다.
