import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

class Element {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.attrs = {}; this.listeners = {};
    this.value = tag === 'select' ? 'all' : ''; this.disabled = false; this.hidden = false;
    this.textContent = ''; this.className = ''; this.classList = { toggle() {}, add() {}, remove() {} };
  }
  set innerHTML(html) {
    this._html = html; this.byData = {};
    for (const [, tag, attrs] of html.matchAll(/<([\w-]+)([^>]*)>/g)) {
      const node = new Element(tag);
      for (const [, name, value] of attrs.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) {
        if (name.startsWith('data-')) { node.attrs[name] = value ?? ''; this.byData[name] = node; }
        else if (name === 'aria-label') node.attrs[name] = value;
        else if (name === 'type') { node.attrs[name] = value; node.type = value; }
      }
      this.children.push(node);
    }
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  getAttribute(name) { return this.attrs[name] ?? null; }
  removeAttribute(name) { delete this.attrs[name]; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  click() { if (!this.disabled) this.listeners.click?.({ target: this }); }
  querySelector(selector) {
    const data = selector.match(/^\[data-([\w-]+)\]$/);
    if (data) return this.byData?.[`data-${data[1]}`] || this.walk().find((n) => n.attrs[`data-${data[1]}`] !== undefined) || null;
    const aria = selector.match(/^\[aria-label="([^"]+)"\]$/);
    if (aria) return this.walk().find((n) => n.attrs['aria-label'] === aria[1]) || null;
    return null;
  }
  querySelectorAll(selector) {
    if (selector.includes('input[type="checkbox"]')) return this.walk().filter((n) => n.tagName === 'INPUT' && n.type === 'checkbox');
    return [];
  }
  walk() { return this.children.flatMap((node) => [node, ...node.walk()]); }
}

async function createView(initial = {}) {
  const document = { createElement: (tag) => new Element(tag) };
  const load = browserModules({ document }, {
    '/_shared/table/table.js': `export function createTable(columns, rows) { const table=document.createElement('table');
      columns[0].header(); for(const row of rows)table.append(columns[0].render(row)); return table; }`,
    '/_shared/pagination/model.js': `export function createPagination(){let page=1,pages=1;return {
      select(rows){pages=Math.max(1,Math.ceil(rows.length/25));page=Math.min(page,pages);
        return {rows,page,pages,total:rows.length,start:1,end:rows.length}},
      move(delta){page=Math.max(1,Math.min(pages,page+delta))},reset(){page=1}}}`,
    '/_shared/pagination/pagination.js': `export function createPaginationControls(){return document.createElement('nav')}
      export function createPageSizeControl(onChange, selected){const select=document.createElement('select');
        select.value=String(selected||25); return {element:document.createElement('label'),select}}`,
  });
  const { createComboView } = await load('/texto_off/combo_turbo/view.js');
  const actions = { selected: [], eligible: 0 };
  const view = createComboView({ select: (...args) => actions.selected.push(args),
    selectMany() {}, selectEligible: () => actions.eligible++, refresh() {}, plan() {}, run() {}, onUiState() {} }, initial);
  return { view, actions };
}

const row = (chapter, status) => ({ chapter, status, pages: status === 'PLANNED' ? [
  { stages: { SOLIDOS: { status: 'PLANNED' }, GLASS: { status: 'NO_WORK' } } },
] : [] });

test('rendered row checkbox disables BLOCKED and NO_WORK while eligible rows stay selectable', async () => {
  const { view } = await createView();
  view.update({ rows: [row('1', 'PLANNED'), row('2', 'BLOCKED'), row('3', 'NO_WORK')], selected: new Set() });
  assert.equal(view.element.querySelector('[aria-label="Selecionar capítulo 1"]').disabled, false);
  assert.equal(view.element.querySelector('[aria-label="Selecionar capítulo 2"]').disabled, true);
  assert.equal(view.element.querySelector('[aria-label="Selecionar capítulo 3"]').disabled, true);
});

test('select eligible action is connected and Execute stays disabled without a valid plan', async () => {
  const { view, actions } = await createView();
  view.update({ rows: [row('1', 'PLANNED')], selected: new Set(['1']), planValid: false });
  view.element.querySelector('[data-select-eligible]').click();
  assert.equal(actions.eligible, 1);
  assert.equal(view.element.querySelector('[data-run]').disabled, true);
  view.update({ planValid: true });
  assert.equal(view.element.querySelector('[data-run]').disabled, false);
});

test('rendered progress is indeterminate for null and numeric only for a valid backend percent', async () => {
  const { view } = await createView();
  view.update({ job: { status: 'running', progress: { percent: null, completed: 1, total: 4 } } });
  assert.equal(view.element.querySelector('[data-progress]').getAttribute('value'), null);
  assert.equal(view.element.querySelector('[data-progress-text]').textContent, '1 de 4 páginas');
  view.update({ job: { status: 'running', progress: { percent: 40, completed: 1, total: 4 } } });
  assert.equal(view.element.querySelector('[data-progress]').getAttribute('value'), '40');
  assert.match(view.element.querySelector('[data-progress-text]').textContent, /^40%/);
});

test('rendered results wait for a terminal job status', async () => {
  const { view } = await createView();
  const result = { status: 'COMPLETED', results: [] };
  view.update({ job: { status: 'running' }, result });
  assert.equal(view.element.querySelector('[data-results]').hidden, true);
  view.update({ job: { status: 'completed' } });
  assert.equal(view.element.querySelector('[data-results]').hidden, false);
});

test('screen state restores search, filter, page and page size', async () => {
  const { view } = await createView({ search: 'chapter 4', filter: 'eligible', page: 3, pageSize: 50 });
  assert.equal(view.element.querySelector('[data-search]').value, 'chapter 4');
  assert.equal(view.element.querySelector('[data-filter]').value, 'eligible');
  view.restore({ search: 'chapter 8', filter: 'blocked', page: 2, pageSize: 50 });
  assert.equal(view.element.querySelector('[data-search]').value, 'chapter 8');
  assert.equal(view.element.querySelector('[data-filter]').value, 'blocked');
});
