import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

async function start(loadContext, fastTimeout = false) {
  const retry = { addEventListener(_type, listener) { this.click = listener; } };
  const detail = { textContent: '' };
  const page = {};
  let mounts = 0;
  const root = {
    innerHTML: '',
    addEventListener() {},
    removeEventListener() {},
    querySelector(selector) {
      if (selector === '.startup-detail') return detail;
      if (selector === '[data-startup-retry]') return retry;
      if (selector === '#page-content') return page;
      return null;
    },
  };
  const load = browserModules({
    console: { error() {} },
    document: { querySelector: () => root }, AbortController,
    setTimeout: (callback, delay) => setTimeout(callback,
      delay === 500 || (fastTimeout && delay === 12000) ? 0 : delay),
    clearTimeout,
    loadContext,
    mount: () => { mounts += 1; },
  }, {
    '/_app/context/context_controller.js':
      'export function initializeContext(signal) { return loadContext(signal); }',
    '/_app/router/router.js':
      'export function disposePage() {} export async function navigate() {}',
    '/_shell/shell.js':
      'export function mountShell() { mount(); return () => {}; }',
    '/_shared/messages/messages.js':
      'export async function showMessage() {}',
  });
  await load('/_app/app.js');
  return { root, retry, detail, get mounts() { return mounts; } };
}

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 10));
}

test('falha inicial apresenta erro e permite reabrir sem reiniciar o servidor', async () => {
  let requests = 0;
  const app = await start(async () => {
    requests += 1;
    if (requests <= 2) throw new Error('Catálogo indisponível');
  });
  await settle();
  assert.equal(requests, 2);
  assert.equal(app.mounts, 0);
  assert.match(app.root.innerHTML, /Tentar novamente/);
  assert.equal(app.detail.textContent, 'Catálogo indisponível');

  app.retry.click();
  await settle();
  assert.equal(requests, 3);
  assert.equal(app.mounts, 1);
});

test('falha transitória recebe nova tentativa automática antes de mostrar erro', async () => {
  let requests = 0;
  const app = await start(async () => {
    requests += 1;
    if (requests === 1) throw new Error('Falha transitória');
  });
  await settle();
  assert.equal(requests, 2);
  assert.equal(app.mounts, 1);
  assert.doesNotMatch(app.root.innerHTML, /Tentar novamente/);
});

test('catálogo recebe o sinal de cancelamento da inicialização', async () => {
  let receivedSignal;
  const load = browserModules({ fetch: async (_url, options) => {
    receivedSignal = options.signal;
    return { ok: true, json: async () => ({ comix: [] }) };
  } });
  const { fetchCatalog } = await load('/_app/api/catalog.js');
  const controller = new AbortController();
  await fetchCatalog(controller.signal);
  assert.equal(receivedSignal, controller.signal);
});

test('requisição travada termina em erro visível após o limite de tempo', async () => {
  let requests = 0;
  const app = await start((signal) => {
    requests += 1;
    return new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new Error('Cancelado')));
    });
  }, true);
  await settle();
  assert.equal(requests, 2);
  assert.equal(app.mounts, 0);
  assert.match(app.root.innerHTML, /Tentar novamente/);
  assert.match(app.detail.textContent, /demorou demais/);
});
