import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

const savedItem = { id: 'persisted-id', numero: 3, tipo: 'texto_residual', observacao: null,
  box_normalized: { left: .1, top: .2, width: .3, height: .2 }, box_pixels: { x: 10, y: 20, width: 30, height: 20 } };

async function setup({ get = [], postError = null } = {}) {
  const calls = []; let getIndex = 0;
  const fetch = async (url, options = {}) => {
    calls.push({ url, options });
    if (options.method === 'POST') return response(postError ? { error: postError } : { ok: true }, !postError);
    return response(get[getIndex++] || { occurrences: [], cataloged: false });
  };
  const load = browserModules({ fetch, AbortController });
  const { createResidueCatalogState } = await load('/texto_off/comparison/residue_catalog_state.js');
  const state = createResidueCatalogState({ provider: 'ridi', manga: 'obra', chapter: '12', step: '1' });
  return { state, calls };
}

function response(payload, ok = true) { return { ok, async json() { return payload; } }; }

test('catalog page GET restores persisted boxes and revisiting does not append duplicates', async () => {
  const env = await setup({ get: [{ occurrences: [savedItem], cataloged: true }, { occurrences: [], cataloged: false }] });
  assert.equal(env.state.canSave(), false);
  await env.state.setPage('page-A.png');
  assert.equal(env.state.current().occurrences.length, 1);
  assert.equal(env.state.current().occurrences[0].box.left, .1);
  assert.equal(env.state.current().persisted, true);
  assert.equal(env.state.canSave(), true);
  env.state.setType('persisted-id', 'outro');
  assert.equal(env.state.current().dirty, true);
  env.state.setNote('persisted-id', 'mancha visível');
  assert.equal(env.state.current().occurrences[0].note, 'mancha visível');
  await env.state.setPage('page-B.png');
  await env.state.setPage('page-A.png');
  assert.equal(env.state.current().occurrences.length, 1);
  assert.equal(env.calls.filter((call) => call.options.method !== 'POST').length, 2);
  assert.match(env.calls[0].url, /step=1/);
});

test('catalog state posts canonical normalized boxes and marks successful edits persisted', async () => {
  const env = await setup({ get: [{ occurrences: [], cataloged: false }] });
  await env.state.setPage('page-A.png');
  assert.equal(env.state.canSave(), false);
  env.state.add({ left: .1, top: .2, width: .3, height: .2 }, 'new-id');
  assert.equal(env.state.canSave(), true);
  assert.equal(env.calls.filter((call) => call.options.method === 'POST').length, 0);
  const saved = await env.state.save({ naturalWidth: 100, naturalHeight: 200 });
  assert.equal(saved.ok, true);
  const post = env.calls.find((call) => call.options.method === 'POST');
  const payload = JSON.parse(post.options.body);
  assert.equal(payload.page, 'page-A.png');
  assert.deepEqual(payload.occurrences[0].box_normalized, { left: .1, top: .2, width: .3, height: .2 });
  assert.equal(env.state.current().occurrences.length, 1);
  assert.equal(env.state.current().dirty, false);
  assert.equal(env.state.current().persisted, true);
});

test('valid draft is catalogable without loaded or persisted flags', async () => {
  const env = await setup();
  env.state.add({ left: .1, top: .2, width: .3, height: .2 }, 'draft-id');
  assert.equal(env.state.current().loaded, false);
  assert.equal(env.state.current().persisted, false);
  assert.equal(env.state.canSave(), true);
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

  await env.state.save({ naturalWidth: 100, naturalHeight: 100 });
  const saved = JSON.parse(env.calls.find((call) => call.options.method === 'POST').options.body);
  assert.deepEqual(saved.occurrences.map(({ id, number }) => [id, number]), [['id-c', 1], ['id-d', 2]]);

  const reloaded = await setup({ get: [{ cataloged: true, occurrences: saved.occurrences.map((item, index) => ({
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
  const saved = await env.state.save({ naturalWidth: 100, naturalHeight: 200 });
  assert.equal(saved.ok, false); assert.match(saved.error, /Falha de disco/);
  assert.equal(env.state.current().occurrences.length, 1);
  assert.equal(env.state.current().occurrences[0].note, 'marca clara');
  assert.equal(env.state.current().dirty, true);
  assert.equal(env.state.canSave(), true);
});
