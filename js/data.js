/**
 * Pharos 데이터 로더.
 * 배포 단위는 web/ 폴더 하나다 — 카탈로그·인덱스·스키마 사본도 web/ 안에 둔다
 * (projects/pharos/scripts/sync_web_data.py 가 원본과 동기화).
 *
 * 읽는 순서
 *   1) core  : data/catalog.json (도메인·대분류·비교군 정의) + data/search-index.json + schema/item.schema.json
 *              + 영어 모드일 때만 data/en/core.json(카탈로그 라벨·장르 사전) 과 data/en/index.json(항목 요약).
 *              v35 부터 영문은 32MB 단일 en.json 이 아니라 core·index 두 파일만 먼저 받는다.
 *   2) arena : 선택한 비교군의 data_file 만 지연 로딩(lazy load)하고 캐시한다.
 *              영어 모드에서는 같은 경로의 data/en/{domain}/{arena}.json 청크를 함께 받아 합친다.
 *              그래서 상세 문장·출처·축 서술 같은 큰 텍스트는 그 비교군을 열 때만 내려온다.
 */

export const DATA_PATHS = {
  catalog: './data/catalog.json',
  searchIndex: './data/search-index.json',
  schema: './schema/item.schema.json',
  enCore: './data/en/core.json',
  enIndex: './data/en/index.json',
};

async function fetchJson(url) {
  const res = await fetch(url, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`${url} → HTTP ${res.status}`);
  return res.json();
}

/* ------------------------------------------------------------ 번역 오버레이 */

const isPlainObject = (value) => Boolean(value) && typeof value === 'object' && !Array.isArray(value);

/**
 * 오버레이 병합 — 객체는 키 단위로 내려가고, 배열·원시값은 통째로 바꾼다.
 * 티어의 `price_display` 는 원본 `price.display` 자리에 들어간다(가격 표기 영문화).
 */
export function mergeOverlay(base, overlay) {
  if (overlay === undefined || overlay === null) return base;
  if (Array.isArray(overlay)) return overlay.slice();
  if (!isPlainObject(overlay)) return overlay;
  const out = isPlainObject(base) ? { ...base } : {};
  for (const [key, value] of Object.entries(overlay)) {
    if (key === 'price_display') {
      out.price = { ...(isPlainObject(out.price) ? out.price : {}), display: value };
      continue;
    }
    out[key] = mergeOverlay(out[key], value);
  }
  return out;
}

/** en 청크의 항목 오버레이를 한 항목에 적용한다. */
export function localizeItem(item, overlays) {
  const overlay = overlays?.[item?.id];
  if (!overlay) return item;
  return mergeOverlay(item, overlay);
}

/** 카탈로그 라벨·설명을 영어 공통부(en/core.json)로 바꾼 사본을 만든다. */
export function localizeCatalog(catalog, core) {
  if (!core) return catalog;
  const copy = JSON.parse(JSON.stringify(catalog));
  for (const domain of copy.domains || []) {
    const t = core.domains?.[domain.id];
    if (t?.label) domain.label = t.label;
    if (t?.description) domain.description = t.description;
    if (t?.filter_labels) domain.filter_labels = { ...(domain.filter_labels || {}), ...t.filter_labels };
  }
  for (const category of copy.categories || []) {
    const t = core.categories?.[category.id];
    if (t?.label) category.label = t.label;
    if (t?.description) category.description = t.description;
  }
  for (const arena of copy.arenas || []) {
    const t = core.arenas?.[arena.id];
    if (t?.label) arena.label = t.label;
    if (t?.description) arena.description = t.description;
  }
  for (const [key, pack] of Object.entries(copy.filter_packs || {})) {
    const t = core.filter_packs?.[key];
    if (t?.label) pack.label = t.label;
    if (t?.description) pack.description = t.description;
  }
  if (copy.home?.gap_report && core.home?.gap_report) {
    if (core.home.gap_report.title) copy.home.gap_report.title = core.home.gap_report.title;
    if (core.home.gap_report.note) copy.home.gap_report.note = core.home.gap_report.note;
  }
  return copy;
}

/**
 * 경량 인덱스(검색·홈 리포트·목록 카드)의 표시 문자열을 영어 요약(en/index.json)으로 바꾼 사본.
 * 항목 요약에는 이름·한 줄·대표 티어 한 줄·장르·개발사만 있으므로 비교군 청크 없이도 그려진다.
 */
