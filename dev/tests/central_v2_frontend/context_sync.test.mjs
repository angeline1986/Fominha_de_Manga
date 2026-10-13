import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred, mangaState, textDocument } from './modules.mjs';

const json = (body, ok = true, status = 200) => ({ ok, status, json: async () => body });

async function controllerSetup(fetch, manga = 'A') {
  const load = browserModules({ fetch, document: textDocument });
  const context = await load('/_app/state/context.js');
  context.setCatalog({ comix: ['A', 'B'] });
  context.selectProvider('comix');
  context.selectManga(manga);
  const state = await load('/_app/state/manga_state.js');
  if (manga) state.setMangaState(mangaState(manga, 1));
  const controller = await load('/_app/context/context_controller.js');
  return { context, state, controller };
}

test('synchronization refreshes catalog and selected work state', async () => {
  const requests = [];
  const { context, state, controller } = await controllerSetup(async (url) => {
    requests.push(url);
    return url === '/api/catalog' ? json({ comix: ['A', 'B', 'C'] })
      : json(mangaState('A', 4));
  });
  await controller.synchronizeContext();
  assert.deepEqual(requests, ['/api/catalog', '/api/state?provider=comix&manga=A']);
  assert.equal(context.getContext().provider, 'comix');
  assert.equal(context.getContext().manga, 'A');
  assert.deepEqual(Array.from(state.getMangaState().chapters), ['1']);
  assert.equal(state.getMangaState().summary.chapters, 4);
});

test('synchronization without selected work only refreshes the catalog', async () => {
  const requests = [];
  const { context, controller } = await controllerSetup(async (url) => {
    requests.push(url);
    return json({ comix: ['A', 'B', 'C'] });
  }, '');
  await controller.synchronizeContext();
  assert.deepEqual(requests, ['/api/catalog']);
  assert.equal(context.getContext().provider, 'comix');
  assert.equal(context.getContext().manga, null);
});

test('catalog failure preserves current context and work state', async () => {
  const { context, state, controller } = await controllerSetup(async () => json({}, false, 503));
  await assert.rejects(controller.synchronizeContext(), /catálogo \(503\)/);
  assert.equal(context.getContext().provider, 'comix');
  assert.equal(context.getContext().manga, 'A');
  assert.equal(state.getMangaState().manga, 'A');
});

test('selected work state failure reports an error without discarding loaded data', async () => {
  const { context, state, controller } = await controllerSetup(async (url) => url === '/api/catalog'
    ? json({ comix: ['A', 'B'] }) : json({}, false, 503));
  await assert.rejects(controller.synchronizeContext(), /estado da obra \(503\)/);
  assert.equal(context.getContext().manga, 'A');
  assert.equal(state.getMangaState().manga, 'A');
});

test('removed provider clears only the now-invalid provider and dependent work', async () => {
  const requests = [];
  const { context, state, controller } = await controllerSetup(async (url) => {
    requests.push(url);
    return json({ mangago: ['B'] });
  });
  await controller.synchronizeContext();
  assert.deepEqual(requests, ['/api/catalog']);
  assert.equal(context.getContext().provider, null);
  assert.equal(context.getContext().manga, null);
  assert.equal(state.getMangaState().manga, null);
});

test('removed work keeps its provider and clears only the invalid work', async () => {
  const requests = [];
  const { context, state, controller } = await controllerSetup(async (url) => {
    requests.push(url);
    return json({ comix: ['B'] });
  });
  await controller.synchronizeContext();
  assert.deepEqual(requests, ['/api/catalog']);
  assert.equal(context.getContext().provider, 'comix');
  assert.equal(context.getContext().manga, null);
  assert.equal(state.getMangaState().manga, null);
});

test('concurrent synchronization is single-flight and preserves a newer selection', async () => {
  const catalog = deferred();
  const workState = deferred();
  const requests = [];
  const { context, state, controller } = await controllerSetup((url) => {
    requests.push(url);
    if (url === '/api/catalog') return catalog.promise;
    return workState.promise;
  });
  const firstSync = controller.synchronizeContext();
  const secondSync = controller.synchronizeContext();
  assert.equal(firstSync, secondSync);
  const change = controller.changeManga('B');
  catalog.resolve(json({ comix: ['A', 'B', 'C'] }));
  await firstSync;
  workState.resolve(json(mangaState('B', 7)));
  await change;
  assert.deepEqual(requests, ['/api/catalog', '/api/state?provider=comix&manga=B']);
  assert.equal(context.getContext().manga, 'B');
  assert.equal(state.getMangaState().manga, 'B');
  assert.equal(state.getMangaState().summary.chapters, 7);
});

test('synchronization reuses an active state request for the selected work', async () => {
  const workState = deferred();
  const requests = [];
  const { state, controller } = await controllerSetup((url) => {
    requests.push(url);
    return url === '/api/catalog' ? Promise.resolve(json({ comix: ['A', 'B'] })) : workState.promise;
  });
  const selection = controller.changeManga('A');
  const sync = controller.synchronizeContext();
  for (let attempt = 0; attempt < 10 && requests.length < 2; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  assert.deepEqual(requests, ['/api/state?provider=comix&manga=A', '/api/catalog']);
  await new Promise((resolve) => setTimeout(resolve, 0));
  workState.resolve(json(mangaState('A', 6)));
  await Promise.all([selection, sync]);
  assert.equal(state.getMangaState().summary.chapters, 6);
  assert.equal(requests.filter((url) => url.startsWith('/api/state')).length, 1);
});

test('late refreshed state cannot replace a work selected during synchronization', async () => {
  const refreshedA = deferred();
  const requests = [];
  const loadB = mangaState('B', 9);
  const { context, state, controller } = await controllerSetup(async (url) => {
    requests.push(url);
    if (url === '/api/catalog') return json({ comix: ['A', 'B'] });
    if (url.endsWith('manga=A')) return refreshedA.promise;
    return json(loadB);
  });
  const sync = controller.synchronizeContext();
  for (let attempt = 0; attempt < 10 && !requests.some((url) => url.endsWith('manga=A')); attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  const change = controller.changeManga('B');
  await change;
  refreshedA.resolve(json(mangaState('A', 99)));
  await sync;
  assert.equal(context.getContext().manga, 'B');
  assert.equal(state.getMangaState().manga, 'B');
  assert.equal(state.getMangaState().summary.chapters, 9);
  assert.deepEqual(requests, ['/api/catalog', '/api/state?provider=comix&manga=A', '/api/state?provider=comix&manga=B']);
});
