# 파로스 Pharos — 오늘 도전할 목표를 비추는 등대

앱·게임·AI 도구를 **내 기준으로 거르는** 파로스의 첫 화면은 이제 **🚨 등대**입니다. 플랫폼·가격·소요 시간·난이도를 한 단계씩 고르면 검증한 명작 50종 중 하나와 그 안의 실제 목표 하나를 퀘스트로 비춥니다. 사용자 평가·객관 신뢰 지표·AI 검토를 **내 가중치로 합치고**, 강제 광고·확률형 아이템·불투명 크레딧 같은 **절대 거름 조건**을 적용하는 1,467종 카탈로그는 **🧭 전체 탐색** 탭에 있습니다.
빌드 도구 없이 HTML/CSS/ES Module만으로 동작하며, 점수·신호·판정 계산은 전부 브라우저에서
`schema/item.schema.json`의 `x-pharos.client` 계약대로 실시간으로 이뤄집니다. 서버는 파일만 전달합니다.

**라이브:** https://aira1346.github.io/pharos/ · 영어: https://aira1346.github.io/pharos/?lang=en

**v21 — 등대 단계형 위저드 · 명작 50종 재선정 · 퀘스트 150개 전면 재작성 (2026-11-27):** 등대를 **한 번에 한 가지만 고르는 4단계 위저드**로 바꿨습니다. Step 0 은 `지금 해볼 만한 명작 / 목표 하나를 비춥니다` 카피와 **`🚨 목표 탐색`** 버튼 하나뿐이고(히어로·4칸 통계·3축 필터·빈 점선 박스 제거), 진행 중인 목표가 `localStorage` 에 있으면 곧바로 Step 4 로 열립니다. Step 1 은 `어디서 플레이하나요?`(전체·PC·모바일) + `가격 조건`(전체·무료만)에 `1 / 3` 진행 표시, Step 2 는 `얼마나 몰입할까요?` 1단계·짧게(1~5시간) / 2단계·제대로(엔딩까지) / 3단계·길게(마스터·심화) 카드(누르면 바로 다음), Step 3 은 `원하는 난이도는요?`(상관없이·편안·보통·매운맛)와 고른 조건 요약, **`조건에 맞는 명작 N종` 실시간 후보 수**, `🚨 목표 받기` 입니다. 플랫폼 3 × 가격 2 × 난이도 4 = **24개 조합 모두 후보 1종 이상**이고 0종이면 버튼을 끄고 이유를 안내합니다. Step 4 카드는 아이콘·이름·난이도 배지·플랫폼/가격 태그·목표 1줄·핵심 팁·상세 링크에 `✅ 완료했어요` · `📺 광고 보고 다른 목표 받기`(5초 카운트다운)를 두고, 완료·건너뛰기 뒤 랜딩으로 돌아갑니다(완료 기록은 1건 이상일 때만 하단에, `1,467개 … 비교해 보기` 배너 유지). **명작 50종**은 `brawl-stars`·`clash-of-clans`·`marvel-snap`·`overwatch-2`·`the-finals` 같은 가벼운 라이브 게임을 빼고 위쳐3·스카이림·엘든링·다크소울3·세키로·BG3·디스코 엘리시움·포탈2·아우터 와일즈·할로우 나이트·셀레스트·하데스·데드셀·슬레이 더 스파이어·발라트로·인스크립션·아이작·뱀파이어 서바이버즈·인투 더 브리치·다키스트 던전·XCOM2·탈로스 원리·바바 이즈 유·모뉴먼트 밸리·오브라 딘·팩토리오·림월드·Oxygen Not Included·마인크래프트·테라리아·스타듀 밸리·서브노티카·발하임·데이브 더 다이버·리스크 오브 레인2·DMC5·역전재판·페르소나5R·RDR2·ETS2 같은 완성작으로 다시 짰고, 무료는 핵심 10종(path-of-exile·warframe·dota-2·counter-strike-2·pubg-battlegrounds·limbus-company·arknights·wuthering-waves·genshin-impact·honkai-star-rail)만 남겼습니다. 게임마다 **난이도 `chill` 13 · `normal` 21 · `hardcore` 16** 을 붙였고, **150개 퀘스트**는 보스·기믹·선택·엔딩 중심으로 KO/EN 전면 재작성했습니다(예: `백오차드의 그리핀을 사냥해 첫 위쳐 계약을 완수`, `사마귀 군주 3연전을 이기고 심연의 문 열기`, `라다곤과 엘덴 비스트를 꺾고 엘덴의 왕이 되기`). `data/lighthouse-quests.json` 은 schema **1.1.0** 으로 게임별 `difficulty` 를 담고, `build_lighthouse.py`·`validate.py` 가 24개 조합 후보 0종 여부까지 검사합니다. 검증: `validate.py` PASS(등대 50종/150 · 잘못된 난이도 음성 테스트) · `check_en_leaks.py --all` 한글 0경로 · 새 `smoke_v21.py` 로컬·라이브 **88/88**(Step 0~4 흐름 · 난이도 3종 · 잠금 · 5초 광고 · 기록 누적 · EN · 390px · 딥링크 회귀 · 콘솔/HTTP 0)(스크린샷 `live/live-v21-step0-desktop.png`·`live/live-v21-step2-3-desktop.png`·`live/live-v21-result-mobile.png`).