export function localizeIndex(index, catalog, en, contract = null) {
  if (!en || !index) return index;
  const core = en.core || {};
  const light = en.index?.items || {};
  const AXES_EN = { user_rating: 'User Rating', objective: 'Objective Trust', ai_review: 'AI Review' };
  const filterKo = new Map(
    (contract?.hard_filters || []).map((def) => [def.label, core.filter_labels?.[def.key] || def.label]),
  );
  for (const domain of catalog?.domains || []) {
    for (const [key, ko] of Object.entries(domain.filter_labels || {})) {
      filterKo.set(ko, core.domains?.[domain.id]?.filter_labels?.[key] || core.filter_labels?.[key] || ko);
    }
  }
  const copy = JSON.parse(JSON.stringify(index));
  const names = new Map();
  for (const rec of copy.items || []) {
    const t = light[rec.id];
    if (!t) continue;
    if (t.name) {
      names.set(rec.id, t.name);
      rec.name = t.name;
    }
    if (t.one_liner) rec.one_liner = t.one_liner;
    rec.tagline = t.tiers?.[rec.tier_of_record] || t.tagline || rec.tagline;
    if (Array.isArray(t.genres)) rec.genres = t.genres;
    else rec.genres = (rec.genres || []).map((g) => core.genres?.[g] || g);
    if (t.developer) rec.developer = t.developer;
    for (const driver of rec.drivers || []) {
      if (filterKo.has(driver.label)) {
        driver.label = filterKo.get(driver.label);
        continue;
      }
      const mark = driver.label.match(/([🟢🟡🔴⚪])\s*(.*)$/);
      if (mark) {
        const axisKo = driver.label.slice(0, mark.index).trim();
        const axisDef = (contract?.axes || []).find((def) => def.label === axisKo);
        const axisName = axisDef ? AXES_EN[axisDef.key] : axisKo;
        driver.label = `${axisName} ${mark[1]} ${mark[2]}`.trim();
      }
    }
  }
  for (const [arenaId, stat] of Object.entries(copy.arena_stats || {})) {
    const t = core.arenas?.[arenaId];
    if (t?.label) stat.label = t.label;
    if (stat.top_item && names.has(stat.top_item.id)) stat.top_item.name = names.get(stat.top_item.id);
  }
  if (copy.gap_report && core.home?.gap_report?.title) copy.gap_report.title = core.home.gap_report.title;
  return copy;
}

/* ------------------------------------------------------------------ 로더 */

/** 영어 공통부 + 항목 요약. 한쪽이 없어도 나머지로 최대한 그린다(조용한 한국어 폴백). */
async function loadEnglish() {
  const [core, index] = await Promise.all([
    fetchJson(DATA_PATHS.enCore).catch(() => null),
    fetchJson(DATA_PATHS.enIndex).catch(() => null),
  ]);
  if (!core) return null;
  return { core, index };
}

export async function loadCore(lang = 'ko') {
  const wantsEn = lang === 'en';
  const [catalog, index, schema, en] = await Promise.all([
    fetchJson(DATA_PATHS.catalog),
    fetchJson(DATA_PATHS.searchIndex),
    fetchJson(DATA_PATHS.schema),
    wantsEn ? loadEnglish() : Promise.resolve(null),
  ]);
  const contract = schema?.['x-pharos']?.client;
  if (!contract) throw new Error('스키마에 x-pharos.client 계산 계약이 없습니다.');
  if (!Array.isArray(catalog?.arenas) || !catalog.arenas.length) {
    throw new Error('data/catalog.json 에 비교군 정의가 없습니다.');
  }
  return {
    catalog: localizeCatalog(catalog, en?.core),
    index: localizeIndex(index, catalog, en, contract),
    schema,
    contract,
    en,
    raw: { catalog, index },
  };
}

/** 비교군 파일 경로 — data_file 은 catalog.json 이 있는 폴더(data/) 기준 상대경로다. */
export function arenaPath(catalog, arenaId) {
  const arena = (catalog?.arenas || []).find((row) => row.id === arenaId);
  if (!arena) return null;
  return `./data/${arena.data_file}`;
}

/** 비교군 영문 청크 경로 — 원본 비교군 파일과 같은 경로를 data/en/ 아래에 둔다. */
export function arenaEnPath(catalog, arenaId) {
  const arena = (catalog?.arenas || []).find((row) => row.id === arenaId);
  if (!arena) return null;
  return `./data/en/${arena.data_file}`;
}

