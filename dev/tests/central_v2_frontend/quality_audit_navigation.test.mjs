import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

class Element {
  constructor() {
    this.children = []; this.events = new Map(); this.attrs = {};
    this.classList = { add() {}, remove() {}, toggle() {} };
  }
  querySelector(selector) {
    this.nodes ??= new Map();
    if (!this.nodes.has(selector)) this.nodes.set(selector, new Element());
    return this.nodes.get(selector);
  }
  addEventListener(name, fn) { this.events.set(name, fn); }
  removeEventListener(name) { this.events.delete(name); }
  setAttribute(name, value) { this.attrs[name] = value; }
  replaceChildren(...items) { this.children = items; items.forEach((item) => { item.parentElement = this; }); }
  append(item) { this.children.push(item); item.parentElement = this; }
  after(item) { this.afterItem = item; item.parentElement = this.parentElement; }
  remove() { this.removed = true; }
}

test('Antes & Depois menu action resolves through router and opens its comparison screen', async () => {
  let tableColumns, openedContext, started = false;
  const row = { chapter: '1', cleaned: true };
  const sources = {
    '/_app/state/context.js': 'export const getContext = () => ({ provider: "comix", manga: "Gazing at you" }); export const subscribeContext = () => () => {};',
    '/_app/api/textoff.js': 'export const fetchMergedTextoff = async () => ({ provider: "comix", manga: "Gazing at you", chapters: [globalThis.row] });',
    '/texto_off/merged/execution.js': 'export const createMergedExecution = () => ({ execute() {}, dispose() {} });',
    '/_shared/icons/icons.js': 'export const iconMarkup = (name) => name;',
    '/texto_off/comparison/screen.js': 'export const createComparisonScreen = (context) => { setOpenedContext(context); return { element: globalThis.screenElement, start() { setStarted(true); }, dispose() {} }; };',
    '/texto_off/merged/stage_filters.js': 'export const createStageFilters = () => ({ matches: () => true, draw() {}, reset() {} });',
    '/_shared/table/table.js': 'export const createTable = (columns) => { setTableColumns(columns); return globalThis.tableElement; };',
    '/_shared/pagination/model.js': 'export const createPagination = () => ({ select: (rows) => ({ rows }), reset() {}, move() {} });',
    '/_shared/pagination/pagination.js': 'export const createPaginationControls = () => globalThis.paginationElement;',
    '/_shared/progress/progress.js': 'export const createJobProgress = () => ({ element: globalThis.progressElement, update() {} });',
    '/texto_off/merged/columns.js': 'export const createMergedColumns = () => [];',
  };
  const load = browserModules({
    document: { createElement: () => new Element() }, AbortController, row,
    tableElement: new Element(), paginationElement: new Element(), progressElement: new Element(),
    screenElement: new Element(),
    setTableColumns(value) { tableColumns = value; },
    setOpenedContext(value) { openedContext = value; },
    setStarted(value) { started = value; },
  }, sources);
  const { navigation } = await load('/_shell/navigation.js');
  const menu = navigation.find((section) => section.id === 'texto-off');
  const action = menu.groups[3].items.find((item) => item.label === 'Antes & Depois').id;
  const { resolveRoute } = await load('/_app/router/routes.js');
  assert.equal(action, 'texto-off-merged-i');
  assert.equal(resolveRoute(action).module, '/texto_off/merged/level1.js');

  const router = await load('/_app/router/router.js');
  const container = new Element();
  await router.navigate(action, container);
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(tableColumns.some((column) => column.id === 'comparison'));

  const button = tableColumns.find((column) => column.id === 'comparison').render(row);
  assert.equal(button.disabled, false);
  button.events.get('click')();
  assert.equal(JSON.stringify(openedContext), JSON.stringify({ provider: 'comix', manga: 'Gazing at you', chapter: '1', step: '1' }));
  assert.equal(started, true);
});
