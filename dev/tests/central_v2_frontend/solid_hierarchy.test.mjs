import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.events = {}; this.className = '';
    this.classList = { add: (value) => { this.className += ` ${value}`; } };
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, callback) { this.events[name] = callback; }
}

function tableSetup() {
  const tables = [], inspections = [], reruns = [], selections = [], sizeChanges = [];
  const sources = {
    '/_shared/icons/icons.js': `export function iconMarkup(name) { return name; }`,
    '/_shared/table/table.js': `export function createTable(columns, rows, label, options) {
      globalThis.tables.push({ columns, rows, label, options });
      return { classList: { add() {} } };
    }`,
    '/_shared/pagination/model.js': `export function createPagination(size = 13) {
      let page = 1, pages = 1;
      return { reset() { page = 1; }, move(delta) { page += delta; }, select(rows) {
        pages = Math.max(1, Math.ceil(rows.length / size)); page = Math.min(page, pages);
        const start = (page - 1) * size;
        return { rows: rows.slice(start, start + size), start: start + 1,
          end: Math.min(start + size, rows.length), total: rows.length, page, pages };
      } };
    }`,
    '/_shared/pagination/pagination.js': `export function createPageSizeControl(onChange) {
      globalThis.sizeChanges.push(onChange); return { element: {} };
    }
      export function createPaginationControls() { return {}; }`,
  };
  const load = browserModules({ document: { createElement: (tag) => new Element(tag) },
    tables, sizeChanges, AbortController }, sources);
  return { load, tables, inspections, reruns, selections, sizeChanges };
}

test('Sólidos expands chapter and page, keeps area rows informational, and exposes supported page actions', async () => {
  const harness = tableSetup(), { createSolidTable } = await harness.load('/texto_off/solidos/table.js');
  const area = { id: 'solid-001', label: 'Branco sólido' };
  const page = { name: 'page-001-006.png', regions: 1, processed: true, outdated: true,
    result_sha256: 'a'.repeat(64),
    areas: [area], areasState: 'ready' };
  const chapter = { chapter: '7', regions: 1, processed: true, pages: [page] };
  let table;
  const redraw = () => table.draw([chapter], new Set(), 0, false);
  table = createSolidTable(new Element(), {
    onSelect: (...args) => harness.selections.push(args), onSelectPage() {},
    inspect: (row) => harness.inspections.push(row), reexecutePage: (row) => harness.reruns.push(row),
    changePage() {}, redraw,
    loadAreas(row) { page.areasState = 'ready'; row.areasState = 'ready'; redraw(); },
  });
  redraw();
  assert.deepEqual(harness.tables.at(-1).rows.map((row) => row.rowType), ['chapter']);
  harness.tables.at(-1).columns[1].render(chapter).children[0].events.click();
  assert.deepEqual(harness.tables.at(-1).rows.map((row) => row.rowType), ['chapter', 'page']);
  const pageRow = harness.tables.at(-1).rows[1];
  assert.equal(harness.tables.at(-1).columns[2].render(pageRow).children[1].textContent, 'Pendente');
  assert.equal(harness.tables.at(-1).columns[3].render(pageRow).children[1].textContent, '1/1');
  harness.tables.at(-1).columns[1].render(pageRow).children[1].events.click();
  const rows = harness.tables.at(-1).rows;
  assert.deepEqual(rows.map((row) => row.rowType), ['chapter', 'page', 'area']);
  const areaRow = rows[2];
  assert.equal(harness.tables.at(-1).columns[0].render(areaRow), '');
  assert.equal(harness.tables.at(-1).columns[2].render(areaRow), '—');
  assert.equal(harness.tables.at(-1).columns[3].render(areaRow), '—');
  assert.equal(harness.tables.at(-1).columns[4].render(areaRow), '—');
  const actions = harness.tables.at(-1).columns[4].render(pageRow).children;
  assert.equal(actions.length, 2);
  actions[0].events.click(); actions[1].events.click();
  assert.equal(harness.inspections[0].rowType, 'page');
  assert.equal(harness.reruns[0].name, page.name);
  const expandedPage = harness.tables.at(-1).rows[1];
  harness.tables.at(-1).columns[1].render(expandedPage).children[1].events.click();
  assert.deepEqual(harness.tables.at(-1).rows.map((row) => row.rowType), ['chapter', 'page']);
  harness.tables.at(-1).columns[1].render(harness.tables.at(-1).rows[0]).children[0].events.click();
  assert.deepEqual(harness.tables.at(-1).rows.map((row) => row.rowType), ['chapter']);
});

