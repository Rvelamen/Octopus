import test from 'node:test';
import assert from 'node:assert/strict';
import { getSceneAreas, normalizeLayout, moveArea } from './librarySceneState.mjs';

test('saved layout survives renamed collections and newly added nested areas', () => {
  const layout = normalizeLayout({ version: 1, positions: { 3: { x: 9, z: -2 } } });
  const areas = getSceneAreas([
    { id: 1, name: 'All' },
    { id: 2, count: 0 },
    { id: 3, name: '新名字', children: [{ id: 4, name: '子区域' }] },
  ], layout);
  assert.deepEqual(areas.map((area) => area.id), [3, 4]);
  assert.deepEqual(areas[0].position, { x: 9, z: -2 });
  assert.notDeepEqual(areas[0].position, areas[1].position);
});

test('invalid coordinates cannot poison the renderer and positions are snapped and bounded', () => {
  const layout = normalizeLayout({ version: 1, positions: {
    3: { x: Infinity, z: 0 }, 4: { x: '1', z: 0 },
    5: { x: 100, z: -2.3 }, invalid: { x: 0, z: 0 },
  } });
  assert.deepEqual(layout.positions, { 5: { x: 32, z: -2.5 } });
  assert.deepEqual(normalizeLayout({ version: 999, positions: layout.positions }).positions, {});
});

test('moving one area preserves other positions without mutating the saved layout', () => {
  const saved = { version: 1, positions: { 3: { x: 1, z: 2 } } };
  const moved = moveArea(saved, 4, { x: 3.2, z: 4.8 });
  assert.deepEqual(saved.positions, { 3: { x: 1, z: 2 } });
  assert.deepEqual(moved.positions, { 3: { x: 1, z: 2 }, 4: { x: 3, z: 5 } });
});

test('empty libraries keep an empty inbox area instead of displaying invented books', () => {
  const areas = getSceneAreas([{ id: 1 }, { id: 2, count: 0 }], normalizeLayout(null));
  assert.equal(areas.length, 1);
  assert.equal(areas[0].id, 2);
  assert.equal(areas[0].count, 0);
});
