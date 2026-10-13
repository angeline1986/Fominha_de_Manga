import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred } from './modules.mjs';

class Element {
  constructor() {
    this.children = []; this.listeners = {}; this.dataset = {}; this.attributes = {};
    this.hidden = true; this.textContent = ''; this.src = '';
  }
  append(...items) { this.children.push(...items); }
  insertBefore(item, reference) {
    this.children = this.children.filter((child) => child !== item);
    const index = this.children.indexOf(reference);
    this.children.splice(index < 0 ? this.children.length : index, 0, item);
  }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener(type, fn) { this.listeners[type] = (this.listeners[type] || []).filter((item) => item !== fn); }
  dispatch(type) { for (const fn of this.listeners[type] || []) fn({ currentTarget: this }); }
  after(...items) { this.afterNodes = items; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; if (name === 'src') this.src = ''; }
  replaceChildren(...items) { this.children = items; }
  querySelectorAll(selector) { return selector === 'input:checked' ? [{ value: 'component-1' }] : []; }
  remove() {}
}

test('feedback contextual mantém os tratamentos independentes e ignora respostas da seleção antiga', async () => {
  const oldStylized = deferred(), newStylized = deferred(), failedSmooth = deferred();
  const fixtures = { stylized: [oldStylized, newStylized], smooth: [failedSmooth], signals: {} };
  const pending = { page: 'page-1.png', selections: [{ x: 1 }] };
  const progressEvents = [];
  let progressId = 0;
  const progress = { start: (title) => { const id = ++progressId; progressEvents.push(['start', title, id]); return id; },
    finish: (id) => progressEvents.push(['finish', id]) };
  const panels = [3, 4].map(() => {
    const panel = new Element(), placeholder = new Element();
    placeholder.hidden = false;
    placeholder.textContent = 'Aguardando execução';
    placeholder.dataset.state = 'waiting';
    panel.placeholder = placeholder; panel.append(placeholder);
    panel.querySelector = () => placeholder;
    return panel;
  });
  const root = { querySelector(selector) {
    if (selector.includes('nth-child(3)')) return panels[0];
    if (selector.includes('nth-child(4)')) return panels[1];
    return null;
  } };
  const load = browserModules({ AbortController, document: { createElement: () => new Element() }, fixtures }, {
    '/_app/api/laboratorio.js': `export async function executeStylizedLaboratory(_payload, signal) {
      globalThis.fixtures.signals.stylized = signal;
      return globalThis.fixtures.stylized.shift().promise;
    } export async function executeSmoothLaboratory(_payload, signal) {
      globalThis.fixtures.signals.smooth = signal;
      return globalThis.fixtures.smooth.shift().promise;
    }`,
  });
  const { connectStylized, connectSmooth } = await load('/texto_off/laboratorio/tratamentos.js');
  const stylizedButton = new Element(), smoothButton = new Element();
  const stylized = connectStylized({ root, button: stylizedButton, getRequest: () => pending, progress });
  connectSmooth({ root, button: smoothButton, getRequest: () => pending, progress });

  stylizedButton.dispatch('click');
  assert.equal(progressEvents[0][1], 'Executando Artístico');
  assert.equal(panels[0].placeholder.dataset.state, 'running');
  assert.equal(panels[0].placeholder.hidden, true);
  assert.equal(panels[1].placeholder.textContent, 'Aguardando execução');
  pending.page = 'page-2.png';
  stylized.invalidate();
  assert.equal(fixtures.signals.stylized.aborted, false);
  oldStylized.resolve({ image_url: '/stale.png' });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(progressEvents[1].slice(0, 2), ['finish', progressEvents[0][2]]);
  assert.equal(panels[0].children.find((item) => item.className === 'lab-treatment-image')?.src, '');
  assert.equal(panels[0].placeholder.dataset.state, 'waiting');

  stylizedButton.dispatch('click');
  newStylized.resolve({ image_url: '/current.png' });
  await new Promise((resolve) => setTimeout(resolve, 0));
  const image = panels[0].children.find((item) => item.className === 'lab-treatment-image');
  image.onload();
  assert.equal(panels[0].placeholder.dataset.state, 'completed');
  assert.equal(image.hidden, false);
  assert.ok(panels[0].children.indexOf(panels[0].placeholder) < panels[0].children.indexOf(image));

  smoothButton.dispatch('click');
  assert.equal(progressEvents.at(-1)[1], 'Executando Suave');
  failedSmooth.reject(new Error('worker falhou'));
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(progressEvents.at(-1)[0], 'finish');
  assert.equal(panels[1].placeholder.dataset.state, 'failed');
  assert.match(panels[1].placeholder.textContent, /worker falhou/);
  assert.equal(panels[0].placeholder.dataset.state, 'completed');
  stylized.dispose();
});

