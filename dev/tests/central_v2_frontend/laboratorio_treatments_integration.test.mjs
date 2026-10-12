import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

class Element {
  constructor() { this.hidden = true; this.naturalWidth = 940; this.naturalHeight = 1660; this.src = ''; }
  append() {}
  removeAttribute(name) { if (name === 'src') this.src = ''; }
}

test('os três tratamentos recebem a mesma seleção natural e invalidam juntos ao mudar ROI', async () => {
  const calls = { options: [], reset: [], invalidated: [], disposed: [], sources: [], zoom: [] };
  const placeholder = new Element(), roiList = new Element();
  const fields = new Map([
    ['.lab-placeholder', placeholder], ['.lab-wide', new Element()],
    ['.lab-panel-body', new Element()], ['[data-lab-degrade]', new Element()],
    ['[data-lab-stylized]', new Element()], ['[data-lab-smooth]', new Element()],
    ['[data-lab-degrade-status]', new Element()], ['[data-lab-stylized-status]', new Element()],
    ['[data-lab-smooth-status]', new Element()], ['.lab-roi-list', roiList],
  ]);
  const panel = { querySelector: (selector) => fields.get(selector) };
  const originalPanel = { querySelector: (selector) => fields.get(selector), append() {} };
  const root = { querySelector(selector) {
    if (selector === '.lab-actions') return panel;
    if (selector === '.lab-cards > .lab-image:first-child') return originalPanel;
    return null;
  } };
  const navigation = { getSelection: () => ({ source: 'img', chapter: '2', page: 'page-013.png',
    pages: [{ name: 'page-013.png', previewUrl: '/original.png' }] }) };
  const workspace = {
    setZoomEnabled: (value) => calls.zoom.push(['enabled', value]),
    resetZoomDimensions: () => calls.zoom.push(['reset']),
    updateZoom: () => calls.zoom.push(['update']),
  };
  class Observer { constructor(callback) { calls.observer = callback; } observe() {} disconnect() {} }
  const load = browserModules({ calls, MutationObserver: Observer, document: { createElement: () => new Element() } }, {
    '/_app/state/context.js': 'export function getContext() { return { provider: "comix", manga: "Obra" }; }',
    '/texto_off/laboratorio/roi_selection.js': `export function connectRoiSelection() { return {
      setSource(...args) { globalThis.calls.sources.push(args); },
      getBoxesPixels() { return [{ x: 284, y: 1065, width: 420, height: 76 }]; }, dispose() {} }; }`,
    '/texto_off/laboratorio/degrade.js': `export function connectDegrade(options) { globalThis.calls.options.push(options);
      return { reset(key) { globalThis.calls.reset.push(['degrade', key]); }, invalidate() { globalThis.calls.invalidated.push('degrade'); }, dispose() { globalThis.calls.disposed.push('degrade'); } }; }`,
    '/texto_off/laboratorio/tratamentos.js': `function connect(options, name) { globalThis.calls.options.push(options);
      return { reset(key) { globalThis.calls.reset.push([name, key]); }, invalidate() { globalThis.calls.invalidated.push(name); }, dispose() { globalThis.calls.disposed.push(name); } }
      } export function connectStylized(options) { return connect(options, 'stylized'); }
      export function connectSmooth(options) { return connect(options, 'smooth'); }`,
  });
  const { connectTreatmentController } = await load('/texto_off/laboratorio/treatment_controller.js');
  const image = new Element();
  const controller = connectTreatmentController({ root, navigation, workspace, image });
  controller.displayOriginal();
  image.onload();
  assert.equal(image.src, '/original.png');
  assert.equal(calls.options.length, 3);
  for (const options of calls.options) {
    assert.deepEqual(JSON.parse(JSON.stringify(options.getRequest())), {
      provider: 'comix', manga: 'Obra', source: 'img', chapter: '2', page: 'page-013.png',
      selections: [{ x: 284, y: 1065, width: 420, height: 76 }],
    });
  }
  calls.observer();
  assert.deepEqual(calls.invalidated, ['degrade', 'stylized', 'smooth']);
  controller.dispose();
  assert.deepEqual(calls.disposed, ['degrade', 'stylized', 'smooth']);
});
