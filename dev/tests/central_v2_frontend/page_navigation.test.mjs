import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Control {
  constructor() { this.children = []; this.events = {}; this.value = ''; this.disabled = false; }
  append(child) { this.children.push(child); }
  replaceChildren() { this.children = []; }
  addEventListener(name, handler) { this.events[name] = handler; }
  change(value) { this.value = value; this.events.change?.(); }
}

test('shared selectors keep eligible chapters and pages synchronized', async () => {
  const chapter = new Control(), page = new Control();
  const root = { querySelector: (selector) => selector === '[data-check-chapter]' ? chapter : page };
  const events = [];
  const load = browserModules({ document: { createElement: () => new Control() } });
  const { pageNavigationMarkup, createPageNavigation } = await load('/texto_off/comparison/page_navigation.js');
  assert.match(pageNavigationMarkup(true), /data-check-chapter[^]*data-check-page[^]*data-search/);
  const navigation = createPageNavigation(root, { chapter: '2', chapters: [{ chapter: '2' }, { chapter: '4' }],
    onChapterChange: (value) => events.push(['chapter', value]),
    onPageChange: (value) => events.push(['page', value]) });
  assert.deepEqual(chapter.children.map((option) => option.value), ['2', '4']);
  assert.equal(chapter.value, '2');
  chapter.change('2');
  chapter.change('4');
  navigation.setPages([{ name: 'page-001-005.png' }, { name: 'page-005-009.png' }]);
  assert.deepEqual(page.children.map((option) => option.textContent), ['Pág. 001-005', 'Pág. 005-009']);
  page.change('1');
  navigation.selectPage(0);
  assert.equal(page.value, '0');
  navigation.setChapterBlocked(true);
  assert.equal(chapter.disabled, true);
  navigation.setPages([]);
  assert.equal(page.disabled, true);
  assert.deepEqual(events, [['chapter', '4'], ['page', 1]]);
});
