import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred, mangaState, textDocument } from './modules.mjs';

async function setup(globals = {}, sources = {}) {
  const load = browserModules({ document: textDocument, ...globals }, {
    '/fixtures/other.js': 'export function render(c) { c.innerHTML = "Other"; }',
    ...sources,
  });
  const { routes } = await load('/_app/router/routes.js');
  routes.other = { module: '/fixtures/other.js' };
  const router = await load('/_app/router/router.js');
  const state = await load('/_app/state/manga_state.js');
  return { router, state, routes };
}

test('leaving summary releases its listener; returning does not duplicate it', async () => {
  const { router, state } = await setup();
  let html = '';
  let writes = 0;
  const container = {
    set innerHTML(value) { html = value; writes += 1; },
    get innerHTML() { return html; },
  };
  await router.navigate('resumo-operacao', container);
  await router.navigate('other', container);
  state.setMangaState(mangaState('A'));
  assert.equal(html, 'Other');
  await router.navigate('resumo-operacao', container);
  await router.navigate('resumo-operacao', container);
  const before = writes;
  state.setMangaState(mangaState('B'));
  assert.equal(writes, before + 1);
  router.disposePage(container);
  const disposed = writes;
  state.clearMangaState();
  assert.equal(writes, disposed);
});

test('unknown routes preserve the active page and its subscription', async () => {
  const { router, state } = await setup();
  const container = { innerHTML: '' };
  await router.navigate('resumo-operacao', container);
  await assert.rejects(router.navigate('missing', container), /Rota não encontrada/);
  state.setMangaState(mangaState('A'));
  assert.match(container.innerHTML, />A<\/strong>/);
});

test('late page imports cannot overwrite the most recent navigation', async () => {
  const gate = deferred();
  const started = deferred();
  const { router, routes } = await setup({ gate: gate.promise, started: started.resolve }, {
    '/fixtures/slow.js': 'started(); await gate; export function render(c) { c.innerHTML = "Slow"; }',
  });
  routes.slow = { module: '/fixtures/slow.js' };
  const container = { innerHTML: '' };
  const pending = router.navigate('slow', container);
  await started.promise;
  await router.navigate('other', container);
  gate.resolve();
  await pending;
  assert.equal(container.innerHTML, 'Other');
});

test('disposing a container also invalidates an unfinished navigation', async () => {
  const gate = deferred();
  const started = deferred();
  const { router, routes } = await setup({ gate: gate.promise, started: started.resolve }, {
    '/fixtures/slow.js': 'started(); await gate; export function render(c) { c.innerHTML = "Slow"; }',
  });
  routes.slow = { module: '/fixtures/slow.js' };
  const container = { innerHTML: 'Initial' };
  const pending = router.navigate('slow', container);
  await started.promise;
  router.disposePage(container);
  gate.resolve();
  await pending;
  assert.equal(container.innerHTML, 'Initial');
});
