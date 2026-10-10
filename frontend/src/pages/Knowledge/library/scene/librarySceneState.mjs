export const SCENE_LAYOUT_PATH = 'knowledge/library/.scene-layout.json';
export const SHELF_PAGE_SIZE = 18;
export const AREA_COLORS = ['#93bba4', '#dca78b', '#9fb9cc', '#c4aed0', '#ddc280', '#aabfa0'];

export function flattenCollections(collections) {
  return collections.flatMap((collection) => [
    { ...collection, children: undefined },
    ...flattenCollections(collection.children || []),
  ]);
}

export function normalizeLayout(value) {
  const positions = {};
  if (value?.version !== 1) return { version: 1, positions };
  for (const [id, position] of Object.entries(value.positions || {})) {
    if (!/^\d+$/.test(id) || !Number.isFinite(position?.x) || !Number.isFinite(position?.z)) continue;
    positions[id] = {
      x: Math.max(-32, Math.min(32, Math.round(position.x * 2) / 2)),
      z: Math.max(-32, Math.min(32, Math.round(position.z * 2) / 2)),
    };
  }
  return { version: 1, positions };
}

export function getSceneAreas(collections, layout) {
  const flat = flattenCollections(collections);
  const custom = flat.filter((collection) => collection.id > 2);
  const inbox = flat.find((collection) => collection.id === 2);
  const visible = [...custom, ...(inbox && (inbox.count > 0 || !custom.length) ? [inbox] : [])];
  const columns = Math.min(3, Math.max(1, visible.length));
  return visible.map((collection, index) => ({
    ...collection,
    name: collection.id === 2 ? '待整理书籍' : collection.name,
    color: /^#[\da-f]{6}$/i.test(collection.color || '') ? collection.color : AREA_COLORS[index % AREA_COLORS.length],
    position: layout.positions[collection.id] || {
      x: ((index % columns) - (columns - 1) / 2) * 5.4,
      z: Math.floor(index / columns) * 4.8,
    },
  }));
}

export function moveArea(layout, id, position) {
  return normalizeLayout({ ...layout, positions: { ...layout.positions, [id]: position } });
}
