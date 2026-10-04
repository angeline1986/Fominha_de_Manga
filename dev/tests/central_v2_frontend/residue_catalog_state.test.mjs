import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

const savedItem = { id: 'persisted-id', numero: 3, tipo: 'texto_residual', observacao: null,
  box_normalized: { left: .1, top: .2, width: .3, height: .2 }, box_pixels: { x: 10, y: 20, width: 30, height: 20 } };

async function setup({ get = [], postError = null, onPersistedCount = () => {} } = {}) {
  const calls = []; let getIndex = 0;
  const fetch = async (url, options = {}) => {
    calls.push({ url, options });
    if (options.method === 'POST') {
      const body = JSON.parse(options.body);
      return response(postError ? { error: postError } : { ok: true, pages: body.pages.map((item) => ({
        page: item.page, total_occurrences: item.occurrences.length,
        occurrences: item.occurrences.map((row) => ({ id: row.id, tipo: row.type,
          observacao: row.note, box_normalized: row.box_normalized })),
      })) }, !postError);
    }
    return response(get[getIndex++] || { occurrences: [], cataloged: false });
  };
  const load = browserModules({ fetch, AbortController });
  const { createResidueCatalogState } = await load('/texto_off/comparison/residue_catalog_state.js');
  const state = createResidueCatalogState({ provider: 'ridi', manga: 'obra', chapter: '12', step: '1' }, () => {}, onPersistedCount);
  return { state, calls };
}

function response(payload, ok = true) { return { ok, status: ok ? 200 : 400, async json() { return payload; } }; }

test('catalog page GET restores persisted boxes and revisiting does not append duplicates', async () => {
  const env = await setup({ get: [{ occurrences: [savedItem], cataloged: true }, { occurrences: [], cataloged: false }] });
  assert.equal(env.state.canSaveChapter(), false);
  await env.state.setPage('page-A.png');
  assert.equal(env.state.current().occurrences.length, 1);
  assert.equal(env.state.current().occurrences[0].box.left, .1);
  assert.equal(env.state.current().persisted, true);
  assert.equal(env.state.canSaveChapter(), false);
  env.state.setType('persisted-id', 'outro');
  assert.equal(env.state.current().dirty, true);
  assert.equal(env.state.canSaveChapter(), false);
  env.state.setNote('persisted-id', 'mancha visível');
  assert.equal(env.state.current().occurrences[0].note, 'mancha visível');
  assert.equal(env.state.canSaveChapter(), true);
  await env.state.setPage('page-B.png');
  await env.state.setPage('page-A.png');
  assert.equal(env.state.current().occurrences.length, 1);
  assert.equal(env.calls.filter((call) => call.options.method !== 'POST').length, 2);
  assert.match(env.calls[0].url, /step=1/);
});

test('catalog state posts canonical normalized boxes and marks successful edits persisted', async () => {
  const env = await setup({ get: [{ occurrences: [], cataloged: false }] });
  await env.state.setPage('page-A.png');
  assert.equal(env.state.canSaveChapter(), false);
  env.state.add({ left: .1, top: .2, width: .3, height: .2 }, 'new-id');
  assert.equal(env.state.canSaveChapter(), true);
  assert.equal(env.calls.filter((call) => call.options.method === 'POST').length, 0);
  const saved = await env.state.saveChapter();
  assert.equal(saved.ok, true);
  const post = env.calls.find((call) => call.options.method === 'POST');
  const payload = JSON.parse(post.options.body);
  assert.deepEqual(payload.pages.map((item) => item.page), ['page-A.png']);
  assert.deepEqual(payload.pages[0].occurrences[0].box_normalized, { left: .1, top: .2, width: .3, height: .2 });
  assert.equal(env.state.current().occurrences.length, 1);
  assert.equal(env.state.current().dirty, false);
  assert.equal(env.state.current().persisted, true);
});

test('save waits until a page is loaded and then accepts a valid unsaved draft', async () => {
  const env = await setup();
  assert.equal(env.state.canSaveChapter(), false);
  await env.state.setPage('page-A.png');
  env.state.add({ left: .1, top: .2, width: .3, height: .2 }, 'draft-id');
  assert.equal(env.state.current().loaded, true);
  assert.equal(env.state.current().persisted, false);
  assert.equal(env.state.canSaveChapter(), true);
});