test('Degradê mantém a revisão assistida e exibe o resultado autorizado no próprio quadro', async () => {
  const calls = [];
  const placeholder = new Element(), card = new Element(), button = new Element(), frame = new Element();
  placeholder.textContent = 'Aguardando execução';
  card.querySelector = () => placeholder; card.append(placeholder);
  const root = { querySelector(selector) {
    if (selector === '.lab-cards > .lab-image:nth-child(2)') return card;
    if (selector === '.lab-roi-frame') return frame;
    return null;
  } };
  const request = { page: 'page-1.png', selections: [{ x: 1 }] };
  const progressEvents = [];
  let progressId = 0;
  const progress = { start: (title) => { const id = ++progressId; progressEvents.push(['start', title, id]); return id; },
    finish: (id) => progressEvents.push(['finish', id]) };
  const load = browserModules({ AbortController, document: { createElement: () => new Element() }, calls }, {
    '/_app/api/laboratorio.js': `export async function executeDegradeLaboratory() {
      throw Object.assign(new Error('adiado'), { status: 422, body: { run_id: 'run-1' } });
    } export async function getDegradeAuthorizationCandidates() {
      return { proposal_run_id: 'proposal-1', proposal_token: 'token', candidates: [{ id: 'component-1' }] };
    } export async function confirmDegradeLaboratory(payload) {
      globalThis.calls.push(payload); return { image_url: '/authorized.png' };
    }`,
    '/texto_off/laboratorio/degrade_candidates.js': 'export function drawDegradeCandidates(options) { options.review.onConfirm = options.onConfirm; }',
  });
  const { connectDegrade } = await load('/texto_off/laboratorio/degrade.js');
  const degrade = connectDegrade({ root, button, getRequest: () => request, progress });
  button.dispatch('click');
  assert.equal(progressEvents[0][1], 'Executando Degradê');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(placeholder.dataset.state, 'waiting');
  assert.match(placeholder.textContent, /revisão e autorização/);
  assert.deepEqual(progressEvents[1].slice(0, 2), ['finish', progressEvents[0][2]]);
  const review = button.afterNodes[0];
  const authorizeButton = new Element();
  authorizeButton.disabled = true;
  authorizeButton.textContent = 'Autorizar e executar';
  assert.equal(authorizeButton.textContent, 'Autorizar e executar');
  await review.onConfirm({ currentTarget: authorizeButton });
  assert.equal(progressEvents[2][1], 'Executando Degradê');
  assert.equal(progressEvents.at(-1)[0], 'finish');
  assert.equal(calls[0].proposal_token, 'token');
  assert.equal(JSON.stringify(calls[0].component_ids), '["component-1"]');
  assert.equal(calls[0].page, 'page-1.png');
  assert.equal(JSON.stringify(calls[0].selections), JSON.stringify(request.selections));
  const image = card.children.find((item) => item.className === 'lab-original-image');
  image.onload();
  assert.equal(placeholder.dataset.state, 'completed');
  assert.equal(image.hidden, false);
  degrade.dispose();
});
