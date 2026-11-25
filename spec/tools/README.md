# 파로스 수집·검증 스크립트

파로스 데이터는 **두 갈래**로 만든다.

- **2단계 발행(빠른 길)**: `bulk_ingest.py` — 공개 API 사실만으로 스키마 100% 를 채운 `auto_fact` 항목을 **100종 단위**로 만든다.
  사람이 쓰지 않으므로 빠르고, 카드·상세에 `자동 수집` 배지와 1차 판정 안내가 붙는다.
- **심층 리뷰(정확한 길)**: `auto_collect.py` → 검토 오버레이 → `apply_review.py` — 사람이 약관·과금·문장을 채워 `verified` 로 발행한다.

```
[A] 대량 팩트 적재 (배치 100종, 사람 손 0)
  ① 수집·변환  scripts/bulk_ingest.py   → data/{domain}/{arena}.json · en.json · catalog.json + 아이콘
  ② 빌드      scripts/sync_web_data.py  → search-index.json 재생성 + web/ 사본 동기화 + validate.py 전체 검증
  ③ 스모크    scripts/smoke_v12.py      → 핵심 30여 항목(홈 건수·신규 비교군·배지·상세 안내·KO/EN·390px)
  ④ 배포      web/ 폴더를 GitHub Pages(AIRA1346/pharos) 루트로 커밋·푸시

[B] 심층 리뷰 (항목·비교군 단위)
  ① 수집    scripts/auto_collect.py   → drafts/{id}.draft.json (사실 70% + 아이콘) + drafts/{id}.review.json
  ② 검토    drafts/reviewed/{id}.json (사람이 나머지 30% 작성)
  ③ 반영    scripts/apply_review.py   → data/{domain}/{arena}.json (review_tier: verified)
  ④ 빌드·검증·배포는 [A]의 ②~④ 와 같다(사람이 문장까지 쓴 배치는 verify_ui.py 전체를 돌린다).
```

## 0. bulk_ingest.py — 대량 팩트 적재(auto_fact)

스펙 JSON 하나로 100종을 한 번에 적재한다. 입력은 비교군·대분류 정의와 항목 목록이다.

```bash
python3 projects/pharos/scripts/bulk_ingest.py \
    --spec projects/pharos/drafts/bulk-2026-11-26/spec.json          # 수집·변환·기록(아이콘 포함)
python3 projects/pharos/scripts/bulk_ingest.py --spec ... --resolve-only   # ID 확정만
python3 projects/pharos/scripts/bulk_ingest.py --spec ... --ids elden-ring,factorio
python3 projects/pharos/scripts/bulk_ingest.py --spec ... --limit 3 --no-write --no-icon
```

**수집**(모두 무료 공개 API, `auto_collect.py` 의 수집·아이콘 모듈 재사용) — Steam(이름→AppID 검색, 한국어/영어
appdetails, 상점 평가 요약, ISteamNews, SteamSpy) · App Store(iTunes 한국·미국) · Google Play(JSON-LD 평점·
업데이트 날짜·광고 표기·og:image) · GitHub(repo 1회 요청으로 라이선스·스타·최근 푸시). 항목은 **워커 8개**로
병렬 수집하고, 응답은 `drafts/<배치>/cache/` 에 URL 해시로 저장해 재실행에서 다시 받지 않는다(GitHub 시간당 60회 보호).

**자동 산정 규칙**(요약에 근거를 그대로 적는다)

| 축 | 계산 |
| :--- | :--- |
| 사용자 | 스토어 평점·평가 수를 **표본 가중 평균**(Steam 누적·최근 30일, App Store 한국/미국 중 큰 표본, Play) |
| 객관 | 62 에서 라이선스(+8/+2)·가격 표기(+4)·업데이트 주기(+8~-14)·플랫폼 수(+2/+4)·출시 연수(+2/+4) |
| AI 검토 | 본질 검토 전 **중립값 60** 에서 스토어 평점·업데이트 주기·표본 규모·라이선스만으로 보정한 **잠정값(45~82)** |
| 판정 | `validate.compute_verdict` 로 **검증기와 같은 규칙**으로 계산(손으로 쓴 판정 없음) |

확인하지 못한 것(확률형 상품·구독·계정·데이터 수집·본질 완성도)은 지어내지 않고 `unknown` 으로 두고,
`data_quality.unverified`·안내 문구로 남긴다. 12개월 넘게 공지·릴리스가 없으면 `stale_over_12m=yes`(상태 미확인)로
검증기 규칙대로 거름이 되고, 완결작 여부는 심층 리뷰에서 확정한다.

**출력** — `data/{domain}/{arena}.json`(새 비교군은 새 파일, 기존 비교군은 뒤에 추가) · `data/en.json`
(항목 오버레이 100% 영문) · `data/catalog.json`(대분류·비교군·featured) · `web/assets/icons/{id}.webp`(192×192)
· `drafts/<배치>/bulk-<날짜>-run.json`(소요 시간·실패 목록·판정 요약).

