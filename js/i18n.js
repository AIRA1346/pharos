/**
 * 파로스 UI 사전 — 한국어/영어(KO · EN)
 *
 * 규칙
 *   · 화면에 나가는 문자열은 전부 이 파일을 거친다. 데이터(카탈로그·항목)의 번역은
 *     `data/en.json` 번들이 맡고, 이 파일은 UI 문자열·메타 라벨만 담는다.
 *   · 항목은 [한국어, 영어] 쌍으로 적는다. 키가 하나면 두 언어가 같이 움직인다.
 *   · 언어 결정 우선순위: URL `?lang=` → localStorage → navigator.language(ko* → ko, 그 외 en).
 *   · 언어를 바꾸면 `<html lang>`, `<title>`, URL 의 `lang`, 딥링크가 함께 바뀐다(app.js).
 */

export const LANGS = ['ko', 'en'];
export const DEFAULT_LANG = 'ko';
export const LANG_STORE_KEY = 'pharos-lang';

/* --------------------------------------------------------------- 문자열 사전 */
/* [한국어, 영어] — {name} 자리는 t(key, {name: value}) 로 채운다. */
const M = {
  /* 공통 */
  'skip.link': ['본문으로 건너뛰기', 'Skip to content'],
  'brand.home': ['파로스 등대 홈', 'Pharos Lighthouse home'],
  'brand.tagline': [
    '별점 대신, 내 기준으로 거르는 앱·게임·AI 도구 선별',
    'Apps, games and AI tools filtered by your standards, not star ratings',
  ],
  'brand.sub': ['파로스', ''],
  'nav.domains': ['화면 전환', 'Switch view'],
  'nav.catalog': ['🧭 전체 탐색', '🧭 Explore'],
  'nav.lighthouse': ['🚨 등대', '🚨 Lighthouse'],
  'nav.bookmarks': ['보관함', 'Saved'],
  'nav.method': ['방법론', 'Method'],
  'nav.tune': ['내 기준 미세조정', 'Tune my criteria'],
  'nav.theme.dark': ['다크', 'Dark'],
  'nav.theme.light': ['라이트', 'Light'],
  'nav.theme.toggle': ['테마 전환', 'Toggle theme'],
  'nav.lang': ['언어', 'Language'],
  'nav.lang.ko': ['한국어', '한국어'],
  'nav.lang.en': ['English', 'English'],
  'dataset.loading': ['불러오는 중…', 'Loading…'],
  'dataset.title': ['데이터·스키마 버전', 'Data and schema versions'],
  'dataset.chip': ['스키마 v{v} · {n}건 · 비교군 {a}', 'Schema v{v} · {n} entries · {a} arenas'],
  'dataset.chipTitle': [
    'item.schema.json v{v} · catalog.json {d}도메인/{c}대분류/{a}비교군 · data/{domain}/{arena}.json 지연 로딩',
    'item.schema.json v{v} · catalog.json {d} domains / {c} categories / {a} arenas · data/{domain}/{arena}.json lazy-loaded',
  ],
  'dataset.none': ['데이터 없음', 'No data'],
  'crumb.label': ['탐색 경로', 'Breadcrumb'],
  'crumb.homeNote': [
    '도메인 → 대분류 → 비교군 → 항목 순으로 좁혀 봅니다. 평균은 같은 비교군 안에서만 계산합니다.',
    'Narrow down domain → category → arena → item. Averages are only ever computed inside the same arena.',
  ],
  'crumb.compare': ['나란히 비교', 'Side by side'],

  /* 홈 */
  'home.eyebrow': ['CATALOG · 전체 탐색', 'CATALOG · EXPLORE'],
  'home.title.before': ['별점 대신, ', 'Filter by '],
  'home.title.hl': ['내 기준', 'your own standards'],
  'home.title.after': ['으로 거르는 앱·게임·AI 도구 선별', ', not star ratings'],
  'home.lede': [
    '강제 광고·확률형 뽑기·불투명 크레딧·계정 필수 같은 <strong>절대 거름 조건</strong>을 먼저 적용하고, 같은 자리의 대체제끼리만 비교합니다.',
    'Hard filters come first — forced ads, gacha pulls, opaque credits, mandatory accounts — and then only the real alternatives in the same arena are compared.',
  ],
  'home.search.placeholder': [
    '‘에버노트 대신 뭐 쓰지?’ — 이름·대체제·키워드로 검색',
    '“What do I use instead of Evernote?” — search by name, alternative or keyword',
  ],
  'home.search.aria': ['통합 검색', 'Search all entries'],
  'home.search.btn': ['검색', 'Search'],
  'home.meta.items': ['<b>{n}</b>건 평가', '<b>{n}</b> entries rated'],
  'home.meta.domains': ['<b>{n}</b>도메인', '<b>{n}</b> domains'],
  'home.meta.arenas': ['<b>{n}</b>비교군', '<b>{n}</b> arenas'],
  'home.meta.schema': ['스키마 v{v}', 'Schema v{v}'],
  'home.meta.lastAssessed': ['마지막 평가 {date}', 'Last assessed {date}'],
  'home.meta.method': ['점수 매기는 법', 'How scoring works'],
  'home.meta.tune': ['⚙ 내 기준 · {preset}', '⚙ My criteria · {preset}'],
  'home.genreTitle': ['장르별 추천', 'Recommended by genre'],
  'home.genreHint.one': [
    '{scope} · 장르를 누르면 전체 비교군, 항목을 누르면 상세가 바로 열립니다',
    '{scope} · tap a genre for its arena, tap an entry for details',
  ],
  'home.genreHint.mine': [
    '{scope} · 타일 점수·판정은 균형 기본 기준, 장르를 열면 내 기준으로 다시 계산합니다',
    '{scope} · tile scores use the balanced default; open a genre to recalculate with your criteria',
  ],
  'home.genreHint.all': ['전체 {n}개 장르', 'All {n} genres'],
  'home.genreHint.domain': ['{domain} {n}개 장르', '{domain} · {n} genres'],
  'home.domainFilterAria': ['홈 장르 도메인 필터', 'Home genre domain filter'],
  'fresh.chipTitle': ['평가일 {date} · {limit}일 초과 시 재검토', 'Assessed {date} · review after {limit} days'],
  'stars.store': ['스토어 누적 별점', 'Store lifetime rating'],
  'stars.aggregate': ['누적 평점(3자 집계)', 'Lifetime score (third-party)'],
  'tiers.weakEvidence': ['근거 약함', 'weak evidence'],
  'bookmark.on': ['★ 보관됨', '★ Saved'],
  'bookmark.off': ['☆ 보관', '☆ Save'],
  'correction.title': ['[정정] {name} ({id})', '[Correction] {name} ({id})'],
  'correction.body': [
    '대상 항목: {name} ({id})\n비교군: {arenas}\n평가일: {date}\n\n정정할 내용:\n\n근거 URL:\n\n',
    'Entry: {name} ({id})\nArena: {arenas}\nAssessed: {date}\n\nWhat needs correcting:\n\nEvidence URL:\n\n',
  ],
  'home.domainAll': ['전체', 'All'],
  'home.genreEmpty': ['이 도메인에는 아직 비교군이 없습니다.', 'No arenas in this domain yet.'],
  'home.gapTitle': ['별점은 높은데 거름 판정', 'High stars, filtered out'],
  'home.gapHint': [
    '스토어 누적 별점 {n}★ 이상인데 파로스 판정은 낮은 항목',
    'Store ratings of {n}★ or more that Pharos rates low',
  ],
  'home.gapEmpty': ['아직 이 조건에 걸리는 항목이 없습니다.', 'Nothing meets this condition yet.'],
  'home.bookmarksTitle': ['☆ 내 보관함', '☆ Saved'],
  'home.bookmarkHint': ['{n}건 · 이 브라우저에만 저장', '{n} saved · stored in this browser only'],
  'home.bookmarkEmpty': [
    '카드나 상세의 ☆ 버튼을 누르면 여기에 모입니다. (localStorage)',
    'Tap ☆ on a card or in the details to keep it here. (localStorage)',
  ],
  'home.gapStars': ['별점', 'Stars'],
  'home.gapScore': ['파로스 가중 점수', 'Pharos weighted score'],
  'home.gapStoreTotal': ['스토어 누적', 'store total'],
  'home.gapSignal': ['신호 기준', 'signal-based'],
  'home.gapMore': ['근거 보기 →', 'See evidence →'],
  'home.gapCount': ['{n}개 · {platform}', '{n} ratings · {platform}'],

  /* 검색 결과 */
  'search.head': ['통합 검색', 'Search'],
  'search.count': ['{n}건 · 경량 인덱스에서 즉시 검색', '{n} results · instant, from the lightweight index'],
  'search.clear': ['지우기', 'Clear'],
  'search.empty': [
    '맞는 항목이 없습니다. 이름·별칭·대체제 키워드로 다시 찾아보세요.',
    'No match. Try a name, alias, or the keyword of an alternative.',
  ],

  /* 장르 블록·타일·카드 */
  'genre.entries': ['{n}종', '{n} entries'],
  'genre.recommended': ['추천 {n}', '{n} recommended'],
  'genre.more': ['전체 {n}종 비교 →', 'Compare all {n} →'],
  'tile.aria': ['{name} 상세 보기 — {verdict}, 가중 점수 {score}', '{name} details — {verdict}, weighted score {score}'],
  'tile.scoreTitle': ['가중 점수(균형 기본 기준)', 'Weighted score (balanced default)'],
  'card.weighted': ['가중 점수', 'weighted'],
  'card.compare': ['비교', 'Compare'],
  'card.compareTitle': ['같은 비교군 2~3개를 체크해 나란히 비교', 'Check 2–3 entries in this arena to compare them side by side'],
  'card.bookmarkAdd': ['{name} 보관함 담기', 'Save {name}'],
  'card.bookmarkRemove': ['{name} 보관함 빼기', 'Remove {name} from saved'],
  'card.more': ['상세 →', 'Details →'],
  'card.aria': ['{name} 상세 보기 — {verdict}, 가중 점수 {score}', '{name} details — {verdict}, weighted score {score}'],
  'card.filterPass': ['하드 필터 통과', 'Passes hard filters'],
  'card.weakEvidence': ['근거 약함 · {label}', 'Weak evidence · {label}'],
  'card.weakEvidenceTitle': ['근거가 약함 · {note}', 'Evidence is weak · {note}'],
  'card.optionalTitle': [
    '상점에 확률형·편의 상품이 있지만 인게임 재화·무과금으로 본편을 즐길 수 있어 거르지 않습니다.',
    'The store sells gacha or convenience items, but the main game is playable free, so it is not filtered out.',
  ],
  'card.optional': ['선택 과금 · 무과금 가능', 'Optional spend · playable free'],
  'card.redSignals': ['🔴 신호 {n}개', '🔴 {n} red signals'],
  'reviewTier.badge': ['자동 수집', 'Auto-collected'],
  'reviewTier.badgeTitle': [
    '공개 스토어·저장소 API 데이터로 자동 생성한 1차 판정입니다. 세부 약관·과금 함정은 순차 검수 중입니다.',
    'A first-pass verdict generated from public store and repository APIs. Detailed terms and monetization traps are still being reviewed.',
  ],
  'reviewTier.notice': [
    '<b>자동 수집</b> — 공개 스토어·저장소 API 데이터 기반 1차 판정이며, 세부 약관·과금 함정은 순차 검수 중입니다.  점수·판정은 수집된 사실로 계산했고, 확인하지 못한 항목은 ⚪로 두었습니다.',
    '<b>Auto-collected</b> — a first-pass verdict built from public store and repository APIs. Detailed terms and monetization traps are still being reviewed. Scores and verdicts are computed from collected facts; anything unconfirmed stays ⚪.',
  ],

  /* 도메인·대분류·비교군 화면 */
  'domain.heading': ['{label} — 장르 {g} · {n}건', '{label} — {g} genres · {n} entries'],
  'domain.filterPack': ['필터 팩 · {pack}', 'Filter pack · {pack}'],
  'category.eyebrow': ['{domain} · 대분류', '{domain} · Category'],
  'arena.entries': ['{n}건', '{n} entries'],
  'arena.filterPack': ['필터 팩 · {pack}', 'Filter pack · {pack}'],
  'arena.filterPackCore': ['필터 팩 · 공통', 'Filter pack · Core'],
  'arena.tune': ['⚙ 내 기준 <b>{preset}</b>', '⚙ My criteria <b>{preset}</b>'],
  'arena.tuneLead': ['내 기준', 'My criteria'],
  'arena.copyLink': ['🔗 링크 복사', '🔗 Copy link'],
  'arena.copyLinkTitle': ['이 비교군 화면의 딥링크를 복사', 'Copy a deep link to this arena'],
  'arena.searchPlaceholder': ['이 비교군 안에서 이름·키워드 검색', 'Search names and keywords in this arena'],
  'arena.searchAria': ['비교군 내 검색', 'Search within this arena'],
  'arena.sort': ['정렬', 'Sort'],
  'arena.showAvoided': ['거름 항목 표시', 'Show filtered-out entries'],
  'arena.listCount': ['0건', '0 entries'],
  'arena.listCountValue': ['{shown}/{total}건', '{shown}/{total} entries'],
  'arena.error': ['비교군 데이터를 불러오지 못했습니다.', 'Could not load this arena’s data.'],
  'compare.error': ['비교할 데이터를 불러오지 못했습니다.', 'Could not load the data to compare.'],

  /* 정렬 */
  'sort.score': ['점수 높은 순', 'Highest score'],
  'sort.scoreAsc': ['점수 낮은 순', 'Lowest score'],
  'sort.risk': ['최근 평가 위험 순', 'Biggest recent drop'],
  'sort.name': ['이름순', 'Name A–Z'],

  /* 비교군 요약 */
  'stats.recommend': ['추천', 'Recommended'],
  'stats.conditional': ['조건부', 'Conditional'],
  'stats.avoid': ['거름', 'Filtered'],
  'stats.recommendSub': ['가중 점수 80+ · 신호 양호', 'Weighted 80+ · healthy signals'],
  'stats.conditionalSub': ['감수할 조건이 있음', 'Comes with conditions'],
  'stats.avoidSub': ['필터·신호 기준 차단', 'Blocked by filters or signals'],
  'stats.avg': ['평균 가중 점수', 'Average weighted score'],
  'stats.avgSub': ['{preset} · 이 비교군 {n}건', '{preset} · {n} entries in this arena'],
  'arena.resultsTitle': ['선별 결과', 'Screened results'],
  'arena.resultsHint': ['{n}건 · 2~3개를 체크하면 나란히 비교', '{n} · check 2–3 to compare'],
  'arena.pickEmpty': [
    '조건에 맞는 항목이 없습니다. 필터를 줄이거나 검색어를 비워보세요.',
    'No entry meets these conditions. Loosen a filter or clear the search.',
  ],
  'arena.avoidTitle': ['거름 — 왜 걸렸는지', 'Filtered out — and why'],
  'arena.avoidHint': ['켜진 필터에 걸린 항목은 점수와 무관하게 아래로 내려갑니다.', 'Anything caught by an active filter drops here regardless of score.'],
  'arena.avoidEmpty': ['지금 설정에서 거름으로 내려간 항목이 없습니다.', 'Nothing is filtered out under the current settings.'],

  /* 프리셋 */
  'preset.custom': ['직접 설정', 'Custom'],
  'preset.balanced': ['균형 기본', 'Balanced default'],
  'preset.balanced.hint': ['사용자 50 · 객관 25 · AI 25', 'User 50 · Objective 25 · AI 25'],
  'preset.popular': ['대중 평가 중심', 'Crowd rating first'],
  'preset.popular.hint': ['수십만~수백만 명이 매긴 평점을 가장 무겁게', 'Weight the ratings of hundreds of thousands of people most'],
  'preset.comfort': ['쾌적성·노과금 중심', 'Comfort & no-spend first'],
  'preset.comfort.hint': ['광고·과금·유지보수를 무겁게', 'Weight ads, monetization and maintenance heavily'],
  'preset.privacy': ['프라이버시·로컬 중시', 'Privacy & local first'],
  'preset.privacy.hint': ['계정·데이터 수집 필터를 함께 켭니다', 'Also switches on the account and data-collection filters'],
  'preset.ai': ['AI 완성도 중심', 'AI quality first'],
  'preset.ai.hint': ['본질·완성도·정직성 위주', 'Focus on essence, completeness and honesty'],

  /* 비교 바·비교 화면 */
  'compareBar.label': ['{n}개 선택됨', '{n} selected'],
  'compareBar.open': ['나란히 비교하기 →', 'Compare side by side →'],
  'compareBar.openOne': ['1개 더 선택', 'Pick one more'],
  'compareBar.clear': ['선택 초기화', 'Clear selection'],
  'compareBar.region': ['비교 선택', 'Compare selection'],
  'compareBar.remove': ['{name} 비교에서 빼기', 'Remove {name} from the comparison'],
  'compare.onlySameArena': ['같은 비교군 항목만 비교할 수 있습니다.', 'You can only compare entries from the same arena.'],
  'compare.max': ['한 번에 최대 3개까지 비교합니다.', 'You can compare up to 3 entries at a time.'],
  'compare.title': ['{arena} — 나란히 비교', '{arena} — side by side'],
  'compare.lede': [
    '같은 비교군 {n}개를 한 표에 놓았습니다. 점수·판정은 지금 내 기준({preset})으로 다시 계산됩니다.',
    '{n} entries from the same arena in one table. Scores and verdicts are recalculated with your current criteria ({preset}).',
  ],
  'compare.back': ['← 목록으로', '← Back to list'],
  'compare.clear': ['비교 비우기', 'Clear comparison'],
  'compare.copyTitle': ['이 비교 화면의 딥링크를 복사', 'Copy a deep link to this comparison'],
  'compare.top': ['최고 <b>{name} {score}</b>', 'Top <b>{name} {score}</b>'],
  'compare.low': ['최저 <b>{name} {score}</b>', 'Low <b>{name} {score}</b>'],
  'compare.diff': ['차이 <b>{n}점</b>', 'Gap <b>{n} pts</b>'],
  'compare.summaryHint': ['내 기준 {preset} · 왼쪽 기준 열 고정', 'My criteria: {preset} · left column stays fixed'],
  'compare.scrollHint': [
    '↔ 표를 옆으로 밀면 나머지 항목이 보입니다. 왼쪽 기준 열은 고정되어 있습니다.',
    '↔ Swipe the table sideways for the rest. The left-hand column stays fixed.',
  ],
  'compare.basis': ['기준', 'Basis'],
  'compare.best': ['최고', 'Best'],
  'compare.row.score': ['가중 점수', 'Weighted score'],
  'compare.row.tier': ['대표 티어 · 가격', 'Flagship tier · price'],
  'compare.row.cheapest': ['최저 비용 경로', 'Lowest-cost path'],
  'compare.row.axis': ['축 · {axis}', 'Axis · {axis}'],
  'compare.row.impact': ['확률형·P2W 강도', 'Gacha/P2W strength'],
  'compare.row.filters': ['걸린 하드 필터', 'Hard filters hit'],
  'compare.row.stars': ['누적 별점·평점', 'Lifetime rating'],
  'compare.row.recent': ['최근 리뷰', 'Recent reviews'],
  'compare.row.life': ['수명 단계', 'Lifecycle stage'],
  'compare.row.freshness': ['평가 신선도', 'Assessment freshness'],
  'compare.row.grade': ['근거 등급', 'Evidence grade'],
  'compare.none': ['없음', 'None'],
  'compare.noImpact': ['상품 없음', 'No such items'],
  'compare.optionalSuffix': ['{label} · 선택 과금', '{label} · optional spend'],
  'compare.noRecent': ['최근 구간 없음', 'No recent window'],

  /* 상세 모달 공통 */
  'modal.detailClose': ['상세 닫기', 'Close details'],
  'modal.assessed': ['평가 {date}', 'assessed {date}'],
  'modal.grade': ['근거 {grade}', 'Evidence {grade}'],
  'modal.copyLink': ['🔗 링크 복사', '🔗 Copy link'],
  'modal.copyLinkTitle': ['이 항목 상세의 딥링크를 복사', 'Copy a deep link to these details'],
  'modal.share': ['공유 요약 복사', 'Copy share summary'],
  'modal.correction': ['정정 제보', 'Report a correction'],
  'modal.save': ['{name} 보관함 담기', 'Save {name}'],
  'modal.unsave': ['{name} 보관함 빼기', 'Remove {name} from saved'],
  'modal.reviewTier': ['발행 단계', 'Publication stage'],
  'modal.sec1': ['판정 요약', 'Verdict'],
  'modal.sec2': ['사실 (Fact)', 'Facts'],
  'modal.sec3': ['의견 (Opinion)', 'Opinion'],
  'modal.sec4': ['티어별 판정 비교', 'Verdict by tier'],
  'modal.sec5': ['축별 신호와 근거', 'Signals and evidence by axis'],
  'modal.sec6a': ['같은 비교군 상위 추천 대체제', 'Top alternatives in this arena'],
  'modal.sec6b': ['같은 비교군의 다른 선택', 'Other choices in this arena'],
  'modal.sec7': ['누적 vs 최근 리뷰', 'Lifetime vs recent reviews'],
  'modal.sec8': ['과금·광고 4분해', 'Monetization and ads, in four parts'],
  'modal.sec9': ['업데이트 성격', 'Character of updates'],
  'modal.sec10': ['근거·출처', 'Evidence and sources'],
  'modal.none': ['—', '—'],
  'modal.na': ['미확인', 'Unconfirmed'],
  'modal.yes': ['있음', 'Listed'],
  'modal.no': ['없음', 'Not listed'],

  /* 01 판정 */
  'verdict.representative': ['대표 티어', 'Flagship tier'],
  'verdict.cheapest': ['최저 비용 · {tier}', 'Lowest cost · {tier}'],
  'verdict.optional': ['선택 과금 · 무과금 가능', 'Optional spend · playable free'],
  'verdict.fresh': ['최신 · {n}', 'Current · {n}'],
  'verdict.staleCallout': [
    '<b>재검토 필요</b> 평가일 {date} 이후 {days}일이 지났습니다(기준 {limit}일). 앱·게임·AI 도구는 업데이트 한 번으로 과금·광고 정책이 바뀌므로 최신 사실로 읽지 마세요.',
    '<b>Needs review</b> It has been {days} days since the {date} assessment (limit {limit}). A single update can change monetization or advertising policy, so do not read this as current fact.',
  ],
  'verdict.rule': ['판정 규칙 <b>{rule}</b>{weak}{unknown}', 'Rule <b>{rule}</b>{weak}{unknown}'],
  'verdict.weakWarn': [' · 근거 약함 경고', ' · weak-evidence warning'],
  'verdict.unknownAxes': [' · ⚪ 미확인 축 {n}개', ' · {n} unconfirmed axes'],
  'verdict.activeFilters': ['활성 필터 점검: {chips}', 'Active filters: {chips}'],
  'verdict.noFilters': ['켜진 필터 없음', 'No filters on'],
  'verdict.arenaNotes': ['비교군 메모', 'Arena note'],
  'verdict.noArenaNote': ['기록된 비교 포인트가 없습니다.', 'No comparison note recorded.'],
  'verdict.calcOpen': [
    '계산 과정 보기 — 가중치 {w} · 필터 {n}개 · {mode} 모드',
    'See the calculation — weights {w} · {n} filters · {mode} mode',
  ],
  'verdict.modeStrict': ['엄격', 'strict'],
  'fresh.stale': ['재검토 필요', 'Needs review'],
  'fresh.days': ['{n}일', '{n} day'],
  'fresh.daysPlural': ['{n}일', '{n} days'],
  'fresh.current': ['최신', 'Current'],
  'fresh.unknown': ['평가일 미확인', 'Assessment date unknown'],
  'filter.noVerdict': ['이 티어에는 판정이 없습니다.', 'No filter verdict recorded for this tier.'],
  'summary.score': ['가중 점수 {score}', 'Weighted score {score}'],
  'summary.tier': ['대표 티어 {tier}', 'Flagship tier {tier}'],
  'summary.optional': ['선택 과금: {list} (무과금 플레이 가능)', 'Optional spend: {list} (playable free)'],
  'summary.filters': ['걸린 필터: {list}', 'Filters hit: {list}'],
  'summary.assessed': ['평가일 {date}', 'Assessed {date}'],
  'summary.url': ['기준·근거 {url}', 'Criteria and evidence {url}'],
  'summary.signature': ['— 파로스 Pharos', '— Pharos'],
  'verdict.modeRelaxed': ['완화', 'relaxed'],
  'verdict.calcScore': ['② 가중 점수 (점수 없는 축은 분자·분모에서 제외)', '② Weighted score (axes without a score leave both numerator and denominator)'],
  'verdict.noScore': ['계산 가능한 축 점수가 없습니다.', 'No axis scores to calculate.'],
  'verdict.calcFilters': ['① 하드 필터 — 티어 <code>{tier}</code>', '① Hard filters — tier <code>{tier}</code>'],
  'verdict.blocked': ['<b>차단</b> {list}', '<b>Blocked</b> {list}'],
  'verdict.optionalFails': [
    '<b>선택 과금</b> {list} — 확률형·P2W 상품은 있지만 무과금으로 본편을 즐길 수 있어 기본 모드에서는 거르지 않고 배지로만 알립니다. <code>strict_monetization</code> 을 켜면 거름이 됩니다.',
    '<b>Optional spend</b> {list} — gacha or pay-to-win items exist, but the main game is playable free, so the default mode only badges them. Switching on <code>strict_monetization</code> filters them out.',
  ],
  'verdict.weakFails': ['<b>근거 약함</b> {list} — 완화 모드에서 조건부 경고로 처리', '<b>Weak evidence</b> {list} — treated as a conditional warning in relaxed mode'],
  'verdict.disabledFilters': ['꺼진 필터 {n}개 보기', 'Show {n} filters that are off'],
  'verdict.calcRules': ['④ 판정 규칙 (위에서부터 먼저 맞는 것)', '④ Verdict rules (the first match from the top wins)'],
  'verdict.defaultSet': [
    '기본 활성 세트({set}) + 엄격 모드 기준 이 티어: <b>{result}</b> · 데이터에 기록된 판정: <b>{stored}</b>',
    'This tier under the default active set ({set}) and strict mode: <b>{result}</b> · verdict recorded in the data: <b>{stored}</b>',
  ],
  'verdict.pass': ['통과', 'passes'],
  'verdict.avoid': ['거름', 'filtered out'],

  /* 필터 칩 */
  'filter.mark.exempt': ['면제', 'exempt'],
  'filter.mark.optional': ['선택 과금', 'optional spend'],
  'filter.mark.fail': ['적중', 'hit'],
  'filter.mark.unknown': ['미확인', 'unconfirmed'],
  'filter.mark.pass': ['통과', 'pass'],
  'filter.off': ['꺼짐 · ', 'off · '],
  'filter.exemptSuffix': [' · 완결작', ' · feature-complete'],
  'filter.noFilters': ['켜진 필터 없음', 'No filters on'],

  /* 02 사실 */
  'facts.badge': ['스토어·공식 표기 · 출처 고정', 'Store and official listings · sources fixed'],
  'facts.note': [
    '스토어 표기·가격·업데이트 날짜처럼 <b>확인 가능한 사실</b>만 모았습니다. 각 값의 출처는 08번 근거·출처에 있습니다. 사실과 판단을 섞지 않기 위해 이 표에는 점수·의견을 넣지 않습니다.',
    'Only <b>verifiable facts</b> — store listings, prices, update dates. Sources for each value are in section 10. To keep fact and judgement apart, no score or opinion appears in this table.',
  ],
  'facts.developer': ['개발사 · 플랫폼', 'Developer · platforms'],
  'facts.price': ['가격 표기(대표 티어)', 'Listed price (flagship tier)'],
  'facts.released': ['출시 {date}', 'released {date}'],
  'facts.storeAds': ['스토어 광고 표기', 'Store ad declaration'],
  'facts.randomItems': ['확률형 아이템 표기', 'Random-item declaration'],
  'facts.latestUpdate': ['최근 업데이트', 'Latest update'],
  'facts.stars': ['별점·평점', 'Rating'],
  'facts.assessed': ['평가일', 'Assessed'],
  'facts.tableNote': [
    '가격은 통화·기간을 분리해 기록하며 환산값을 임의로 만들지 않습니다. 확인하지 못한 값은 추정으로 채우지 않고 ⚪ 미확인으로 둡니다.',
    'Prices keep currency and period separate; no invented conversions. Unverified values stay ⚪ unconfirmed rather than guessed.',
  ],

  /* 03 의견 */
  'opinion.badge': ['AI·편집 검토 · 사실과 구분', 'AI and editorial review · kept apart from facts'],
  'opinion.note': [
    '아래는 기준표 v{v}에 따라 AI와 편집자가 내린 <b>판단</b>입니다. 02번 사실과 섞이지 않게 따로 두었고, 판정 규칙과 계산 과정은 01번에서 그대로 공개합니다.',
    'These are <b>judgements</b> made by AI and editors under criteria v{v}, kept apart from the facts in section 02. The verdict rules and calculation are published in full in section 01.',
  ],
  'opinion.reasons': ['판정 이유', 'Why this verdict'],
  'opinion.noReasons': ['기록된 이유가 없습니다.', 'No reasons recorded.'],
  'opinion.conditions': ['조건·주의', 'Conditions and cautions'],
  'opinion.aiSummary': ['AI 검토 요약', 'AI review summary'],
  'opinion.noAi': ['AI 검토 서술이 없습니다.', 'No AI review text recorded.'],
  'opinion.deductions': ['감점 사유는 05번 축별 신호와 04번 티어별 판정에 반영되어 있습니다.', 'Point deductions are reflected in the axis signals (05) and the tier verdicts (04).'],
  'opinion.fit': ['적합 대상', 'A good fit for'],
  'opinion.fitLine': ['이런 결을 원하는 사람: {tags}', 'For people who want: {tags}'],
  'opinion.noTags': ['취향 태그가 기록되지 않았습니다.', 'No taste tags recorded.'],
  'opinion.redNote': ['🔴 신호 {n}개 — 이 감점 요인을 감수하기 어려운 사용자에게는 맞지 않습니다.', '🔴 {n} red signals — a poor fit for anyone who cannot accept that trade-off.'],
  'opinion.correction': ['판정이 낡았거나 사실과 다르다면 <a href="{url}" target="_blank" rel="noopener noreferrer">정정 제보</a>로 근거와 함께 알려 주세요.', 'If this verdict is stale or wrong, <a href="{url}" target="_blank" rel="noopener noreferrer">report a correction</a> with your evidence.'],

  /* 04 티어 */
  'tiers.badge': ['{n}개 티어', '{n} tiers'],
  'tiers.note': [
    '무료·구독·1회 구매는 사실상 다른 제품입니다. 판정은 현재 가중치·필터·엄격도로 티어마다 다시 계산됩니다.',
    'Free, subscription and one-time purchase are effectively different products. Each tier is judged separately with your current weights, filters and strictness.',
  ],
  'tiers.name': ['티어', 'Tier'],
  'tiers.price': ['가격', 'Price'],
  'tiers.verdict': ['판정', 'Verdict'],
  'tiers.score': ['점수', 'Score'],
  'tiers.filters': ['걸린 필터', 'Filters hit'],
  'tiers.oneLiner': ['한 줄', 'In a line'],
  'tiers.main': ['대표', 'flagship'],
  'tiers.cheapest': ['최저 비용', 'lowest cost'],
  'tiers.recorded': ['기록: {verdict}', 'recorded: {verdict}'],
  'tiers.limits': ['한도: {limits}', 'Limits: {limits}'],
  'tiers.offNote': ['(꺼짐) ', '(off) '],

  /* 05 축 */
  'axes.note': ['한 줄 정의: {text}', 'One-line definition: {text}'],
  'axes.profileOnly': ['P1 프로필 전용', 'P1 profile only'],
  'axes.evidence': ['근거 {grade}', 'Evidence {grade}'],
  'axes.confidence': ['확신 {level}', 'Confidence {level}'],
  'axes.confidenceHigh': ['높음', 'high'],
  'axes.confidenceMedium': ['보통', 'medium'],
  'axes.confidenceLow': ['낮음', 'low'],
  'axes.tierOverride': ['티어 오버라이드', 'Tier override'],
  'axes.weightZero': ['가중치 0 · 판정 미포함', 'Weight 0 · not counted'],
  'axes.noSummary': ['서술 없음', 'No description'],
  'axes.overrideNote': ['앱 공통 점수 {base} → 이 티어 {score} (사유: {note})', 'App-wide score {base} → this tier {score} (reason: {note})'],
  'axes.scoreNotes': ['v0.5.0 산정 메모', 'v0.5.0 scoring note'],

  /* 06 대체제 */
  'alt.scope': ['{arena} 안에서만', '{arena} only'],
  'alt.note': [
    '다른 분야로 건너뛰지 않습니다. 같은 자리를 두고 겨루는 대체제 중 지금 내 기준에서 추천 판정인 항목만 점수 순으로 보여줍니다.',
    'No jumping across fields. Among true alternatives for the same slot, only the ones recommended under your current criteria, by score.',
  ],
  'alt.see': ['보기 →', 'Open →'],

  /* 07 리뷰 */
  'reviews.minSample': ['최소 표본 {n}건 {state}', 'Minimum sample {n} {state}'],
  'reviews.minSampleOk': ['· 충족', '· met'],
  'reviews.minSampleShort': ['· 부족 {n}곳', '· short in {n}'],
  'reviews.note': [
    '5점 척도는 ×20, 10점 척도는 ×10으로 0~100에 맞춰 비교합니다. 누적값만 보면 놓치는 ‘최근 망가짐’을 겨냥합니다.',
    'Five-point scales are ×20 and ten-point scales ×10, all on a 0–100 range. This is aimed at recent damage that a lifetime average hides.',
  ],
  'reviews.periodUnknown': ['기간 미상', 'window unknown'],
  'reviews.none': ['없음', 'none'],
  'reviews.noRecent': ['최근 구간 없음', 'no recent window'],
  'reviews.gap': ['격차 <b>{gap}p</b> {state}', 'Gap <b>{gap}p</b> {state}'],
  'reviews.gapDamaged': ['· 최근 평가 훼손', '· recent ratings damaged'],
  'reviews.gapDown': ['· 하락', '· falling'],
  'reviews.gapUp': ['· 개선', '· improving'],
  'reviews.gapStable': ['· 안정', '· stable'],
  'reviews.cumulative': ['누적', 'Lifetime'],
  'reviews.recent': ['최근', 'Recent'],
  'reviews.metaCumulative': ['누적 · {meta}', 'Lifetime · {meta}'],
  'reviews.metaRecent': ['최근 · {meta}', 'Recent · {meta}'],
  'reviews.count': ['{n}건', '{n} ratings'],
  'reviews.rule': ['<b>표본 규칙</b> 최근 표본이 {min}건 미만이면 신호를 한 단계 낮춥니다. 점검한 플랫폼 {checked}곳 · 하향 필요 {need} · 데이터 {state}', '<b>Sample rule</b> When the recent sample is under {min}, the signal drops one step. Platforms checked {checked} · downgrade needed {need} · data {state}'],
  'reviews.needYes': ['있음', 'yes'],
  'reviews.needNo': ['없음', 'no'],
  'reviews.applied': ['하향 적용됨', 'downgrade applied'],
  'reviews.notApplied': ['하향 미적용', 'downgrade not applied'],
  'reviews.sufficient': ['표본 충분(하향 미적용)', 'sample sufficient (no downgrade)'],
  'reviews.unknownState': ['표본 상태 미기재', 'sample state not recorded'],

  /* 08 과금 */
  'money.randomBadge': ['확률형 {v}', 'Random items {v}'],
  'money.iapBadge': ['IAP {v}', 'IAP {v}'],
  'money.note': [
    '‘광고 있음/없음’ 한 칸으로는 미끼형 유입 광고 피해를 잡지 못합니다. 인앱 노출과 유입 정직성을 분리합니다.',
    'A single “ads yes/no” cannot catch misleading acquisition ads. In-app exposure and acquisition honesty are separated.',
  ],
  'money.adsExposure': ['⑴ 인앱 광고 노출', '1. In-app ad exposure'],
  'money.adsStore': ['스토어 광고 표기: {v}', 'Store ad declaration: {v}'],
  'money.inflow': ['⑵ 유입 광고 정직성', '2. Acquisition ad honesty'],
  'money.inflowExists': ['존재 {v}', 'Present {v}'],
  'money.inflowGrade': ['근거 {grade}', 'Evidence {grade}'],
  'money.noRecord': ['평가 기록 없음', 'No assessment recorded'],
  'money.notAssessed': ['미평가', 'Not assessed'],
  'money.random': ['⑶ 확률형 아이템', '3. Random items'],
  'money.iapExists': ['IAP 존재 {v}', 'IAP present {v}'],
  'money.randomNote': [
    '확률형 여부는 스토어 표기(‘Includes Random Items’)를 그대로 지표로 씁니다 — 등급 A.',
    'Random-item status uses the store declaration (“Includes Random Items”) as the indicator — grade A.',
  ],
  'money.price': ['⑷ IAP 최고가·첫 결제 유도', '4. Top IAP price and first-purchase prompt'],
  'money.priceRange': ['{min} ~ {max}', '{min} – {max}'],
  'money.priceUnknown': ['가격대 미확인', 'Price range unconfirmed'],
  'money.noIap': ['인앱결제 없음', 'No in-app purchases'],
  'money.firstPrompt': ['첫 유도 {v}', 'First prompt {v}'],
  'money.p2w': ['P2W {v}', 'P2W {v}'],
  'money.required': ['진행 필수 {v}', 'Required to progress {v}'],
  'money.priceNoteNone': ['가격대 기록 없음', 'No price range recorded'],
  'money.subscription': ['구독', 'Subscription'],
  'money.summary': ['과금 요약', 'Monetization summary'],
  'money.impactTitle': ['확률형·P2W 강도 (impact)', 'Gacha / P2W strength (impact)'],
  'money.freePlay': ['무과금 충분성: <b>{v}</b> · 근거 {grade} — {note}', 'Free-play sufficiency: <b>{v}</b> · evidence {grade} — {note}'],
  'money.freePlayNone': ['무과금 충분성은 기록되지 않았습니다(⚪).', 'Free-play sufficiency is not recorded (⚪).'],
  'money.impactNote': [
    'impact <code>optional</code> 은 상품이 있어도 무과금으로 본편을 즐길 수 있다는 뜻이며, 기본 모드에서는 거르지 않고 배지로 알립니다. <code>core</code> 는 과금 없이 진행이 막혀 거름입니다.',
    'An <code>optional</code> impact means the items exist but the main game is playable free; the default mode badges them instead of filtering. <code>core</code> means progress is walled without paying, so it is filtered out.',
  ],

  /* 09 업데이트 */
  'updates.lifeStage': ['수명 단계 · {label}', 'Lifecycle · {label}'],
  'updates.cadence': ['주기 {v}', 'Cadence {v}'],
  'updates.latest': ['최근 업데이트 {date}{platform}', 'Latest update {date}{platform}'],
  'updates.note': [
    '‘활발한가’가 아니라 ‘무엇을 실어 나르는가’를 봅니다 — {desc}.',
    'Not “is it active” but “what is it shipping” — {desc}.',
  ],
  'updates.lifeCallout': ['<b>수명 단계 · {label}</b> {note}{extra}', '<b>Lifecycle · {label}</b> {note}{extra}'],
  'updates.lifeExtra': [
    ' — 완결작은 <code>stale_over_12m</code> 필터가 켜져 있어도 면제(exempt)로 계산합니다. 단 보안·OS 호환성 문제가 별도 신호로 잡히면 추천 대신 조건부 경고로 내립니다.',
    ' — a feature-complete work is exempt even with the <code>stale_over_12m</code> filter on. But if a security or OS compatibility signal appears, it drops from recommended to a conditional warning.',
  ],
  'updates.risky': [
    '<b>경고 고정</b> 과금·약관 변경이 최근 평가 하락과 겹칩니다. 최근 업데이트 일자만으로 유지보수 신호를 🟢로 주지 않습니다.',
    '<b>Warning fixed</b> Monetization or terms changes coincide with a drop in recent ratings. A recent update date alone does not earn a 🟢 maintenance signal.',
  ],
  'updates.compat': ['보안·OS 호환성 신호: <b>{v}</b> — {note}', 'Security / OS compatibility signal: <b>{v}</b> — {note}'],
  'updates.noCompatNote': ['기록 없음', 'no record'],
  'updates.date': ['날짜', 'Date'],
  'updates.type': ['성격', 'Character'],
  'updates.platform': ['플랫폼', 'Platform'],
  'updates.promise': ['공약', 'Promise'],
  'updates.evidence': ['근거', 'Evidence'],
  'updates.memo': ['메모', 'Note'],
  'updates.noUpdates': ['기록된 업데이트가 없습니다.', 'No updates recorded.'],
  'updates.dateUnknown': ['날짜 미상', 'date unknown'],

  /* 10 근거 */
  'evidence.grade': ['데이터 신뢰도 {grade}', 'Data confidence {grade}'],
  'evidence.method': ['평가 방법 {v}', 'Method {v}'],
  'evidence.note': [
    '등급 A=스토어·공식 직접 확인, B=언론·공식 발표 인용, C=3자 집계·개별 리뷰·커뮤니티. 복합 등급은 가장 약한 등급으로 표기합니다.',
    'Grade A = verified first-hand at the store or official source, B = press or official announcement, C = third-party aggregates, individual reviews or community. Composite grades show the weakest part.',
  ],
  'evidence.unverified': ['확인하지 못한 값', 'Values not verified'],
  'evidence.conflicts': ['출처 충돌', 'Source conflicts'],
  'evidence.resolution': ['해결: {v}', 'Resolved: {v}'],
  'evidence.limitations': ['한계: {v}', 'Limitations: {v}'],
  'evidence.flags': ['판정에 쓰인 원자료(flags) {n}개', 'Raw flags behind the verdict ({n})'],
  'evidence.key': ['키', 'Key'],
  'evidence.item': ['항목', 'Field'],
  'evidence.value': ['값', 'Value'],
  'evidence.verification': ['검증', 'Verification'],
  'evidence.open': ['열기 ↗', 'Open ↗'],
  'evidence.noLink': ['링크 없음', 'no link'],
  'evidence.access': ['접근 {date}', 'accessed {date}'],

  /* 미세조정 드로어 */
  'tune.title': ['미세조정', 'Fine-tune'],
  'tune.mine': ['내 기준', 'My criteria'],
  'tune.close': ['미세조정 닫기', 'Close the fine-tune panel'],
  'tune.presets': ['가중치 프리셋', 'Weight presets'],
  'tune.presetsHint': ['합계 100%로 정규화', 'normalized to 100%'],
  'tune.axisN': ['축 {n}', 'Axis {n}'],
  'tune.default': ['기본 {v}', 'default {v}'],
  'tune.axisWeightAria': ['{axis} 가중치', '{axis} weight'],
  'tune.presetHint': [
    '‘균형 기본’은 처음 온 사람을 위한 기본값입니다. 슬라이더를 움직이면 지금 보고 있는 비교군이 즉시 다시 계산됩니다.',
    '“Balanced default” is the starting point for a first visit. Moving a slider recalculates the arena you are looking at immediately.',
  ],
  'tune.hardFilters': ['하드 필터', 'Hard filters'],
  'tune.hardFiltersHint': [
    '켜진 필터에 하나라도 걸리면 그 티어는 곧바로 <strong>거름</strong>입니다. 지금 도메인의 팩을 먼저 보여줍니다.',
    'One hit on an active filter and that tier is <strong>filtered out</strong> immediately. Your current domain’s pack comes first.',
  ],
  'tune.isDefault': ['기본 · ', 'default · '],
  'tune.reset': ['기본 세트로 되돌리기', 'Reset to the default set'],
  'tune.spendTitle': ['과금 강도', 'Monetization strictness'],
  'tune.spendToggle': [
    '<code>strict_monetization</code> — 상점에 확률형·P2W 상품이 하나라도 있으면 거름',
    '<code>strict_monetization</code> — filter out anything selling gacha or P2W items at all',
  ],
  'tune.spendOn': [
    '지금은 상품이 있기만 해도 거름입니다(기존 v0.3.1 동작). 무과금으로 충분한 작품까지 걸러집니다.',
    'For now, merely selling such items is enough to be filtered out (the old v0.3.1 behaviour). Even works that are fine to play free get caught.',
  ],
  'tune.spendOff': [
    '기본값은 OFF 입니다. 확률형·P2W 상품이 있어도 무과금으로 본편을 즐길 수 있으면 「선택 과금 · 무과금 가능」 배지로만 알리고, 점수·신호로 추천·조건부를 정합니다. 과금 없이 진행이 막히는 작품(impact: core)은 이 설정과 무관하게 거름입니다.',
    'Off by default. If gacha or P2W items exist but the main game is playable free, we only show the “Optional spend · playable free” badge and let scores and signals decide recommended or conditional. Works walled without paying (impact: core) are filtered out regardless.',
  ],
  'tune.evidenceMode': ['근거 엄격 모드', 'Evidence strictness'],
  'tune.evidenceToggle': [
    '<code>strict_evidence</code> — 등급 C 근거만 있는 필터 적중도 거름으로 처리',
    '<code>strict_evidence</code> — even filter hits backed only by grade C evidence are filtered out',
  ],
  'tune.evidenceOn': [
    '끄면 근거가 약한(등급 C) 필터 적중은 ‘근거 약함’ 경고가 붙은 <strong>조건부</strong>로 완화됩니다.',
    'Switch it off and a filter hit backed only by weak (grade C) evidence becomes <strong>conditional</strong> with a “weak evidence” warning.',
  ],
  'tune.evidenceOff': [
    '지금은 완화 모드입니다. 등급 C 근거의 필터 적중은 거름 대신 <strong>조건부 경고</strong>로 내려갑니다.',
    'Relaxed mode is on. Filter hits backed by grade C evidence drop to a <strong>conditional warning</strong> instead of being filtered out.',
  ],
  'tune.current': ['현재 설정', 'Current settings'],
  'tune.foot': [
    '{preset} · {weights}<br>필터 {n}개 · {mode} 모드 · 선택 과금 {spend}',
    '{preset} · {weights}<br>{n} filters · {mode} mode · optional spend {spend}',
  ],
  'tune.spendFiltered': ['거름', 'filtered'],
  'tune.spendAllowed': ['허용', 'allowed'],
  'tune.method': ['방법론·용어 보기', 'Method and glossary'],
  'tune.copy': ['이 기준 링크 복사', 'Copy a link to these criteria'],

  /* 방법론 모달 */
  'method.label': ['기준·방법론', 'Criteria and method'],
  'method.title': ['파로스가 점수를 매기는 법', 'How Pharos scores'],
  'method.sub': ['가중치·필터·근거 등급·판정 규칙을 그대로 공개합니다.', 'Weights, filters, evidence grades and verdict rules, published in full.'],
  'method.close': ['방법론 닫기', 'Close the method'],

  /* 보관함·토스트 */
  'toast.bookmarkAdd': ['보관함에 담았습니다.', 'Saved.'],
  'toast.bookmarkRemove': ['보관함에서 뺐습니다.', 'Removed from saved.'],
  'toast.shareCopied': ['공유용 요약을 복사했습니다.', 'Share summary copied.'],
  'toast.shareFail': ['복사 권한이 없습니다. 아래 요약을 직접 선택해 주세요.', 'Clipboard permission was denied. Select the summary below and copy it yourself.'],
  'toast.linkCopied': ['링크를 복사했어요', 'Link copied'],
  'toast.linkFail': ['링크를 복사하지 못했습니다.', 'Could not copy the link.'],
  'toast.criteriaCopied': ['현재 기준 링크를 복사했습니다.', 'Link to the current criteria copied.'],
  'toast.copyFail': ['복사하지 못했습니다.', 'Copy failed.'],
  'toast.langChanged': ['언어를 {lang}로 바꿨습니다.', 'Language switched to {lang}.'],
  'bookmark.remove': ['빼기', 'Remove'],

  /* 오류 */
  'error.data': ['데이터를 불러오지 못했습니다.', 'Could not load the data.'],
  'error.fileHint': [
    '이 페이지는 <code>index.html</code>을 파일로 직접 열면 <code>fetch</code>가 차단됩니다. <code>projects/pharos/web</code> 폴더에서 <code>python3 -m http.server 8000</code> 을 실행한 뒤 <code>http://localhost:8000/</code> 로 접속하세요. (<code>data/</code>·<code>schema/</code> 사본이 없으면 <code>python3 projects/pharos/scripts/sync_web_data.py</code> 로 원본과 맞춥니다.)',
    'Opening <code>index.html</code> from disk blocks <code>fetch</code>. Run <code>python3 -m http.server 8000</code> in <code>projects/pharos/web</code> and open <code>http://localhost:8000/</code>. (If the <code>data/</code> or <code>schema/</code> copies are missing, run <code>python3 projects/pharos/scripts/sync_web_data.py</code>.)',
  ],
  'boot.note': [
    '이 페이지는 <strong>정적 HTTP 서버</strong>로 열어야 합니다. <code>projects/pharos/web</code> 폴더에서 <code>python3 -m http.server 8000</code> 을 실행한 뒤 <code>http://localhost:8000/</code> 로 접속해 주세요.',
    'This page must be served over <strong>HTTP</strong>. Run <code>python3 -m http.server 8000</code> in <code>projects/pharos/web</code> and open <code>http://localhost:8000/</code>.',
  ],
  'noscript': ['파로스는 브라우저에서 계산합니다. JavaScript를 켜야 선별 결과가 보입니다.', 'Pharos calculates in your browser. Turn on JavaScript to see the screening results.'],

  /* 페이지 메타 */
  'meta.title': [
    '파로스 Pharos — 오늘 도전할 목표를 비추는 등대 · 앱·게임·AI 도구 선별',
    'Pharos — a lighthouse for your next goal · apps, games and AI tools screened',
  ],
  'meta.description': [
    '오늘 뭐 하지? 파로스 등대는 가격·플랫폼·기간을 고르면 검증한 명작 중 하나와 그 안의 실제 목표를 퀘스트로 비춥니다. 앱·게임·AI 도구는 사용자 평가·객관 신뢰 지표·AI 검토를 내 가중치로 합치고, 강제 광고·확률형 아이템·불투명 크레딧 같은 절대 거름 조건을 적용해 선별합니다. 모든 계산은 브라우저에서 실시간으로 이뤄집니다.',
    'What do I play tonight? Pick price, platform and length, and the Pharos Lighthouse shines on one vetted masterwork and a real goal inside it. Apps, games and AI tools are screened by combining user ratings, objective trust metrics and AI review with your own weights, then applying hard filters — forced ads, gacha items, opaque credits. Every calculation runs live in your browser.',
  ],
  'meta.ogTitle': [
    '파로스 Pharos — 오늘 도전할 목표를 비추는 등대',
    'Pharos — a lighthouse for your next goal',
  ],
  'meta.ogDescription': [
    '조건만 고르면 명작 한 편과 그 안의 실제 목표 하나를 비춥니다. 별점 대신 조건(광고·과금·계정·수명)으로 거르는 앱·게임·AI 도구 선별은 옆 탐색 탭에.',
    'Pick your terms and get one masterwork and a real goal inside it. Screening by conditions — ads, monetization, accounts, lifecycle — instead of star ratings lives in the Explore tab.',
  ],

  /* 판정 규칙 전문(방법론·계산 과정) */
  'rule.text.0': [
    '켜진 하드 필터에 걸리면 거름. 단 확률형·P2W의 「선택 과금(impact: optional)」은 기본 설정에서 거르지 않고 배지로만 알린다. (완화 모드에서 등급 C 근거만 있으면 조건부 경고)',
    'A hit on an active hard filter means filtered out — except that gacha/P2W items marked “optional spend” (impact: optional) are only badged by default. (In relaxed mode, grade-C-only evidence becomes a conditional warning.)',
  ],
  'rule.text.1': ['🔴 신호가 2개 이상이면 거름', 'Two or more 🔴 signals → filtered out'],
  'rule.text.2': ['🔴 신호가 1개면 조건부', 'One 🔴 signal → conditional'],
  'rule.text.3': ['🟡 신호가 2개 이상이면 조건부', 'Two or more 🟡 signals → conditional'],
  'rule.text.4': ['점수 80 이상이고 🟡가 1개 이하면 추천', 'Score 80 or more with at most one 🟡 → recommended'],
  'rule.text.5': ['그 외에는 조건부', 'Everything else → conditional'],
  'rule.text.6': ['완결작 면제에 보안·OS 호환성 신호가 붙으면 추천 대신 조건부 경고', 'A feature-complete exemption plus a security/OS compatibility signal → conditional warning instead of recommended'],

  /* 방법론 모달 본문 */
  'method.a.title': ['4단 구조 — 무엇을 같은 표에 놓는가', 'The four levels — what gets put in the same table'],
  'method.a.note': [
    '도메인(앱·게임·AI 도구) → 대분류 → 비교군 → 항목·티어. <b>점수 평균·순위·요약은 오직 같은 비교군 안에서만</b> 계산합니다. 노트 앱과 카드 게임을 한 줄에 섞어 평균 내지 않습니다.',
    'Domain (apps, games, AI tools) → category → arena → item and tier. <b>Averages, rankings and summaries are computed only inside the same arena.</b> A note-taking app and a card game are never averaged on one line.',
  ],
  'method.level': ['단계', 'Level'],
  'method.role': ['역할', 'Role'],
  'method.thisData': ['이 데이터', 'In this data'],
  'method.l1': ['1 도메인', '1 Domain'],
  'method.l2': ['2 대분류', '2 Category'],
  'method.l3': ['3 비교군', '3 Arena'],
  'method.l4': ['4 항목·티어', '4 Item · tier'],
  'method.l2role': ['도메인 안의 큰 갈래', 'A large branch inside a domain'],
  'method.l3role': ['실제 대체제 묶음', 'A set of genuine alternatives'],
  'method.l4role': ['선택·판정 단위(무료/구독/1회 구매)', 'The unit of choice and verdict (free / subscription / one-time)'],
  'method.l4data': ['같은 앱이라도 티어마다 따로 판정', 'Even one app is judged tier by tier'],
  'method.b.title': ['네 축과 가중 점수', 'Four axes and the weighted score'],
  'method.b.axis': ['축', 'Axis'],
  'method.b.what': ['무엇을 보는가', 'What it looks at'],
  'method.b.default': ['기본 가중치', 'Default weight'],
  'method.b.user': ['최근 구간 vs 누적 괴리 + 표본 규모 검증(수십만~수백만 누적 우대)', 'Recent window vs lifetime gap, plus sample-scale verification (favouring hundreds of thousands to millions of lifetime ratings)'],
  'method.b.objective': ['기능 완성도·생태계/연동성·안정성·보안·정책/과금 투명성 — 클라우드·비공개 소스라는 이유만으로 깎지 않음', 'Feature completeness, ecosystem and integrations, stability, security, policy and monetization transparency — no deduction merely for being cloud-based or closed-source'],
  'method.b.ai': ['본질 완성도·함정 구조·강점/약점', 'Essential completeness, trap structures, strengths and weaknesses'],
  'method.b.fit': ['취향 태그·프로필 적합도(있을 때만 — 켜지지 않은 프로필 축은 판정에 세지 않음)', 'Taste tags and profile fit (only when present — a profile axis you have not enabled is not counted)'],
  'method.b.profileOnly': ['(프로필 전용)', '(profile only)'],
  'method.b.note1': [
    '가중 점수 = Σ(w×s) ÷ Σw. 점수가 없는 축(⚪)은 분자·분모에서 모두 빠집니다. 입력 가중치는 합계로 정규화합니다. 과금의 <b>강도</b>는 점수 대신 impact·free_play 로 따로 기록해, 같은 사실을 두 번 감점하지 않습니다.',
    'Weighted score = Σ(w×s) ÷ Σw. An axis without a score (⚪) leaves both numerator and denominator. Entered weights are normalized by their total. Monetization <b>strength</b> is recorded separately as impact and free_play instead of a score, so the same fact is not deducted twice.',
  ],
  'method.b.note2': [
    '<b>v0.5.0 기본 배분은 사용자 50 · 객관 25 · AI 25.</b> 대중이 실제로 검증한 평점의 무게를 높였습니다. 가중치가 0인 축(내 기준 적합)은 신호가 있어도 추천/거름 계산에 세지 않습니다 — 프로필을 켰을 때만 네 번째 축이 됩니다.',
    '<b>The v0.5.0 default split is User 50 · Objective 25 · AI 25.</b> Ratings that a crowd has actually tested carry more weight. An axis at weight 0 (personal fit) is not counted toward recommended or filtered even when it has a signal — it only becomes a fourth axis when you enable a profile.',
  ],
  'method.b2.title': ['사용자 평가의 표본 규모 검증', 'Sample-scale verification for user ratings'],
  'method.b2.note1': [
    '같은 4.4~4.6★이라도 <b>리뷰 1만 개와 수십만~수백만 개</b>는 검증의 무게가 다릅니다. 누적 표본으로 규모 등급을 매기고, 얇은 3자 최근 표본이 큰 스토어 누적을 통째로 덮지 않게 합니다.',
    'The same 4.4–4.6★ carries different weight with <b>10,000 reviews and with hundreds of thousands to millions.</b> Lifetime samples set a scale grade, and a thin third-party recent sample cannot blanket a large store lifetime figure.',
  ],
  'method.b2.sample': ['누적 표본', 'Lifetime sample'],
  'method.b2.grade': ['규모 등급', 'Scale grade'],
  'method.b2.use': ['쓰는 법', 'How it is used'],
  'method.b2.r1a': ['100만 이상', '1 million or more'],
  'method.b2.r1b': ['대규모 활성 유저', 'Large active audience'],
  'method.b2.r1c': ['4.4★(88) 이상 유지 시 🟢 검증 하한(75)', 'If it holds 4.4★ (88) or more, 🟢 verified floor (75)'],
  'method.b2.r2a': ['10만~100만', '100,000 – 1 million'],
  'method.b2.r2b': ['대형', 'Large'],
  'method.b2.r2c': ['같은 하한 적용', 'Same floor applies'],
  'method.b2.r3a': ['1만~10만', '10,000 – 100,000'],
  'method.b2.r3b': ['중형', 'Medium'],
  'method.b2.r3c': ['점수 보정 없음 — 있는 그대로', 'No adjustment — as recorded'],
  'method.b2.r4a': ['1천 미만', 'Under 1,000'],
  'method.b2.r4b': ['소형·미세 표본', 'Small or micro sample'],
  'method.b2.r4c': ['최근 값 우선 + 신호 한 단계 하향(과대평가 방지)', 'Recent value first, signal down one step (guards against overrating)'],
  'method.b2.note2': [
    '최근 구간이 <b>3자 집계(등급 C)·1,000건 미만</b>인데 스토어 누적이 <b>등급 A/B·10만 건 이상·4.4★ 이상</b>이면, 최근 값은 ‘하락 방향 신호’로만 쓰고 그 플랫폼 점수는 (누적+최근)÷2로 둡니다. 단 과금·약관 변경이 급락과 겹친 경우(예: 에버노트 가격 인상)는 완화하지 않습니다 — 돈·조건이 바뀌어 생긴 하락은 표본이 얇아도 실제 신호입니다.',
    'When the recent window is a <b>third-party aggregate (grade C) under 1,000 ratings</b> while the store lifetime figure is <b>grade A/B, 100,000+ ratings, 4.4★ or more</b>, the recent value is used only as a direction signal and the platform score becomes (lifetime + recent) ÷ 2. But when a monetization or terms change coincides with the slump (Evernote’s price rise, for example) there is no softening — a fall caused by money or conditions changing is real even on a thin sample.',
  ],
  'method.c.title': ['근거 등급 A/B/C', 'Evidence grades A/B/C'],
  'method.c.grade': ['등급', 'Grade'],
  'method.c.def': ['정의', 'Definition'],
  'method.c.a': ['스토어·공식 가격 페이지·개발자 공지에서 직접 확인', 'Verified first-hand at the store, official pricing page or developer notice'],
  'method.c.b': ['언론 보도·공식 발표 인용(1차를 인용한 신뢰 매체)', 'Press coverage or quotation of an official announcement (a reliable outlet citing a primary source)'],
  'method.c.c': ['3자 집계·개별 리뷰·커뮤니티(교차 확인 전 신뢰도 중간)', 'Third-party aggregates, individual reviews or community (moderate confidence until cross-checked)'],
  'method.c.none': ['확인하지 못한 값 — 추정으로 채우지 않고 계산에서 제외', 'A value we could not verify — never guessed, and left out of the calculation'],
  'method.c.note': [
    '최근 리뷰 표본이 100건 미만이면 신호를 한 단계 낮춥니다. 복합 등급(A/C)은 가장 약한 등급으로 표기합니다.',
    'A recent-review sample under 100 drops the signal one step. Composite grades (A/C) are shown at their weakest part.',
  ],
  'method.d.title': ['확률형·P2W 강도 3단계', 'Gacha and P2W strength in three levels'],
  'method.d.note1': [
    '상점에 확률형·P2W 상품이 <b>하나라도 있으면 거름</b>이 아니라, 그 상품을 사지 않아도 게임이 성립하는지를 먼저 봅니다. 필터 상태는 <code>fail</code> 로 남겨 상품이 있다는 사실을 숨기지 않고, 판정만 강도에 따라 나뉩니다.',
    'It is not <b>“any gacha or P2W item means filtered out”</b>: what matters is whether the game still works without buying it. The filter status stays <code>fail</code>, so the existence of the item is never hidden; only the verdict depends on strength.',
  ],
  'method.d.impact': ['impact', 'impact'],
  'method.d.means': ['뜻', 'Meaning'],
  'method.d.verdict': ['기본 모드의 판정', 'Verdict in the default mode'],
  'method.d.none': ['상품 자체가 없다', 'There is no such item at all'],
  'method.d.noneV': ['필터 통과', 'Passes the filter'],
  'method.d.optional': ['상품은 있으나 인게임 재화·무과금으로 본편·핵심 콘텐츠를 충분히 즐길 수 있다', 'Items exist, but in-game currency or free play is enough for the main game and its core content'],
  'method.d.optionalV': ['<b>거르지 않고</b> 「선택 과금 · 무과금 가능」 배지 · 점수·신호로 추천/조건부', '<b>Not filtered:</b> “Optional spend · playable free” badge, with recommended or conditional from scores and signals'],
  'method.d.core': ['과금·확률형 뽑기 없이는 성장 벽에 막히거나 진행·경쟁이 실질적으로 불가능하다', 'Without paying or pulling, a progression wall blocks you and progress or competition is effectively impossible'],
  'method.d.coreV': ['거름(🔴)', 'Filtered out (🔴)'],
  'method.d.note2': [
    '근거는 <code>monetization.free_play</code>(무과금 충분성)에 남깁니다. <code>impact: optional</code> 이면 무과금으로 충분하다는 근거가 있어야 하고 검증기가 이를 확인합니다. ‘내 기준 미세조정’의 <code>strict_monetization</code>(기본 OFF)을 켜면 optional 까지 상품 존재만으로 거릅니다 — v0.3.1 과 같은 동작입니다.',
    'The evidence lives in <code>monetization.free_play</code> (free-play sufficiency). An <code>impact: optional</code> requires evidence that free play is sufficient, and the validator enforces it. Switching on <code>strict_monetization</code> in “Tune my criteria” (off by default) filters even optional items just for existing — the old v0.3.1 behaviour.',
  ],
  'method.e.title': ['판정 규칙 (위에서부터 먼저 맞는 것)', 'Verdict rules (first match from the top)'],
  'method.e.note': [
    '티어 단위로 판정하고, 최소 비용 추천 경로를 함께 냅니다. 완결작(<code>maintenance_status=feature_complete</code>)은 업데이트 공백 필터에서 면제하되, 보안·OS 호환성 신호가 있으면 조건부 경고로 내립니다.',
    'Verdicts are decided per tier, together with the lowest-cost recommended path. A feature-complete work (<code>maintenance_status=feature_complete</code>) is exempt from the update-gap filter, but a security or OS compatibility signal drops it to a conditional warning.',
  ],
  'method.f.title': ['독립성 — 무엇을 받지 않는가', 'Independence — what we take'],
  'method.f.body': [
    '<b>파로스는 어필리에이트 링크·유료 광고·협찬 배치를 쓰지 않습니다.</b> 순위·판정·점수는 어떤 대가와도 무관하며, 스토어 이미지도 복제하지 않고 텍스트·수치·공식 링크만 씁니다. 판정이 틀렸거나 낡았다면 누구나 근거와 함께 정정을 제보할 수 있습니다.',
    '<b>Pharos uses no affiliate links, paid advertising or sponsored placements.</b> Rankings, verdicts and scores are independent of any payment; store imagery is not copied — only text, numbers and official links. Anyone can report a correction with evidence if a verdict is wrong or stale.',
  ],
  'method.g.title': ['용어 도움말', 'Glossary'],
  'method.g.evidence': ['근거 등급', 'Evidence grade'],
  'method.g.evidenceD': ['A/B/C — 값이 어디서 왔는지. C뿐이면 판정을 낮게 잡습니다.', 'A/B/C — where a value came from. Grade C alone keeps the verdict conservative.'],
  'method.g.hard': ['하드 필터', 'Hard filter'],
  'method.g.hardD': ['점수와 무관하게 거르는 절대 조건(강제 광고·확률형 뽑기·P2W·계정 필수 등).', 'An absolute condition that filters regardless of score (forced ads, gacha pulls, P2W, mandatory accounts).'],
  'method.g.optional': ['선택 과금(impact: optional)', 'Optional spend (impact: optional)'],
  'method.g.optionalD': ['상점에 확률형·P2W 상품이 있어도 인게임 재화·무과금으로 본편을 충분히 즐길 수 있는 상태. 기본 모드에서는 거르지 않고 「선택 과금 · 무과금 가능」 배지로 알립니다.', 'Gacha or P2W items exist, yet in-game currency or free play is enough for the main game. The default mode badges it rather than filtering it out.'],
  'method.g.core': ['핵심 과금(impact: core)', 'Core monetization (impact: core)'],
  'method.g.coreD': ['과금·확률형 뽑기 없이는 성장 벽에 막히거나 진행·경쟁이 실질적으로 불가능한 상태. 기본 모드에서도 거름입니다.', 'Without paying or pulling, a progression wall blocks you and progress or competition is effectively impossible. Filtered out even in the default mode.'],
  'method.g.strictmon': ['strict_monetization', 'strict_monetization'],
  'method.g.strictmonD': ['‘내 기준 미세조정’의 토글(기본 OFF). 켜면 상품이 있기만 해도 거름 — v0.3.1 과 같은 동작입니다.', 'A toggle in “Tune my criteria” (off by default). When on, merely selling the items filters the tier out — the old v0.3.1 behaviour.'],
  'method.g.strict': ['엄격 모드', 'Strict mode'],
  'method.g.strictD': ['등급 C 근거의 필터 적중도 거름으로 처리. 끄면 ‘근거 약함’ 조건부 경고로 완화합니다.', 'Even filter hits backed by grade C evidence are filtered out. Off, they soften to a conditional “weak evidence” warning.'],
  'method.g.exempt': ['면제(exempt)', 'Exempt'],
  'method.g.exemptD': ['완결작이 12개월 넘게 업데이트가 없어도 방치가 아니라고 판단한 상태. 거름이 아닙니다.', 'A feature-complete work with no update for over 12 months, judged not abandoned. It is not filtered out.'],
  'method.g.sample': ['표본 규모 검증', 'Sample-scale verification'],
  'method.g.sampleD': ['수십만~수백만 명이 매긴 누적 평점은 수백 건짜리 3자 최근 표본보다 무겁게 봅니다. 얇은 최근 표본은 ‘하락 방향 신호’로만 쓰고, 큰 누적과 반씩 섞습니다(v0.5.0).', 'A lifetime rating from hundreds of thousands of people outweighs a recent third-party sample of a few hundred. A thin recent sample is used only as a direction signal and mixed half-and-half with the large lifetime figure (v0.5.0).'],
  'method.g.privacy': ['프라이버시·로컬 중시 프리셋', 'Privacy & local first preset'],
  'method.g.privacyD': ['객관 비중을 높이고 ‘계정 필수·과도한 데이터 수집’ 필터를 함께 켜는 프리셋. 기본 화면은 클라우드·비공개 소스를 깎지 않고, 로컬·프라이버시가 목적일 때 이 프리셋으로 가릅니다.', 'Raises the objective weight and switches on the “mandatory accounts” and “heavy data collection” filters. The default view does not penalize cloud or closed source; this preset is how you screen for local-first privacy.'],
  'method.g.arena': ['비교군', 'Arena'],
  'method.g.arenaD': ['같은 자리를 두고 겨루는 대체제 묶음. 평균·순위는 이 안에서만 냅니다.', 'A set of alternatives competing for the same slot. Averages and rankings are only computed inside it.'],
  'method.g.unknown': ['⚪ 미확인', '⚪ Unconfirmed'],
  'method.g.unknownD': ['근거를 찾지 못한 값. 통과로 치지 않고 ‘주의’로 표시합니다.', 'A value with no evidence found. Not counted as a pass; shown as “caution”.'],
  'method.g.stale': ['재검토 필요', 'Needs review'],
  'method.g.staleD': ['평가일 이후 {n}일이 지난 판정. 최신 사실로 읽지 마세요.', 'A verdict older than {n} days. Do not read it as current fact.'],

  /* 판정 규칙 짧은 문구 */
  'rule.short.1': ['① 활성 필터 적중 → 거름', '1 · Active filter hit → filtered out'],
  'rule.short.1w': ['① 완화 모드 · 등급 C 필터 적중 → 조건부 경고', '1 · Relaxed mode, grade-C filter hit → conditional warning'],
  'rule.short.1c': ['⑦ 완결작 면제 · 호환성 주의 → 조건부', '7 · Feature-complete exemption, compatibility caution → conditional'],
  'rule.short.2': ['② 🔴 신호 {n}개 → 거름', '2 · {n} red signals → filtered out'],
  'rule.short.3': ['③ 🔴 신호 1개 → 조건부', '3 · 1 red signal → conditional'],
  'rule.short.4': ['④ 🟡 신호 {n}개 → 조건부', '4 · {n} amber signals → conditional'],
  'rule.short.5': ['⑤ 점수 {score} ≥ 80·🟡 {n}개 → 추천', '5 · Score {score} ≥ 80 with {n} amber → recommended'],
  'rule.short.6': ['⑥ 그 외 → 조건부', '6 · Otherwise → conditional'],

  /* 도메인·대분류·비교군 라벨 (데이터 번들이 없는 경우의 안전망) */
  'domain.app': ['앱', 'Apps'],
  'domain.game': ['게임', 'Games'],
  'domain.ai': ['AI 도구', 'AI Tools'],
  'category.productivity': ['생산성 · 지식관리', 'Productivity · Knowledge'],
  'category.security-utilities': ['보안 · 유틸리티', 'Security · Utilities'],
  'category.internet-privacy': ['인터넷 · 프라이버시', 'Internet · Privacy'],
  'category.strategy-card': ['전략 · 카드', 'Strategy · Cards'],
  'category.rpg': ['RPG · 수집', 'RPG · Collection'],
  'category.action-indie': ['액션 · 인디', 'Action · Indie'],
  'category.mmorpg': ['RPG · MMORPG', 'RPG · MMORPG'],
  'category.mobile-strategy': ['모바일 전략 · 디펜스', 'Mobile Strategy · Defense'],
  'category.ai-chat-research': ['대화 · 리서치', 'Chat · Research'],
  'category.ai-coding': ['개발 · 코딩', 'Development · Coding'],
  'pack.app': ['앱 팩', 'App pack'],
  'pack.game': ['게임 팩', 'Game pack'],
  'pack.ai': ['AI 도구 팩', 'AI tools pack'],
  'pack.core': ['공통 코어', 'Core'],

  /* 축 라벨 */
  'axis.user_rating': ['사용자 평가', 'User Rating'],
  'axis.objective': ['객관·신뢰 지표', 'Objective Trust'],
  'axis.ai_review': ['AI 검토', 'AI Review'],
  'axis.personal_fit': ['내 기준 적합', 'Personal Fit'],

  /* 하드 필터 라벨 */
  'filter.forced_ads': ['강제 전면 광고 제외', 'Forced full-screen ads'],
  'filter.gacha_random_items': ['확률형 아이템 제외', 'Gacha / loot boxes'],
  'filter.bait_ad': ['미끼형 광고 제외', 'Bait acquisition ads'],
  'filter.p2w': ['P2W 제외', 'Pay-to-win'],
  'filter.iap_required_to_progress': ['과금 없이 진행 불가 제외', 'Paywalls on progress'],
  'filter.stale_over_12m': ['12개월 이상 방치 제외', 'Dormant 12+ months'],
  'filter.subscription_required': ['구독 필수 제외', 'Subscription-only'],
  'filter.account_required': ['계정 필수 제외', 'Forced accounts'],
  'filter.data_collection': ['과도한 데이터 수집 제외', 'Heavy data collection'],

  /* 신호·판정·티어·플랫폼 등 메타 라벨 */
  'signal.green': ['좋음', 'Good'],
  'signal.yellow': ['주의', 'Caution'],
  'signal.red': ['나쁨', 'Poor'],
  'signal.unknown': ['미확인', 'Unconfirmed'],
  'verdictMeta.recommend': ['추천', 'Recommended'],
  'verdictMeta.conditional': ['조건부', 'Conditional'],
  'verdictMeta.avoid': ['거름', 'Filtered'],
  'tri.yes': ['예', 'Yes'],
  'tri.no': ['아니오', 'No'],
  'tri.unknown': ['미확인', 'Unconfirmed'],
  'tri.not_assessed': ['미평가', 'Not assessed'],
  'kind.free': ['완전 무료', 'Free'],
  'kind.freemium': ['무료 시작(한도·광고·IAP)', 'Free to start (limits · ads · IAP)'],
  'kind.demo': ['체험판', 'Demo'],
  'kind.one_time': ['1회 구매', 'One-time purchase'],
  'kind.subscription': ['구독', 'Subscription'],
  'kind.license': ['라이선스', 'License'],
  'kind.consumable': ['소모성 결제', 'Consumable purchase'],
  'platform.web': ['웹', 'Web'],
  'platform.console': ['콘솔', 'Console'],
  'platform.other': ['기타', 'Other'],
  'exposure.none': ['없음', 'None'],
  'exposure.low': ['낮음', 'Low'],
  'exposure.medium': ['보통', 'Medium'],
  'exposure.high': ['높음', 'High'],
  'exposure.unknown': ['미확인', 'Unconfirmed'],
  'honesty.honest': ['정직함', 'Honest'],
  'honesty.partly_misleading': ['부분 과장', 'Partly misleading'],
  'honesty.misleading': ['오해 유발', 'Misleading'],
  'honesty.unknown': ['미확인', 'Unconfirmed'],
  'honesty.not_assessed': ['미평가', 'Not assessed'],
  'adType.none': ['광고 없음', 'No ads'],
  'adType.rewarded': ['보상형', 'Rewarded'],
  'adType.interstitial': ['전면', 'Interstitial'],
  'adType.banner': ['배너', 'Banner'],
  'adType.native': ['네이티브', 'Native'],
  'adType.forced_interstitial': ['강제 전면', 'Forced interstitial'],
  'adType.unknown': ['미확인', 'Unconfirmed'],
  'prompt.immediate': ['즉시', 'Immediately'],
  'prompt.early': ['초반', 'Early'],
  'prompt.mid': ['중반', 'Mid-game'],
  'prompt.late': ['후반', 'Late'],
  'prompt.none': ['없음', 'None'],
  'prompt.unknown': ['미확인', 'Unconfirmed'],
  'maint.healthy': ['건강함', 'Healthy'],
  'maint.healthy.desc': ['최근 6개월 내 업데이트 + 과금·약관 변경 없음', 'Updated within 6 months, no monetization or terms changes'],
  'maint.risky_terms': ['위험한 변경', 'Risky changes'],
  'maint.risky_terms.desc': ['활발하나 과금·약관 변경이 평가 급락과 겹침', 'Active, but monetization or terms changes coincide with a rating slump'],
  'maint.stalled_but_trusted': ['지연됐지만 신뢰', 'Stalled but trusted'],
  'maint.stalled_but_trusted.desc': ['과금 압박이 없는 지연, 신뢰 유지', 'A pause without monetization pressure; trust intact'],
  'maint.abandoned': ['방치', 'Abandoned'],
  'maint.abandoned.desc': ['12개월 이상 업데이트 없음 + 공약 미이행', 'No updates for 12+ months and unfulfilled promises'],
  'maint.unknown': ['미확인', 'Unconfirmed'],
  'maint.unknown.desc': ['근거 부족', 'Not enough evidence'],
  'life.active': ['개발 중', 'In development'],
  'life.active.desc': ['업데이트·운영이 이어지고 있다', 'Updates and operations continue'],
  'life.feature_complete': ['완결작', 'Feature-complete'],
  'life.feature_complete.desc': ['개발사가 완결을 선언 — 업데이트 공백이 방치와 다르다', 'The developer has declared it complete — a gap in updates is not abandonment'],
  'life.stale_unknown': ['상태 미확인', 'Status unconfirmed'],
  'life.stale_unknown.desc': ['오래 멈췄고 완결인지 방치인지 확인하지 못했다', 'Long dormant; whether complete or abandoned is unknown'],
  'life.abandoned': ['방치', 'Abandoned'],
  'life.abandoned.desc': ['12개월 이상 중단 + 공약 미이행', 'Stopped for 12+ months with promises unfulfilled'],
  'impact.none': ['상품 없음', 'No such items'],
  'impact.optional': ['선택 과금 · 무과금 가능', 'Optional spend · playable free'],
  'impact.core': ['핵심 과금 · 성장 벽', 'Core monetization · progression wall'],
  'impact.mark.none': ['없음', 'none'],
  'impact.mark.optional': ['선택 과금', 'optional'],
  'impact.mark.core': ['핵심 과금', 'core'],
  'grade.none': ['근거 없음', 'No evidence'],
  'grade.A': ['A · 1차 확인', 'A · first-hand'],
  'grade.B': ['B · 보도·인용', 'B · press or citation'],
  'grade.C': ['C · 3자·커뮤니티', 'C · third-party / community'],
  'cadence.active': ['활발', 'Active'],
  'cadence.irregular': ['불규칙', 'Irregular'],
  'cadence.dormant': ['휴면', 'Dormant'],
  'cadence.unknown': ['미확인', 'Unconfirmed'],
  'updateType.bugfix': ['버그 수정', 'Bug fixes'],
  'updateType.performance': ['성능·호환', 'Performance · compatibility'],
  'updateType.content': ['콘텐츠·기능', 'Content · features'],
  'updateType.monetization_terms': ['과금·가격 변경', 'Monetization or price change'],
  'updateType.policy_terms': ['약관·정책 변경', 'Terms or policy change'],
  'updateType.other': ['기타', 'Other'],
  'updateType.unknown': ['성격 미확인', 'Character unconfirmed'],
  'promise.not_applicable': ['해당 없음', 'Not applicable'],
  'promise.on_time': ['약속대로', 'As promised'],
  'promise.delayed': ['지연', 'Delayed'],
  'promise.delivered_late': ['늦게라도 이행', 'Delivered late'],
  'promise.unfulfilled': ['미이행', 'Unfulfilled'],
  'export.full': ['전체', 'Full'],
  'export.partial': ['부분', 'Partial'],
  'export.none': ['불가', 'None'],
  'export.unknown': ['미확인', 'Unconfirmed'],
  'freePlay.sufficient': ['무과금으로 충분', 'Sufficient free'],
  'freePlay.constrained': ['무과금은 제한적', 'Constrained free'],
  'freePlay.blocked': ['무과금 진행 불가', 'Free play blocked'],
  'freePlay.unknown': ['미확인', 'Unconfirmed'],
  'method.desk_research': ['데스크 리서치', 'Desk research'],
  'method.hands_on': ['직접 사용', 'Hands-on'],
  'method.mixed': ['혼합', 'Mixed'],
  'verification.direct': ['직접 확인', 'First-hand'],
  'verification.reported_only': ['3자 서술', 'Third-party report'],
  'verification.inferred': ['정황 추론', 'Inferred'],
  'verification.absent': ['부재 근거', 'Absence of evidence'],
  'flag.contains_ads': ['앱 내 광고 포함', 'Contains in-app ads'],
  'flag.gacha_random_items': ['확률형 아이템', 'Random items (gacha)'],
  'flag.forced_ad_before_use': ['강제 전면 광고', 'Forced full-screen ads'],
  'flag.bait_ad': ['미끼형 유입 광고', 'Bait acquisition ads'],
  'flag.p2w': ['P2W(과금이 승패를 좌우)', 'Pay-to-win'],
  'flag.iap_required_to_progress': ['과금 없이 진행 불가', 'Cannot progress without paying'],
  'flag.subscription_required': ['구독 필수', 'Subscription required'],
  'flag.account_required': ['계정 필수', 'Account required'],
  'flag.stale_over_12m': ['12개월 이상 방치', 'Dormant 12+ months'],
  'flag.data_collected': ['과도한 데이터 수집', 'Heavy data collection'],
  'flag.data_export': ['데이터 내보내기', 'Data export'],
  'flag.compat_risk': ['보안·OS 호환성 위험', 'Security / OS compatibility risk'],
  'tag.empty': ['취향 태그 없음', 'No taste tags'],

  /* 등대(Lighthouse) — 조건을 골라 명작 퀘스트 하나를 받는 화면 */
  'lh.kicker': ['LIGHTHOUSE · 등대', 'LIGHTHOUSE'],
  'lh.landing.l1': ['지금 해볼 만한 명작', 'One masterpiece.'],
  'lh.landing.l2': ['목표 하나를 비춥니다', 'One real goal.'],
  'lh.start': ['목표 탐색', 'Find a goal'],
  /* 항해 서약(Pledge) — 목표 탐색 직후, 조건을 고르기 전에 한 번 서는 각서 화면 */
  'lh.pledge.aria': ['항해 서약서', 'Voyage pledge'],
  'lh.pledge.kicker': ['LIGHTHOUSE PLEDGE · 항해 서약', 'LIGHTHOUSE PLEDGE'],
  'lh.pledge.title': ['시작 전 각오', 'Before we set sail'],
  'lh.pledge.body1': [
    '아무거나 대충 구경만 할 거면 지금 돌아가도 좋습니다.',
    'If you are only here to look around, turn back now.',
  ],
  'lh.pledge.body2': [
    '등대는 룰렛을 돌리는 곳이 아니라, 한 번 비춘 목표를 끝까지 걸어가는 사람을 위한 곳입니다.',
    'The lighthouse is no roulette wheel — it is for people who walk the path to the end once a goal is lit.',
  ],
  'lh.pledge.body3': [
    '오늘 받는 좌표는 변명 없이, 다시 뽑을 수 없습니다.',
    'The coordinates you receive today cannot be drawn again. No excuses.',
  ],
  'lh.pledge.check': [
    '오늘 받는 목표를 끝까지 완수할 각오가 되어 있습니다.',
    'I accept these terms and will not turn back.',
  ],
  'lh.pledge.accept': ['서약하고 나아가기', 'Take the Oath'],
  'lh.pledge.back': ['돌아가기', 'Turn Back'],
  'lh.pledge.hint': ['각오를 체크하면 서약 버튼이 열립니다.', 'Tick the box above to unlock the oath.'],
  'lh.q.platform': ['어디서 플레이하나요?', 'Where do you play?'],
  'lh.q.price': ['가격 조건', 'Price'],
  'lh.q.time': ['얼마나 몰입할까요?', 'How deep do you want to go?'],
  'lh.q.difficulty': ['원하는 난이도는요?', 'How hard should it be?'],
  'lh.opt.all': ['전체', 'All'],
  'lh.opt.allSub': ['PC·모바일 모두', 'PC and mobile'],
  'lh.opt.pcSub': ['PC에서만', 'PC only'],
  'lh.opt.mobile': ['모바일', 'Mobile'],
  'lh.opt.mobileSub': ['폰·태블릿', 'Phone or tablet'],
  'lh.opt.priceAll': ['전체', 'All'],
  'lh.opt.priceAllSub': ['유료 포함', 'Paid included'],
  'lh.opt.priceFreeSub': ['무료 게임만', 'Free games only'],
  'lh.opt.diffAllSub': ['아무거나 좋아요', 'Anything goes'],
  'lh.opt.diffChillSub': ['스토리·힐링', 'Story and comfort'],
  'lh.opt.diffNormalSub': ['적당한 도전', 'A fair challenge'],
  'lh.opt.diffHardSub': ['고난도·피지컬', 'Brutal and technical'],
  'lh.diff.all': ['상관없이', 'Any'],
  'lh.diff.chill': ['편안', 'Chill'],
  'lh.diff.normal': ['보통', 'Normal'],
  'lh.diff.hardcore': ['매운맛', 'Spicy'],
  'lh.next': ['다음 →', 'Next →'],
  'lh.prev': ['← 이전', '← Back'],
  'lh.home': ['← 처음으로', '← Start over'],
  'lh.count': ['조건에 맞는 명작 {n}종', '{n} masterworks match'],
  'lh.countZero': ['이 조합에 맞는 명작이 없습니다', 'No masterwork matches this combination'],
  'lh.countZeroHint': ['플랫폼이나 가격 조건을 바꿔 보세요.', 'Try another platform or price.'],
  'lh.inprogress': ['진행 중인 목표', 'Your goal in progress'],
  'lh.eyebrow': ['LIGHTHOUSE · 등대', 'LIGHTHOUSE'],
  'lh.titleBefore': ['별점 사이트가 아니라, ', 'Not another ratings site. '],
  'lh.titleHl': ['지금 도전할 목표', 'A goal for right now'],
  'lh.titleAfter': ['를 비춥니다', '.'],
  'lh.lede': [
    '가격·플랫폼·기간만 고르면, 파로스가 검증한 명작 {n}종 중 하나와 그 안의 실제 목표 하나를 퀘스트로 비춥니다. 장비 목록이 아니라 “오늘 뭐 하지”에 대한 답입니다.',
    'Pick price, platform and length, and the Lighthouse shines on one of {n} vetted masterworks and a real goal inside it — an answer to “what do I play tonight,” not another backlog list.',
  ],
  'lh.stepsAria': ['등대 사용 순서', 'How the Lighthouse works'],
  'lh.step1': ['① 조건 고르기', '① Set your terms'],
  'lh.step2': ['② 명작 한 편', '② One masterwork'],
  'lh.step3': ['③ 목표 하나 완료', '③ Finish one goal'],
  'lh.stat.games': ['명작 게임', 'Vetted games'],
  'lh.stat.quests': ['퀘스트', 'Quests'],
  'lh.stat.free': ['무료 게임', 'Free to play'],
  'lh.stat.done': ['내 완료', 'Done by you'],
  'lh.catalog.kicker': ['전체 카탈로그 · CATALOG', 'FULL CATALOG'],
  'lh.catalog.link': ['{n}개 앱·게임·AI 도구 직접 비교해 보기', 'Compare all {n} apps, games and AI tools'],
  'lh.catalog.sub': ['장르별 추천부터 3축 점수·근거까지 — 등대 뒤의 파로스 전체 데이터',
    'Genre picks, three-axis scores and evidence — the whole Pharos dataset'],
  'lh.filtersAria': ['등대 조건', 'Lighthouse conditions'],
  'lh.price': ['가격', 'Price'],
  'lh.price.all': ['전체', 'All'],
  'lh.price.free': ['무료만', 'Free only'],
  'lh.platform': ['플랫폼', 'Platform'],
  'lh.platform.all': ['전체', 'All'],
  'lh.platform.mobile': ['모바일', 'Mobile'],
  'lh.tier': ['난이도', 'Tier'],
  'lh.tierShort': ['{n}단계', 'Tier {n}'],
  'lh.draw': ['목표 받기', 'Get my goal'],
  'lh.drawLocked': ['퀘스트 진행 중 — 잠김', 'Quest in progress — locked'],
  'lh.lockedNote': ['받은 목표와 조건이 고정됐습니다. 완료하거나 건너뛰면 새로 뽑을 수 있습니다.',
    'Your goal and its conditions are locked. Complete it or skip it to draw again.'],
  'lh.poolNote': ['이 조건에 맞는 명작 {n}종 중 하나를 추첨합니다.', 'One of {n} matching games will be drawn.'],
  'lh.emptyTitle': ['아직 등대를 비추지 않았습니다', 'The lighthouse is not lit yet'],
  'lh.emptyBody': ['위에서 조건을 고르고 ‘이 조건으로 등대 비추기’를 눌러 오늘의 퀘스트를 받아 보세요.',
    'Choose your conditions above and press “Shine the lighthouse” to get today’s quest.'],
  'lh.questKicker': ['오늘의 퀘스트', "Today's quest"],
  'lh.tipLabel': ['한 줄 팁', 'Tip:'],
  'lh.estLabel': ['예상 소요', 'Est. time'],
  'lh.score': ['파로스 {score}점', 'Pharos {score}'],
  'lh.badge.free': ['무료', 'Free'],
  'lh.badge.paid': ['유료', 'Paid'],
  'lh.complete': ['✅ 완료했어요', '✅ Done'],
  'lh.adSkip': ['📺 광고 보고 다른 목표 받기', '📺 Watch an ad for a new goal'],
  'lh.detail': ['게임 상세 보기', 'View game details'],
  'lh.historyTitle': ['완료 기록', 'Completion log'],
  'lh.historyCount': ['누적 완료 {n} · 건너뛰기 {s}회', '{n} completed · {s} skipped'],
  'lh.historyEmpty': ['완료한 퀘스트가 아직 없습니다 — 첫 퀘스트를 끝내면 여기에 배지가 쌓입니다.',
    'No completed quests yet — finish your first one and its badge lands here.'],
  'lh.crumbNote': ['조건을 고르면 명작 하나와 그 안의 실제 목표를 비춥니다.',
    'Pick conditions and the Lighthouse shines on one game and a real goal inside it.'],
  'lh.toast.drawn': ['등대가 한 게임을 비췄습니다.', 'The lighthouse picked one.'],
  'lh.toast.completed': ['퀘스트 완료 — {name}', 'Quest complete — {name}'],
  'lh.toast.skipped': ['건너뛰었습니다. 새 퀘스트를 뽑을 수 있습니다.', 'Skipped. You can draw a new quest.'],
  'lh.toast.noMatch': ['이 조건에 맞는 게임이 없습니다. 조건을 바꿔 보세요.', 'No game matches these conditions. Try another combination.'],
  'lh.toast.noData': ['등대 데이터를 불러오지 못했습니다. 새로고침해 주세요.', 'Could not load the Lighthouse data. Please refresh.'],
  'lh.ad.label': ['보상형 광고 자리', 'Rewarded ad slot'],
  'lh.ad.title': ['광고 보고 건너뛰기', 'Watch an ad to skip'],
  'lh.ad.close': ['광고 닫기', 'Close ad'],
  'lh.ad.mock': ['정식 출시 시 보상형 동영상 광고가 재생되는 자리입니다',
    'This is where a rewarded video ad will play at launch'],
  'lh.ad.sub': ['지금은 5초 테스트 시청으로 대체합니다. 끝나면 새 퀘스트를 뽑을 수 있습니다.',
    'For now it is a five-second test slot. When it ends you can draw a new quest.'],
  'lh.ad.seconds': ['초', 's'],
  'lh.ad.wait': ['{n}초 후 건너뛰기 가능', 'Skip in {n}s'],
  'lh.ad.ready': ['건너뛰고 새 퀘스트 뽑기', 'Skip and draw a new quest'],
};

