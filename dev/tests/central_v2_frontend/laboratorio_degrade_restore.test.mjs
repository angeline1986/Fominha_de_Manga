import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

test('Degradê recuperado mantém a seleção e o horário de execução', async () => {
  const events = [];
  const placeholder = { dataset: {}, setAttribute() {}, hidden: false, textContent: '' };
  const panel = { children: [], querySelector: () => placeholder,
    append(item) { this.children.push(item); } };
  const root = { querySelector: (selector) => selector === '[data-lab-card="degrade"]'
    ? panel : null };
  const button = { addEventListener() {}, removeEventListener() {} };
  const load = browserModules({ document: { createElement: () => ({
    hidden: true, removeAttribute() {}, remove() {}, src: '',
  }) } });
  const { connectDegrade } = await load('/texto_off/laboratorio/degrade.js');
  const controller = connectDegrade({ root, button, getRequest: () => null,
    review: { ready: (...args) => events.push(['ready', ...args]) },
    order: { complete: (...args) => events.push(['order', ...args]) } });
  const identity = { provider: 'comix', manga: 'obra', chapter: '1', page: 'page.png' };
  assert.equal(controller.restore({ treatment: 'degrade', run_id: 'run-1',
    image_url: '/preview.png', completed_at: 123 }, identity,
  controller.revision()), true);
  panel.children[0].onload();
  assert.equal(placeholder.dataset.state, 'completed');
  assert.deepEqual(events, [['ready', 'degrade', identity, 'run-1'],
    ['order', 'degrade', 123]]);
  controller.dispose();
});