## 1. auto_collect.py — 반자동 수집

이름·스토어 ID·저장소만 주면 `item.schema.json` v0.4.0 초안을 만든다.

```bash
# 배치(권장) — 스펙 파일에 여러 항목을 적고 한 번에
python3 projects/pharos/scripts/auto_collect.py --spec projects/pharos/drafts/spec-2026-11-25.json

# 한 건만
python3 projects/pharos/scripts/auto_collect.py --id celeste --name Celeste \
    --domain game --category action-indie --arena metroidvania-platformer --steam-id 504230

# 배치에서 일부만 다시(수집 로직을 고친 뒤 특정 항목만 재수집)
python3 projects/pharos/scripts/auto_collect.py --spec ... --ids celeste,nine-sols

# 옵션: --no-icon(아이콘 생략) · --force(아이콘 덮어쓰기) · --list-todos(남은 TODO 출력) · --out 폴더
```

### 지원 소스 (모두 무료, API 키 불필요)

| 소스 | 옵션 | 가져오는 사실 |
| :--- | :--- | :--- |
| Apple App Store | `ios_id` · `ios_bundle` · `ios_search` | 앱명·개발사·가격/통화·평점·평가 수·최근 버전/날짜·번들 ID·스토어 URL·공식 아트워크(512px)·앱 내 구입 목록(이름·가격)·한국 스토어 출시 여부 |
| Steam | `steam_id` | 게임명·개발사/배급사·가격(KRW/USD)·무료 여부·출시일·누적/최근 30일 긍정률·표본 수·장르·플랫폼·DLC 목록·개발사 업데이트 공지(마지막 패치)·SteamSpy 전체 평가(등급 C) |
| GitHub | `github_repo` | 라이선스·최근 릴리스/푸시·스타 수·아카이브 여부·조직 아바타. `gh` CLI 가 있으면 그것을(시간당 15,000회), 없으면 공개 API(60회)를 쓴다 |
| Google Play | `play_package` | 앱명·개발자·평점/평가 수(JSON-LD)·가격·공식 아이콘(og:image) |

`github_repo` 는 선택이지만, 오픈소스 항목이면 넣어야 라이선스·유지 상태의 근거 등급이 A 가 된다.
`ios_entity`(기본 `software`), `ios_countries`(기본 `["kr","us"]`), `platforms`, `aliases`, `keywords`, `developer`,
`icon_url`/`icon_crop`(center·top·bottom·left·right)/`icon_provider` 도 스펙에서 지정할 수 있다.

### 만드는 것

- `drafts/{id}.draft.json` — 스키마 v0.4.0 을 만족하는 초안(스크립트가 매번 스키마 검사 PASS 를 출력한다)
- `drafts/{id}.review.json` — 남은 TODO 목록, 수집 로그(요청 수·소요 시간·커버리지·경고)
- `web/assets/icons/{id}.webp` (192×192 webp/q90) + `web/assets/icons/manifest.json` 갱신
  (아이콘 우선순위: `icon_url` → App Store 아트워크 → Play 아이콘 → GitHub 조직 아바타 → Steam 라이브러리 캡슐)
- `drafts/logs/{날짜}-auto-collect.json` — 배치 기록(항목별 커버리지·요청 수·소요 시간·경고)

### TODO 표시와 커버리지

사람이 판단해야 하는 문자열은 `TODO(리뷰):` 로 시작한다. 커버리지는 두 가지로 센다.

- **사실 필드**(19개: 이름·플랫폼·개발사·출시일·가격·리뷰 표본·업데이트 기록 등) — API 로 자동
- **판단 필드**(29개: 한 줄 정의·객관/AI 축 점수·과금 판단·판정 문장 등) — 리뷰어가 채움

2026-11-25 10건 배치 결과: **평균 커버리지 70.6%**(사실 18~19/19, 판단 15~16/29),
항목당 평균 1.45초·요청 6.5건. 이 숫자가 "Fact 70% + 검토 30%" 설계가 실제로 지켜졌다는 증거다.

## 2. 검토 오버레이 (`drafts/reviewed/{id}.json`)

초안에서 **바꾸거나 더할 값만** 적는다. dict 는 재귀 병합, `tier_id`/`id` 가 있는 dict 리스트는 항목별 병합,
그 밖의 리스트는 통째로 교체한다. `_drop_sources` 로 자동 수집한 출처 중 쓸모없는 것을 뺄 수 있다.

```json
{
  "id": "celeste",
  "one_liner": "한 번의 점프를 수백 번 다시 시도하게 만드는 정밀 플랫포머 …",
  "flags": {"stale_over_12m": {"value": "yes", "note": "마지막 패치 2021-03-29 … 완결로 면제"}},
  "axes": {"objective": {"score": 72, "summary": "…"}, "ai_review": {"score": 92, "summary": "…"}},
  "verdict": {"one_liner": "…", "reasons": ["…"], "condition_notes": ["…"]},
  "tiers": [{"tier_id": "steam", "limits": ["…"]}],
  "sources": [{"id": "official-x", "title": "…", "url": "https://…", "type": "official", "grade": "A",
               "accessed_at": "2026-11-25", "note": "…"}]
}
```

