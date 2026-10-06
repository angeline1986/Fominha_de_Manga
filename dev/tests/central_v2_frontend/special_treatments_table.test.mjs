import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.events = {}; this.value = '';
    this.classList = { toggle() {}, remove() {}, add() {} };
    if (tag === 'section') this.nodes = Object.fromEntries([
      'query', 'filters', 'results', 'status', 'execute',
    ].map((name) => [`[data-${name}]`, new Element()]));
    if (tag === 'section') this.nodes['.auto-merge-toolbar'] = new Element();
  }
  set innerHTML(value) { this.markup = value; }
  querySelector(selector) { return this.nodes?.[selector]; }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
  after(element) { this.afterElement = element; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, callback) { this.events[name] = callback; }
  removeEventListener(name) { delete this.events[name]; }
  remove() { this.removed = true; }
}

function setup() {
  const calls = [], tables = [], requests = [], progressStates = [], confirmations = [];
  const data = {
    degrade: { treatment: 'degrade', chapters: [{ chapter: '1', pages: ['a.png'], page_count: 1,
      occurrence_count: 2, status: 'pending' }], summary: { chapters: 1, pages: 1, occurrences: 2 } },
    estilizado: { treatment: 'estilizado', chapters: [], summary: { chapters: 0, pages: 0, occurrences: 0 } },
    gradiente_suave: { treatment: 'gradiente_suave', chapters: [{ chapter: '1', pages: ['b.png', 'c.png'],
      page_count: 2, occurrence_count: 11, status: 'processed' }],
    summary: { chapters: 1, pages: 2, occurrences: 11 } },
  };
  const load = browserModules({ document: { createElement: (tag) => new Element(tag) },
    AbortController, calls, tables, data, requests, progressStates, confirmations }, {
    '/_app/state/context.js': `export function getContext() { return {provider:'comix',manga:'Example'}; }
      export function subscribeContext() { return () => {}; }`,
    '/_app/api/textoff.js': `export async function fetchSpecialTreatments(provider,manga,treatment) {
      globalThis.calls.push(treatment); return globalThis.data[treatment]; }
      export async function startSpecialTreatments(...args) {
        globalThis.requests.push(args); return {job:{id:'job'}}; }
      export async function waitForTextoffJob(job, onProgress) {
        onProgress({status:'running',progress:{percent:50,completed:0,total:1,message:'Tratando'}});
        return [{chapter:'1',status:'processed'}]; }`,
    '/_shared/messages/messages.js': `export async function confirmMessage(options) {
        globalThis.confirmations.push(options); return true; }
      export async function showMessage() { return true; }
      export async function showOperationSummary() { return true; }`,
    '/_shared/progress/progress.js': `export function createJobProgress() {
      return {element:{},update(state) { globalThis.progressStates.push(state); }}; }`,
    '/_shared/table/table.js': `export function createTable(columns, rows, label, options) {
      globalThis.tables.push({columns,rows,label,options}); return {tag:'table'}; }`,
  });
  return { load, calls, tables, requests, progressStates, confirmations, data };
}

test('three routes reuse one table; only selected Degradê can execute', async () => {
  const { load, calls, tables } = setup();
  for (const [level, treatment, count, pages] of [
    ['6', 'degrade', 2, 1], ['7', 'estilizado', 0, 0], ['8', 'gradiente_suave', 11, 2],
  ]) {
    const { render } = await load(`/texto_off/especiais/level${level}.js`);
    const container = new Element();
    const dispose = render(container);
    await new Promise((resolve) => setImmediate(resolve));
    const root = container.children[0];
    const table = tables.at(-1);
    assert.equal(calls.at(-1), treatment);
    assert.match(root.className, /cleaner-overview sommelier-page/);
    assert.equal(table.rows.length, count ? 1 : 0);
    if (count) {
      assert.equal(table.rows[0].page_count, pages);
      assert.equal(table.rows[0].occurrence_count, count);
    }
    assert.match(root.markup, /data-execute disabled/);
    assert.doesNotMatch(root.markup, /data-summary/);
    const footer = root.nodes['[data-results]'].children.at(-1);
    const sizeLabel = footer.children[0];
    const size = sizeLabel.children[0];
    assert.equal(footer.className, 'pagination');
    assert.equal(sizeLabel.textContent, 'Exibir:');
    assert.deepEqual(size.children.map((item) => item.value),
      ['15', '20', '30', '40', '50']);
    assert.equal(size.value, '15');
    if (count) {
      assert.equal(footer.children[1].children[0].textContent, '<<');
      assert.equal(footer.children[1].children[1].textContent, '1 / 1');
      assert.equal(footer.children[1].children[2].textContent, '>>');
      assert.equal(footer.children[1].children[0].disabled, true);
      assert.equal(footer.children[1].children[2].disabled, true);
    } else assert.equal(footer.children.length, 1);
    assert.equal(table.columns.map((column) => column.label).join('|'),
      '|Capítulo|PÁGINAS|OCORRÊNCIAS|STATUS|REVISAR');
    if (count) {
      const review = table.columns.at(-1).render(table.rows[0]);
      assert.equal(review.disabled, true);
      assert.match(review.markup, /ui-icon--eye/);
      assert.equal(review.events.click, undefined);
      const checkbox = table.columns[0].render(table.rows[0]);
      checkbox.checked = true; checkbox.events.change();
      assert.equal(root.nodes['[data-execute]'].disabled, treatment !== 'degrade');
      root.nodes['[data-query]'].value = table.rows[0].chapter;
      root.nodes['[data-query]'].events.input();
      assert.equal(tables.at(-1).columns[0].render(tables.at(-1).rows[0]).checked, true);
    } else assert.equal(table.options.emptyMessage, 'Nenhum tratamento artístico pendente.');
    dispose();
  }
});

