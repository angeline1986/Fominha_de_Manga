import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { browserModules } from './modules.mjs';

class Element {
  constructor() {
    this.dataset = {}; this.children = []; this.innerHTML = ''; this.parent = null;
    this.style = { setProperty: (name, value) => { this.style[name] = value; } };
    this.classList = { add: (name) => { this.className = `${this.className || ''} ${name}`; } };
  }
  append(child) { child.parent = this; this.children.push(child); }
  replaceChildren(...children) { this.children = children; children.forEach((child) => { child.parent = this; }); }
  querySelector() { return new Element(); }
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

test('a merged Mapear and Sommelier occurrence renders one ROI with shared X identity', async () => {
  const document = { createElement: () => new Element() };
  const load = browserModules({ document }, {
    '/_shared/icons/icons.js': 'export function iconMarkup() { return ""; }',
  });
  const { renderResidueOccurrences } = await load('/texto_off/comparison/residue_catalog_view.js');
  const overlay = new Element(), layers = new Element();
  const merged = { id: 'mapear-1', type: 'residuo_gradiente', note: null,
    box: { left: .2, top: .3, width: .4, height: .2 },
    origin: 'MAPEAR', origins: ['MAPEAR', 'SOMMELIER'],
    source_references: [{ origin: 'MAPEAR' }, { origin: 'SOMMELIER' }] };

  renderResidueOccurrences(overlay, layers, [merged], '');
  assert.equal(overlay.children.length, 1);
  assert.equal(layers.children.length, 1);
  assert.equal((layers.children[0].innerHTML.match(/data-remove="mapear-1"/g) || []).length, 1);
  assert.equal((overlay.children[0].innerHTML.match(/data-remove="mapear-1"/g) || []).length, 1);
});

test('Check boxes, numbers and bullets use the exact classification palette after reclassification', async () => {
  const document = { createElement: () => new Element() };
  const load = browserModules({ document }, {
    '/_shared/icons/icons.js': 'export function iconMarkup() { return ""; }',
  });
  const { renderResidueOccurrences } = await load('/texto_off/comparison/residue_catalog_view.js');
  const { checkColor } = await load('/texto_off/comparison/check_palette.js');
  const overlay = new Element(), layers = new Element();
  const areas = ['residuo_gradiente', 'residuo_balao_solido_branco'].map((type, index) => ({
    id: `area-${index}`, type, box: { left: .1, top: .1, width: .2, height: .2 },
  }));
  renderResidueOccurrences(overlay, layers, areas, '', { check: true });
  assert.equal(checkColor('residuo_gradiente'), '#7C3AED');
  assert.equal(checkColor('residuo_balao_solido_branco'), '#A7C957');
  assert.deepEqual(overlay.children.map((box) => box.style['--check-box-color']),
    ['#7C3AED', '#A7C957']);
  assert.deepEqual(layers.children.map((row) => row.style['--check-card-accent']),
    ['#7C3AED', '#A7C957']);
  areas[0].type = 'balao_transparente';
  renderResidueOccurrences(overlay, layers, areas, '', { check: true });
  assert.equal(overlay.children[0].dataset.boxId, 'area-0');
  assert.equal(overlay.children[0].style['--check-box-color'], '#0891B2');
  assert.equal(layers.children[0].style['--check-card-accent'], '#0891B2');
  const css = await readFile(new URL('../../../central_v2/frontend/texto_off/comparison/style.css', import.meta.url), 'utf8');
  assert.match(css, /border: 2px solid var\(--check-box-color/);
  assert.match(css, /\.comparison-residue-box \.comparison-residue-number \{[^}]*var\(--check-box-color/);
});
