import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { browserModules, deferred } from './modules.mjs';

class Element {
  constructor() {
    this.children = []; this.listeners = {}; this.attributes = {};
    this.hidden = false; this.textContent = ''; this.src = ''; this.value = ''; this.dataset = {};
    this.classList = { add() {}, remove() {}, toggle() {} };
    this.style = { setProperty() {}, removeProperty() {} };
  }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter((item) => item !== fn); }
  dispatch(type, event = {}) { for (const fn of this.listeners[type] || []) fn({ currentTarget: this, ...event }); }
  append(...items) { this.children.push(...items); }
  insertBefore(item, reference) {
    this.children = this.children.filter((child) => child !== item);
    const index = this.children.indexOf(reference);
    this.children.splice(index < 0 ? this.children.length : index, 0, item);
  }
  add(item) { this.children.push(item); }
  after(...items) { this.afterNodes = items; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; if (name === 'src') this.src = ''; }
  replaceChildren(...items) { this.children = items; }
  remove() {}
  querySelector(selector) { return selector === '.lab-placeholder' ? this.placeholder : null; }
  querySelectorAll(selector) { return selector === 'input:checked' ? [{ value: 'candidate-1' }] : []; }
}

function degradeRoot() {
  const card = new Element(); card.placeholder = new Element();
  const note = card.placeholder, frame = new Element();
  return {
    card, note, frame,
    root: { querySelector(selector) {
      if (selector === '.lab-cards > .lab-image:nth-child(2)') return card;
      if (selector === '.lab-roi-frame') return frame;
      return null;
    } },
  };
}

