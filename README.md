# 파로스 Pharos — 별점 대신, 내 기준으로 거르는 앱·게임 선별

사용자 평가·객관 신뢰 지표·AI 검토를 **내 가중치로 합치고**, 강제 광고·확률형 아이템 같은
**절대 거름 조건**을 적용해 앱과 게임을 선별하는 정적 웹 앱입니다.
빌드 도구 없이 HTML/CSS/ES Module만으로 동작하며, 점수·신호·판정 계산은 전부 브라우저에서
`schema/item.schema.json`의 `x-pharos.client` 계약대로 실시간으로 이뤄집니다. 서버는 파일만 전달합니다.

**라이브:** https://aira1346.github.io/pharos/

## 무엇을 보여주나

- **세 축 가중치** — 사용자 평가 / 객관 신뢰 지표 / AI 검토. 슬라이더로 비중을 바꾸면 카드 점수와 판정이 즉시 재계산됩니다(합계 100% 정규화).
- **하드 필터** — 켜진 필터(강제 광고, 확률형 아이템, 과금 유도, 12개월 이상 업데이트 없음 등)에 하나라도 걸리면 점수와 무관하게 **거름**으로 내려가고, 왜 걸렸는지 사유를 함께 보여줍니다.
- **근거 엄격 모드** — 끄면 근거 등급 C뿐인 필터 적중은 '근거 약함' 조건부 경고로 완화됩니다.
- **비교군(arena)** — 같은 자리를 두고 겨루는 대체제끼리 묶어 봅니다(예: 노트·지식관리, 덱빌딩).
- **수명 단계** — 완결작(`feature_complete`)과 방치(`abandoned`)를 구분해, 완결작은 '업데이트 없음' 필터에서 면제합니다(점수는 그대로).

## 실행

```bash
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000/ 접속
```

`file://`로 `index.html`을 직접 열면 `fetch`가 차단됩니다. 반드시 HTTP로 열어 주세요.

## 저장소 구조

```
index.html              화면 골격 (컨트롤 패널 + 비교군 탭 + 카드 그리드 + 상세 모달)
styles.css              등대 테마 (다크 기본 / 라이트 토글), 반응형
js/engine.js            계산 엔진 — x-pharos.client 계약 구현 (DOM 비의존 순수 함수)
js/app.js               데이터·스키마 로드, 상태, 렌더링, 이벤트
data/items.json         아이템 데이터 (스키마 v0.3.1, 비교군 3개)
schema/item.schema.json 스키마 + 클라이언트 계산 계약(x-pharos.client)
spec/                   설계 문서 (vision · criteria · plan · pilot-test)와 검증 도구
.nojekyll               GitHub Pages의 Jekyll 처리 비활성화
```

`index.html` → `./js/app.js` → `./data/items.json` · `./schema/item.schema.json` 로 이어지는
상대 경로만 쓰므로, 이 저장소 루트가 그대로 배포 단위입니다(상위 폴더 참조 없음).

## 설계 문서

| 문서 | 내용 |
| --- | --- |
| [spec/vision.md](spec/vision.md) | 제품 비전과 문제 정의 |
| [spec/criteria.md](spec/criteria.md) | 선별 기준표 — 축·가중치·산식·하드 필터·판정 규칙 |
| [spec/plan.md](spec/plan.md) | 개발 계획과 단계 |
| [spec/pilot-test.md](spec/pilot-test.md) | 파일럿 검증 기록 |
| [spec/README.md](spec/README.md) | 문서 읽는 순서와 검증 도구 안내 |

## 계산 원칙

- 카드·상세의 수치는 모두 `data/items.json`과 현재 설정에서 계산됩니다. 점수·판정 하드코딩은 없습니다.
- 비교군은 화면 상태가 아니라 데이터(`arenas` + 스키마 `arenas` 메타)에서 옵니다.
- 확인하지 못한 값은 ⚪/'미확인'으로 표시하고 추정으로 채우지 않습니다.
- 화면은 데이터에 기록된 `verdict`와 현재 설정 재계산값을 나란히 보여 주며, 값이 다르면 상세의 '계산 과정'에서 적용된 규칙을 확인할 수 있습니다.
