import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.events = {}; this.children = [];
    this.classList = { add() {}, toggle() {}, contains() { return false; } };
    if (tag === 'aside') this.nodes = {
      '[data-layers]': new Element(), '[data-count]': new Element(),
    };
  }
  set innerHTML(value) { this.markup = value; }
  querySelector(selector) { return this.nodes?.[selector]; }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, callback) { this.events[name] = callback; }
  removeEventListener(name) { delete this.events[name]; }
  replaceChildren(...children) { this.children = children; }
  remove() { this.removed = true; }
}

test('Degradê reuses read-only ROI overlay and comparison visual contract', async () => {
  const rendered = [], overlays = [];
  const load = browserModules({ document: { createElement: (tag) => new Element(tag) },
    rendered, overlays }, {
    '/_shared/icons/icons.js': `export function iconMarkup() { return '<svg></svg>'; }`,
    '/texto_off/comparison/residue_catalog_view.js': `export function renderResidueOccurrences(
      overlay, layers, occurrences, options, flags) {
      globalThis.rendered.push({occurrences,flags}); }`,
  });
  const { createDegradeContext } = await load('/texto_off/comparison/degrade_context.js');
  const { comparisonModeConfig, INITIAL_ZOOM, TRIPTYCH_PANEL_GAP } =
    await load('/texto_off/comparison/model.js');
  const slider = { mountAfterOverlay: (overlay) => overlays.push(overlay),
    getImageMetrics: () => ({ naturalWidth: 940, naturalHeight: 6572 }) };
  const context = createDegradeContext({ workspace: new Element(), slider });
  context.setPages([{ name: 'page-050-057.png', occurrence_ids: ['one', 'two'],
    rois: [{ x: 113, y: 3378, width: 447, height: 355 },
      { x: 453, y: 3763, width: 355, height: 283 }] }]);
  context.setPage('page-050-057.png');
  assert.equal(overlays.length, 1);
  assert.equal(rendered[0].occurrences.length, 2);
  assert.equal(rendered[0].flags.readOnly, true);
  assert.equal(rendered[0].occurrences[0].box.left, 113 / 940);
  assert.equal(rendered[0].occurrences[1].box.top, 3763 / 6572);
  assert.equal(context.element.querySelector('[data-count]').value, '2');
  assert.equal(INITIAL_ZOOM, 40);
  assert.equal(TRIPTYCH_PANEL_GAP, 18);
  assert.deepEqual([...comparisonModeConfig('degrade').sides], ['before', 'after']);
  context.dispose();
});
