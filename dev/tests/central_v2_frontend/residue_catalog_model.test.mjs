import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

const model = await browserModules()('/texto_off/comparison/residue_model.js');

test('residue pointer coordinates clamp and normalize reversible boxes', () => {
  const rect = { left: 100, top: 50, width: 200, height: 100 };
  const start = model.normalizedPoint({ clientX: 350, clientY: 25 }, rect);
  const end = model.normalizedPoint({ clientX: 50, clientY: 200 }, rect);
  const box = model.normalizedBox(start, end);
  assert.equal(box.left, 0); assert.equal(box.top, 0);
  assert.equal(box.width, 1); assert.equal(box.height, 1);
  assert.deepEqual({ ...model.normalizedPoint({ clientX: 125, clientY: 75 }, rect) }, { x: .125, y: .25 });
});

test('residue minimum uses rendered dimensions and normalized state stays zoom independent', () => {
  const box = { left: .2, top: .1, width: .05, height: .1 };
  const small = model.renderedBoxSize(box, { width: 300, height: 400 });
  const large = model.renderedBoxSize(box, { width: 800, height: 900 });
  assert.ok(small.width < 20); assert.ok(small.height >= 20);
  assert.ok(large.width >= 20); assert.ok(large.height >= 20);
  assert.equal(box.left, .2); assert.equal(box.width, .05);
});

test('draft identity stays stable while visible numbering follows current list order', () => {
  const draft = model.createPageDraft();
  const first = model.addOccurrence(draft, { left: 0, top: 0, width: .1, height: .1 }, 'id-a');
  const second = model.addOccurrence(draft, { left: .1, top: .1, width: .1, height: .1 }, 'id-b');
  const third = model.addOccurrence(draft, { left: .2, top: .2, width: .1, height: .1 }, 'id-c');
  assert.deepEqual(JSON.parse(JSON.stringify(draft.occurrences.map((item, index) => [item.id, index + 1]))), [
    ['id-a', 1], ['id-b', 2], ['id-c', 3],
  ]);
  assert.equal(model.removeFromDraft(draft, second.id), true);
  assert.deepEqual(JSON.parse(JSON.stringify(draft.occurrences.map((item, index) => [item.id, index + 1]))), [
    ['id-a', 1], ['id-c', 2],
  ]);
  const fourth = model.addOccurrence(draft, { left: .3, top: .3, width: .1, height: .1 }, 'id-d');
  assert.deepEqual(JSON.parse(JSON.stringify(draft.occurrences.map((item, index) => [item.id, index + 1]))), [
    ['id-a', 1], ['id-c', 2], ['id-d', 3],
  ]);
  assert.equal(draft.occurrences[1], third);
  assert.equal(draft.occurrences[2], fourth);
  assert.equal(model.removeFromDraft(draft, first.id), true);
  assert.deepEqual(JSON.parse(JSON.stringify(draft.occurrences.map((item, index) => [item.id, index + 1]))), [
    ['id-c', 1], ['id-d', 2],
  ]);
  assert.equal(model.removeFromDraft(draft, 'missing'), false);
});

test('residue types include canonical values and changing away from other clears its note', () => {
  assert.deepEqual(Array.from(model.RESIDUE_TYPES, ([value]) => value), [
    'residuo_transparencia', 'residuo_degrade', 'residuo_gradiente',
    'fragmento_balao', 'texto_residual', 'outro',
  ]);
  const item = { type: 'outro', note: 'marca' };
  model.updateOccurrenceType(item, 'residuo_degrade');
  assert.equal(item.note, null); assert.equal(item.type, 'residuo_degrade');
});

test('page-keyed draft map preserves independent pages during navigation', () => {
  const drafts = model.createPageDraftStore();
  model.addOccurrence(drafts.get('step:page-a'), { left: 0, top: 0, width: .1, height: .1 }, 'a');
  model.addOccurrence(drafts.get('step:page-b'), { left: .5, top: .5, width: .2, height: .2 }, 'b');
  assert.equal(drafts.get('step:page-a').occurrences[0].id, 'a');
  assert.equal(drafts.get('step:page-b').occurrences[0].id, 'b');
  assert.deepEqual(Array.from(drafts.get('step:page-a').occurrences, (item) => item.id), ['a']);
});
