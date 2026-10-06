import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.events = {}; this.value = ''; this.isConnected = true;
    const classes = new Set();
    this.classList = { add: (name) => classes.add(name), remove: (name) => classes.delete(name),
      contains: (name) => classes.has(name), toggle() {} };
    if (tag === 'section') this.nodes = Object.fromEntries(
      ['query', 'filters', 'results', 'status', 'execute'].map((name) => [`[data-${name}]`, new Element()]));
    if (tag === 'section') this.nodes['.auto-merge-toolbar'] = new Element();
  }
  set innerHTML(value) { this.markup = value; }
  querySelector(selector) { return this.nodes?.[selector]; }
  replaceChildren(...children) { this.children = children; children.forEach((child) => { child.parentElement = this; }); }
  append(...children) { this.children.push(...children); }
  prepend(...children) { this.children.unshift(...children); }
  after(element) { this.afterElement = element; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, callback) { this.events[name] = callback; }
  removeEventListener(name) { delete this.events[name]; }
  remove() { this.removed = true; }
  focus() { this.focused = true; }
}

function setup() {
  const tables = [], screens = [];
  const data = { treatment: 'degrade', chapters: [{ chapter: '1', pages: ['page.png'],
    page_count: 1, occurrence_count: 2, status: 'processed', review_available: true }],
  summary: { chapters: 1, pages: 1, occurrences: 2 } };
  const load = browserModules({ document: { createElement: (tag) => new Element(tag) },
    AbortController, tables, screens, data }, {
    '/_app/state/context.js': `export function getContext() { return {provider:'comix',manga:'Example'}; }
      export function subscribeContext() { return () => {}; }`,
    '/_app/api/textoff.js': `export async function fetchSpecialTreatments() { return globalThis.data; }
      export async function startSpecialTreatments() { throw new Error('no processing'); }
      export async function waitForTextoffJob() { throw new Error('no processing'); }`,
    '/_shared/table/table.js': `export function createTable(columns,rows) {
      globalThis.tables.push({columns,rows}); return {tag:'table'}; }`,
    '/_shared/progress/progress.js': `export function createJobProgress() {
      return {element:{},update(){}}; }`,
    '/_shared/messages/messages.js': `export async function confirmMessage() { return false; }
      export async function showMessage() {} export async function showOperationSummary() {}`,
    '/texto_off/comparison/screen.js': `export function createComparisonScreen(context,onBack) {
      const element = globalThis.document.createElement('article');
      element.nodes = {'.comparison-page-heading':globalThis.document.createElement('header')};
      const screen = {context,element,start(){screen.started=true;},dispose(){screen.disposed=true;},onBack};
      globalThis.screens.push(screen); return screen; }`,
  });
  return { load, tables, screens, data };
}

test('only valid processed or no_change Degradê enables the eye', async () => {
  const { load, tables, data } = setup();
  const { render } = await load('/texto_off/especiais/level6.js');
  for (const [status, available, expected] of [
    ['processed', true, false], ['no_change', true, false], ['pending', true, true],
    ['failed', true, true], ['processed', false, true], ['no_change', false, true],
  ]) {
    data.chapters[0].status = status; data.chapters[0].review_available = available;
    const dispose = render(new Element());
    await new Promise((resolve) => setImmediate(resolve));
    const table = tables.at(-1);
    assert.equal(table.columns.at(-1).render(table.rows[0]).disabled, expected, status);
    dispose();
  }
});

test('eye opens the shared comparator and Back restores Degradê', async () => {
  const { load, tables, screens } = setup();
  const { render } = await load('/texto_off/especiais/level6.js');
  const container = new Element();
  const dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const root = container.children[0];
  const eye = tables.at(-1).columns.at(-1).render(tables.at(-1).rows[0]);
  eye.events.click();
  assert.equal(screens[0].context.comparisonMode, 'degrade');
  assert.equal(screens[0].context.scope, 'degrade');
  assert.equal(screens[0].started, true);
  assert.equal(root.classList.contains('comparison-origin-hidden'), true);
  const back = screens[0].element.querySelector('.comparison-page-heading').children[0];
  back.events.click();
  assert.equal(root.classList.contains('comparison-origin-hidden'), false);
  assert.equal(screens[0].disposed, true);
  dispose();
});
