import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred } from './modules.mjs';

class Element {
  constructor() {
    this.hidden = true; this.disabled = true; this.textContent = '';
    this.src = ''; this.open = false; this.listeners = {};
  }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener(type, fn) {
    this.listeners[type] = (this.listeners[type] || []).filter((item) => item !== fn);
  }
  dispatch(type) { for (const fn of this.listeners[type] || []) fn(); }
  removeAttribute(name) { if (name === 'src') this.src = ''; }
  showModal() { this.open = true; }
  close() { this.open = false; this.dispatch('close'); }
}

function fixture() {
  const names = ['dialog', 'page', 'status', 'current', 'candidate', 'select', 'close', 'cancel'];
  const view = Object.fromEntries(names.map((name) => [name, new Element()]));
  view.dispose = () => { view.disposed = true; };
  const note = new Element(), applyButton = new Element();
  const buttons = Object.fromEntries(['degrade', 'estilizado', 'gradiente_suave', 'solidos']
    .map((name) => [name, new Element()]));
  const root = { querySelector(selector) {
    if (selector === '[data-lab-final-selection]') return note;
    if (selector === '[data-lab-final-apply]') return applyButton;
    return buttons[selector.match(/data-lab-review="([^"]+)"/)?.[1]];
  } };
  return { view, note, applyButton, buttons, root };
}

const request = { provider: 'ridi', manga: 'obra', chapter: '1', page: 'page.png' };
const response = { ...request, treatment: 'degrade', run_id: 'a'.repeat(32), version: 'v1',
  current_image_url: '/current.png', candidate_image_url: '/candidate.png' };

async function connect(propose, apply = async () => ({}), confirm = async () => true) {
  const pieces = fixture();
  const load = browserModules({ AbortController, propose, apply, confirm, view: pieces.view }, {
    '/_app/api/laboratorio.js': `export function getFinalLaboratoryProposal(payload, signal) { return globalThis.propose(payload, signal); }
      export function applyFinalLaboratory(payload) { return globalThis.apply(payload); }`,
    '/_shared/messages/messages.js': 'export function confirmMessage() { return globalThis.confirm(); }',
    '/texto_off/laboratorio/final_review_view.js': 'export function createFinalReviewView() { return globalThis.view; }',
  });
  const { connectFinalReview } = await load('/texto_off/laboratorio/final_review.js');
  return { ...pieces, review: connectFinalReview(pieces.root) };
}

test('resultado só pode ser selecionado após proposta e duas imagens carregadas', async () => {
  const pending = deferred();
  let sent, signal;
  const { review, view, note, applyButton, buttons } = await connect((payload, active) => {
    sent = payload; signal = active; return pending.promise;
  });
  review.ready('degrade', request, response.run_id);
  assert.equal(buttons.degrade.hidden, false);
  buttons.degrade.dispatch('click');
  assert.equal(JSON.stringify(sent), JSON.stringify({
    ...request, treatment: 'degrade', run_id: response.run_id,
  }));
  assert.equal(view.select.disabled, true);
  pending.resolve(response);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(view.current.src, '/current.png');
  assert.equal(view.candidate.src, '/candidate.png');
  view.current.onload();
  assert.equal(view.select.disabled, true);
  view.candidate.onload();
  assert.equal(view.select.disabled, false);
  view.select.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(review.getSelection().version, 'v1');
  assert.equal(applyButton.hidden, false);
  assert.match(note.textContent, /Degradê selecionado após comparação/);
  assert.equal(signal.aborted, true);
  review.clear('degrade');
  assert.equal(buttons.degrade.hidden, true);
  assert.equal(applyButton.hidden, true);
  assert.equal(review.getSelection(), null);
  review.dispose();
});

test('comparação usa capítulo e página oficiais retornados para arquivo clean', async () => {
  const selected = { ...request, chapter: 'clean', page: 'page_clean.png' };
  const { review, view, buttons } = await connect(async () => response);
  review.ready('degrade', selected, response.run_id);
  buttons.degrade.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.match(view.page.textContent, /Cap\. 1 · page\.png/);
  review.dispose();
});

test('mudança de seleção descarta comparação ainda pendente', async () => {
  const pending = deferred();
  let signal;
  const { review, view, buttons } = await connect((_payload, active) => {
    signal = active; return pending.promise;
  });
  review.ready('degrade', request, response.run_id);
  buttons.degrade.dispatch('click');
  review.clear('degrade');
  assert.equal(signal.aborted, true);
  assert.equal(view.dialog.open, false);
  pending.resolve(response);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(view.current.src, '');
  assert.equal(review.getSelection(), null);
  review.dispose();
});

test('falha ao carregar uma das imagens bloqueia a seleção', async () => {
  const { review, view, buttons } = await connect(async () => response);
  review.ready('degrade', request, response.run_id);
  buttons.degrade.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  view.current.onload();
  view.candidate.onerror();
  assert.equal(view.select.disabled, true);
  view.select.dispatch('click');
  assert.equal(review.getSelection(), null);
  review.dispose();
});

test('versão alterada durante a revisão não é selecionada', async () => {
  let calls = 0;
  const { review, view, buttons } = await connect(async () => ({
    ...response, version: ++calls === 1 ? 'v1' : 'v2',
  }));
  review.ready('degrade', request, response.run_id);
  buttons.degrade.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  view.current.onload();
  view.candidate.onload();
  view.select.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(review.getSelection(), null);
  assert.match(view.status.textContent, /versão final mudou/);
  assert.equal(view.select.disabled, true);
  review.dispose();
});

test('aplicar usa a versão revisada e exige confirmação explícita', async () => {
  const calls = [];
  const { review, view, buttons, applyButton, note } = await connect(
    async () => response, async (payload) => { calls.push(payload); return { status: 'applied' }; });
  review.ready('degrade', request, response.run_id);
  buttons.degrade.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  view.current.onload(); view.candidate.onload(); view.select.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  applyButton.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].version, 'v1');
  assert.equal(calls[0].confirmed, true);
  assert.equal(review.getSelection(), null);
  assert.equal(applyButton.hidden, true);
  assert.match(note.textContent, /aplicado ao Consolidado Final/);
  review.dispose();
});

test('cancelamento não envia publicação', async () => {
  let applied = false;
  const { review, view, buttons, applyButton } = await connect(async () => response,
    async () => { applied = true; }, async () => false);
  review.ready('degrade', request, response.run_id);
  buttons.degrade.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  view.current.onload(); view.candidate.onload(); view.select.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  applyButton.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(applied, false);
  assert.equal(review.getSelection().version, 'v1');
  review.dispose();
});

test('resposta de aplicação não reaparece após mudar a página', async () => {
  const pending = deferred();
  const { review, view, buttons, applyButton, note } = await connect(
    async () => response, () => pending.promise);
  review.ready('degrade', request, response.run_id);
  buttons.degrade.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  view.current.onload(); view.candidate.onload(); view.select.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  applyButton.dispatch('click');
  await new Promise((resolve) => setTimeout(resolve, 0));
  review.clear('degrade');
  pending.resolve({ status: 'applied' });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(note.hidden, true);
  assert.equal(review.getSelection(), null);
  review.dispose();
});
