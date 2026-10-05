import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor() {
    this.nodes = new Map(); this.attrs = {}; this.events = new Map(); this.style = {};
    this.className = ''; this.textContent = ''; this.hidden = false;
    this.classList = {
      add: (name) => { this.className = `${this.className} ${name}`.trim(); },
      toggle: () => {},
      contains: () => false,
    };
  }
  querySelector(selector) {
    if (!this.nodes.has(selector)) this.nodes.set(selector, new Element());
    return this.nodes.get(selector);
  }
  querySelectorAll() { return []; }
  setAttribute(key, value) { this.attrs[key] = value; }
  removeAttribute(key) { delete this.attrs[key]; }
  append() {}
  addEventListener(key, handler) { this.events.set(key, handler); }
  removeEventListener(key) { this.events.delete(key); }
  remove() {}
}

test('comparison initially loads, loads another page, and ignores selecting the current page', async () => {
  const hooks = {};
  const sources = {
    '/_shared/focus_mode/focus_mode.js': 'export function bindFocusMode() { return () => {}; }',
    '/_shared/icons/icons.js': 'export function iconMarkup() { return ""; }',
    '/_app/api/comparison.js': `
      export async function fetchComparison(context) { globalThis.testHooks.requestContext = context; return { pages: [
        { id: '0', name: 'page-0.png', version: 'v0' },
        { id: '1', name: 'page-1.png', version: 'v1', level2_status: 'no_change' },
      ] }; }
      export function comparisonImageUrl(context, page, side) { return page.id + ':' + side; }
    `,
    '/texto_off/comparison/slider.js': `
      export function createSlider(canvas, onState) {
        const calls = [];
        globalThis.testHooks.sliderCalls = calls;
        return { load(images, status) { calls.push([images, status]); onState('loading'); onState('ready'); },
          zoom() {}, getImageMetrics() { return {}; }, dispose() {} };
      }
    `,
    '/texto_off/comparison/model.js': `
      export const INITIAL_ZOOM = 40;
      export function clampZoom(value) { return value; }
    `,
    '/texto_off/comparison/page_list.js': `
      export function createPageList({ onSelect }) {
        globalThis.testHooks.selectPage = onSelect;
        return { render() {}, dispose() {} };
      }
    `,
    '/texto_off/comparison/residue_catalog.js': `
      export function createResidueCatalog() {
        return { element: {}, setPage() {}, setOpen() {}, toggle() {}, dispose() {} };
      }
    `,
  };
  const globals = { testHooks: hooks, AbortController,
    document: { createElement: () => new Element(), body: { append() {} } } };
  const load = browserModules(globals, sources);
  const { createComparisonScreen } = await load('/texto_off/comparison/screen.js');
  const screen = createComparisonScreen({ chapter: '1', provider: 'ridi', manga: 'work', step: '1' }, () => {});

  await screen.start();
  assert.equal(JSON.stringify(hooks.sliderCalls[0][0]), JSON.stringify(['0:original', '0:level1', '0:level2']));
  assert.equal(hooks.requestContext.layout, 'triptych');
  hooks.selectPage(0);
  assert.equal(hooks.sliderCalls.length, 1);
  hooks.selectPage(1);
  assert.equal(JSON.stringify(hooks.sliderCalls[1][0]), JSON.stringify(['1:original', '1:level1', '1:level2']));
  assert.match(hooks.sliderCalls[1][1], /analisado sem alterações/);
  hooks.selectPage(1);
  assert.equal(hooks.sliderCalls.length, 2);
  screen.dispose();
});
