/**
 * Pharos 데이터 로더.
 * 배포 단위는 web/ 폴더 하나다 — 카탈로그·인덱스·스키마 사본도 web/ 안에 둔다
 * (projects/pharos/scripts/sync_web_data.py 가 원본과 동기화).
 *
 * 읽는 순서
 *   1) core  : data/catalog.json (도메인·대분류·비교군 정의) + data/search-index.json + schema/item.schema.json
 *   2) arena : 선택한 비교군의 data_file 만 지연 로딩(lazy load)하고 캐시한다.
 */

export const DATA_PATHS = {
  catalog: './data/catalog.json',
  searchIndex: './data/search-index.json',
  schema: './schema/item.schema.json',
};

async function fetchJson(url) {
  const res = await fetch(url, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`${url} → HTTP ${res.status}`);
  return res.json();
}

export async function loadCore() {
  const [catalog, index, schema] = await Promise.all([
    fetchJson(DATA_PATHS.catalog),
    fetchJson(DATA_PATHS.searchIndex),
    fetchJson(DATA_PATHS.schema),
  ]);
  const contract = schema?.['x-pharos']?.client;
  if (!contract) throw new Error('스키마에 x-pharos.client 계산 계약이 없습니다.');
  if (!Array.isArray(catalog?.arenas) || !catalog.arenas.length) {
    throw new Error('data/catalog.json 에 비교군 정의가 없습니다.');
  }
  return { catalog, index, schema, contract };
}

/** 비교군 파일 경로 — data_file 은 catalog.json 이 있는 폴더(data/) 기준 상대경로다. */
export function arenaPath(catalog, arenaId) {
  const arena = (catalog?.arenas || []).find((row) => row.id === arenaId);
  if (!arena) return null;
  return `./data/${arena.data_file}`;
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
 */
export function createArenaStore(catalog) {
  const cache = new Map();
  const pending = new Map();
  async function load(arenaId) {
    if (cache.has(arenaId)) return cache.get(arenaId);
    if (pending.has(arenaId)) return pending.get(arenaId);
    const url = arenaPath(catalog, arenaId);
    if (!url) throw new Error(`알 수 없는 비교군: ${arenaId}`);
    const task = fetchJson(url)
      .then((items) => {
        const list = Array.isArray(items) ? items : [items];
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
