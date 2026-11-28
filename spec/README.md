# 파로스 수집·검증 스크립트

파로스 데이터는 **두 갈래**로 만든다.

- **2단계 발행(빠른 길)**: `bulk_ingest.py` — 공개 API 사실만으로 스키마 100% 를 채운 `auto_fact` 항목을 **100종 단위**로 만든다.
  사람이 쓰지 않으므로 빠르고, 카드·상세에 `자동 수집` 배지와 1차 판정 안내가 붙는다.
- **심층 리뷰(정확한 길)**: `auto_collect.py` → 검토 오버레이 → `apply_review.py` — 사람이 약관·과금·문장을 채워 `verified` 로 발행한다.

```
[A] 대량 팩트 적재 (배치 100종, 사람 손 0)
  ① 수집·변환  scripts/bulk_ingest.py   → data/{domain}/{arena}.json · en.json · catalog.json + 아이콘
  ② 빌드      scripts/sync_web_data.py  → search-index.json 재생성 + web/data/en/ 분할 + web/ 사본 동기화 + validate.py 전체 검증
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

**중복 방지 가드** — 적재를 시작하기 전에 `data/search-index.json` 과 `data/{domain}/*.json` 전체를 읽어
id · 정규화 이름(소문자·특수문자 제거) · 스토어 ID(Steam AppID · App Store trackId · Play 패키지 · GitHub 저장소)를
인덱스로 만든다(`load_dup_index`). 스펙 항목이 겹치면 **수집 전에** 스킵하고, 수집이 끝나면 검색어로 확정된 실제
스토어 ID 로 **한 번 더** 검사한다(이름이 달라도 같은 제품이면 걸린다). 스킵은 `↷ 스킵 {id}: {사유}` 로 출력되고
실행 로그의 `skipped[]` 에 남으며, 실패로 세지 않는다. 같은 배치를 두 번 돌려도 중복이 생기지 않는다.
`validate.py` 도 전체 데이터의 id·정규화 이름·스토어 ID 중복을 검사해 1건이라도 있으면 FAIL 한다.

**Steam 요청 간격** — `PHAROS_STEAM_PACE=1.1` 처럼 초 단위 간격을 주면 `store.steampowered.com` 요청을 그 간격만큼
벌린다(기본 0 = 기존 동작). 160종 넘는 게임 배치에서 appdetails 가 `429` 를 내면 30종 단위로 나눠 이 값과 함께
여러 번 돌린다 — 캐시 덕분에 재실행은 성공분을 다시 받지 않는다.

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

## 4. sync_web_data.py — 인덱스 재생성 + 영문 분할 + 사본 + 전체 검증

```bash
python3 projects/pharos/scripts/sync_web_data.py          # search-index 재생성 → en/ 분할 → web/ 복사 → validate.py
python3 projects/pharos/scripts/sync_web_data.py --check  # 쓰지 않고 최신 여부만 확인
```

**v35 부터 영문 번들은 첫 화면에서 통째로 받지 않는다.** 원본은 지금처럼 `data/en.json` 하나이고
(`bulk_ingest.py`·`media_ingest.py`·`backfill_encyclopedia.py`·`rescore_scale.py` 가 계속 여기에 쓴다),
`sync_web_data.py` 가 웹 배포용 사본만 네 갈래로 나눈다.

| 웹 파일 | 내용 | 첫 화면 |
| :--- | :--- | :--- |
| `web/data/en/core.json` | 도메인·대분류·비교군·필터 팩 라벨, 장르 사전, 홈 갭 리포트 문구 | 받음 (~50KB) |
| `web/data/en/index.json` | 항목 요약 — 이름·한 줄·대표 티어 한 줄·장르·개발사 | 받음 (~1.1MB) |
| `web/data/en/{domain}/{arena}.json` | 그 비교군 항목의 전체 오버레이(판정·축·티어·출처·사전) | 그 비교군을 열 때만 (중앙 0.16MB·최대 0.78MB) |
| `web/data/en/manifest.json` | 파일별 sha256·건수·원본 해시 | 검증용(브라우저는 읽지 않음) |

- 그래서 영어 모드 첫 화면은 `core + index ≈ 1.17MB` 만 받고, 3,661종 전체 오버레이(30.8MB)는
  비교군을 열 때 그 청크 하나씩만 내려온다. 단일 `web/data/en.json` 사본은 만들지 않는다.
- 새 항목을 `data/en.json` 에 쓰고 `sync_web_data.py` 를 돌리면 청크·요약·manifest 가 함께 갱신된다
  (원본이 그대로면 아무 파일도 다시 쓰지 않는다).
- `validate.py` [10-0] 이 `data/en.json` 에서 다시 만든 결과와 `web/data/en/` 의 해시·건수·항목 집합을
  비교하고, 변조·누락 음성 테스트까지 돈다(어긋나면 FAIL).

**검색 인덱스도 가볍게 쓴다.** `data/search-index.json` 은 들여쓰기 없는 압축 JSON 으로 쓰고
(4.92MB → 2.85MB), 홈 갭 리포트 카드에서만 쓰는 `drivers`·`store_stars` 는 gap 항목에만 싣는다.
항목마다 남기는 검색용 텍스트(이름·별칭·키워드·한 줄 정의)는 첫 화면 통합 검색이 비교군 파일 없이
전 도메인을 즉시 훑는 데 필요하므로 도메인별로 쪼개지 않는다(쪼개면 검색 범위가 열린 도메인으로 좁아진다).

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

## 5-0. smoke_v13.py — 2차 대량 적재(330종+) 스모크

카탈로그·인덱스에서 건수를 계산해(하드코딩 없이) 이번 배치의 신규 12개 비교군과 보강 7개 비교군을 확인한다:
홈 데이터 칩·장르 블록, 비교군별 카드 수·`자동 수집` 배지·192px 아이콘, auto_fact 상세 안내, EN 한글 0,
390px 넘침 0, 콘솔·HTTP 오류 0, 스크린샷 2장(`live-v13-bulk2-home.png`·`live-v13-bulk2-arena.png`).

```bash
python3 projects/pharos/scripts/smoke_v13.py
python3 projects/pharos/scripts/smoke_v13.py --live --shots-dir projects/pharos/live
```

## 5-0-1. smoke_v16.py — 5차 대량 적재(1,000종 돌파) 스모크

카탈로그·인덱스에서 건수를 계산해(하드코딩 없이) 이번 배치의 신규 7개 비교군과 보강 8개 비교군을 확인한다.
`자동 수집` 배지·192px 아이콘·auto_fact 상세 안내·EN 한글 0·390px 넘침 0·콘솔/HTTP 오류 0 에 더해,
**완결작 면제 항목(Portal)이 거름이 아니라 조건부로 표시되고 상세에 '면제' 사유가 보이는지**를 확인한다.

```bash
python3 projects/pharos/scripts/smoke_v16.py
python3 projects/pharos/scripts/smoke_v16.py --live --shots-dir projects/pharos/live
```

## 5-0-2. smoke_v21.py — 등대 위저드·명작 50종 v21 스모크

기본 URL(Step 0 심플 랜딩)부터 `목표 탐색` → **항해 서약(v23, 체크 + `서약하고 나아가기`)** → Step 1(플랫폼·가격) → Step 2(소요 시간) → Step 3(난이도·후보 수) →
Step 4(목표 카드)까지 실제로 클릭하며 확인한다. 난이도 `chill`·`normal`·`hardcore` 각각 후보 수와 발급 게임의 난이도가
데이터와 일치하는지, 24개 조건 조합이 비지 않는지, 새로고침 잠금·5초 광고 건너뛰기·완료 기록 누적·EN 한글 0건·
390px 가로 넘침 0건·`?domain=catalog`/`?arena=`/`?item=` 회귀·콘솔/HTTP 오류 0건을 본다.

```bash
python3 projects/pharos/scripts/smoke_v21.py                     # web/ 로컬 서버
python3 projects/pharos/scripts/smoke_v21.py --live --shots-dir projects/pharos/live
```

스크린샷은 `--shots-dir` 에 `{prefix}-step0-desktop.png` · `{prefix}-step2-3-desktop.png` · `{prefix}-result-mobile.png` 로 저장된다.

## 5-0-2-1. smoke_v23_pledge.py — 항해 서약 v23 스모크

`목표 탐색` 직후의 **항해 서약(Pledge)** 단계를 본다. 서약을 건너뛰고 Step 1 로 가는 경로가 없는지, 키커·제목·세 문장이
확정 문구(② “끝까지 걸어가는 사람을…”)와 같은지, 체크 전 `서약하고 나아가기` 가 비활성이고 마우스·키보드(Space)로 켜지는지,
`돌아가기` → Step 0 복귀와 재진입 시 체크 초기화, 잠긴 퀘스트가 있으면 서약 없이 결과 카드로 가는지,
EN 한글 잔존 0건, 라이트 테마 룬 주변 사각 배경 없음, 390px 넘침 0, 오류 0건을 확인한다.

```bash
python3 projects/pharos/scripts/smoke_v23_pledge.py
python3 projects/pharos/scripts/smoke_v23_pledge.py --live --shots-dir projects/pharos/live
```

스크린샷은 `{prefix}-desktop.png` · `-mobile.png`(라이브 기본 prefix `live-v23-pledge`).

## 5-0-3. smoke_v22_brand.py — 브랜드 룬·등대 심볼 v22 스모크

`assets/brand/` 에셋의 존재·알파(모서리 0)·HTTP 200, 헤더 룬 마크(46px/모바일 34px)·파비콘 연결, Step 0 등대 심볼의
크기(데스크톱 126~180px · 모바일 104~140px)·가로 중앙·CTA 위 배치, `🚨` 제거, 라이트 테마에서 모서리에 사각 배경이
비치지 않는지(스크린샷 픽셀), KO/EN, 390px 넘침 0, 콘솔/HTTP 오류 0 을 본다.

```bash
python3 projects/pharos/scripts/smoke_v22_brand.py
python3 projects/pharos/scripts/smoke_v22_brand.py --live --shots-dir projects/pharos/live
```

스크린샷은 `{prefix}-desktop.png` · `-mobile.png` · `-light.png` · `-en.png` 로 저장된다(라이브 기본 prefix `live-v22-brand`).

## 5-0-4. make_brand_assets.py — 브랜드 심볼 에셋 생성

`downloads/` 의 승인 원본(사파이어 나침반 룬 · 골드 모노라인 등대)에서 검정/딥 네이비 배경을 알파로 분리하고,
경계 픽셀을 배경색으로 un-premultiply 해 프린징 없이 페더링한 뒤 타이트 트리밍해 `web/assets/brand/` 에 저장한다.
원본은 `web/assets/brand/source/` 와 `projects/pharos/assets/brand/source/` 에 그대로 보관하며 절대 덮어쓰지 않는다.

```bash
python3 projects/pharos/scripts/make_brand_assets.py            # 에셋 생성
python3 projects/pharos/scripts/make_brand_assets.py --preview  # live/brand-preview/ 에 다크·라이트 합성 미리보기
```

## 5-0-5. smoke_v28_lighthouse_v3.py — 등대 v3(4분야 + 전체 랜덤) 스모크

등대가 게임·애니·영화·만화 네 분야와 `🎲 상관없이(전체 랜덤)` 를 함께 추첨하는 v3 흐름을 본다.
서약 뒤 **분야 선택**(다섯 카드) → 게임은 `1/3 플랫폼·가격 → 2/3 소요 시간 → 3/3 난이도`,
애니·영화·만화·전체 랜덤은 `1/2 분량·시간 → 2/2 무게감`(플랫폼·가격 단계 없음) → 목표 카드.
카드의 분야 배지(🎮/📺/🎬/📖)·목표 문구·난이도·상세 모달·완료·5초 광고 건너뛰기, 분야와 무관하게
`localStorage` 의 current 가 하나만 잠기는지(version 3), 새로고침 뒤에도 같은 목표인지, EN 각 단계 한글 0건,
390px 가로 넘침 0건, 콘솔·HTTP 오류 0건을 확인한다. 데이터 계약(작품 139종 · 목표 271개 ·
분야마다 단계×난이도 9조합 후보 2개 이상 · 모든 id 가 search-index.json 과 일치)도 함께 검사한다.

```bash
python3 projects/pharos/scripts/smoke_v28_lighthouse_v3.py
python3 projects/pharos/scripts/smoke_v28_lighthouse_v3.py --live --shots-dir projects/pharos/live
```

스크린샷은 `{prefix}-lighthouse-v3-category.png` · `-lighthouse-v3-media-quest.png` · `-lighthouse-v3-media-mobile.png`
(라이브 기본 prefix `live-v28`).

## 4-1. build_lighthouse.py — 등대 퀘스트 카탈로그(v3.0.0)

`drafts/lighthouse/` 의 편집 원본(게임 `games-*.json`, 미디어 `media-anime.json`·`media-movie.json`·`media-manga.json`)을
한 파일 `data/lighthouse-quests.json`(+`web/data/` 사본)로 합친다. 게임은 `game_id`·`free_to_play`·`platforms`,
미디어는 `item_id`·`category` 만 다르고 퀘스트 8필드(`title`·`desc`·`tip`·`est_time` × KO/EN)는 같다.
분야별 단계 문구(`tiers.game/anime/movie/manga/all`)와 분야 메타(`categories`)도 여기서 만든다.

```bash
python3 projects/pharos/scripts/build_lighthouse.py          # 쓰기 + 검사
python3 projects/pharos/scripts/build_lighthouse.py --check   # 원본·사본 최신 여부만
```

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

## 7. media_ingest.py — 작품 도메인(영화·애니·만화) 적재

```bash
python3 projects/pharos/scripts/media_ingest.py            # 수집·생성·기록(포스터 아이콘 포함)
python3 projects/pharos/scripts/media_ingest.py --no-icon  # 아이콘 생략
python3 projects/pharos/scripts/media_ingest.py --only anime
```

v31(2026-11-28)부터 통합 `media` 도메인 대신 **영화(movie)·애니(anime)·만화(manga) 3개 도메인**을 쓰고,
도메인마다 대분류 2개·장르 비교군 7개(총 21비교군)에 항목을 나눠 적재한다. 새 항목의 비교군은
`pick_arena()` 가 AniList·Letterboxd 장르와 형식(극장판)으로 고르고, 규칙에 없는 장르는 도메인 기본
비교군(`movie-drama`·`anime-action`·`manga-action`)으로 간다. 스펙(`drafts/media-2026-11-27/spec.json`)의
작품을 **AniList GraphQL**(평균 점수·채점 분포·표지·장르·방영/연재 기간·스튜디오·작가)과
**Letterboxd 영화 페이지 JSON-LD**(평점·평가 수·감독·장르·개봉일·포스터)로 채운다. 키가 필요 없다.

| 축 | 계산 |
| :--- | :--- |
| 사용자 | AniList 평균(0~100)·Letterboxd 평점(5점)×20, 표본 수 = 채점 분포 합 / 평가 수 |
| 표본 보정 | v0.6.0 계약(`validate.scale_expected`)을 그대로 호출 — 검증기와 같은 계산 |
| 객관 | 62 + 완결성(+12/−10/−14) + 접근 경로 수(+8/+2) + 작품 수명(+8/+5/+2) |
| AI 검토 | 중립 60 + (사용자 평균−80)×0.7 + min(6, log10 표본) + 완결성(+6/0/−6) |
| 판정 | `validate.compute_verdict` — 손으로 쓴 판정 없음 |

포스터는 2:3 비율을 그대로 쓰지 않고 **흐린 배경 위에 세로로 앉힌 320×320 WebP** 로 만들어
정사각 아이콘 틀(`.item-icon`)에서 잘리지 않게 한다. 확인하지 못한 값(한국 시청 플랫폼·작품 단위 가격·
최근 화 공개일)은 `unknown`·`data_quality.unverified` 로 남기고, 가격 표기는 `amount: null`(통화 `none`)이다.

```bash
python3 projects/pharos/scripts/smoke_v26_media.py                     # 구 미디어 URL 호환 스모크 20항목
python3 projects/pharos/scripts/smoke_v31_split_media.py               # 분리 3도메인·21비교군 스모크 67항목
python3 projects/pharos/scripts/smoke_v31_split_media.py --live --shots-dir projects/pharos/live
```

## 8. verify_ui.py 상태 (2026-11-27)

`web/tests/verify_ui.py` 는 v3 홈(`.hero`) 시절 선택자를 아직 들고 있어 현재 등대 첫 화면에서는
`Page.inner_text(.hero)` 대기로 멈춘다(이번 배치 이전부터의 상태). 지금의 회귀 검증은
`smoke_v21.py`(120항목) · `smoke_v22_brand.py`(69) · `smoke_v23_pledge.py`(61) · `smoke_v26_media.py`(20, 구 URL 호환) ·
`smoke_v28_lighthouse_v3.py`(101, 등대 4분야·전체 랜덤) · `smoke_v30_encyclopedia.py`(41) · `smoke_v31_split_media.py`(67, 도메인 분리)가 맡는다.

## 9. v29 (2026-11-28) — 미디어 3차 225종 + 게임·앱·AI 80종 = 2,072종

미디어는 2차와 같은 두 스크립트로 적재하고(새 배치 폴더 `drafts/media-2026-11-28-batch3/`), 게임·앱·AI 는
`bulk_ingest.py` 스펙 하나(`drafts/bulk7-2026-11-28/spec7.json`, 96종 중 80종 신규)로 넣었다.
이번 배치부터 `bulk_ingest.py` 는 **사용자 축이 빈 항목에 `scale_adjustment` 기록을 만들지 않는다**
(표본이 없는데 `sample_count` 0 기록이 붙어 검증기와 어긋나던 문제).

```bash
python3 projects/pharos/drafts/media-2026-11-28-batch3/build_spec.py
python3 projects/pharos/drafts/media-2026-11-28-batch3/resolve.py --only anilist
python3 projects/pharos/drafts/media-2026-11-28-batch3/resolve.py --only movie
python3 projects/pharos/scripts/media_ingest.py --merge \
    --spec projects/pharos/drafts/media-2026-11-28-batch3/spec.json \
    --hooks projects/pharos/drafts/media-2026-11-28-batch3/hooks.json
python3 projects/pharos/scripts/bulk_ingest.py --spec projects/pharos/drafts/bulk7-2026-11-28/spec7.json
python3 projects/pharos/drafts/bulk7-2026-11-28/check_steam_categories.py     # 완결작 면제 근거
python3 projects/pharos/drafts/bulk7-2026-11-28/patch_feature_complete.py --write
python3 projects/pharos/scripts/sync_web_data.py
python3 projects/pharos/scripts/check_en_leaks.py --all
python3 projects/pharos/scripts/shot_v29_2000.py        # live-v29-2000-home.png · -media.png
```

결과 기록: `projects/pharos/drafts/bulk7-2026-11-28/2026-11-28-v29-summary.md`

## 10. v30 (2026-11-28) — 사전(encyclopedia) 기반 · 대표작 168종 백필

평가(점수·티어·판정)와 분리된 **작품·앱 사전**을 스키마·파이프라인·상세 UI 에 넣었다.
`encyclopedia` 는 선택 필드라 기존 2,072종은 그대로 유효하고, 없는 항목은 UI 가
`one_liner·developer·release_date·genres·platforms·sources` 로 **기본 제원 폴백 뷰**를 그린다.

```bash
# 1) 대표작 사실 재확인 — Steam 언어(한국어 지원)·상점 분류(모드)·공식 사이트 (49종)
python3 projects/pharos/scripts/enrich_encyclopedia_facts.py

# 2) 큐레이션(등대 139종 + 주요 앱·AI 29종) + 수집 사실 → data/{domain}/*.json · data/en.json
python3 projects/pharos/scripts/backfill_encyclopedia.py --dry-run
python3 projects/pharos/scripts/backfill_encyclopedia.py

# 3) 인덱스·웹 사본·검증
python3 projects/pharos/scripts/sync_web_data.py
python3 projects/pharos/scripts/check_en_leaks.py --all

# 4) 스모크 — 신규 사전 + 기존 등대·브랜드·서약·미디어
python3 projects/pharos/scripts/smoke_v30_encyclopedia.py
python3 projects/pharos/scripts/smoke_v21.py
python3 projects/pharos/scripts/smoke_v22_brand.py
python3 projects/pharos/scripts/smoke_v23_pledge.py
python3 projects/pharos/scripts/smoke_v26_media.py
python3 projects/pharos/scripts/smoke_v28_lighthouse_v3.py
```

**파이프라인** — `bulk_ingest.py` 는 이제 Steam `supported_languages`·`categories`·`website` 를 함께 읽어
신규 항목에 기본 사전(플랫폼·한국어·플레이 방식·모드·가격·평가·최근 업데이트·라이선스)을 자동 생성한다.
`media_ingest.py` 도 제작·분량·방영·평점·장르·감상 경로로 기본 사전을 만들고, `--dry-run` 으로 쓰지 않고 확인할 수 있다.
두 스크립트의 사전 생성은 `scripts/encyclopedia.py`(`compose`)를 공유하며, 확인하지 못한 값은 넣지 않는다
(제원 3개를 못 채우면 사전 없이 두고 UI 폴백이 맡는다).

**검증기** — `validate.py` 가 ⑴ 사전 블록의 타입·길이(스키마), ⑵ `related[].id` 가 실제 카탈로그 항목인지·자기 참조·중복,
⑶ `related[].relation` 5종, ⑷ KO/EN 개수·순서 일치와 한글 잔존, ⑸ 음성 테스트(없는 id·자기 참조·중복·짧은 개요·http(s) 아님)를
검사하고, 관계 왕복(sequel↔prequel)은 경고로 남긴다.

## 11. smoke_v35_split_data.py — 영문 번들 분할·지연 로딩 스모크 (v35)

```bash
python3 projects/pharos/scripts/smoke_v35_split_data.py                                  # web/ 로컬
python3 projects/pharos/scripts/smoke_v35_split_data.py --live --shots-dir projects/pharos/live
```

3,661종 32MB `data/en.json` 을 첫 화면에서 받지 않는지 화면과 네트워크 양쪽에서 확인한다.

- 데이터 — `en/manifest.json` 항목 수 = 카탈로그 전체, 비교군 청크 101개가 항목을 한 번씩만 담음,
  단일 `web/data/en.json` 사본 없음, `core + index` 가 원본의 15% 이하, 최대 청크 1MB 이하.
- 초기 로드(EN) — `en/core.json`·`en/index.json` 만 받고 비교군 청크·`en.json` 은 받지 않음,
  첫 화면 JSON 이 원본의 1/5 이하 (실측 4.24MB vs 30.83MB).
- 초기 로드(KO) — `/data/en/` 요청 0건.
- 비교군(EN) — 그 비교군 청크 하나만 추가로 받고, 카드 수 = 데이터 건수, 카드에 한글 0.
- 상세·관련작(EN) — 딥링크로 모달이 바로 열리고, 관련작을 누르면 그 비교군 청크를 새로 받아
  제목·URL 이 바뀌며 한글이 없다. 사전(기본 정보) 섹션 영문.
- 검색(EN) — 영문 이름으로 결과가 나온다(요약 인덱스만으로, 비교군 파일 없이).
- 딥링크 — `?domain=media` 구 URL → 영화, `?lang=en&item=` 새로 열기, KO 복귀·언어 전환.
- 반응형 390px 가로 넘침 0 · 콘솔 오류 0 · 스크린샷 `live-v35-split-home.png`·`live-v35-split-en.png`.
