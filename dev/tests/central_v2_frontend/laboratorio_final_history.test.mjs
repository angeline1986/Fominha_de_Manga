import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred } from './modules.mjs';

class Element {
  constructor() {
    this.hidden = true; this.disabled = true; this.textContent = '';
    this.src = ''; this.open = false; this.value = ''; this.options = [];
    this.listeners = {};
  }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener(type, fn) {
    this.listeners[type] = (this.listeners[type] || []).filter((item) => item !== fn);
  }
  dispatch(type) { for (const fn of this.listeners[type] || []) fn(); }
  removeAttribute(name) { if (name === 'src') this.src = ''; }
  replaceChildren() { this.options = []; this.value = ''; }
  append(option) { this.options.push(option); if (this.options.length === 1) this.value = option.value; }
  showModal() { this.open = true; }
  close() { this.open = false; this.dispatch('close'); }
}

const identity = { provider: 'ridi', manga: 'obra', chapter: '1', page: 'page.png' };
const history = { ...identity, version: 'v1', current_image_url: '/current.png',
  revisions: [{ revision_id: 'r1', sha256: 'a'.repeat(64), origin: 'PINCEL_SUAVE',
    image_url: '/old.png' }] };

async function connect(read, write = async () => ({}), confirm = async () => true) {
  const button = new Element();
  const names = ['dialog', 'page', 'status', 'current', 'candidate', 'select',
    'close', 'cancel', 'picker'];
  const view = Object.fromEntries(names.map((name) => [name, new Element()]));
  view.dispose = () => { view.disposed = true; };
  const root = { querySelector: () => button };
  const load = browserModules({ AbortController, read, write, confirm, view,
    document: { createElement: () => new Element() } }, {
    '/_app/api/laboratorio.js': `export function getFinalLaboratoryHistory(identity, signal) { return globalThis.read(identity, signal); }
      export function restoreFinalLaboratory(payload) { return globalThis.write(payload); }`,
    '/_shared/messages/messages.js': 'export function confirmMessage() { return globalThis.confirm(); }',
    '/texto_off/laboratorio/final_history_view.js':
      'export function createFinalHistoryView() { return globalThis.view; }',
  });
  const { connectFinalHistory } = await load('/texto_off/laboratorio/final_history.js');
  return { button, view, controller: connectFinalHistory(root, () => identity) };
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

test('histórico exige duas imagens carregadas e confirmação para restaurar', async () => {
  const writes = [];
  const { button, view, controller } = await connect(async () => history,
    async (payload) => { writes.push(payload); });
  assert.equal(button.hidden, false);
  button.dispatch('click'); await tick();
  assert.equal(view.current.src, '/current.png');
  assert.equal(view.candidate.src, '/old.png');
  view.select.dispatch('click'); await tick();
  assert.equal(writes.length, 0);
  view.current.onload(); view.candidate.onload();
  assert.equal(view.select.disabled, false);
  view.select.dispatch('click'); await tick();
  assert.equal(writes.length, 1);
  assert.equal(writes[0].version, 'v1');
  assert.equal(writes[0].revision_id, 'r1');
  assert.equal(writes[0].confirmed, true);
  assert.match(view.status.textContent, /Versão restaurada/);
  controller.dispose();
});

test('cancelamento e troca de página impedem restauração', async () => {
  let writes = 0;
  const { button, view, controller } = await connect(async () => history,
    async () => { writes++; }, async () => false);
  button.dispatch('click'); await tick();
  view.current.onload(); view.candidate.onload();
  view.select.dispatch('click'); await tick();
  assert.equal(writes, 0);
  controller.pageChanged();
  assert.equal(view.dialog.open, false);
  controller.dispose();
});

test('resposta tardia e erro de imagem não permitem restaurar', async () => {
  const pending = deferred();
  let calls = 0;
  const { button, view, controller } = await connect(() =>
    ++calls === 1 ? pending.promise : Promise.resolve(history));
  button.dispatch('click');
  controller.pageChanged();
  pending.resolve(history); await tick();
  assert.equal(view.current.src, '');
  button.dispatch('click'); await tick();
  view.current.onload(); view.candidate.onerror();
  assert.equal(view.select.disabled, true);
  controller.dispose();
});
