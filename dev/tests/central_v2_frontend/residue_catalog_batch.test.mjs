import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

const box = { left: .1, top: .2, width: .3, height: .2 };
function manifestRow(id) {
  return { id, numero: 1, tipo: 'residuo_transparencia', observacao: null, box_normalized: box };
}
function response(payload, status = 200) {
  return { ok: status >= 200 && status < 300, status, async json() { return payload; } };
}
async function setup({ initial = {}, postMode = 'success', onDraftState = () => {} } = {}) {
  const stored = new Map(Object.entries(initial)), calls = [];
  const fetch = async (url, options = {}) => {
    calls.push({ url, options });
    if (options.method !== 'POST') {
      const page = new URL(url, 'http://central').searchParams.get('page');
      const occurrences = stored.get(page) || [];
      return response({ occurrences, cataloged: occurrences.length > 0 });
    }
    const payload = JSON.parse(options.body);
    if (postMode === 'reject') return response({ error: 'lote rejeitado' }, 400);
    for (const item of payload.pages) stored.set(item.page, item.occurrences.map((row) => ({
      id: row.id, tipo: row.type, observacao: row.note,
      box_normalized: row.box_normalized,
    })));
    if (postMode === 'commit-then-drop') throw new TypeError('conexão interrompida');
    return response({ pages: payload.pages.map((item) => ({
      page: item.page, total_occurrences: item.occurrences.length,
      occurrences: item.occurrences.map((row) => ({ id: row.id, tipo: row.type,
        observacao: row.note, box_normalized: row.box_normalized })),
    })) });
  };
  const load = browserModules({ fetch, AbortController });
  const { createResidueCatalogState } = await load('/texto_off/comparison/residue_catalog_state.js');
  const state = createResidueCatalogState({ provider: 'ridi', manga: 'obra', chapter: '12', step: '1' },
    () => {}, () => {}, onDraftState);
  return { state, stored, calls };
}

test('draft indicator follows current state and persisted removal stays dirty on failure', async () => {
  const states = [], persisted = { 'page-2.png': [manifestRow('old')] };
  const env = await setup({ initial: persisted, postMode: 'reject',
    onDraftState: (page, count, dirty) => states.push([page, count, dirty]) });
  await env.state.setPage('page-2.png');
  assert.deepEqual(states.at(-1), ['page-2.png', 1, false]);
  env.state.add({ ...box }, 'new-draft');
  assert.deepEqual(states.at(-1), ['page-2.png', 2, true]);
  env.state.remove('old');
  assert.deepEqual(states.at(-1), ['page-2.png', 1, true]);
  env.state.remove('new-draft');
  assert.deepEqual(states.at(-1), ['page-2.png', 0, true]);
  assert.equal(env.state.canSaveChapter(), true);
  assert.equal((await env.state.saveChapter()).ok, false);
  assert.deepEqual(states.at(-1), ['page-2.png', 0, true]);
  assert.equal(env.state.current().dirty, true);
  assert.equal(env.stored.get('page-2.png').length, 1);
  env.state.dispose();

  const draftStates = [], fresh = await setup({
    onDraftState: (page, count, dirty) => draftStates.push([page, count, dirty]),
  });
  await fresh.state.setPage('page-new.png');
  fresh.state.add({ ...box }, 'temporary');
  assert.deepEqual(draftStates.at(-1), ['page-new.png', 1, true]);
  fresh.state.remove('temporary');
  assert.deepEqual(draftStates.at(-1), ['page-new.png', 0, false]);
  assert.equal(fresh.state.canSaveChapter(), false);
  fresh.state.dispose();
});

test('chapter batch keeps page drafts while navigating and saves from a clean page', async () => {
  const counts = [], env = await setup({ onDraftState: (page, count) => counts.push([page, count]) });
  for (const page of ['page-2.png', 'page-5.png', 'page-15.png']) {
    await env.state.setPage(page);
    env.state.add({ ...box }, `${page}-occ`);
  }
  await env.state.setPage('page-10.png');
  await env.state.setPage('page-2.png');
  assert.equal(env.state.current().occurrences[0].id, 'page-2.png-occ');
  assert.equal(env.state.dirtyPageCount(), 3);
  await env.state.setPage('page-10.png');
  assert.equal(env.state.canSaveChapter(), true);
  const result = await env.state.saveChapter();
  const request = JSON.parse(env.calls.find((call) => call.options.method === 'POST').options.body);
  assert.equal(result.savedPages, 3);
  assert.deepEqual(request.pages.map((item) => item.page), ['page-15.png', 'page-2.png', 'page-5.png']);
  assert.equal(env.state.dirtyPageCount(), 0);
  assert.deepEqual(['page-2.png', 'page-5.png', 'page-15.png'].map((page) => env.stored.get(page).length), [1, 1, 1]);
  assert.ok(counts.some(([page, count]) => page === 'page-5.png' && count === 1));
  env.state.dispose();
});

test('network loss after atomic save is reconciled through GET without duplicating IDs', async () => {
  const env = await setup({ postMode: 'commit-then-drop' });
  await env.state.setPage('page-2.png');
  env.state.add({ ...box }, 'stable-occurrence-id');
  const result = await env.state.saveChapter();
  assert.equal(result.ok, true);
  assert.equal(result.reconciled, true);
  assert.equal(env.state.current().dirty, false);
  assert.deepEqual(env.stored.get('page-2.png').map((item) => item.id), ['stable-occurrence-id']);
  assert.equal(env.calls.filter((call) => call.options.method === 'POST').length, 1);
  assert.equal(env.calls.filter((call) => call.options.method !== 'POST').length, 2);
  env.state.dispose();
});
