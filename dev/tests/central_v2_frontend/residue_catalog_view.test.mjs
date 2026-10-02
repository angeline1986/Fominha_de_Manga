import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor() { this.dataset = {}; this.style = {}; this.children = []; this.innerHTML = ''; this.parent = null; }
  append(child) { child.parent = this; this.children.push(child); }
  replaceChildren(...children) { this.children = children; children.forEach((child) => { child.parent = this; }); }
  querySelector() { return { value: '' }; }
  querySelectorAll(selector) {
    return this.children.filter((child) => child.dataset.boxId || child.dataset.liveBox !== undefined);
  }
  setAttribute() {}
  remove() { this.removed = true; if (this.parent) this.parent.children = this.parent.children.filter((child) => child !== this); }
}

test('rendered box and layer numbers follow list order while occurrence IDs stay stable', async () => {
  const document = { createElement: () => new Element() };
  const load = browserModules({ document }, {
    '/_shared/icons/icons.js': 'export function iconMarkup() { return ""; }',
  });
  const { renderResidueOccurrences } = await load('/texto_off/comparison/residue_catalog_view.js');
  const overlay = new Element(), layers = new Element();
  const occurrence = (id) => ({ id, number: 99, type: 'texto_residual', note: null,
    box: { left: .1, top: .1, width: .2, height: .2 } });
  const a = occurrence('id-a'), b = occurrence('id-b'), c = occurrence('id-c'), d = occurrence('id-d');

  renderResidueOccurrences(overlay, layers, [a, b, c], '');
  assert.deepEqual(layers.children.map((row) => row.innerHTML.match(/comparison-residue-number">(\d+)/)[1]), ['1', '2', '3']);
  renderResidueOccurrences(overlay, layers, [a, c], '');
  assert.deepEqual(layers.children.map((row) => row.innerHTML.match(/comparison-residue-number">(\d+)/)[1]), ['1', '2']);
  assert.deepEqual(overlay.children.map((box) => box.dataset.boxId), ['id-a', 'id-c']);
  renderResidueOccurrences(overlay, layers, [a, c, d], '');
  assert.deepEqual(layers.children.map((row) => row.innerHTML.match(/comparison-residue-number">(\d+)/)[1]), ['1', '2', '3']);
  renderResidueOccurrences(overlay, layers, [c, d], '');
  assert.deepEqual(layers.children.map((row) => row.innerHTML.match(/comparison-residue-number">(\d+)/)[1]), ['1', '2']);
  assert.deepEqual(layers.children.map((row) => row.dataset.occurrenceId), ['id-c', 'id-d']);
});
