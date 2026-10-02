import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor() {
    this.children = []; this.dataset = {}; this.attrs = {}; this.events = new Map(); this.className = '';
    this.classList = { toggle() {} };
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  setAttribute(name, value) { this.attrs[name] = value; }
  removeAttribute(name) { delete this.attrs[name]; }
  addEventListener(name, handler) { this.events.set(name, handler); }
  removeEventListener(name) { this.events.delete(name); }
  querySelectorAll() { return this.children; }
}

test('persisted counts render/update the page dot and zero removes it without changing selection', async () => {
  const document = { createElement: () => new Element() };
  const sources = {
    '/_shared/pagination/model.js': `
      export function createPagination() { return { select(pages) { return {
        rows: pages.map((page, originalIndex) => ({ page, originalIndex })),
        start: pages.length ? 1 : 0, end: pages.length, total: pages.length, page: 1, pages: 1,
      }; }, move() {}, reset() {} }; }
    `,
    '/texto_off/comparison/model.js': `
      export const COMPARISON_PAGE_SIZE = 20;
      export function filterComparisonPages(pages) { return pages; }
    `,
  };
  const load = browserModules({ document }, sources);
  const { createPageList } = await load('/texto_off/comparison/page_list.js');
  const list = new Element(), search = new Element(), paginationRoot = new Element(); search.value = '';
  const pageList = createPageList({ list, search, paginationRoot, onSelect() {}, onPreview() {}, onPreviewPosition() {} });
  const pages = [
    { id: '0', name: 'page-empty.png', residue_occurrence_count: 0 },
    { id: '1', name: 'page-cataloged.png', residue_occurrence_count: 3 },
  ];
  pageList.render(pages, 1);
  const [empty, cataloged] = list.children;
  assert.equal(empty.dataset.hasResidueOccurrences, 'false');
  assert.equal(empty.attrs.title, undefined);
  assert.equal(cataloged.dataset.hasResidueOccurrences, 'true');
  assert.equal(cataloged.title, 'Possui resíduo catalogado');
  assert.equal(cataloged.attrs['aria-selected'], 'true');

  pageList.setOccurrenceCount('page-cataloged.png', 0);
  assert.equal(pages[1].residue_occurrence_count, 0);
  assert.equal(cataloged.dataset.hasResidueOccurrences, 'false');
  assert.equal(cataloged.attrs.title, undefined);
  pageList.setOccurrenceCount('page-empty.png', 1);
  assert.equal(empty.dataset.hasResidueOccurrences, 'true');
  assert.equal(empty.title, 'Possui resíduo catalogado');
  pageList.dispose();
});