test('Laboratório carrega sua composição modular e mantém os quatro cartões', async () => {
  const load = browserModules();
  const { render } = await load('/texto_off/laboratorio/index.js');
  assert.equal(typeof render, 'function');
  const { routes } = await load('/_app/router/routes.js');
  assert.equal(routes.laboratorio.module, '/texto_off/laboratorio/index.js');
  const view = await readFile(new URL('../../../central_v2/frontend/texto_off/laboratorio/view.js', import.meta.url), 'utf8');
  const style = await readFile(new URL('../../../central_v2/frontend/texto_off/laboratorio/style.css', import.meta.url), 'utf8');
  const degrade = await readFile(new URL('../../../central_v2/frontend/texto_off/laboratorio/degrade.js', import.meta.url), 'utf8');
  const candidates = await readFile(new URL('../../../central_v2/frontend/texto_off/laboratorio/degrade_candidates.js', import.meta.url), 'utf8');
  const cards = [...view.matchAll(/<header>(ORIGINAL|DEGRADÊ|ARTÍSTICO|SUAVE)<\/header>/g)].map((match) => match[1]);
  assert.deepEqual(cards, ['ORIGINAL', 'DEGRADÊ', 'ARTÍSTICO', 'SUAVE']);
  assert.equal((view.match(/Selecione uma página e pelo menos uma área\./g) || []).length, 0);
  assert.equal((view.match(/data-treatment-status=/g) || []).length, 3);
  assert.match(view, /class="lab-treatment-actions"[\s\S]*data-lab-degrade[\s\S]*data-lab-stylized[\s\S]*data-lab-smooth/);
  assert.match(style, /\.lab-treatment-actions\s*\{\s*display:\s*grid;\s*gap:\s*10px;/);
  assert.match(style, /\.lab-placeholder\[data-treatment-status\]\s*\{[^}]*position:\s*sticky;[^}]*top:\s*var\(--lab-treatment-header-height/);
  assert.equal((view.match(/class="lab-image lab-treatment-card"/g) || []).length, 3);
  assert.match(style, /\.lab-treatment-card > header\s*\{[^}]*position:\s*sticky;[^}]*top:\s*0;/);
  assert.doesNotMatch(style, /lab-degrade-progress|lab-treatment-spin|content:\s*["'][0-9]+%/);
  assert.doesNotMatch(degrade, /confirmMessage|Autorizar componentes adiados/);
  assert.match(candidates, /confirm\.textContent\s*=\s*'Autorizar e executar'/);
});

test('páginas carregadas continuam selecionáveis e origem dispara o mesmo evento', async () => {
  const elements = new Map();
  for (const selector of ['[data-lab-chapter]', '[data-lab-page]', '[data-lab-list]',
    '[data-lab-prev]', '[data-lab-next]', '[data-lab-counter]', '[data-lab-preview]']) {
    elements.set(selector, new Element());
  }
  const previewImage = new Element();
  elements.get('[data-lab-preview]').querySelector = () => previewImage;
  const sources = ['img', 'merge'].map((source) => {
    const button = new Element(); button.dataset.labSource = source; return button;
  });
  const listeners = {}, dispatched = [];
  const root = {
    querySelector: (selector) => elements.get(selector),
    querySelectorAll: () => sources,
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
    removeEventListener(type, fn) { listeners[type] = (listeners[type] || []).filter((item) => item !== fn); },
    dispatchEvent(event) { dispatched.push(event); for (const fn of listeners[event.type] || []) fn(event); },
  };
  class BrowserEvent { constructor(type, options = {}) { this.type = type; this.detail = options.detail; } }
  class OptionValue { constructor(text, value) { this.text = text; this.value = value; } }
  const load = browserModules({ CustomEvent: BrowserEvent, Option: OptionValue,
    document: { createElement: () => new Element() } });
  const { connectPageNavigation } = await load('/texto_off/laboratorio/page_navigation.js');
  const order = [];
  const navigation = connectPageNavigation(root, {
    beforeDraw: () => order.push('selection'), afterDraw: () => order.push('render'),
  });
  root.dispatchEvent(new BrowserEvent('laboratorio:pages', { detail: {
    chapters: { '1': [{ name: 'page-001.png', previewUrl: '/page-001.png' }] },
  } }));
  assert.equal(JSON.stringify(navigation.getSelection()), JSON.stringify({
    source: 'img', chapter: '', page: '', pages: [],
  }));
  elements.get('[data-lab-chapter]').value = '1';
  elements.get('[data-lab-chapter]').dispatch('change');
  assert.equal(navigation.selectPage('1', 'page-001.png'), true);
  assert.equal(JSON.stringify(navigation.getSelection()), JSON.stringify({
    source: 'img', chapter: '1', page: 'page-001.png',
    pages: [{ name: 'page-001.png', previewUrl: '/page-001.png' }],
  }));
  sources[1].dispatch('click');
  assert.equal(navigation.getSelection().source, 'merge');
  assert.equal(dispatched.at(-1).type, 'laboratorio:source');
  assert.deepEqual(order.slice(-2), ['selection', 'render']);
  navigation.dispose();
});

test('carregamento antigo de páginas não substitui a origem mais recente', async () => {
  const requests = [deferred(), deferred()], emitted = [], listeners = {};
  let requestCount = 0;
  const root = {
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
    removeEventListener(type, fn) { listeners[type] = (listeners[type] || []).filter((item) => item !== fn); },
    dispatchEvent(event) {
      if (event.type === 'laboratorio:pages') emitted.push(event.detail);
      for (const fn of listeners[event.type] || []) fn(event);
    },
  };
  class BrowserEvent { constructor(type, options = {}) { this.type = type; this.detail = options.detail; } }
  const load = browserModules({ AbortController, CustomEvent: BrowserEvent,
    context: { provider: 'comix', manga: 'Obra' },
    fetch: () => requests[requestCount++].promise }, {
    '/_app/state/context.js': 'export function getContext() { return globalThis.context; } export function subscribeContext() { return () => {}; }',
  });
  const { connectLaboratorio } = await load('/texto_off/laboratorio/data_loader.js');
  const disconnect = connectLaboratorio(root);
  root.dispatchEvent(new BrowserEvent('laboratorio:source', { detail: { source: 'merge' } }));
  assert.equal(requestCount, 2);
  requests[1].resolve({ ok: true, json: async () => ({ chapters: { '2': [{ name: 'merge.png' }] } }) });
  await new Promise((resolve) => setTimeout(resolve, 0));
  requests[0].resolve({ ok: true, json: async () => ({ chapters: { '1': [{ name: 'stale.png' }] } }) });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(emitted.length, 1);
  assert.equal(emitted[0].chapters['2'][0].name, 'merge.png');
  disconnect();
});

test('resposta Degradê atrasada não substitui a seleção invalidada', async () => {
  const execution = deferred(), state = { request: { page: 'a.png', selections: [{ x: 1 }] } };
  const load = browserModules({ AbortController, document: { createElement: () => new Element() }, execution }, {
    '/_shared/messages/messages.js': 'export async function confirmMessage() { return true; }',
    '/_app/api/laboratorio.js': 'export async function executeDegradeLaboratory(_payload, signal) { globalThis.execution.signal = signal; return globalThis.execution.promise; } export async function confirmDegradeLaboratory() {} export async function getDegradeAuthorizationCandidates() {}',
    '/texto_off/laboratorio/degrade_candidates.js': 'export function drawDegradeCandidates() {}',
  });
  const { connectDegrade } = await load('/texto_off/laboratorio/degrade.js');
  const { root, card } = degradeRoot(), button = new Element();
  const connector = connectDegrade({ root, button, getRequest: () => state.request });
  button.dispatch('click');
  connector.invalidate();
  assert.equal(execution.signal.aborted, false);
  execution.resolve({ image_url: '/stale.png' });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(card.children.find((child) => child.className === 'lab-original-image').src, '');
  connector.dispose();
});

test('mudança da ROI antes da autorização invalida a proposta sem executar', async () => {
  const calls = { confirmed: 0 };
  const state = { request: { page: 'a.png', selections: [{ x: 1 }] } };
  const load = browserModules({ AbortController, document: { createElement: () => new Element() }, calls }, {
    '/_app/api/laboratorio.js': `export async function executeDegradeLaboratory() { throw Object.assign(new Error('deferred'), { status: 422, body: { run_id: 'run-1' } }); }
      export async function getDegradeAuthorizationCandidates() { return { proposal_run_id:'proposal-1', proposal_token:'token', candidates:[{id:'candidate-1',component:2}] }; }
      export async function confirmDegradeLaboratory() { globalThis.calls.confirmed++; }`,
    '/texto_off/laboratorio/degrade_candidates.js': 'export function drawDegradeCandidates(options) { options.review.onConfirm = options.onConfirm; }',
  });
  const { connectDegrade } = await load('/texto_off/laboratorio/degrade.js');
  const { root, note } = degradeRoot(), button = new Element();
  const connector = connectDegrade({ root, button, getRequest: () => state.request });
  button.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  const confirm = button.afterNodes.find((child) => child.className === 'lab-degrade-review').onConfirm;
  state.request = { page: 'a.png', selections: [{ x: 9 }] };
  await confirm({ currentTarget: new Element() });
  assert.equal(calls.confirmed, 0);
  assert.equal(note.textContent, 'Aguardando execução');
  connector.dispose();
});
