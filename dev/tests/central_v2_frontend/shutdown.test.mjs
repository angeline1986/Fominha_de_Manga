import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred } from './modules.mjs';

async function setup(response, confirmed = true) {
  const requests = [];
  let stopped = 0;
  let alerts = 0;
  let handler;
  const button = {
    disabled: false, innerHTML: '<span>Finalizar servidor</span>', textContent: '',
    addEventListener(_, callback) { handler = callback; },
    removeEventListener() { handler = null; },
  };
  const document = { body: { innerHTML: 'Central' } };
  const load = browserModules({
    document,
    window: { close() {}, closed: false },
    confirmPopup: async () => confirmed,
    messagePopup: async () => { alerts += 1; },
    console: { error() {} },
    fetch: async (...args) => { requests.push(args); return await response; },
  }, {
    '/_shared/messages/messages.js': `
      export const confirmMessage = confirmPopup;
      export const showMessage = messagePopup;
    `,
  });
  const { bindShutdown } = await load('/_shell/shutdown.js');
  const dispose = bindShutdown(button, () => { stopped += 1; });
  return {
    button, document, requests, dispose,
    click: () => handler?.(),
    stopped: () => stopped,
    alerts: () => alerts,
  };
}

test('cancelled confirmation does not request shutdown', async () => {
  const ui = await setup(null, false);
  await ui.click();
  assert.equal(ui.requests.length, 0);
  assert.equal(ui.document.body.innerHTML, 'Central');
  ui.dispose();
  assert.equal(ui.click(), undefined);
});

test('HTTP error keeps Central visible and restores the button for retry', async () => {
  const ui = await setup({ ok: false, status: 500 });
  await ui.click();
  assert.equal(ui.stopped(), 0);
  assert.equal(ui.alerts(), 1);
  assert.equal(ui.button.disabled, false);
  assert.equal(ui.button.innerHTML, '<span>Finalizar servidor</span>');
  assert.equal(ui.document.body.innerHTML, 'Central');
});

test('successful HTTP without shutdown acknowledgement is rejected', async () => {
  const ui = await setup({ ok: true, json: async () => ({ status: 'other' }) });
  await ui.click();
  assert.equal(ui.stopped(), 0);
  assert.equal(ui.alerts(), 1);
});

test('acknowledged shutdown disposes application before showing completion', async () => {
  const response = deferred();
  const ui = await setup(response.promise);
  const pending = ui.click();
  await ui.click();
  assert.equal(ui.requests.length, 1);
  assert.equal(ui.button.disabled, true);
  assert.equal(ui.document.body.innerHTML, 'Central');
  response.resolve({ ok: true, json: async () => ({ status: 'shutting_down' }) });
  await pending;
  assert.equal(ui.requests[0][0], '/api/shutdown');
  assert.equal(ui.requests[0][1].method, 'POST');
  assert.equal(ui.stopped(), 1);
  assert.match(ui.document.body.innerHTML, /finalizada com sucesso/);
});