test('Sólidos loads real Check areas through the existing read API and excludes other classifications', async () => {
  const calls = [], rows = [{ chapter: '7', pages: [{ name: 'page-001-006.png' }] }];
  const load = browserModules({ AbortController, calls, rows }, {
    '/_app/api/residue_occurrences.js': `export async function fetchResidueOccurrences(context) {
      globalThis.calls.push(context); return { occurrences: [
        { id: 'solid-001', tipo: 'residuo_balao_solido_branco', label: 'Branco sólido' },
        { id: 'other-001', tipo: 'residuo_degrade', label: 'Degradê' },
      ] };
    }`,
  });
  const { createSolidAreaLoader } = await load('/texto_off/solidos/area_loader.js');
  const page = rows[0].pages[0];
  const loader = createSolidAreaLoader(() => ({ provider: 'comix', manga: 'Obra' }), () => rows, () => {});
  await loader.load({ ...page, chapter: '7' });
  assert.equal(calls[0].scope, 'check'); assert.equal(calls[0].step, '1');
  assert.equal(JSON.stringify(page.areas), JSON.stringify([
    { id: 'solid-001', number: undefined, label: 'Branco sólido' },
  ]));
  assert.equal(page.areasState, 'ready');
  loader.dispose();
});

test('search finds pages, narrows their expanded list, and keeps chapter-based filters', async () => {
  const load = browserModules({}, {});
  const { filterSolidChapters } = await load('/texto_off/solidos/filter.js');
  const rows = [
    { chapter: '7', processed: true, pages: [{ name: 'page-001-006.png' }, { name: 'page-006-014.png' }] },
    { chapter: '8', processed: false, pages: [{ name: 'page-014-021.png' }] },
  ];
  const pageMatch = filterSolidChapters(rows, 'page-006', 'all');
  assert.equal(pageMatch.length, 1);
  assert.deepEqual(pageMatch[0].displayPages.map((row) => row.name), ['page-006-014.png']);
  assert.equal(filterSolidChapters(rows, '', 'pending')[0].chapter, '8');
  assert.equal(filterSolidChapters(rows, '', 'processed')[0].chapter, '7');
});

test('chapter pagination keeps expansions and page-size changes preserve the selected chapter', async () => {
  const harness = tableSetup(), { createSolidTable } = await harness.load('/texto_off/solidos/table.js');
  const chapters = Array.from({ length: 14 }, (_, index) => ({ chapter: String(index + 1),
    regions: 1, processed: true, pages: [{ name: `page-${index}.png`, regions: 1,
      processed: true, result_sha256: 'b'.repeat(64), areasState: 'ready', areas: [] }] }));
  let table, currentPage = 0;
  const selected = new Set(['1']); chapters[0].processed = false;
  const draw = () => table.draw(chapters, selected, currentPage, false);
  table = createSolidTable(new Element(), { onSelect() {}, onSelectPage() {}, inspect() {},
    reexecutePage() {}, loadAreas() {}, changePage(next) { currentPage = next; draw(); }, redraw: draw });
  draw();
  const firstChapter = harness.tables.at(-1).rows[0];
  harness.tables.at(-1).columns[1].render(firstChapter).children[0].events.click();
  assert.equal(harness.tables.at(-1).rows.some((row) => row.rowType === 'page'), true);
  harness.sizeChanges[0](20);
  assert.equal(harness.tables.at(-1).rows.length, 15);
  assert.equal(harness.tables.at(-1).rows[1].rowType, 'page');
  assert.equal(harness.tables.at(-1).columns[0].render(harness.tables.at(-1).rows[0]).checked, true);
});

test('page visualization opens the existing comparison viewer on that page', async () => {
  const contexts = [];
  const loaded = browserModules({ contexts, document: { activeElement: null,
    createElement: (tag) => new Element(tag) } }, {
    '/texto_off/comparison/screen.js': `export function createComparisonScreen(context) {
      globalThis.contexts.push(context); return { element: { querySelector() {
        return { prepend() {} };
      }, remove() {} }, start() {}, dispose() {} };
    }`,
    '/_shared/icons/icons.js': `export function iconMarkup() { return ''; }`,
  });
  const { createSolidInspector } = await loaded('/texto_off/solidos/inspector.js');
  const root = new Element(); root.parentElement = { scrollTop: 0 };
  root.classList = { add() {}, remove() {} }; root.after = () => {};
  const inspector = createSolidInspector(root);
  inspector.open({ chapter: '7', name: 'page-001-006.png', rowType: 'page' },
    { provider: 'comix', manga: 'Obra' });
  assert.equal(contexts[0].initialPage, 'page-001-006.png');
  assert.equal(contexts[0].chapter, '7');
  inspector.dispose();
});