**v20 — 등대가 메인 화면, 카탈로그는 전체 탐색 탭 (2026-11-27):** 기본 랜딩(`/`)이 **등대 퀘스트 화면**이 됐습니다. 로고를 눌러도 등대로 돌아오고, 기존 `?domain=lighthouse` · `?tab=lighthouse` 딥링크도 그대로입니다. 상단 탭은 **`🚨 등대`(기본) · `🧭 전체 탐색` · `앱` · `게임` · `AI 도구`** 순서로 재편했고, 기존 카탈로그 홈(통합 검색 · 도메인 필터 · 장르별 추천 · 갭 리포트)은 **`🧭 전체 탐색`** 탭(`?domain=catalog` · `?domain=all`)이 맡습니다 — 기존 `?arena=…` · `?item=…` · `?compare=…` 딥링크는 100% 유지됩니다. 등대 히어로는 "별점 사이트가 아니라, 지금 도전할 목표를 비춥니다"로 정체성을 세우고 **① 조건 고르기 → ② 명작 한 편 → ③ 목표 하나 완료** 3단계 안내와 명작·퀘스트·무료·내 완료 4칸 통계 패널을 붙였으며, 완료 기록 아래에는 **`1,467개 앱·게임·AI 도구 직접 비교해 보기 →`** 카탈로그 배너를 두었습니다. KO/EN 문구를 모두 채우고 390×844에서 탭 5개가 한 줄에 들어가도록 다듬었습니다. 검증: `validate.py` PASS · `check_en_leaks.py --all` 한글 0경로 · `smoke_v20.py` 로컬·라이브 **78/78**(스크린샷 `live/live-v20-main-lighthouse-desktop.png`·`live/live-v20-main-lighthouse-mobile.png`) · 기존 `smoke_v19.py` **49/49** 재통과.

**🚨 등대 퀘스트 v19 (2026-11-27):** 파로스가 검증한 **명작 50종** 중 하나를 추첨해 그 게임의 **실제 목표 하나**를 비춥니다 — 퀘스트는 **150개(50×3)**, 무료 게임 **18종**(모바일 가챠·타워디펜스·카드, PC FPS·MOBA·ARPG·루터슈터, 프리미엄 로그라이크·메트로배니아·오토메이션·CRPG 등)이라 `무료만` 필터에서도 장르가 다양합니다. 퀘스트는 '튜토리얼·1시간 플레이' 같은 빈말이 아니라 **첫 보스·중반 전환점·엔딩/최고 난이도**를 실제 인게임 목표로 적었고(예: Hades 메가에라 → 첫 탈출 → 열기 16, Hollow Knight 거짓 기사 → 사마귀 군주 → 광휘 진엔딩, Balatro 안테 8 → 덱 3종 클리어 → 골드 스테이크), 게임마다 한 줄 팁과 예상 소요를 붙였습니다. **한 번 받은 퀘스트는 `localStorage(pharos_lighthouse_state_v1)` 에 저장**돼 새로고침·재방문해도 같은 게임·같은 퀘스트가 유지되고 그동안 조건·재뽑기가 잠깁니다. `✅ 퀘스트 완료` 는 완료 기록(누적 카운트 + 최근 배지)을 남긴 뒤 재뽑기를 해금하고, `🎬 광고 보고 건너뛰기` 는 보상형 광고 자리 안내 모달과 **5초 테스트 카운트다운** 뒤 건너뛰기를 열어 줍니다. 카드의 `게임 상세 보기` 는 기존 파로스 상세 모달을 등대 화면 위에서 엽니다(`?domain=lighthouse&item=…`). 데이터는 `data/lighthouse-quests.json`(+`web/data/` 사본)에 KO/EN 8필드로 두고 `scripts/build_lighthouse.py` 가 생성·검사하며, `validate.py` [11]·`check_en_leaks.py` 가 50종·150개·game_id 실재·EN 한글 0을 확인합니다. 검증: `validate.py` PASS(1,467건 + 등대 50종/150퀘스트) · `check_en_leaks.py --all` 한글 0경로 · `smoke_v19.py` 로컬·라이브 **49/49**(스크린샷 `live/live-v19-lighthouse-desktop.png`·`live-v19-lighthouse-mobile.png`) · 기존 `smoke_v18.py` 로컬·라이브 **29/29**.

