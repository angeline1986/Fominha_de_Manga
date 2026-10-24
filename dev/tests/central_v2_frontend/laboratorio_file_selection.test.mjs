import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

class Element {
  constructor() {
    this.children = []; this.listeners = {}; this.dataset = {};
    this.value = ''; this.hidden = false; this.textContent = '';
    this.classList = { toggle() {} };
  }
  addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
  removeEventListener(type, listener) {
    this.listeners[type] = (this.listeners[type] || []).filter((entry) => entry !== listener);
  }
  dispatch(type) { for (const listener of this.listeners[type] || []) listener({ type }); }
  append(...items) { this.children.push(...items); }
  add(item) { this.children.push(item); }
  replaceChildren(...items) { this.children = items; }
  removeAttribute() {}
  setAttribute() {}
  remove() {}
  querySelector() { return this.image; }
}

class BrowserEvent {
  constructor(type, options = {}) { this.type = type; this.detail = options.detail; }
}

test('arquivo de outra pasta aparece como seleção e é limpo ao mudar a obra', async () => {
  const selectors = ['[data-lab-chapter]', '[data-lab-page]', '[data-lab-list]',
    '[data-lab-prev]', '[data-lab-next]', '[data-lab-counter]', '[data-lab-preview]'];
  const elements = new Map(selectors.map((selector) => [selector, new Element()]));
  elements.get('[data-lab-preview]').image = new Element();
  const sources = ['img', 'merge'].map((source) => {
    const button = new Element(); button.dataset.labSource = source; return button;
  });
  const root = {
    isConnected: true, listeners: {},
    querySelector: (selector) => elements.get(selector),
    querySelectorAll: () => sources,
    addEventListener: Element.prototype.addEventListener,
    removeEventListener: Element.prototype.removeEventListener,
    dispatchEvent(event) {
      for (const listener of this.listeners[event.type] || []) listener(event);
    },
  };
  const load = browserModules({ CustomEvent: BrowserEvent,
    Option: class { constructor(text, value) { this.text = text; this.value = value; } },
    document: { createElement: () => new Element(), addEventListener() {}, removeEventListener() {} } });
  const context = await load('/_app/state/context.js');
  context.setCatalog({ comix: ['obra', 'nova'] });
  context.selectProvider('comix');
  context.selectManga('obra');
  const { connectPageNavigation } = await load('/texto_off/laboratorio/page_navigation.js');
  const navigation = connectPageNavigation(root);
  navigation.selectFile({ path: 'BASICA/10/clean/page-001.png', name: 'page-001.png',
    chapter: 'clean', folderLabel: 'BASICA/10/clean', previewUrl: '/preview.png' });
  assert.deepEqual(JSON.parse(JSON.stringify(navigation.getSelection())), {
    source: 'file', chapter: 'clean', page: 'page-001.png',
    path: 'BASICA/10/clean/page-001.png',
    pages: [{ name: 'page-001.png', previewUrl: '/preview.png' }],
  });
  assert.equal(elements.get('[data-lab-chapter]').children[0].text, 'BASICA/10/clean');
  assert.equal(elements.get('[data-lab-list]').children[0].textContent, 'page-001.png');

  sources[1].dispatch('click');
  assert.equal(navigation.getSelection().source, 'merge');
  assert.equal(navigation.getSelection().path, undefined);
  navigation.selectFile({ path: 'BASICA/10/clean/page-001.png', name: 'page-001.png',
    chapter: 'clean', folderLabel: 'BASICA/10/clean', previewUrl: '/preview.png' });

  context.selectManga('nova');
  assert.equal(navigation.getSelection().path, undefined);
  assert.equal(navigation.getSelection().source, 'merge');
  navigation.dispose();
});

