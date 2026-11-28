# 11차 대량 적재 — 3,661 → 4,436종 (+775) · 2026-11-28

## 결과

| 도메인 | 이전 | 이후 | 순증 | 추천 | 조건부 | 거름 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 영화 movie | 410 | **568** | +158 | 146 | 12 | 0 |
| 애니 anime | 645 | **802** | +157 | 10 | 147 | 0 |
| 만화 manga | 587 | **739** | +152 | 5 | 147 | 0 |
| 게임 game | 1,201 | **1,412** | +211 | 40 | 131 | 41 |
| 앱 app | 738 | **813** | +75 | 45 | 151 | 7 |
| AI ai | 80 | **102** | +22 | 6 | 14 | 4 |
| **합계** | **3,661** | **4,436** | **+775** | 252 | 601 | 52 |

- 계층은 6도메인 · 70대분류 · 101비교군 그대로. 사전 226 → **243종**(관련작 361 → 398개). 등대 139종/271목표 그대로.
- 기존 3,661종은 **항목 단위 전 필드 비교로 변경 0건**(배포본 `repo-pharos/data` 대조).

## 어떻게 채웠나

### 미디어 467종 — Wikidata(CC0)만 사용, AniList·Letterboxd 흔적 0
- `drafts/media-2026-11-28-batch11/pool.py` 가 Wikidata SPARQL로 도메인별 작품을 **위키백과 언어판 문서 수(sitelinks) 순**으로 받아 후보 풀을 만들고(영화 175 · 애니 984 · 만화 362), 이미 적재된 QID·이름을 뺐다. 사람이 고른 작품은 `picks_movie.py`·`picks_anime.py`·`picks_manga.py` 에 **QID를 풀에서 확정해** 적었다(검색으로 다른 작품을 집는 사고 차단).
- `scripts/media_ingest.py`(v2.0)는 Wikidata 사실(공개일·종료일·화수·권수·감독·작가·제작사·장르·수상 P166·후보 P1411·언어판 문서 수)로 `auto_fact` 항목을 만들고, 판정은 `validate.compute_verdict` 로 계산한다. 사용자 축은 비우고(⚪), 작품성 축은 수상·후보·문서 폭으로 계산한다.
- **media_ingest v2.0 보수 4건** — ⑴ 객관 축을 새 사실에서 다시 계산(기존엔 틀 항목의 점수를 물려받았다) ⑵ 영화는 개봉 시점에 완결로 처리(기존 410종과 같은 규칙) ⑶ 만화 접근 경로 `print+web` ⑷ 연 단위 정밀도 날짜는 날짜 필드에 쓰지 않음.
- 표지: Wikidata P18(자유 이용)이 영화·애니 대부분에 없어, **파로스가 직접 그린 표지 467장**(어두운 바탕·금색 테두리·작품명·분야 표기, 320×320 WebP)을 만들었다. 남의 이미지를 가져오지 않았다.
- 영문 오버레이: 같은 비교군 기존 영문 항목을 틀로 구조를 맞추고, 수치 문장은 항목 자신의 값에서 계산, 한 줄 소개는 사람이 쓴 영문(`hooks.json`).

### 게임 211종 — Steam·App Store·Play 공개 API
- `bulk_ingest.py` 스펙(`build_games.py`, 237종 제안 중 211종 성공). 30종씩 8청크, `PHAROS_STEAM_PACE=1.1` 로 429 회피.
- **완결형 패키지 게임 면제**: Steam 상점 분류를 592종 확인해 **Single-player 단독 391종**을 근거(등급 A)로 `maintenance_status=feature_complete`·`stale_over_12m=exempt` 처리 → 신규 게임 거름 105 → 41.

### 앱 75종 · AI 22종
- 앱: App Store 검색·GitHub 저장소·Play 패키지. GitHub API 시간당 60회와 iTunes 403 에 막힌 구간은 Play 페이지 수집으로 우회했고, AI 22종은 App Store 검색과 Play 패키지(`com.deepseek.chat` 등)로 채웠다.
- 한국어 전용 이름 3종(Naver Pay/Dictionary/Calendar)은 영문 이름 + 한국어 별칭으로 바꿔 EN 화면 한글 누출을 없앴다.

### 사전(encyclopedia) 17종 직접 작성
《백설 공주와 일곱 난쟁이》·《밤비》·《석양의 무법자》·《브이 포 벤데타》·《콰이강의 다리》·《소녀혁명 우테나》·《신비한 바다의 나디아》·《미래소년 코난》·《천사의 알》·《울프스 레인》·《러브히나》·《츠바사》·《사자에상》·《여기는 잘나가는 파출소》·《테르마이 로마이》·Recettear·Moonlighter — KO/EN 개요·핵심 제원·특징·관련작. 이번 배치의 자동 조립 사전 블록은 지웠다(문장이 기계적).

## 검증 (로컬 = 라이브)

- `schema/validate.py` **PASS** — 4,436건 스키마 100% · 의미 규칙 위반 0 · 계층 6/70/101 · 판정 재계산 일치 · 음성 테스트 33/33 · 완결작 면제 9/9 · 강도 3단계 10/10 · **아이콘 4,436/4,436** · **영문 4,436/4,436** · web 사본 일치 · 등대 139종/271목표 · 사전 243건/관련작 398개.
- `scripts/check_en_leaks.py --all` — 4,436건 한글 잔존 **0개**(등대 271퀘스트 0건).
- 스모크 9종: v21 120/120 · v22 69/69 · v23 61/61 · v26 20/20 · v28 101/101 · v30 41/41 · v31 69/69 · v35 40/40 · v38 66/66.
- `smoke_v38_three_modes.py` 의 건수 단언(3,661·226)을 데이터에서 계산하도록 고쳤다(배치가 늘어도 낡지 않게).

## 넣지 못한 것 (지어내지 않고 제외)

- Steam 검색 미확정: Jet Set Radio · Friday Night Funkin'(DLC만 존재) · Blade & Soul · Zero Escape: Virtue's Last Reward(코스튬 DLC만) · OOTP 25 · BlazBlue: Central Fiction · FATAL FRAME 2종(정식 표기 불일치) · Caesar III(™ 표기) · Zeus · Emperor.
- App Store 확정 실패: Alchemy Stars · Project SEKAI · Idoly Pride · Artery Gear · Lineage W · Ni no Kuni: Cross Worlds · Evony 등.
- GitHub 403(시간당 60회)으로 미수집: Lobe Chat · Big-AGI · Chatbot UI · SillyTavern · Cody · MLX · Stable Diffusion · Diffusers · AnimateDiff 등 20종 → 다음 배치 1순위.
- 한계: 미디어는 한국 시청 가능 플랫폼·작품 단위 가격·최근 화 공개일 미확인, 작품성 축은 자동 기록. 앱·AI 일부는 스토어 표본이 얇다.

## 재현 파일

`projects/pharos/drafts/media-2026-11-28-batch11/` — `pool.py`·`pool.json`·`picks_*.py`·`build_spec.py`·`spec.json`·`hooks.json`·`finalize_en.py`·`generate_icons.py`·`curated.py`·`apply_encyclopedia.py`·`build_games.py`·`build_apps.py`·`spec-*.json`·`check_steam_categories.py`·`patch_feature_complete.py`·`steam-categories.json`.