test('Degradê submits chapter intent once and reloads after completion', async () => {
  const { load, tables, requests, calls } = setup();
  const { render } = await load('/texto_off/especiais/level6.js');
  const container = new Element();
  const dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const root = container.children[0];
  const checkbox = tables.at(-1).columns[0].render(tables.at(-1).rows[0]);
  checkbox.checked = true; checkbox.events.change();
  const execute = root.nodes['[data-execute]'];
  execute.events.click(); execute.events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests.length, 1);
  assert.equal(JSON.stringify(requests[0]), JSON.stringify(['comix', 'Example', 'degrade', ['1'], false]));
  assert.equal(calls.length, 2);
  assert.ok(root.nodes['.auto-merge-toolbar'].afterElement);
  assert.ok(requests.length && requests[0][4] === false);
  assert.equal(execute.disabled, true);
  dispose();
});

test('failed Degradê is selectable and sends explicit retry with progress', async () => {
  const { load, data, tables, requests, progressStates, confirmations } = setup();
  data.degrade.chapters[0].status = 'failed';
  const { render } = await load('/texto_off/especiais/level6.js');
  const container = new Element();
  const dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const root = container.children[0];
  const checkbox = tables.at(-1).columns[0].render(tables.at(-1).rows[0]);
  assert.equal(checkbox.disabled, false);
  checkbox.checked = true; checkbox.events.change();
  const execute = root.nodes['[data-execute]'];
  assert.equal(execute.textContent, 'Tentar novamente');
  execute.events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests[0][4], true);
  assert.match(confirmations[0].message, /Tentar novamente/);
  assert.ok(progressStates.some((state) => state.busy && state.percent === 50));
  assert.equal(progressStates.at(-1).busy, false);
  dispose();
});

test('search by page and status filters restrict chapter rows', async () => {
  const { load, tables } = setup();
  const { renderSpecialTable, matchesSpecialRow } = await load('/texto_off/especiais/table.js');
  assert.equal(matchesSpecialRow({ chapter: '1', pages: ['a.png'], status: 'pending' }, 'a.png', 'pending'), true);
  assert.equal(matchesSpecialRow({ chapter: '1', pages: ['a.png'], status: 'failed' }, '', 'completed'), false);
  const container = new Element();
  const dispose = renderSpecialTable(container, 'gradiente_suave');
  await new Promise((resolve) => setImmediate(resolve));
  const root = container.children[0];
  const query = root.nodes['[data-query]'];
  query.value = 'missing.png'; query.events.input();
  assert.equal(tables.at(-1).rows.length, 0);
  query.value = 'b.png'; query.events.input();
  assert.equal(tables.at(-1).rows.length, 1);
  const buttons = root.nodes['[data-filters]'].children;
  buttons[1].events.click();
  assert.equal(tables.at(-1).rows.length, 0);
  root.nodes['[data-filters]'].children[2].events.click();
  assert.equal(tables.at(-1).rows.length, 1);
  const size = root.nodes['[data-results]'].children.at(-1).children[0].children[0];
  size.value = '20'; size.events.change();
  assert.equal(size.value, '20');
  dispose();
});

test('shared pagination keeps its original contract on other pages', async () => {
  const { load } = setup();
  const { createPaginationControls } = await load('/_shared/pagination/pagination.js');
  const footer = createPaginationControls({ page: 1, pages: 5, start: 1, end: 15, total: 65 }, () => {});
  assert.equal(footer.children[0].textContent, '1–15 de 65');
  assert.equal(footer.children[1].children[1].textContent, '1 / 5');
  assert.equal(footer.children[1].children[0].textContent, '<<');
});

test('pagination keeps previous and next disabled at the page boundaries', async () => {
  const { load } = setup();
  const { createPaginationControls } = await load('/_shared/pagination/pagination.js');
  for (const [page, pages, previous, next] of [
    [1, 5, true, false], [3, 5, false, false], [5, 5, false, true], [1, 1, true, true],
  ]) {
    const footer = createPaginationControls({ page, pages, start: 1, end: 15, total: 65 }, () => {});
    const actions = footer.children[1].children;
    assert.equal(actions[0].disabled, previous);
    assert.equal(actions[1].textContent, `${page} / ${pages}`);
    assert.equal(actions[2].disabled, next);
  }
});