/* --------------------------------------------------------------- 언어 상태 */

let current = DEFAULT_LANG;

function normalizeLang(value) {
  const lang = String(value || '').toLowerCase();
  return lang.startsWith('ko') ? 'ko' : lang ? 'en' : null;
}

/** 우선순위: URL ?lang= → localStorage → 브라우저 언어(ko* 만 한국어, 그 외 전부 영어). */
export function detectLang(search = typeof location !== 'undefined' ? location.search : '') {
  try {
    const fromUrl = normalizeLang(new URLSearchParams(search).get('lang'));
    if (fromUrl) return fromUrl;
  } catch {
    /* URL 파싱 실패는 무시 */
  }
  try {
    const stored = normalizeLang(localStorage.getItem(LANG_STORE_KEY));
    if (stored) return stored;
  } catch {
    /* 저장소 접근 실패는 무시 */
  }
  const nav = typeof navigator !== 'undefined' ? navigator.language || navigator.userLanguage : '';
  return normalizeLang(nav) || 'en';
}

export function initLang(search) {
  current = detectLang(search);
  if (typeof document !== 'undefined') document.documentElement.lang = current;
  return current;
}

export function setLang(lang) {
  const next = LANGS.includes(lang) ? lang : DEFAULT_LANG;
  current = next;
  try {
    localStorage.setItem(LANG_STORE_KEY, next);
  } catch {
    /* 무시 */
  }
  if (typeof document !== 'undefined') document.documentElement.lang = next;
  return next;
}

