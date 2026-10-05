import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor() {
    this.nodes = new Map(); this.children = []; this.dataset = {}; this.attrs = {};
    this.style = {}; this.className = ''; this.textContent = ''; this.hidden = false;
    this.classList = {
      add: (name) => { this.className = `${this.className} ${name}`.trim(); },
      toggle: () => {}, contains: (name) => this.className.split(' ').includes(name),
    };
  }
  querySelector(selector) {
    if (!this.nodes.has(selector)) this.nodes.set(selector, new Element());
    return this.nodes.get(selector);
  }
  querySelectorAll() { return []; }
  setAttribute(key, value) { this.attrs[key] = value; }
  removeAttribute(key) { delete this.attrs[key]; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  addEventListener() {}
  removeEventListener() {}
  remove() {}
}

test('Comparar Capítulo composes real catalog facade, state, and page list', async () => {
  const document = { createElement: () => new Element(), body: { append() {} } };
  const fetch = async (url) => ({ ok: true, status: 200, async json() {
    return url.startsWith('/api/textoff/residue-occurrences')
      ? { occurrences: [], cataloged: false }
      : { pages: [{ id: 'page-1', name: 'page-001.png', version: 'v1' }] };
  } });
  const sources = {
    '/_shared/focus_mode/focus_mode.js': 'export function bindFocusMode() { return () => {}; }',
    '/_shared/icons/icons.js': 'export function iconMarkup() { return ""; }',
    '/_shared/messages/messages.js': 'export async function showMessage() {}',
    '/_app/api/comparison.js': `
      export async function fetchComparison() { return { pages: [
        { id: 'page-1', name: 'page-001.png', version: 'v1' },
      ] }; }
      export function comparisonImageUrl(context, page, side) { return page.id + ':' + side; }
    `,
    '/texto_off/comparison/slider.js': `
      export function createSlider(canvas, onState) { return {
        mountAfterOverlay() {}, load() { onState('ready'); }, setMode() {}, zoom() {},
        setInteractionMode() {}, getImageMetrics() { return {}; }, dispose() {},
      }; }
    `,
  };
  const load = browserModules({ document, fetch, AbortController }, sources);
  const { createComparisonScreen } = await load('/texto_off/comparison/screen.js');
  const screen = createComparisonScreen({ provider: 'comix', manga: 'work', chapter: '1', step: '1',
    comparisonMode: 'level1' }, () => {});

  await screen.start();
  await new Promise((resolve) => setImmediate(resolve));

  const pageList = screen.element.querySelector('[data-pages]');
  assert.equal(pageList.children.length, 1);
  assert.equal(pageList.children[0].dataset.pageName, 'page-001.png');
  assert.equal(pageList.children[0].dataset.hasResidueOccurrences, 'false');
  assert.equal(screen.element.querySelector('[data-state]').hidden, true);
  screen.dispose();
});
