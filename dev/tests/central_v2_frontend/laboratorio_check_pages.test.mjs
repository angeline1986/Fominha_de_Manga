import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

test('Laboratório inicia no Glass e alterna as quatro origens', async () => {
  const urls = [], listeners = new Map();
  const root = {
    addEventListener(name, listener) { listeners.set(name, listener); },
    removeEventListener(name) { listeners.delete(name); },
    dispatchEvent(event) { listeners.get(event.type)?.(event); },
  };
  const load = browserModules({ AbortController, CustomEvent: class {
    constructor(type, options) { this.type = type; this.detail = options.detail; }
  }, fetch: async (url) => {
    urls.push(url);
    return { ok: true, json: async () => ({ chapters: {} }) };
  } }, {
    '/_app/state/context.js': `export function getContext() {
      return { provider: 'comix', manga: 'Obra' };
    } export function subscribeContext() { return () => {}; }`,
  });
  const { connectLaboratorio } = await load('/texto_off/laboratorio/data_loader.js');
  const disconnect = connectLaboratorio(root);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(new URL(urls[0], 'http://localhost').searchParams.get('source'), 'glass');
  root.dispatchEvent({ type: 'laboratorio:source', detail: { source: 'merge' } });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(new URL(urls[1], 'http://localhost').searchParams.get('source'), 'merge');
  assert.equal(new URL(urls[1], 'http://localhost').searchParams.get('check_other'), '1');
  root.dispatchEvent({ type: 'laboratorio:source', detail: { source: 'img' } });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(new URL(urls[2], 'http://localhost').searchParams.get('source'), 'img');
  assert.equal(new URL(urls[2], 'http://localhost').searchParams.has('check_other'), false);
  root.dispatchEvent({ type: 'laboratorio:source', detail: { source: 'check' } });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(new URL(urls[3], 'http://localhost').searchParams.get('source'), 'check');
  assert.equal(new URL(urls[3], 'http://localhost').searchParams.has('check_other'), false);
  disconnect();
});
