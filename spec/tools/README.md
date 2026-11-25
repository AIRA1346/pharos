# 파로스 수집·검증 스크립트

파로스 데이터는 **무료 공개 API 로 사실을 모으고, 사람이 판단만 얹는** 반자동 파이프라인으로 만든다.
아래 순서대로 실행하면 새 비교군 1개를 30분 안에 라이브까지 올릴 수 있다.

```
① 수집    scripts/auto_collect.py   → drafts/{id}.draft.json (사실 70% + 아이콘) + drafts/{id}.review.json
② 검토    drafts/reviewed/{id}.json (사람이 나머지 30% 작성)
③ 반영    scripts/apply_review.py   → data/{domain}/{arena}.json
④ 빌드    scripts/sync_web_data.py  → search-index.json 재생성 + web/ 사본 동기화 + validate.py 전체 검증
⑤ 검증    web/tests/verify_ui.py    → 실제 화면 동작(Playwright) + 아이콘 로드
⑥ 배포    web/ 폴더를 GitHub Pages(AIRA1346/pharos) 루트로 커밋·푸시
```

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

## 5. verify_ui.py — 실제 화면 검증

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