## 3. apply_review.py — 병합·판정 재계산·기록

```bash
python3 projects/pharos/scripts/apply_review.py \
    --spec projects/pharos/drafts/spec-2026-11-25.json \
    --reviews projects/pharos/drafts/reviewed --check   # 쓰지 않고 검사만
python3 projects/pharos/scripts/apply_review.py ... --write   # data/{domain}/{arena}.json 에 반영
```

병합 뒤 **하드 필터·축 신호·티어 판정·대표 판정을 계산 규칙으로 다시 맞춘다**(`auto_collect.finalize_item`).
사람이 점수와 문장만 주면 `validate.py` 와 어긋나지 않는다. 실행하면 항목별 스키마·의미 검사 결과와
남은 TODO 문자열 수가 나온다 — `0/…` 이면 그 항목은 최종 데이터로 완성된 상태다.

> 새 비교군을 처음 넣을 때는 `data/catalog.json` 의 `arenas`(와 `home.featured_arenas`)에 먼저 등록한다.
> `apply_review.py` 는 카탈로그에 없는 비교군을 거부한다.

## 4. sync_web_data.py — 인덱스 재생성 + 사본 + 전체 검증

```bash
python3 projects/pharos/scripts/sync_web_data.py          # search-index 재생성 → web/ 복사 → validate.py
python3 projects/pharos/scripts/sync_web_data.py --check  # 쓰지 않고 최신 여부만 확인
```

## 5. smoke_v12.py — 배치용 빠른 스모크 (auto_fact 배치마다)

`verify_ui.py` 전체(730여 항목)는 사람이 문장까지 쓴 배치에서만 돌리고, `auto_fact` 대량 배치는
**핵심 30여 항목**만 빠르게 확인한다(1분 이내).

```bash
python3 projects/pharos/scripts/smoke_v12.py                      # web/ 로컬 서버
python3 projects/pharos/scripts/smoke_v12.py --live --shots-dir projects/pharos/live
```

확인 항목 — 데이터 칩(건수·비교군), 홈 장르 블록 = featured, 신규 비교군 건수·`자동 수집` 배지·192px 아이콘,
`auto_fact` 상세의 1차 판정 안내(검증 완료 항목에는 없음), EN 모드 한글 0건·`Auto-collected` 배지,
390px 가로 넘침 0, 콘솔 오류·HTTP 4xx 0건, 스크린샷(`live-v12-bulk100-home.png`·`live-v12-bulk100-arena.png`).

## 5-1. check_en_leaks.py — 영문 오버레이 누출 검사

`data/en.json` 은 부분 번역(오버레이)이라 덮지 않은 필드가 영문 화면에 한글로 남기 쉽다.
`web/js/data.js` 와 같은 규칙으로 병합한 뒤 **화면에 나가는 문자열**에 한글이 남은 경로를 모아 보여준다(별칭·키워드 제외).

```bash
python3 projects/pharos/scripts/check_en_leaks.py          # auto_fact 항목
python3 projects/pharos/scripts/check_en_leaks.py --all    # 전체
```

## 5-2. verify_ui.py — 실제 화면 검증

```bash
LD_LIBRARY_PATH=/workspace/.cache/chromedeps/root/usr/lib/x86_64-linux-gnu \
python3 projects/pharos/web/tests/verify_ui.py
```

건수 단언은 카탈로그·인덱스에서 계산하므로, 데이터를 늘려도 테스트가 낡지 않는다.
v3.4 절은 `auto_collect.py` 로 추가한 두 비교군(메트로배니아·플랫포머 / 이메일 클라이언트)이
홈·비교군 화면·상세 모달에 실제로 반영되는지 확인한다.

## 6. fetch_icons.py — 기존 57종 아이콘 재수집

```bash
python3 projects/pharos/scripts/fetch_icons.py --check
python3 projects/pharos/scripts/fetch_icons.py --ids todoist,cline
```

`auto_collect.py` 가 넣은 아이콘(SOURCES 에 없는 항목)은 manifest 에서 지우지 않고 유지한다.

## 참고 — 2026-11-25 실전 검증(10건)

| 비교군 | 항목 | 소스 | 결과 |
| :--- | :--- | :--- | :--- |
| 게임 › 메트로배니아 · 플랫포머 | Hollow Knight · Celeste · Ori and the Will of the Wisps · Nine Sols · Blasphemous | Steam 5 + App Store 1 | 전부 추천 |
| 앱 › 이메일 클라이언트 | Thunderbird · K-9 Mail · Proton Mail · Spark Mail · Apple Mail | App Store 4 + GitHub 3 + Play 1 | 추천 3 · 조건부 2 |

수집 로그: `drafts/logs/2026-11-25-auto-collect.json` · 초안/리뷰: `drafts/*.draft.json`, `drafts/*.review.json`,
`drafts/reviewed/*.json`