/** 카탈로그 조회 도우미 (도메인·대분류·비교군 라벨). */
export function createCatalogView(catalog) {
  const domains = new Map((catalog?.domains || []).map((d) => [d.id, d]));
  const categories = new Map((catalog?.categories || []).map((c) => [c.id, c]));
  const arenas = new Map((catalog?.arenas || []).map((a) => [a.id, a]));
  return {
    catalog,
    domains,
    categories,
    arenas,
    domain: (id) => domains.get(id) || null,
    category: (id) => categories.get(id) || null,
    arena: (id) => arenas.get(id) || null,
    domainLabel: (id) => domains.get(id)?.label || id,
    categoryLabel: (id) => categories.get(id)?.label || id,
    arenaLabel: (id) => arenas.get(id)?.label || id,
    arenasOf: (domainId, categoryId) =>
      (catalog?.arenas || []).filter(
        (a) => (!domainId || a.domain === domainId) && (!categoryId || a.category === categoryId),
      ),
    categoriesOf: (domainId) => (catalog?.categories || []).filter((c) => c.domain === domainId),
    filterPack: (packId) => (catalog?.filter_packs || {})[packId] || null,
  };
}

/**
 * 비교군 데이터 지연 로딩 + 캐시.
 * 홈·검색은 경량 인덱스만 쓰고, 목록·상세·비교는 이 스토어로 필요한 파일만 읽는다.
 * 영어 모드에서는 비교군 파일과 그 영문 청크를 나란히 받아 항목마다 오버레이를 합친다
 * (영문 청크가 없거나 실패하면 한국어 항목 그대로 — 화면이 비지 않는다).
 */
export function createArenaStore(catalog, en = null) {
  const cache = new Map();
  const pending = new Map();
  async function load(arenaId) {
    if (cache.has(arenaId)) return cache.get(arenaId);
    if (pending.has(arenaId)) return pending.get(arenaId);
    const url = arenaPath(catalog, arenaId);
    if (!url) throw new Error(`알 수 없는 비교군: ${arenaId}`);
    const enUrl = en ? arenaEnPath(catalog, arenaId) : null;
    const task = Promise.all([
      fetchJson(url),
      enUrl ? fetchJson(enUrl).catch(() => null) : Promise.resolve(null),
    ])
      .then(([items, chunk]) => {
        const overlays = chunk?.items || null;
        const list = (Array.isArray(items) ? items : [items]).map((item) => localizeItem(item, overlays));
        cache.set(arenaId, list);
        pending.delete(arenaId);
        return list;
      })
      .catch((err) => {
        pending.delete(arenaId);
        throw err;
      });
    pending.set(arenaId, task);
    return task;
  }
  return {
    loaded: (arenaId) => cache.has(arenaId),
    get: (arenaId) => cache.get(arenaId) || null,
    load,
    async loadMany(arenaIds) {
      const unique = [...new Set(arenaIds.filter(Boolean))];
      const lists = await Promise.all(unique.map((id) => load(id)));
      return lists.flat();
    },
  };
}

/**
 * 통합 검색 — 이름·별칭·개발사·장르·취향 태그·키워드·한 줄 정의 + 비교군/대분류 라벨.
 * 경량 인덱스만 읽으므로 비교군 파일을 내려받지 않고 즉시 결과를 낸다.
 */
export function searchRecords(index, catalogView, query) {
  const q = String(query || '').trim().toLowerCase();
  if (!q) return [];
  const tokens = q.split(/\s+/).filter(Boolean);
  const rows = [];
  for (const rec of index?.items || []) {
    const arenaLabels = (rec.arenas || []).map((id) => catalogView.arenaLabel(id));
    const hay = [
      rec.name,
      ...(rec.aliases || []),
      rec.developer,
      ...(rec.keywords || []),
      ...(rec.taste_tags || []),
      ...arenaLabels,
      catalogView.categoryLabel(rec.category),
      catalogView.domainLabel(rec.domain),
      rec.one_liner,
    ]
      .join(' ')
      .toLowerCase();
    let score = 0;
    for (const token of tokens) {
      if (hay.includes(token)) score += token.length >= 2 ? 3 : 1;
    }
    if (rec.name.toLowerCase().startsWith(q)) score += 8;
    if ((rec.aliases || []).some((alias) => alias.toLowerCase() === q)) score += 6;
    if (!score) continue;
    rows.push({ record: rec, score, arenaLabels });
  }
  return rows.sort(
    (a, b) => b.score - a.score || (b.record.score ?? -1) - (a.record.score ?? -1),
  );
}
