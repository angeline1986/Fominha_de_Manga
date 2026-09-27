import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

async function setup() {
  const dialogs = [];
  let focused;
  function node() {
    const listeners = {};
    return {
      isConnected: true,
      children: [],
      setAttribute() {},
      append(...children) { this.children.push(...children); },
      addEventListener(name, handler) { listeners[name] = handler; },
      fire(name) { listeners[name]?.({ preventDefault() {} }); },
      focus() { focused = this; },
    };
  }
  const origin = node();
  const document = {
    activeElement: origin,
    body: { append(dialog) { dialogs.push(dialog); } },
    createElement() {
      const children = new Map();
      return Object.assign(node(), {
        querySelector(selector) {
          if (!children.has(selector)) children.set(selector, node());
          return children.get(selector);
        },
        showModal() {},
        close(value) { this.returnValue = value; this.fire('close'); },
        remove() { this.removed = true; },
      });
    },
  };
  const load = browserModules({ document });
  const api = await load('/_shared/messages/messages.js');
  return { api, dialogs, origin, focused: () => focused };
}
const tick = () => new Promise((resolve) => setImmediate(resolve));

test('confirmation renders text safely, focuses cancel and restores focus on acceptance', async () => {
  const ui = await setup();
  const result = ui.api.confirmMessage({ title: 'Finalizar', message: '<b>texto</b>' });
  await tick();
  const dialog = ui.dialogs[0];
  assert.equal(dialog.querySelector('p').textContent, '<b>texto</b>');
  assert.equal(ui.focused(), dialog.querySelector('[data-cancel]'));
  dialog.querySelector('[data-accept]').fire('click');
  assert.equal(await result, true);
  assert.equal(dialog.removed, true);
  assert.equal(ui.focused(), ui.origin);
});

test('Escape dismisses confirmation and queued messages open one at a time', async () => {
  const ui = await setup();
  const first = ui.api.confirmMessage({ title: 'Confirmar', message: 'Ação' });
  const second = ui.api.showMessage({ title: 'Aviso', message: 'Mensagem' });
  await tick();
  assert.equal(ui.dialogs.length, 1);
  ui.dialogs[0].fire('cancel');
  assert.equal(await first, false);
  await tick();
  assert.equal(ui.dialogs.length, 2);
  const dialog = ui.dialogs[1];
  assert.equal(dialog.querySelector('[data-cancel]').hidden, true);
  assert.equal(ui.focused(), dialog.querySelector('[data-accept]'));
  dialog.querySelector('[data-close]').fire('click');
  assert.equal(await second, false);
});

test('operation summary uses the shared dialog and renders chapter details as text', async () => {
  const ui = await setup();
  const result = ui.api.showOperationSummary({
    summary: {
      headline: '1 capítulo processado',
      breakdown: '1 parcial',
      items: [{
        chapter: '11', status: 'Concluído parcialmente', count: '12 merges', warning: true,
        details: [['Residual', '6200–20200 px']],
      }],
    },
  });
  await tick();
  const dialog = ui.dialogs[0];
  assert.match(dialog.className, /message-summary-dialog/);
  assert.equal(dialog.querySelector('[data-caption]').hidden, false);
  assert.equal(dialog.querySelector('[data-headline]').textContent, '1 capítulo processado');
  assert.equal(dialog.querySelector('[data-breakdown]').textContent, '1 parcial');
  const row = dialog.querySelector('[data-items]').children[0];
  assert.equal(row.children[0].children[0].textContent, 'Cap. 11');
  assert.equal(row.children[0].children[1].textContent, 'Concluído parcialmente');
  assert.equal(dialog.querySelector('[data-accept]').textContent, 'Fechar');
  dialog.querySelector('[data-accept]').fire('click');
  assert.equal(await result, true);
});
