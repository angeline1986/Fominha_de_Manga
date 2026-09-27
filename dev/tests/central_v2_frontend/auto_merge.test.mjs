import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred } from './modules.mjs';

async function setup(selected = false) {
  const requests = [];
  const load = browserModules({
    AbortController,
    fetch(url, options) {
      const request = deferred();
      requests.push({ ...request, url, signal: options.signal });
      return request.promise;
    },
  });
  const context = await load('/_app/state/context.js');
  context.setCatalog({ comix: ['A', 'B'] });
  if (selected) { context.selectProvider('comix'); context.selectManga('A'); }
  const { createLevel1Store } = await load('/_app/state/auto_merge.js');
  const { connectLevel1 } = await load('/_app/auto_merge/controller.js');
  const store = createLevel1Store();
  const controller = connectLevel1(store);
  return { context, requests, store, controller, load };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));
function reply(request, manga, chapters = []) {
  request.resolve({ ok: true, json: async () => ({ provider: 'comix', manga, chapters }) });
}

test('query waits for a work and loads the selected context', async () => {
  const { context, requests, store, controller } = await setup();
  assert.equal(requests.length, 0);
  assert.equal(store.get().status, 'idle');
  context.selectProvider('comix');
  context.selectManga('A');
  assert.equal(store.get().status, 'loading');
  assert.match(requests[0].url, /provider=comix&manga=A/);
  reply(requests[0], 'A', [{ chapter: '1' }]);
  await tick();
  assert.equal(store.get().status, 'ready');
  assert.equal(store.get().chapters[0].chapter, '1');
  controller.dispose();
});

test('context switch clears old rows and discards late responses', async () => {
  const { context, requests, store, controller } = await setup(true);
  context.selectManga('B');
  assert.equal(requests[0].signal.aborted, true);
  reply(requests[1], 'B', [{ chapter: '2' }]);
  await tick();
  reply(requests[0], 'A', [{ chapter: '1' }]);
  await tick();
  assert.equal(store.get().manga, 'B');
  assert.equal(store.get().chapters[0].chapter, '2');
  context.selectProvider('comix');
  assert.equal(store.get().status, 'idle');
  assert.equal(store.get().chapters.length, 0);
  controller.dispose();
});

test('HTTP errors are visible and refresh retries the current work', async () => {
  const { requests, store, controller } = await setup(true);
  requests[0].resolve({ ok: false, status: 500, json: async () => ({ error: 'Unreadable' }) });
  await tick();
  assert.equal(store.get().status, 'error');
  assert.equal(store.get().error, 'Unreadable');
  const refresh = controller.refresh();
  reply(requests[1], 'A');
  await refresh;
  assert.equal(store.get().status, 'ready');
  assert.equal(store.get().error, '');
  controller.dispose();
});

test('leaving the page stops requests and context subscriptions', async () => {
  const { context, requests, store, controller } = await setup(true);
  controller.dispose();
  assert.equal(requests[0].signal.aborted, true);
  let notifications = 0;
  store.subscribe(() => { notifications += 1; });
  reply(requests[0], 'A');
  await tick();
  context.selectManga('B');
  await controller.refresh();
  assert.equal(requests.length, 1);
  assert.equal(notifications, 0);
});

test('response for a different work is rejected', async () => {
  const { requests, store, controller } = await setup(true);
  reply(requests[0], 'B');
  await tick();
  assert.equal(store.get().status, 'error');
  assert.equal(store.get().chapters.length, 0);
  controller.dispose();
});

test('record labels do not treat missing artifacts as completed work', async () => {
  const { load, controller } = await setup();
  const { level1Label, needsAttention } = await load('/processamento/auto_merge/registros.js');
  const record = { status: 'recorded', kind: 'complete', artifacts: [{ exists: false }] };
  assert.equal(level1Label(record), 'Arquivos ausentes');
  assert.equal(needsAttention({ level1: record, official: {}, attempt: {} }), true);
  assert.equal(level1Label({ status: 'absent' }), 'Sem registro');
  controller.dispose();
});