test('explorador permite escolher uma imagem em BASICA/10/clean', async () => {
  const dialog = new Element(), list = new Element(), pathLabel = new Element();
  const explore = new Element(), close = new Element();
  dialog.open = false;
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; dialog.dispatch('close'); };
  const fields = new Map([
    ['[data-lab-explorer]', dialog], ['[data-lab-explorer-list]', list],
    ['[data-lab-explorer-path]', pathLabel], ['[data-lab-explore]', explore],
    ['[data-lab-explorer-close]', close],
  ]);
  const root = { querySelector: (selector) => fields.get(selector) };
  const selected = [];
  const navigation = { selectFile: (file) => selected.push(file) };
  const fetch = async (url) => {
    const path = new URL(url, 'http://localhost').searchParams.get('path');
    const next = { '': 'BASICA', BASICA: 'BASICA/10',
      'BASICA/10': 'BASICA/10/clean' }[path];
    const entries = next ? [{ type: 'directory', name: next.split('/').at(-1), path: next }]
      : [{ type: 'file', name: 'page-001.png', path: 'BASICA/10/clean/page-001.png' }];
    return { ok: true, json: async () => ({ path, entries }) };
  };
  const load = browserModules({ AbortController, fetch, document: { createElement: () => new Element() } }, {
    '/_app/state/context.js':
      'export function getContext() { return { provider: "comix", manga: "obra" }; }',
  });
  const { connectFileExplorer } = await load('/texto_off/laboratorio/file_explorer.js');
  const explorer = connectFileExplorer(root, navigation);
  explore.dispatch('click');
  for (const folder of ['BASICA', '10', 'clean']) {
    await new Promise((resolve) => setTimeout(resolve, 0));
    list.children.find((entry) => entry.textContent.includes(folder)).dispatch('click');
  }
  await new Promise((resolve) => setTimeout(resolve, 0));
  const file = list.children.find((entry) => entry.textContent.includes('page-001.png'));
  assert.match(file.textContent, /Selecionar/);
  file.dispatch('click');
  assert.equal(dialog.open, false);
  assert.equal(selected[0].path, 'BASICA/10/clean/page-001.png');
  assert.match(selected[0].previewUrl, /browse_image=1/);
  explorer.dispose();
});

test('tratamentos recebem o caminho da imagem escolhida', async () => {
  let getRequest;
  const placeholder = new Element(), roiList = new Element();
  const panel = { querySelector: (selector) => selector === '.lab-roi-list' ? roiList : new Element() };
  const originalPanel = { querySelector: () => placeholder, append() {} };
  const root = { querySelector: (selector) => selector === '.lab-actions' ? panel : originalPanel };
  const image = new Element();
  image.naturalWidth = 30;
  image.naturalHeight = 30;
  const navigation = { getSelection: () => ({ source: 'file', chapter: 'clean',
    page: 'page-001.png', path: 'BASICA/10/clean/page-001.png',
    pages: [{ name: 'page-001.png', previewUrl: '/preview.png' }] }) };
  const workspace = { setZoomEnabled() {}, resetZoomDimensions() {}, updateZoom() {} };
  const load = browserModules({
    document: { createElement: () => new Element() },
    MutationObserver: class { observe() {} disconnect() {} },
    record: (options) => { getRequest = options.getRequest; },
  }, {
    '/_app/state/context.js':
      'export function getContext() { return { provider: "comix", manga: "obra" }; }',
    '/texto_off/laboratorio/roi_selection.js': `export function connectRoiSelection() { return {
      setSource() {}, getBoxesPixels() { return [{ x: 1, y: 1, width: 15, height: 15 }]; },
      dispose() {} }; }`,
    '/texto_off/laboratorio/degrade.js': `export function connectDegrade(options) {
      record(options); return { reset() {}, invalidate() {}, dispose() {} }; }`,
    '/texto_off/laboratorio/tratamentos.js': `function connect() {
      return { reset() {}, invalidate() {}, dispose() {} }; }
      export const connectStylized = connect;
      export const connectSmooth = connect;
      export const connectSolid = connect;`,
  });
  const { connectTreatmentController } = await load('/texto_off/laboratorio/treatment_controller.js');
  const controller = connectTreatmentController({ root, navigation, workspace, image });
  controller.displayOriginal();
  image.onload();
  assert.equal(image.src, '/preview.png');
  const request = getRequest();
  assert.equal(request?.path, 'BASICA/10/clean/page-001.png');
  assert.equal(request?.source, 'file');
  controller.dispose();
});