**기준표 v0.6.0 — 유저 수 규모 보정 (2026-11-26, v18):** 같은 별점이라도 **몇 명이 검증했는가**를 사용자 축 점수로 옮겼습니다. 누적 표본 1만 건을 기준점(0)으로 **10만 +3.0 · 100만 +5.5 · 1,000만+ +7.5**, 1,000건 −2.0 · 100건 −5.0 · 100건 미만 −6.0을 `log10(표본 수)` 선형 보간으로 적용해 경계에서 판정이 계단처럼 뒤집하지 않게 했습니다. 다만 **평점 게이트**가 먼저입니다 — 기본 평점 70점 이상만 보정 100%, 60~70은 비례, 60 미만은 0이라 '욕먹지만 유명한 앱'은 표본 크기로 미화하지 않습니다(Hero Wars 4.6★·181만 → 보정 0, 그대로 거름). **하드 필터는 그대로 먼저** 걸립니다 — Clash Royale 은 표본 4,190만으로 사용자 축이 80→87.5 로 올랐지만 확률형 상자가 성장의 핵심이라 계속 거름, Microsoft To Do 는 95→99.7 이지만 2027-06-30 종료 예고로 계속 거름입니다. 1,467종을 다시 계산해 판정 **추천 365→376 · 조건부 978→967 · 거름 124 그대로**(판정 변화 23건) — YouTube 80→**87.5** 🟢 · Instagram 81.7→**89.2** 🟢 · TikTok 82.2→**89.7** 🟢 · Brawl Stars 85.1→**92.6** 🟢 · Rainbow Six Siege 81→**86.3** 🟢 · Black Desert 72→**74.9**(축 80.95) 🟢 이 올라갔고, 표본이 얇은 Mathpix(142건) 90→**85.5** 🟡 · Star Valor(2,261건) 88→**86.7** 🟡 · Krita(6,937건) 72→**71.7** 🟡 이 내려갔습니다. 항목마다 `axes.user_rating.scale_adjustment`(표본 수 · 로그 보정 · 게이트 · 적용치 · 최종)를 남기고 상세 '산정 메모'에 계산 과정을 보여 주며, `validate.py` 는 그 기록을 계약으로 **다시 계산해 대조**합니다. 검증: `validate.py` PASS(1,467건 · 판정 재계산 일치) · `check_en_leaks.py --all` 한글 0경로 · `smoke_v18.py` 로컬·라이브 **29/29**.

**6차 대량 팩트 적재 278종 · 1,400종 돌파 (2026-11-26, v17):** 앱 5 · 게임 2, **신규 7개 비교군**에 81종을 넣고 기존 30여 비교군을 197종 보강해 **도메인 3 · 대분류 64 · 비교군 80 · 전체 1,467종**(verified 107 + auto_fact 1,360)이 됐습니다. 앱은 **웹툰·만화·전자책 서비스**(KakaoPage · RIDI · Lezhin Comics · 밀리의 서재 · 교보eBook · NAVER Series · Manta · MANGA Plus · Marvel Unlimited · 봄툰)·**습관·집중·타이머**(Loop Habit Tracker · Finch · Flora · Focus To-Do · Toggl Track · Clockify · Structured · Streaks · Routinery)·**2단계 인증·OTP**(Ente Auth · 2FAS · Aegis · Google/Microsoft Authenticator · Yubico · Bitwarden Authenticator · Duo Mobile)·**마인드맵·다이어그램**(Xmind · MindMeister · Lucidchart · Concepts · draw.io · tldraw · MindNode)·**커뮤니티·RSS**(Substack · NetNewsWire · FreshRSS · Miniflux · Lemmy · Ghost · Primal), 게임은 **모바일·크로스플랫폼 MMORPG**(Old School RuneScape · RuneScape · Diablo Immortal · MapleStory M · Toram Online · EVE Echoes · Ragnarok X · Pax Dei)와 **스포츠 매니저·구단 운영**(Motorsport Manager · F1 Manager 2024 · OOTP 26 · Tennis Manager 2024 · Pro Basketball Manager 2025 · EA SPORTS FC Mobile · BASEBALL 9 · Retro Bowl)입니다. 계획서의 디지털 TCG·리듬 게임은 기존 비교군(카드 22종·리듬 17종)과 같은 장르라 중복 가드에 걸려 빈 비교군이 되므로 **기존 비교군 보강**으로 넣었습니다(각 6종). ① **완결작 34건** — Steam 상점 분류를 260종 재확인해 `Single-player` 단독 34종을 `feature_complete` 로 면제(The Wolf Among Us · Cobalt Core · Rise of the Tomb Raider · SMT V: Vengeance · Heavy Rain 등). ② **검증** — `validate.py` PASS(1,467건 · 아이콘 1,467/1,467 · 영문 1,467/1,467) · `check_en_leaks.py --all` 한글 0경로 · `smoke_v17.py` 로컬·라이브 **68/68**. ③ **판단** — iTunes Search API 가 429→403 으로 IP 를 막아 iOS 전용 8종은 Play 동등 앱으로 교체했고(Squid · Adobe Express · Fotor · Blackmagic Camera · TimeTree · Calendly · GroupCal · Ragnarok X), 면제 항목 영문 판정의 '할인' 표기 누출도 고쳤습니다.

