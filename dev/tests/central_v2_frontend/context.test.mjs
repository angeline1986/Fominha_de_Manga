import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred, mangaState, textDocument } from './modules.mjs';

async function setup() {
  const requests = [];
  const load = browserModules({
    document: textDocument,
    fetch() {
      const request = deferred();
      requests.push(request);
      return request.promise;
    },
  });
  const context = await load('/_app/state/context.js');
  context.setCatalog({ comix: ['A', 'B'], mangago: [] });
  const controller = await load('/_app/context/context_controller.js');
  controller.changeProvider('comix');
  const state = await load('/_app/state/manga_state.js');
  const router = await load('/_app/router/router.js');
  const container = { innerHTML: '' };
  await router.navigate('resumo-operacao', container);
  return { controller, state, router, container, requests };
}

function reply(request, manga, count = 3) {
  request.resolve({ ok: true, json: async () => mangaState(manga, count) });
}

test('open summary follows completed loads, clearing and provider changes', async () => {
  const { controller, container, requests } = await setup();
  assert.match(container.innerHTML, /Nenhuma obra selecionada/);
  const pending = controller.changeManga('A');
  assert.match(container.innerHTML, /Nenhuma obra selecionada/);
  reply(requests[0], 'A', 65);
  await pending;
  assert.match(container.innerHTML, />A<\/strong>/);
  assert.match(container.innerHTML, />65<\/strong>/);
  await controller.changeManga('');
  assert.match(container.innerHTML, /Nenhuma obra selecionada/);
  const next = controller.changeManga('B');
  reply(requests[1], 'B');
  await next;
  controller.changeProvider('mangago');
  assert.match(container.innerHTML, /Nenhuma obra selecionada/);
});

test('older responses cannot replace the selected work or provider', async () => {
  const { controller, state, requests } = await setup();
  const first = controller.changeManga('A');
  const second = controller.changeManga('B');
  reply(requests[1], 'B');
  await second;
  reply(requests[0], 'A');
  await first;
  assert.equal(state.getMangaState().manga, 'B');
  const third = controller.changeManga('A');
  controller.changeProvider('mangago');
  reply(requests[2], 'A');
  await third;
  assert.equal(state.getMangaState().manga, null);
});

test('failed loads leave no data from the previous work on the page', async () => {
  const { controller, container, requests } = await setup();
  const first = controller.changeManga('A');
  reply(requests[0], 'A');
  await first;
  const second = controller.changeManga('B');
  requests[1].resolve({ ok: false, status: 500 });
  await assert.rejects(second, /500/);
  assert.match(container.innerHTML, /Nenhuma obra selecionada/);
  assert.doesNotMatch(container.innerHTML, />A<\/strong>/);
});

test('state subscriptions publish final values and can be released', async () => {
  const { state } = await setup();
  const seen = [];
  const unsubscribe = state.subscribeMangaState((value) => seen.push(value.manga));
  state.setMangaState(mangaState('A'));
  state.clearMangaState();
  unsubscribe();
  state.setMangaState(mangaState('B'));
  assert.deepEqual(seen, ['A', null]);
  const snapshot = state.getMangaState();
  snapshot.chapters.push('unexpected');
  assert.equal(state.getMangaState().chapters.length, 1);
});
