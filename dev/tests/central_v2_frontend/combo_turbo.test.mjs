import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

async function behavior() {
  const load = browserModules();
  return load('/texto_off/combo_turbo/behavior.js');
}

const eligible = (chapter) => ({ chapter, status: 'PLANNED', pages: [
  { stages: { SOLIDOS: { status: 'PLANNED' }, GLASS: { status: 'NO_WORK' } } },
] });
const blocked = { chapter: 'b', status: 'BLOCKED', pages: [] };
const noWork = { chapter: 'n', status: 'NO_WORK', pages: [] };

test('checkbox policy rejects BLOCKED and NO_WORK chapters in the selection handler', async () => {
  const { isSelectable, selectChapter } = await behavior();
  assert.equal(isSelectable(blocked), false);
  assert.equal(isSelectable(noWork), false);
  for (const row of [blocked, noWork]) {
    const result = selectChapter(new Set(), [row], row.chapter, true);
    assert.equal(result.changed, false);
    assert.match(result.reason, /sem elegibilidade/);
  }
});

test('select all includes only eligible chapters and caps the selection at 40', async () => {
  const { selectEligible } = await behavior();
  const rows = [...Array.from({ length: 42 }, (_, i) => eligible(String(i + 1))), blocked, noWork];
  const selected = selectEligible(rows);
  assert.equal(selected.size, 40);
  assert.deepEqual([...selected], Array.from({ length: 40 }, (_, i) => String(i + 1)));
});

test('individual and page selection enforce eligibility and the 40 chapter limit', async () => {
  const { selectChapter, selectChapters } = await behavior();
  let selected = new Set(Array.from({ length: 40 }, (_, i) => String(i + 1)));
  assert.equal(selectChapter(selected, [eligible('41')], '41', true).changed, false);
  assert.equal(selectChapters(selected, [eligible('41')], ['41'], true).changed, false);
  const removed = selectChapter(selected, [], '1', false);
  assert.equal(removed.selected.size, 39);
  assert.equal(removed.changed, true);
});

test('eligibility changes prune selection and signal plan invalidation', async () => {
  const { reconcileSelection } = await behavior();
  const selected = new Set(['1', '2']);
  const result = reconcileSelection(selected, [eligible('1'), blocked]);
  assert.deepEqual([...result.selected], ['1']);
  assert.equal(result.changed, true);
});

test('Execute requires a valid plan and no active load, conflict, or job', async () => {
  const { canExecute } = await behavior();
  const base = { selected: new Set(['1']), planValid: true };
  assert.equal(canExecute(base), true);
  for (const field of ['busy', 'loading', 'conflict']) assert.equal(canExecute({ ...base, [field]: true }), false);
  assert.equal(canExecute({ ...base, planValid: false }), false);
  assert.equal(canExecute({ ...base, selected: new Set() }), false);
});

test('progress is indeterminate for null percent and reports page counts without inventing a ratio', async () => {
  const { progressPresentation } = await behavior();
  const result = progressPresentation({ status: 'running', progress: {
    percent: null, completed: 2, total: 5,
  } });
  assert.equal(result.percent, null);
  assert.equal(result.text, '2 de 5 páginas');
  assert.equal(result.terminal, false);
});

test('valid progress percent is used and active jobs cannot display 100 percent', async () => {
  const { progressPresentation } = await behavior();
  const result = progressPresentation({ status: 'running', progress: {
    percent: 60, completed: 2, total: 5,
  } });
  assert.equal(result.percent, 60);
  assert.equal(result.text, '60% · 2 de 5 páginas');
  assert.equal(result.terminal, false);
  assert.equal(progressPresentation({ status: 'running', percent: 100 }).percent, 99);
});

test('results remain hidden until a terminal job state, including completed/failed/blocked', async () => {
  const { resultVisible } = await behavior();
  const result = { status: 'COMPLETED', results: [] };
  assert.equal(resultVisible({ status: 'running' }, result), false);
  for (const status of ['completed', 'failed', 'blocked']) {
    assert.equal(resultVisible({ status }, result), true);
  }
});

test('HTTP 409 is recognized as a plan conflict requiring replanning', async () => {
  const { isConflict } = await behavior();
  assert.equal(isConflict({ status: 409 }), true);
  assert.equal(isConflict({ status: 400 }), false);
});
