import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

class FakeElement {
  constructor() {
    this.nodes = new Map();
    this.children = [];
    this.listeners = new Map();
    this.value = '';
    this.disabled = false;
  }

  querySelector(selector) {
    if (!this.nodes.has(selector)) this.nodes.set(selector, new FakeElement());
    return this.nodes.get(selector);
  }
  addEventListener(event, handler) { this.listeners.set(event, handler); }
  removeEventListener(event) { this.listeners.delete(event); }
  replaceChildren(...items) { this.children = items; }
  append(...items) { this.children.push(...items); }
  after() {}
  setAttribute() {}
  click() { return this.listeners.get('click')?.(); }
}

test('level 2 shows a separate Reprocessar action only for completed rows', async () => {
  const document = { createElement: () => new FakeElement() };
  const load = browserModules({ document }, {
    '/texto_off/comparison/launcher.js': `
      export function createComparisonLauncher() { return { column: {}, dispose() {} }; }`,
    '/texto_off/merged/outcome_filters.js': `
      export function matchesOutcome() { return true; }
      export function drawOutcomeFilters() {}`, 
    '/_app/state/context.js': `
      export function getContext() { return {}; }
      export function subscribeContext() { return () => {}; }`,
    '/_app/api/textoff.js': `export function fetchMergedTextoff() { return {}; }`,
    '/_shared/table/table.js': `
      export function createTable(columns, rows) { return { columns, rows }; }`,
    '/_shared/pagination/model.js': `
      export function createPagination() { return { reset() {}, select(rows) { return { rows }; } }; }`,
    '/_shared/pagination/pagination.js': `
      export function createPaginationControls() { return {}; }`,
    '/_shared/progress/progress.js': `
      export function createJobProgress() { return { element: {}, update() {} }; }`,
    '/texto_off/merged/execution.js': `export function createMergedExecution() { return {}; }`,
    '/texto_off/merged/outcome_columns.js': `export function createOutcomeColumns() { return []; }`,
  });
  const { createMergedLevel2View } = await load('/texto_off/merged/level2.js');
  const rerun = [];
  const view = createMergedLevel2View(() => {}, (chapter) => rerun.push(chapter));
  const rows = [
    { chapter: '1', level2_status: 'pending', selectable: true },
    { chapter: '2', level2_status: 'processed', selectable: false },
    { chapter: '3', level2_status: 'no_change', selectable: false },
    { chapter: '4', level2_status: 'missing_level1', selectable: false },
  ];
  view.update({ status: 'ready', provider: 'comix', manga: 'work', chapters: rows });
  const table = view.element.querySelector('.auto-merge-results').children[0];
  const action = table.columns.find((column) => column.id === 'reprocess');
  assert.equal(action.render(rows[0]), '');
  assert.equal(action.render(rows[3]), '');
  const processed = action.render(rows[1]);
  const unchanged = action.render(rows[2]);
  assert.equal(processed.textContent, 'Reprocessar');
  assert.equal(unchanged.textContent, 'Reprocessar');
  assert.equal(table.columns[0].render(rows[1]).disabled, true);
  processed.click();
  unchanged.click();
  assert.deepEqual(rerun, ['2', '3']);
  view.dispose();
});

test('confirmation distinguishes reprocess from ordinary execution', async () => {
  const state = { confirmations: [], requests: [] };
  const load = browserModules({ testState: state }, {
    '/_app/state/context.js': `
      export function getContext() { return { provider: 'comix', manga: 'work' }; }`,
    '/_app/api/textoff.js': `
      export async function startMergedTextoff(...args) {
        globalThis.testState.requests.push(args);
        return { job: { id: 'job' } };
      }
      export async function waitForTextoffJob() { return []; }`,
    '/_shared/messages/messages.js': `
      export async function confirmMessage(value) {
        globalThis.testState.confirmations.push(value);
        return true;
      }
      export async function showMessage() {}
      export async function showOperationSummary() {}`,
  });
  const { createMergedExecution } = await load('/texto_off/merged/execution.js');
  const flow = createMergedExecution({ level: '2', onStatus() {}, async onComplete() {} });
  await flow.reprocess('1');
  await flow.execute(['2']);
  assert.match(state.confirmations[0].message, /execução anterior.*substituída/);
  assert.equal(state.confirmations[0].confirmText, 'Reprocessar');
  assert.equal(state.requests[0][4], true);
  assert.equal(state.requests[1][4], false);
  flow.dispose();
});

test('API sends reprocess true only for explicit rerun', async () => {
  const requests = [];
  const load = browserModules({
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { ok: true, async json() { return { job: { id: 'job' } }; } };
    },
  });
  const { startMergedTextoff } = await load('/_app/api/textoff.js');
  await startMergedTextoff('comix', 'work', ['1'], '2', true);
  await startMergedTextoff('comix', 'work', ['2'], '2');
  assert.equal(requests[0].url, '/api/textoff/merged/level2/execute');
  assert.deepEqual(JSON.parse(requests[0].options.body), {
    provider: 'comix', manga: 'work', chapters: ['1'], reprocess: true,
  });
  assert.deepEqual(JSON.parse(requests[1].options.body), {
    provider: 'comix', manga: 'work', chapters: ['2'],
  });
});
