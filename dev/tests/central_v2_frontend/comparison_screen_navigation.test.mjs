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
        { id: '1', name: 'page-1.png', version: 'v1', ...(context.layout === 'triptych' ? { level2_status: 'no_change' } : {}) },
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
      export function level2StatusText(status) {
        return status === 'no_change' ? 'Nível II: analisado sem alterações' : status;
      }
      export function comparisonModeConfig(mode) { return ({
        level1: { layout: 'pair', title: 'Auto-Cleaner — Passo 1', heading: 'AUTO-CLEANER · PASSO 1', sides: ['before', 'after'] },
        level2: { layout: 'pair', title: 'Auto-Cleaner — Passo 2', heading: 'AUTO-CLEANER · PASSO 2', sides: ['before', 'after'] },
        before_after: { layout: 'triptych', title: 'Antes & Depois', heading: 'AUDITORIA DE QUALIDADE · ANTES & DEPOIS', sides: ['original', 'level1', 'level2'] },
      })[mode]; }
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
  for (const [mode, step, layout, sides] of [
    ['level1', '1', 'pair', ['before', 'after']],
    ['level2', '2', 'pair', ['before', 'after']],
    ['before_after', '1', 'triptych', ['original', 'level1', 'level2']],
  ]) {
    hooks.sliderCalls = [];
    const screen = createComparisonScreen({ chapter: '1', provider: 'ridi', manga: 'work', step,
      comparisonMode: mode }, () => {});
    await screen.start();
    assert.equal(hooks.requestContext.layout, layout, mode);
    assert.deepEqual(Array.from(hooks.sliderCalls[0][0]), sides.map((side) => `0:${side}`), mode);
    hooks.selectPage(1);
    assert.deepEqual(Array.from(hooks.sliderCalls[1][0]), sides.map((side) => `1:${side}`), mode);
    if (mode === 'before_after') assert.match(hooks.sliderCalls[1][1], /analisado sem alterações/);
    else assert.equal(hooks.sliderCalls[1][1], '');
    screen.dispose();
  }
});