test('removal renumbers only serialized order and reload ignores historical numero gaps', async () => {
  const env = await setup({ get: [{ occurrences: [], cataloged: false }] });
  await env.state.setPage('page-A.png');
  env.state.add({ left: .1, top: .1, width: .2, height: .2 }, 'id-a');
  env.state.add({ left: .2, top: .2, width: .2, height: .2 }, 'id-b');
  env.state.add({ left: .3, top: .3, width: .2, height: .2 }, 'id-c');
  env.state.remove('id-b');
  env.state.add({ left: .4, top: .4, width: .2, height: .2 }, 'id-d');
  env.state.remove('id-a');
  assert.deepEqual(Array.from(env.state.current().occurrences, (item) => item.id), ['id-c', 'id-d']);

  await env.state.saveChapter();
  const saved = JSON.parse(env.calls.find((call) => call.options.method === 'POST').options.body);
  assert.deepEqual(saved.pages[0].occurrences.map(({ id, number }) => [id, number]), [['id-c', 1], ['id-d', 2]]);

  const reloaded = await setup({ get: [{ cataloged: true, occurrences: saved.pages[0].occurrences.map((item, index) => ({
    id: item.id, numero: index === 0 ? 4 : 9, tipo: item.type, observacao: item.note,
    box_normalized: item.box_normalized,
  })) }] });
  await reloaded.state.setPage('page-A.png');
  assert.deepEqual(Array.from(reloaded.state.current().occurrences, (item) => item.id), ['id-c', 'id-d']);
  assert.deepEqual(Array.from(reloaded.state.current().occurrences, (item, index) => index + 1), [1, 2]);
  assert.equal(reloaded.state.current().occurrences[0].id, 'id-c');
  assert.equal(reloaded.state.current().occurrences[1].id, 'id-d');
});

test('catalog POST errors preserve editable draft and leave retry enabled', async () => {
  const env = await setup({ get: [{ occurrences: [], cataloged: false }], postError: 'Falha de disco.' });
  await env.state.setPage('page-A.png');
  env.state.add({ left: .1, top: .2, width: .3, height: .2 }, 'new-id');
  env.state.setType('new-id', 'outro'); env.state.setNote('new-id', 'marca clara');
  const saved = await env.state.saveChapter();
  assert.equal(saved.ok, false); assert.match(saved.error, /Falha de disco/);
  assert.equal(env.state.current().occurrences.length, 1);
  assert.equal(env.state.current().occurrences[0].note, 'marca clara');
  assert.equal(env.state.current().dirty, true);
  assert.equal(env.state.canSaveChapter(), true);
});

test('removing every persisted occurrence stays saveable until empty POST succeeds', async () => {
  const persisted = [savedItem, { ...savedItem, id: 'persisted-id-2', numero: 4 }];
  const indicators = [];
  const env = await setup({ get: [{ occurrences: persisted, cataloged: true }],
    onPersistedCount: (page, count) => indicators.push([page, count]) });
  await env.state.setPage('page-A.png');
  assert.equal(env.state.canSaveChapter(), false);
  env.state.remove('persisted-id');
  assert.equal(env.state.canSaveChapter(), true);
  env.state.remove('persisted-id-2');
  assert.equal(env.state.canSaveChapter(), true);
  const saved = await env.state.saveChapter();
  assert.equal(saved.ok, true);
  assert.deepEqual(JSON.parse(env.calls.find((call) => call.options.method === 'POST').options.body).pages[0].occurrences, []);
  assert.equal(env.state.current().dirty, false);
  assert.equal(env.state.current().persisted, false);
  assert.equal(env.state.canSaveChapter(), false);
  assert.deepEqual(indicators, [['page-A.png', 0]]);
});

test('persisted count callback changes only after successful POST and reports actual total', async () => {
  const indicators = [];
  const failed = await setup({ get: [{ occurrences: [savedItem], cataloged: true }], postError: 'Falha.',
    onPersistedCount: (page, count) => indicators.push([page, count]) });
  await failed.state.setPage('page-A.png');
  failed.state.remove('persisted-id');
  assert.equal((await failed.state.saveChapter()).ok, false);
  assert.deepEqual(indicators, []);

  const success = await setup({ get: [{ occurrences: [], cataloged: false }],
    onPersistedCount: (page, count) => indicators.push([page, count]) });
  await success.state.setPage('page-A.png');
  success.state.add({ left: .1, top: .2, width: .3, height: .2 }, 'new-id');
  assert.deepEqual(indicators, []);
  await success.state.saveChapter();
  assert.deepEqual(indicators, [['page-A.png', 1]]);
});
