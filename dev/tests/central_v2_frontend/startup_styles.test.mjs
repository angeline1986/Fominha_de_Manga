import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

function fakeLink(loaded = false) {
  const listeners = new Map();
  return {
    sheet: loaded ? {} : null,
    addEventListener(type, listener) { listeners.set(type, listener); },
    removeEventListener(type) { listeners.delete(type); },
    cloneNode() { return fakeLink(); },
    fire(type) { listeners.get(type)?.(); },
    replaceWith(replacement) { this.replacement = replacement; },
  };
}

function loadStyles(link) {
  const load = browserModules({
    document: { querySelectorAll: () => [link] }, setTimeout, clearTimeout,
  });
  return load('/_app/startup_styles.js');
}

test('estilo carregado permite abrir a interface', async () => {
  const link = fakeLink(true);
  const { ensureStylesheets } = await loadStyles(link);
  await ensureStylesheets();
  assert.equal(link.replacement, undefined);
});

test('estilo que falhou é carregado novamente antes de abrir a interface', async () => {
  const link = fakeLink();
  const { ensureStylesheets } = await loadStyles(link);
  const pending = ensureStylesheets();
  link.fire('error');
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(link.replacement);
  link.replacement.sheet = {};
  link.replacement.fire('load');
  await pending;
});

test('falha persistente impede abertura com layout incompleto', async () => {
  const link = fakeLink();
  const { ensureStylesheets } = await loadStyles(link);
  const pending = ensureStylesheets();
  link.fire('error');
  await new Promise((resolve) => setImmediate(resolve));
  link.replacement.fire('error');
  await assert.rejects(pending, /Não foi possível carregar os estilos/);
});
