import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

test('Glass Básica offers chapters only after Passo 2 has a valid result', async () => {
  const { canCompare } = await browserModules()('/texto_off/comparison/launcher.js');
  assert.equal(canCompare({ cleaned: true, level2_status: 'pending' }, '2', 'level2'), false);
  assert.equal(canCompare({ cleaned: true, level2_status: 'no_candidates' }, '2', 'level2'), false);
  assert.equal(canCompare({ cleaned: true, level2_status: 'processed' }, '2', 'level2'), true);
  assert.equal(canCompare({ cleaned: true, level2_status: 'no_change' }, '2', 'level2'), true);
});

test('audit chapter change retains zoom, focus and selected panels', async () => {
  const contexts = [];
  const origin = {
    parentElement: { scrollTop: 0 },
    classList: { add() {}, remove() {} },
    after() {},
  };
  const load = browserModules({
    getTestContext: () => ({ provider: 'comix', manga: 'obra' }),
    subscribeTestContext: () => () => {},
    createTestScreen(context) {
      contexts.push(context);
      return { element: { remove() {} }, start() {}, dispose() {},
        getViewState: () => ({ zoom: 80, focus: true, visiblePanels: ['original', 'final'] }) };
    },
  }, {
    '/_app/state/context.js': 'export const getContext = () => getTestContext(); export const subscribeContext = () => subscribeTestContext();',
    '/_shared/icons/icons.js': 'export const iconMarkup = () => "";',
    '/texto_off/comparison/screen.js': 'export const createComparisonScreen = (...args) => createTestScreen(...args);',
  });
  const { createComparisonLauncher } = await load('/texto_off/comparison/launcher.js');
  const launcher = createComparisonLauncher(origin, '1', 'before_after');
  const rows = [{ chapter: '1', cleaned: true }, { chapter: '2', cleaned: false },
    { chapter: '3', cleaned: true }];
  launcher.setChapters(rows);
  launcher.open(rows[0], null);
  assert.deepEqual(contexts[0].availableChapters.map((row) => row.chapter), ['1', '3']);
  contexts[0].onChapterChange('2');
  assert.equal(contexts.length, 1);
  contexts[0].onChapterChange('3');
  assert.equal(contexts[1].chapter, '3');
  assert.deepEqual(contexts[1].viewState, { zoom: 80, focus: true, visiblePanels: ['original', 'final'] });
  launcher.dispose();
});