**3차 대량 팩트 적재 255종 · 500종 돌파 (2026-11-26, v14):** 게임 5 · 앱 5 · AI 1, **신규 11개 비교군**에 169종을 넣고 기존 26개 비교군을 86종 보강해 **도메인 3 · 대분류 44 · 비교군 56 · 전체 607종**(verified 107 + auto_fact 500)이 됐습니다. 게임은 **공포·서바이벌 호러**(Resident Evil 2 **84.0 🟢** · RE4 · SILENT HILL 2 · Dead by Daylight · Alien: Isolation)·**스토리·내러티브·추리**(Phoenix Wright: Ace Attorney Trilogy **85.8 🟢** · Disco Elysium · Pentiment · Citizen Sleeper)·**생활·농장·타이쿤 시뮬**(Fields of Mistria **84.8 🟢** · Dave the Diver · PowerWash Simulator · Two Point Hospital)·**디지털 보드·카드·체스**(Tabletop Simulator **85.75 🟢** · Wingspan · Terraforming Mars · Hearthstone · Chess.com · Lichess)·**모바일 액션·아케이드·러너**(Stick War: Legacy · Temple Run 2 · Alto's Odyssey · Soul Knight), 앱은 **지도·내비게이션·여행**(Booking.com · Google Maps · NAVER Map · KakaoMap · T map · Organic Maps)·**사진 편집·카메라·스캔**(Darkroom · Lightroom · Snapseed · Halide Mark III · Remini)·**가계부·금융·자산**(YNAB · Toss · KakaoPay · KakaoBank · TradingView · Wise)·**원격 제어·네트워크**(Shazam · AnyDesk · RustDesk · Tailscale · WireGuard · 1.1.1.1)·**전자책·만화·뉴스·팟캐스트**(AntennaPod · Kindle · Libby · Pocket Casts · Feedly · WEBTOON), AI 도구는 **AI 영상·음성·음악 생성**(Suno · ElevenLabs · Kling AI · Runway + GitHub 오픈소스 10종: Bark · AudioCraft · Coqui TTS · OpenVoice · RVC · F5-TTS · Fish Speech · SadTalker · Wav2Lip · Stable Audio Tools)입니다. ① **가드** — 중복 스킵 0건(255종 전량 신규) · 607건 id/이름/스토어 ID 중복 0. ② **실측** — 콜드 수집 106.3초(HTTP 514회) 중 Steam **429** 로 24종 실패 → 5분 뒤 워커 1로 재시도해 **24/24 회복**(+39초), 아이콘 255건 74초, **합계 약 147초**. ③ **검증** — `validate.py` PASS(607건 · 아이콘 607/607 · 영문 607/607), `check_en_leaks.py --all` 한글 0경로, 새 스모크 `spec/tools/smoke_v14.py` **65/65**(500종 돌파 · 신규 19비교군 · EN 한글 0 · 390px · 콘솔 0). ④ **판정** — 전체 추천 243 🟢 · 조건부 281 🟡 · 거름 83 🔴. ⑤ **남긴 판단** — MultiVersus(서비스 종료)·PC Building Simulator 2·THRONE AND LIBERTY(한국 스토어 검색 불가)·Pokemon TCG Live·Wallet by BudgetBakers·Microsoft Lens·Affinity Photo·Wavve(미국 레코드가 다른 앱)는 대체작으로 교체하고, Procreate→**Procreate Pocket**·Max→**HBO Max**·Asphalt 9→**Asphalt Legends** 로 실제 스토어 표기를 따랐습니다. KakaoMap 패키지를 카카오내비(`com.locnall.KimGiSa`)에서 카카오맵(`net.daum.android.map`)으로 정정하고, TVING 장르가 한글로 영문 화면에 새던 문제는 `bulk_ingest.py` 의 한글 장르→영문 역매핑으로 고쳤습니다. 완결형 내러티브 게임(Outer Wilds·Obra Dinn·Danganronpa·Detroit 등)은 "12개월 공지 없음 + 완결작 미확인" 규칙으로 거름이 되어, 심층 검수에서 `feature_complete` 기록이 필요한 상태로 남겼습니다.

**2단계 발행 구조 · 1차 대량 팩트 적재 103종 (2026-11-26):** 1,000종 확장을 전제로 발행 구조를 **2단계**로 바꿨습니다. ① **`review_tier`**(`verified` 기본값 | `auto_fact`) — 사람이 약관·과금·문장까지 검토한 기존 107종은 `verified`, 공개 API 값만으로 만든 1차 항목은 `auto_fact` 로 두고 **카드에 `자동 수집` 배지**, **상세 모달 상단에 "공개 스토어·저장소 API 데이터 기반 1차 판정이며, 세부 약관·과금 함정은 순차 검수 중" 안내**를 띄웁니다(검증 완료 항목에는 배지·안내 없음). ② **`spec/tools/bulk_ingest.py`** — 이름·스토어 ID·저장소 목록만 주면 Steam(이름→AppID·한국어/영어 appdetails·상점 평가·ISteamNews·SteamSpy)·App Store(iTunes 한국/미국)·Google Play(JSON-LD 평점·업데이트 날짜·광고 표기)·GitHub(repo 1회 요청)에서 사실을 모아 **스키마를 100% 채운 `auto_fact` 항목**을 만듭니다. 사용자 축=스토어 평점 표본 가중, 객관 축=라이선스·가격 표기·업데이트 주기·플랫폼 수·출시 연수, AI 축=본질 검토 전 중립값(60)에서 사실만으로 보정한 잠정값, 판정=`validate.compute_verdict` 로 검증기와 같은 규칙. 확인하지 못한 것(확률형·구독·계정·데이터 수집)은 지어내지 않고 ⚪`unknown` 으로 남깁니다. 워커 8개 병렬 + 응답 캐시로 **103종 수집 14.4초(HTTP 409회, 항목당 0.16초) + 아이콘 25.8초 ≈ 40초**, 재실행 1.8초입니다. ③ **첫 배치 103종** — 게임 `핵 앤 슬래시·액션 RPG`(8)·`소울라이크`(8)·`도시 건설·경영`(10)·`협동·파티`(10)·`레이싱·스포츠`(8) + 기존 4비교군 보강 12, 앱 `메신저·팀 협업`(8)·`미디어 플레이어`(10)·`영상 편집·녹화`(7)·`개발자 도구·터미널·API`(10)·`백업·파일 동기화`(8)·`읽기·북마크`(4). 신규 대분류 7개로 **도메인 3 · 대분류 22 · 비교군 33 · 전체 210종**(verified 107 + auto_fact 103)이 됐습니다. ④ **검증** — `validate.py` 전체 PASS(210건 · 아이콘 210/210 · 영문 210/210 · 음성 27/27), 새 스모크 `spec/tools/smoke_v12.py` **55/55**, 기존 `verify_ui.py` **733/733**(건수 단언을 데이터에서 계산하도록 바꿔 배치가 늘어도 낡지 않게 했습니다). ⑤ **남긴 판단** — 스토어 평점이 없는 GitHub 전용 도구 27종은 사용자 축을 비워 자동 단계에서는 🟢 대신 🟡 로 두고(근거 없는 추천 금지), 12개월 넘게 공지가 없는 15종은 완결작 여부를 확인할 수 없어 **거름 + "상태 미확인"** 으로 남겼습니다(심층 리뷰에서 `feature_complete` 확정 대상). 서비스가 종료된 Pocket 은 대상에서 뺐습니다.

**2차 대량 팩트 적재 142종 (2026-11-26, v13):** 유명·인기 앱·게임을 **신규 12개 비교군**으로 묶어 **142종**을 더해 **도메인 3 · 대분류 34 · 비교군 45 · 전체 352종**(verified 107 + auto_fact 245)이 됐습니다. 게임은 오픈월드 RPG(The Witcher 3 **86.2 🟢** · Cyberpunk 2077 · Red Dead Redemption 2 · Skyrim SE)·샌드박스(Satisfactory **85.8 🟢** · Garry's Mod · Kerbal Space Program · Teardown)·격투(Devil May Cry 5 **85.2 🟢** · Street Fighter 6 · TEKKEN 8)·리듬(Beat Saber **85.2 🟢** · DJMAX RESPECT V · osu!)·모바일 캐주얼 퍼즐(Monument Valley **86.4 🟢** · Brawl Stars · Roblox)·스포츠·MOBA·경쟁(Dota 2 · PUBG: BATTLEGROUNDS · EA SPORTS FC 25), 앱은 소셜(X **84.9 🟢** · Reddit · Instagram · KakaoTalk)·OTT(Netflix **86.1 🟢** · YouTube · Twitch · CHZZK)·건강(Headspace **84.5 🟢** · Strava · Nike Run Club)·언어(Anki **85.9 🟢** · Duolingo · Memrise)·음악·오디오(SoundCloud **84.8 🟢** · YouTube Music · Audacity)·오피스(Microsoft Word **86.1 🟢** · LibreOffice · Figma)이며, FPS·서바이벌·로그라이크·메트로배니아·턴제 전략·MMORPG·모바일 가챠 **7개 비교군을 18종 보강**했습니다. ① **자동 중복 방지 가드** — 적재 전 `data/` 전체에서 id·정규화 이름·스토어 ID(Steam AppID · App Store trackId · Play 패키지 · GitHub 저장소)를 인덱스로 만들고, **수집 전과 수집 후(확정 ID) 두 번** 검사해 겹치는 항목을 자동 스킵합니다(스킵 로그·실행 로그에 사유 기록 · 이번 배치 스킵 0건 · 같은 배치를 다시 돌리면 142종 전량 스킵). `validate.py` 도 전체 데이터의 id·이름·스토어 ID 중복을 검사합니다. ② **실측** — 콜드 수집 142종 **56.0초**(HTTP 642회) · 캐시 재수집 8.9초 · 아이콘 142건 26.8초 · 기록 포함 36.9초. ③ **검증** — `validate.py` PASS(352건 · 아이콘 352/352 · 영문 352/352 · 중복 0), `check_en_leaks.py --all` 한글 남은 경로 0, 새 스모크 `spec/tools/smoke_v13.py` **59/59**(건수는 데이터에서 계산). ④ **판정** — 추천 **80 🟢** · 조건부 **47 🟡** · 거름 **15 🔴**(전부 12개월 공백 + 완결작 미확인). ⑤ **남긴 판단** — Rocket League(Steam 목록에서 내려감)·NBA 2K25(신작 출시로 검색 불가)는 넣지 않고 Call of Duty: Warzone·NBA 2K26 으로 대체했고, 카카오톡·치지직·스픽은 스토어 레코드가 한국어라 영문 화면에 한글이 새던 것을 미국 스토어 레코드 우선 표기로 고쳤습니다.

**KO / EN 다국어 (2026-11-25):** 헤더 오른쪽 `KO | EN` 토글로 언어를 바꿉니다. 우선순위는 **URL `?lang=` → `localStorage` → 브라우저 언어**로, `ko`로 시작하지 않는 모든 해외 브라우저는 영어 화면을 봅니다. 전환하면 `<html lang>`·`<title>`·메타 설명·URL·🔗 링크 복사 딥링크가 함께 바뀌고 보던 화면은 그대로 유지됩니다. UI 문자열은 `js/i18n.js` 한 곳에 모았고(판정 배지 `Recommended`/`Conditional`/`Filtered`, 3축 `User Rating`/`Objective Trust`/`AI Review`, 상세 `Facts`/`Opinion`/`Verdict by tier`/`Signals`/`Alternatives`/`Reviews`/`Monetization`/`Updates`/`Sources`, 비교 표 `Best`, 방법론 모달·드로어·토스트·오류 화면까지), 데이터는 `data/en.json` 번들이 3도메인·10대분류·14비교군·**67종 전체**를 옮깁니다(카드·타일 헤드라인은 직접 쓴 영어). `validate.py` 가 영문 커버리지 67/67과 한글 잔존 0을 검사하고, `verify_ui.py` **690항목**(EN 전 화면 한글 0·390px 넘침 0·언어 전환 딥링크·브라우저 언어 감지 포함)이 통과합니다.

**반자동 수집 파이프라인 + 신규 2개 비교군 (2026-11-25):** 수집 속도를 올리기 위해 **무료 공개 API 만으로 사실 약 70%를 채우는 파이프라인**을 먼저 만들었습니다(`spec/tools/auto_collect.py`). 이름·스토어 ID·저장소만 주면 App Store(iTunes lookup + 앱 내 구입 목록)·Steam(appdetails·상점 평가·개발사 공지·SteamSpy)·GitHub(repo·릴리스·라이선스)·Google Play(평점·아이콘)에서 사실을 모아 **스키마 v0.4.0 초안 + 192×192 공식 아이콘**을 만들고, 사람이 판단할 값만 `TODO(리뷰)` 로 남깁니다. 검토 오버레이를 병합하는 `spec/tools/apply_review.py` 가 하드 필터·축 신호·티어·대표 판정을 검증기와 같은 규칙으로 다시 계산합니다. 이 파이프라인으로 **10건을 자동 수집(65요청 · 14.5초 · 항목당 1.45초 · 평균 자동 채움 70.6%)** 해 두 비교군을 새로 올렸습니다 — 게임 `메트로배니아 · 플랫포머`(Hollow Knight **90.0 🟢** · Celeste **89.5 🟢** · Nine Sols **89.25 🟢** · Ori and the Will of the Wisps **87.75 🟢** · Blasphemous **83.0 🟢**)와 앱 `이메일 클라이언트`(Proton Mail **89.0 🟢** · Thunderbird **86.0 🟢** · Apple Mail **84.0 🟢** · Spark Mail **80.0 🟡** · K-9 Mail **69.5 🟡**). 전체는 **도메인 3 · 대분류 10 · 비교군 14 · 67건**. Thunderbird 는 스토어 평점 표본이 없어 사용자 축을 ⚪로 두고 판정에서 뺐고, K-9 Mail 은 Play 3.0★(99,620건)이라 조건부, Spark Mail 은 AI 기능이 메일을 외부 AI 제공자로 넘기는 구조(개인정보 처리방침 2026-09-10) 때문에 조건부입니다. `verify_ui.py` 는 건수 단언을 데이터에서 계산하도록 바꿔 **690항목**(KO/EN 포함)이 통과합니다.

**화면·UX 마감 v3.3 (2026-11-25):** 홈 `장르별 추천` 위에 **도메인 필터 바(전체 12 · 앱 5 · 게임 5 · AI 도구 2)** 를 두어 12개 장르를 원하는 도메인만 모아 볼 수 있고, 바는 스크롤해도 상단에 붙습니다. 비교군에서 항목을 체크하면 **하단 플로팅 비교 바**(`2개 선택됨 · 나란히 비교하기 → · 선택 초기화`)가 스크롤 위치와 무관하게 떠오르고, 비교 표는 **첫 열 고정 · `최고` 셀 · 점수 차이(−2.3) · 최고/최저/차이 요약**으로 차이를 바로 보여 줍니다. 비교군 헤더와 상세 모달에는 **🔗 링크 복사**(현재 딥링크 + `링크를 복사했어요` 토스트)를 넣었습니다. 390px 모바일에서 홈·도메인·목록·비교 표·상세·방법론 모달·미세조정 드로어의 **가로 넘침 0**, 주요 버튼 터치 영역 34~40px, **라이트 테마 텍스트 대비 4.2:1 이상**까지 점검했고 `verify_ui.py` **625항목**이 통과했습니다.

**기준표 v0.5.0 — 평가 배분·표본 규모 검증 (2026-11-25):** 기본 배분을 **사용자 50 · 객관 25 · AI 25**로 바꿨습니다. 대중이 실제로 검증한 평점의 무게를 높이고, 얇은 3자 최근 표본이 수십만 건의 스토어 누적을 덮지 않게 **표본 규모 검증**을 넣었습니다(Notion 66.6→**77.0**, Obsidian 82.0→**82.5**). 객관·AI 축에서는 클라우드·비공개 소스라는 이유의 감점을 없애고 기능 완성도·생태계/연동성·안정성·보안·정책/과금 투명성으로 다시 매겼습니다 — **Google Gemini 76.2→81.5 🟢 · ChatGPT 79.3→84.0 🟢 · Google Drive 72.2→81.5 🟢 · OneDrive 73.55→81.25 🟢**. 로컬·계정·데이터 수집은 `flags` 사실로만 남기고, 새 **'프라이버시·로컬 중시' 프리셋**(객관 55% + 계정·데이터 수집 필터 자동)으로 가릅니다. 가중치 0인 프로필 축은 판정에 세지 않으며, 홈 갭 리포트는 제목대로 **거름(avoid)만** 보여줍니다. 안전장치는 그대로 — **Hero Wars 38.0 · Microsoft To Do 66.75 · Archero 58.25 · Clash Royale 61.0 은 계속 🔴**입니다.

**분야 확장 v0.4.2 (2026-11-25):** 도메인 3 · 대분류 8 · 비교군 9 · **전체 42건**. 앱에 `할 일 · 일정 관리`(Todoist 83.0 🟢 · TickTick 80.8 🟢 · Things 3 87.3 🟢 · Tasks.org 88.0 🟢 · Microsoft To Do 60.45 🔴)와 새 대분류 `보안 · 유틸리티` 아래 `비밀번호 관리`(Bitwarden 91.7 🟢 · KeePassXC 84.67 🟢 · 1Password 82.4 🟢 · Dashlane 74.45 🟡)를 더했고, 새 도메인 **AI 도구**(`ai`)의 `AI 코딩 에디터 · 에이전트`(Cline 85.75 🟢 · GitHub Copilot 83.8 🟢 · Windsurf/Devin Desktop 74.7 🟡 · Cursor 71.3 🟡)를 넣었습니다. Microsoft To Do 는 4.6★·무료·광고 없음인데도 2027-06-30 앱 종료·개인 계정 이관 불가(2026-11-18 공지)로 **거름**, Cursor 는 2026-10 X 구독으로 Claude·GPT를 **첫 요청부터 API 정가**로 청구해 **조건부**가 됐습니다. AI 도구 팩은 같은 9개 필터를 도메인 문법으로 다시 부르고(`filter_labels` — 「불투명 크레딧·한도 함정 제외」 등) 스키마·엔진은 그대로 둡니다. '별점은 높은데 거름' 리포트의 별점은 실제 스토어(android·ios·steam) 표본만 씁니다.

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

**공식 아이콘 (2026-11-25):** 42종 모두 카드·상세·비교 표에 공식 아이콘을 붙였습니다. App Store 아트워크 → 공식 사이트
아이콘 → 공식 브랜드 마크 순으로 내려받아 192×192 webp 로 저장하고(`assets/icons/`), 출처는 `assets/icons/manifest.json` 에
남깁니다. 아이콘은 각 권리자의 상표·아트워크이며 **식별 목적**으로만 씁니다.

**v3 — 장르가 먼저, 자세한 건 들어가서 (2026-11-25):** 홈과 앱·게임 화면에서 장르 설명 대신 **그 장르의 추천**이 먼저 보입니다.
장르 블록마다 공식 아이콘(44px) · 이름 · 판정(🟢 추천 / 🟡 조건부) · 가중 점수 타일 3~4개가 바로 놓이고, 타일을 누르면 상세 모달,
장르 이름이나 `전체 N종 비교 →`를 누르면 그 장르 비교군 화면으로 갑니다. 비교군 목록 카드는 아이콘·이름·개발사/장르·판정·점수 +
한 줄 요약 + 핵심 태그 2개(`선택 과금 · 무과금 가능`, `핵심 과금 · 성장 벽`, `완결작`)만 남기고, 3축 점수·필터 통과 목록·가격 티어·신선도는
상세 모달에만 두었습니다. 타일 수치도 홈이 비교군 파일을 내려받지 않고 `search-index.json` 만으로 그립니다(균형 기본 가중치·기본 필터 기준).

## v2 — 4단 탐색으로 개편

`spec/plan.md` v2.0 의 2단계 결과물입니다. 비교군 → 앱/게임 역전 구조와 `전체` 평균 혼합을 폐기하고,
분야가 늘어나도 무너지지 않는 계층으로 바꿨습니다.

| 단계 | 예 |
| :--- | :--- |
| 1 도메인 | 앱 · 게임 · AI 도구 (추후 콘텐츠·제품) |
| 2 대분류 | 생산성·지식관리 / 보안·유틸리티 / 인터넷·프라이버시 / 전략·카드 / RPG·수집 / 액션·인디 / RPG·MMORPG / 모바일 전략·디펜스 / 대화·리서치 / 개발·코딩 |
| 3 비교군 | 노트·지식관리 · 할 일·일정 관리 · 비밀번호 관리 · 클라우드 스토리지 · 웹 브라우저 · 이메일 클라이언트 · 덱빌딩 게임 · 모바일 수집형 RPG · 액션 로그라이크 · 메트로배니아·플랫포머 · PC MMORPG · 모바일 전략·디펜스 · AI 어시스턴트·검색 · AI 코딩 에디터·에이전트 |
| 4 항목·티어 | Obsidian(무료/Sync), Balatro(1회 구매) |

- **데이터 분리**: `data/catalog.json`(도메인·대분류·비교군 정의) + 비교군별 파일 `data/{domain}/{arena}.json`
  (웹은 선택한 파일만 지연 로딩) + 자동 생성 경량 인덱스 `data/search-index.json`(통합 검색·홈 리포트).
- **홈 요약 뷰**: 비교군 바로가기, `별점은 높은데 거름 판정` 리포트(예: Hero Wars 4.6★ vs 38.0점),
  통합 검색(이름·별칭·키워드), 보관함(localStorage).
- **첫 화면 경량화**: 기본 `균형 기본` 프리셋. 가중치·하드 필터·엄격 모드는 `내 기준 미세조정` 드로어 안으로,
  선택한 도메인의 필터 팩(게임 팩 / 앱 팩 / AI 도구 팩)을 먼저 노출. AI 도구 팩은 같은 9개 필터에 도메인 문법 이름을 붙입니다(`catalog.domains[].filter_labels`).
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
data/app/task-managers.json        할 일·일정 관리 5건
data/app/password-managers.json    비밀번호 관리 4건
data/app/web-browsers.json         웹 브라우저 5건
data/app/cloud-storage.json        클라우드 스토리지 5건
data/app/email-clients.json        이메일 클라이언트 5건 (auto_collect)
data/game/roguelike-deckbuilder.json  덱빌딩 4건
data/game/mobile-gacha-rpg.json       모바일 수집형 RPG 6건
data/game/action-roguelike.json       액션 로그라이크 4건
data/game/metroidvania-platformer.json 메트로배니아·플랫포머 5건 (auto_collect)
data/game/pc-mmorpg.json              PC MMORPG 4건
data/game/mobile-strategy-defense.json 모바일 전략·디펜스 6건
data/ai/ai-assistants.json         AI 어시스턴트·검색 5건
data/ai/ai-coding-tools.json       AI 코딩 에디터·에이전트 4건
assets/icons/              67종 공식 아이콘 192×192 webp + manifest.json(출처)
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
| [spec/tools/README.md](spec/tools/README.md) | 무료 API 반자동 수집 파이프라인 사용법 (`auto_collect.py` → `apply_review.py` → `sync_web_data.py` → `verify_ui.py`) |

## 계산 원칙

- 카드·상세의 수치는 모두 분할 데이터와 현재 설정에서 계산됩니다. 점수·판정 하드코딩은 없습니다.
- 비교군은 화면 상태가 아니라 데이터(`catalog.json` 의 `arenas`)에서 옵니다.
- 확인하지 못한 값은 ⚪/'미확인'으로 표시하고 추정으로 채우지 않습니다.
- 화면은 데이터에 기록된 `verdict`와 현재 설정 재계산값을 나란히 보여 주며, 값이 다르면 상세의 '계산 과정'에서 적용된 규칙을 확인할 수 있습니다.
- 파로스는 어필리에이트·유료 광고·협찬 배치를 쓰지 않습니다. 정정·이의제기는 GitHub Issue(`correction.yml`)로 받습니다.
