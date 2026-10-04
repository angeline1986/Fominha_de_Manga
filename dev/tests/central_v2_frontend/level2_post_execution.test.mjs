import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

class FakeElement {
  constructor(name = 'element') {
    this.name = name;
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.classes = new Set();
    this.classList = {
      toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name),
      contains: (name) => this.classes.has(name),
    };
    this.value = '';
    this.textContent = '';
    this.hidden = false;
    this.disabled = false;
    this.nodes = new Map();
  }

  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name); }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  removeEventListener(name) { this.listeners.delete(name); }
  replaceChildren(...children) { this.children = [...children]; }
  append(...children) { this.children.push(...children); }
  after(node) { this.afterNode = node; }
  querySelector(selector) {
    if (!this.nodes.has(selector)) this.nodes.set(selector, new FakeElement(selector));
    return this.nodes.get(selector);
  }
  async click() { return this.listeners.get('click')?.(); }
  change() { return this.listeners.get('change')?.(); }
}

function chapters(statuses) {
  return Array.from({ length: 31 }, (_, index) => ({
    chapter: String(index + 1),
    selectable: statuses[index + 1] === 'pending',
    level2_status: statuses[index + 1] || 'pending',
  }));
}

function pendingChapters() {
  return chapters({});
}

async function mount({ responses, outcome = 'success' }) {
  const state = {
    responses: [...responses],
    outcome,
    fetchCount: 0,
    contextRefresh: null,
    errors: [],
    summaries: [],
  };
  const document = { createElement: (name) => new FakeElement(name) };
  const load = browserModules({
    document,
    AbortController: class { constructor() { this.signal = {}; } abort() {} },
    testState: state,
  }, {
    '/_app/state/context.js': `
      export function getContext() { return { provider: 'comix', manga: 'Obra teste' }; }
      export function subscribeContext(callback) {
        globalThis.testState.contextRefresh = callback;
        return () => {};
      }
    `,
    '/_app/api/textoff.js': `
      export async function fetchMergedTextoff() {
        globalThis.testState.fetchCount += 1;
        return globalThis.testState.responses.shift();
      }
      export async function startMergedTextoff() { return { job: { id: 'job-1' } }; }
      export async function waitForTextoffJob() {
        if (globalThis.testState.outcome === 'failed') throw new Error('Falha simulada');
        return [{ chapter: '1', status: 'ok', pages: 10, outputs: 8, masks: 10 }];
      }
    `,
    '/_shared/messages/messages.js': `
      export async function confirmMessage() { return true; }
      export async function showMessage(value) { globalThis.testState.errors.push(value); }
      export async function showOperationSummary(value) { globalThis.testState.summaries.push(value); }
    `,
    '/texto_off/comparison/launcher.js': `
      export function createComparisonLauncher() { return { column: {}, dispose() {} }; }
    `,
    '/_shared/table/table.js': `
      export function createTable(columns, rows, caption, options) {
        return { kind: 'table', columns, rows, caption, options };
      }
    `,
    '/_shared/pagination/pagination.js': `
      export function createPaginationControls(selection, onMove) {
        return { kind: 'pagination', selection, move: onMove };
      }
    `,
    '/_shared/progress/progress.js': `
      export function createJobProgress() {
        return { element: globalThis.document.createElement('progress'), update() {} };
      }
    `,
    '/texto_off/merged/outcome_columns.js': `export function createOutcomeColumns() { return []; }`,
  });
  const { render } = await load('/texto_off/merged/level2.js');
  const container = new FakeElement('container');
  const dispose = render(container);
  for (let index = 0; index < 8; index += 1) await Promise.resolve();
  return { state, root: container.children[0], dispose };
}

function filterButton(root, label) {
  return root.querySelector('.auto-merge-filters').children.find((button) => button.textContent.startsWith(label));
}

function table(root) {
  return root.querySelector('.auto-merge-results').children.find((child) => child.kind === 'table');
}

function selectChapter(root, chapter) {
  const row = table(root).rows.find((item) => item.chapter === chapter);
  const checkbox = table(root).columns[0].render(row);
  checkbox.checked = true;
  checkbox.change();
  return checkbox;
}

function pagination(root) {
  return root.querySelector('.auto-merge-results').children.find((child) => child.kind === 'pagination');
}

test('successful Passo 2 completion switches pending to ALL, resets pagination and shows processed/no_change rows', async () => {
  const updated = chapters({ 1: 'processed', 2: 'no_change' });
  const app = await mount({ responses: [
    { status: 'ready', provider: 'comix', manga: 'Obra teste', chapters: pendingChapters() },
    { status: 'ready', provider: 'comix', manga: 'Obra teste', chapters: updated },
  ] });
  const { root, state, dispose } = app;

  assert.equal(filterButton(root, 'Pendente').getAttribute('aria-pressed'), 'true');
  assert.equal(filterButton(root, 'Pendente').textContent, 'Pendente (31)');
  selectChapter(root, '1');
  assert.equal(root.querySelector('[data-execute]').disabled, false);
  pagination(root).move(1);
  assert.equal(pagination(root).selection.page, 2);

  await root.querySelector('[data-execute]').click();

  assert.equal(state.fetchCount, 2, 'successful completion uses one existing reload');
  assert.equal(filterButton(root, 'ALL').getAttribute('aria-pressed'), 'true');
  assert.equal(filterButton(root, 'ALL').textContent, 'ALL (31)');
  assert.equal(pagination(root).selection.page, 1);
  assert.ok(table(root).rows.some((row) => row.chapter === '1' && row.level2_status === 'processed'));
  assert.ok(table(root).rows.some((row) => row.chapter === '2' && row.level2_status === 'no_change'));
  assert.equal(filterButton(root, 'Concluído').textContent, 'Concluído (1)');
  assert.equal(filterButton(root, 'Inalterado').textContent, 'Inalterado (1)');
  assert.equal(root.querySelector('[data-execute]').disabled, true, 'successful completion clears selection');
  dispose();
});

test('failed Passo 2 job does not switch filters or reload as a success', async () => {
  const app = await mount({ responses: [
    { status: 'ready', provider: 'comix', manga: 'Obra teste', chapters: pendingChapters() },
  ], outcome: 'failed' });
  const { root, state, dispose } = app;
  selectChapter(root, '1');
  pagination(root).move(1);

  await root.querySelector('[data-execute]').click();

  assert.equal(state.fetchCount, 1);
  assert.equal(filterButton(root, 'Pendente').getAttribute('aria-pressed'), 'true');
  assert.equal(pagination(root).selection.page, 2);
  assert.equal(state.errors.length, 1);
  dispose();
});

test('ordinary same-manga refresh preserves the filter selected by the user', async () => {
  const initial = chapters({ 1: 'processed', 2: 'no_change' });
  const refreshed = chapters({ 1: 'processed', 2: 'no_change', 3: 'processed' });
  const app = await mount({ responses: [
    { status: 'ready', provider: 'comix', manga: 'Obra teste', chapters: initial },
    { status: 'ready', provider: 'comix', manga: 'Obra teste', chapters: refreshed },
  ] });
  const { root, state, dispose } = app;

  await filterButton(root, 'Concluído').click();
  assert.equal(filterButton(root, 'Concluído').getAttribute('aria-pressed'), 'true');
  await state.contextRefresh();

  assert.equal(state.fetchCount, 2);
  assert.equal(filterButton(root, 'Concluído').getAttribute('aria-pressed'), 'true');
  assert.deepEqual(table(root).rows.map((row) => row.chapter), ['1', '3']);
  assert.equal(filterButton(root, 'ALL').textContent, 'ALL (31)');
  dispose();
});
