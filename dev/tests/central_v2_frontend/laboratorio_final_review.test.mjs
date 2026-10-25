import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred } from './modules.mjs';

class Element {
  constructor() {
    this.hidden = true; this.disabled = false; this.textContent = '';
    this.attributes = {}; this.listeners = {};
  }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener(type, fn) {
    this.listeners[type] = (this.listeners[type] || []).filter((item) => item !== fn);
  }
  dispatch(type) {
    if (!this.disabled) for (const fn of this.listeners[type] || []) fn();
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name]; }
}

const names = ['degrade', 'estilizado', 'gradiente_suave', 'solidos'];
const request = { provider: 'ridi', manga: 'obra', chapter: 'clean', page: 'page_clean.png' };
const response = { provider: 'ridi', manga: 'obra', chapter: '1', page: 'page.png',
  treatment: 'degrade', run_id: 'a'.repeat(32), version: 'v1',
  current_sha256: 'current', candidate_sha256: 'candidate' };
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

async function connect(propose, apply = async () => ({}), confirm = async () => true) {
  const note = new Element(), applyButton = new Element();
  const buttons = Object.fromEntries(names.map((name) => [name, new Element()]));
  const root = { querySelector(selector) {
    if (selector === '[data-lab-final-selection]') return note;
    if (selector === '[data-lab-final-apply]') return applyButton;
    return buttons[selector.match(/data-lab-final-select="([^"]+)"/)?.[1]];
  } };
  const load = browserModules({ AbortController, propose, apply, confirm }, {
    '/_app/api/laboratorio.js': `export function getFinalLaboratoryProposal(payload, signal) { return globalThis.propose(payload, signal); }
      export function applyFinalLaboratory(payload) { return globalThis.apply(payload); }`,
    '/_shared/messages/messages.js': 'export function confirmMessage(options) { return globalThis.confirm(options); }',
  });
  const { connectFinalReview } = await load('/texto_off/laboratorio/final_review.js');
  let opened = 0;
  const review = connectFinalReview(root, () => { opened++; });
  return { review, note, applyButton, buttons, get opened() { return opened; } };
}

test('seleciona cartão concluído e mostra destino oficial no painel sem abrir comparador', async () => {
  let sent;
  const ui = await connect(async (payload) => { sent = payload; return response; });
  ui.review.ready('degrade', request, response.run_id);
  assert.equal(ui.buttons.degrade.hidden, false);
  ui.buttons.degrade.dispatch('click');
  await tick();
  assert.deepEqual(JSON.parse(JSON.stringify(sent)),
    { ...request, treatment: 'degrade', run_id: response.run_id });
  assert.equal(ui.opened, 1);
  assert.match(ui.note.textContent, /Cap. 1 · page.png/);
  assert.equal(ui.applyButton.hidden, false);
  assert.equal(ui.buttons.degrade.getAttribute('aria-pressed'), 'true');
  assert.equal(ui.review.getSelection().version, 'v1');
  ui.buttons.degrade.dispatch('click');
  assert.equal(ui.review.getSelection(), null);
  assert.equal(ui.applyButton.hidden, true);
  ui.review.dispose();
});

test('troca de cartão ignora resposta anterior e mantém somente a nova seleção', async () => {
  const first = deferred();
  let signal;
  const ui = await connect((payload, active) => {
    if (payload.treatment === 'degrade') { signal = active; return first.promise; }
    return Promise.resolve({ ...response, treatment: 'estilizado', run_id: 'b'.repeat(32) });
  });
  ui.review.ready('degrade', request, response.run_id);
  ui.review.ready('estilizado', request, 'b'.repeat(32));
  ui.buttons.degrade.dispatch('click');
  ui.buttons.estilizado.dispatch('click');
  first.resolve(response);
  await tick();
  assert.equal(signal.aborted, true);
  assert.equal(ui.review.getSelection().treatment, 'estilizado');
  assert.equal(ui.buttons.degrade.getAttribute('aria-pressed'), 'false');
  ui.review.clear('estilizado');
  assert.equal(ui.review.getSelection(), null);
  assert.equal(ui.applyButton.hidden, true);
  ui.review.dispose();
});