export function getLang() {
  return current;
}

export function isEn() {
  return current === 'en';
}

/* --------------------------------------------------------------- 조회·보간 */

function interpolate(text, params) {
  if (!params) return text;
  return String(text).replace(/\{(\w+)\}/g, (all, key) => (params[key] === undefined ? all : params[key]));
}

/** UI 문자열 — 현재 언어, 없으면 한국어, 없으면 키 그대로. */
export function t(key, params) {
  const row = M[key];
  const text = row ? (current === 'en' ? row[1] : row[0]) : key;
  return interpolate(text ?? '', params);
}

/** 라벨 그룹 조회 — meta.label 처럼 `{group}.{key}` 키가 있으면 그걸, 없으면 fallback. */
export function labeled(group, key, fallback) {
  const full = `${group}.${key}`;
  if (M[full]) return t(full);
  return fallback ?? key;
}

/** 일수 표기 — 영어는 1 day / N days, 한국어는 N일. */
export function days(n) {
  const count = Number(n);
  return t(count === 1 ? 'fresh.days' : 'fresh.daysPlural', { n: count });
}

/** 숫자 표기 — 언어에 맞는 천 단위 구분. */
export function nfmt(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString(current === 'en' ? 'en-US' : 'ko-KR');
}

/** 정적 마크업(index.html)의 data-i18n 계열 속성을 현재 언어로 채운다. */
export function applyStaticI18n(root = typeof document !== 'undefined' ? document : null) {
  if (!root) return;
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  root.querySelectorAll('[data-i18n-html]').forEach((el) => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
  root.querySelectorAll('[data-i18n-aria-label]').forEach((el) => {
    el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
  });
  root.querySelectorAll('[data-i18n-title]').forEach((el) => {
    el.setAttribute('title', t(el.dataset.i18nTitle));
  });
  root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    el.setAttribute('placeholder', t(el.dataset.i18nPlaceholder));
  });
}
