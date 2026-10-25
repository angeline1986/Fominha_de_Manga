import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred } from './modules.mjs';

class Element {
  constructor() {
    this.listeners = {}; this.dataset = {}; this.hidden = true;
    this.src = ''; this.textContent = ''; this.children = [];
  }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener(type, fn) {
    this.listeners[type] = (this.listeners[type] || []).filter((item) => item !== fn);
  }
  dispatch(type) { for (const fn of this.listeners[type] || []) fn(); }
  append(item) { this.children.push(item); }
  removeAttribute(name) { if (name === 'src') this.src = ''; }
  setAttribute() {}
  remove() {}
}

function fixture() {
  const cards = [2, 3, 4, 5].map(() => {
    const card = new Element();
    card.placeholder = new Element();
    card.querySelector = () => card.placeholder;
    return card;
  });
  const root = { querySelector(selector) {
    const index = Number(selector.match(/nth-child\((\d+)\)/)?.[1]);
    return cards[index - 2];
  } };
  return { cards, root };
}

test('quatro cartões só oferecem seleção após carregamento e revogam ao invalidar', async () => {
  const { cards, root } = fixture();
  const calls = { ready: [], clear: [] };
  const review = { ready: (...args) => calls.ready.push(args),
    clear: (name) => calls.clear.push(name) };
  const request = { provider: 'ridi', manga: 'obra', chapter: '1',
    page: 'page.png', selections: [{ x: 1 }] };
  const load = browserModules({ document: { createElement: () => new Element() }, AbortController }, {
    '/_app/api/laboratorio.js': `
      export async function executeDegradeLaboratoryJob() { return { run_id: 'd', image_url: '/d.png' }; }
      export async function executeStylizedLaboratoryJob() { return { run_id: 'a', image_url: '/a.png' }; }
      export async function executeSmoothLaboratoryJob() { return { run_id: 's', image_url: '/s.png' }; }
      export async function executeSolidLaboratory() { return { run_id: 'b', image_url: '/b.png' }; }`,
  });
  const { connectDegrade } = await load('/texto_off/laboratorio/degrade.js');
  const { connectStylized, connectSmooth, connectSolid } = await load('/texto_off/laboratorio/tratamentos.js');
  const connectors = [connectDegrade, connectStylized, connectSmooth, connectSolid]
    .map((connect) => {
      const button = new Element();
      return { button, controller: connect({ root, button, getRequest: () => request, review }) };
    });
  for (const item of connectors) item.button.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  for (const card of cards) card.children[0].onload();
  assert.deepEqual(calls.ready.map(([name]) => name),
    ['degrade', 'estilizado', 'gradiente_suave', 'solidos']);
  assert.equal(calls.ready.every(([, payload]) => payload.page === 'page.png'), true);
  assert.deepEqual(calls.ready.map(([, , runId]) => runId), ['d', 'a', 's', 'b']);
  for (const item of connectors) item.controller.invalidate();
  assert.equal(calls.clear.length, 8);
  for (const item of connectors) item.controller.dispose();
});

test('resposta tardia não volta a habilitar a seleção', async () => {
  const { cards, root } = fixture();
  const pending = deferred();
  const calls = [];
  const review = { ready: (...args) => calls.push(args), clear() {} };
  const load = browserModules({ document: { createElement: () => new Element() },
    AbortController, pending }, {
    '/_app/api/laboratorio.js': `
      export function executeStylizedLaboratoryJob() { return globalThis.pending.promise; }
      export async function executeSmoothLaboratoryJob() {}
      export async function executeSolidLaboratory() {}`,
  });
  const { connectStylized } = await load('/texto_off/laboratorio/tratamentos.js');
  const button = new Element();
  const controller = connectStylized({ root, button, review,
    getRequest: () => ({ page: 'page.png', selections: [{ x: 1 }] }) });
  button.dispatch('click');
  controller.invalidate();
  pending.resolve({ run_id: 'old', image_url: '/old.png' });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(cards[1].children[0].src, '');
  assert.equal(calls.length, 0);
  controller.dispose();
});

test('Artístico e Sólidos recuperados reaparecem nos cartões para seleção', async () => {
  const { cards, root } = fixture();
  const calls = [];
  const review = { ready: (...args) => calls.push(args), clear() {} };
  const load = browserModules({ document: { createElement: () => new Element() } }, {
    '/_app/api/laboratorio.js': `export async function executeStylizedLaboratoryJob() {}
      export async function executeSmoothLaboratoryJob() {}
      export async function executeSolidLaboratory() {}`,
  });
  const { connectStylized, connectSolid } = await load('/texto_off/laboratorio/tratamentos.js');
  const controller = connectStylized({ root, button: new Element(),
    getRequest: () => null, review });
  const solids = connectSolid({ root, button: new Element(),
    getRequest: () => null, review });
  const identity = { provider: 'comix', manga: 'obra', chapter: 'images',
    page: 'page.png', source: 'file', path: 'check/4/images/page.png' };
  const result = { treatment: 'estilizado', run_id: 'a'.repeat(32),
    image_url: '/api/textoff/laboratorio/estilizado/image?run_id=' + 'a'.repeat(32) };
  const revision = controller.revision();
  assert.equal(controller.restore(result, identity, revision), true);
  cards[1].children[0].onload();
  assert.equal(cards[1].placeholder.textContent, 'Resultado recuperado');
  assert.equal(calls[0][0], 'estilizado');
  assert.equal(calls[0][2], result.run_id);
  const solidResult = { ...result, treatment: 'solidos',
    image_url: '/api/textoff/laboratorio/solidos/image?run_id=' + result.run_id };
  assert.equal(solids.restore(solidResult, identity, solids.revision()), true);
  cards[3].children[0].onload();
  assert.equal(cards[3].placeholder.textContent, 'Resultado recuperado');
  assert.equal(calls[1][0], 'solidos');
  controller.invalidate();
  assert.equal(controller.restore(result, identity, revision), false);
  controller.dispose();
  solids.dispose();
});