test('mudança de página cancela proposta pendente', async () => {
  const pending = deferred();
  let signal;
  const ui = await connect((_payload, active) => { signal = active; return pending.promise; });
  ui.review.ready('degrade', request, response.run_id);
  ui.buttons.degrade.dispatch('click');
  ui.review.clear('degrade');
  pending.resolve(response);
  await tick();
  assert.equal(signal.aborted, true);
  assert.equal(ui.review.getSelection(), null);
  assert.equal(ui.note.hidden, true);
  ui.review.dispose();
});

test('aplicação revalida a versão, confirma o destino e usa a identidade oficial', async () => {
  const sent = [];
  let confirmed;
  const ui = await connect(async () => response,
    async (payload) => { sent.push(payload); return { status: 'applied' }; },
    async (options) => { confirmed = options; return true; });
  ui.review.ready('degrade', request, response.run_id);
  ui.buttons.degrade.dispatch('click');
  await tick();
  ui.applyButton.dispatch('click');
  await tick();
  assert.match(confirmed.message, /page.png \(Cap. 1\)/);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].chapter, '1');
  assert.equal(sent[0].page, 'page.png');
  assert.equal(sent[0].version, 'v1');
  assert.equal(sent[0].confirmed, true);
  assert.equal(ui.review.getSelection(), null);
  assert.equal(ui.buttons.degrade.hidden, true);
  assert.match(ui.note.textContent, /aplicado ao Consolidado Final/);
  ui.review.dispose();
});

test('cancelar confirmação conserva a seleção e não publica', async () => {
  let applied = false;
  const ui = await connect(async () => response, async () => { applied = true; },
    async () => false);
  ui.review.ready('degrade', request, response.run_id);
  ui.buttons.degrade.dispatch('click');
  await tick();
  ui.applyButton.dispatch('click');
  await tick();
  assert.equal(applied, false);
  assert.equal(ui.review.getSelection().version, 'v1');
  assert.equal(ui.applyButton.hidden, false);
  ui.review.dispose();
});

test('versão alterada bloqueia publicação e exige nova seleção', async () => {
  let calls = 0, applied = false;
  const ui = await connect(async () => ({ ...response, version: ++calls === 1 ? 'v1' : 'v2' }),
    async () => { applied = true; });
  ui.review.ready('degrade', request, response.run_id);
  ui.buttons.degrade.dispatch('click');
  await tick();
  ui.applyButton.dispatch('click');
  await tick();
  assert.equal(applied, false);
  assert.equal(ui.review.getSelection(), null);
  assert.match(ui.note.textContent, /mudou/);
  ui.review.dispose();
});

test('falha da proposta aparece no painel sem permitir aplicação', async () => {
  const ui = await connect(async () => { throw new Error('Página ambígua'); });
  ui.review.ready('degrade', request, response.run_id);
  ui.buttons.degrade.dispatch('click');
  await tick();
  assert.match(ui.note.textContent, /Página ambígua/);
  assert.equal(ui.applyButton.hidden, true);
  ui.review.dispose();
});

test('resposta de aplicação não reaparece após mudar de página', async () => {
  const pending = deferred();
  const ui = await connect(async () => response, () => pending.promise);
  ui.review.ready('degrade', request, response.run_id);
  ui.buttons.degrade.dispatch('click');
  await tick();
  ui.applyButton.dispatch('click');
  await tick();
  ui.review.clear('degrade');
  pending.resolve({ status: 'applied' });
  await tick();
  assert.equal(ui.note.hidden, true);
  assert.equal(ui.review.getSelection(), null);
  ui.review.dispose();
});
