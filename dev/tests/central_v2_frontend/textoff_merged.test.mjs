import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

test('TextOff menu exposes Merged I, II, IV and V and keeps Legacy separate', async () => {
  const load = browserModules();
  const { resolveRoute, routes } = await load('/_app/router/routes.js');
  const level1 = resolveRoute('texto-off-merged-i');
  const level2 = resolveRoute('texto-off-merged-ii');
  const legacy = resolveRoute('texto-off-legacy');
  assert.equal(level1.context, 'texto-off');
  assert.equal(level1.module, '/texto_off/merged/level1.js');
  assert.equal(level2.context, 'texto-off');
  assert.equal(level2.module, '/texto_off/merged/level2.js');
  for (const [level, numeral] of [['IV', '4'], ['V', '5']]) {
    const route = resolveRoute(`texto-off-merged-${level.toLowerCase()}`);
    assert.equal(route.context, 'texto-off');
    assert.equal(route.module, `/texto_off/merged/level${numeral}.js`);
    await load(route.module);
  }
  const { navigation } = await load('/_shell/navigation.js');
  const selector = navigation.find((section) => section.id === 'texto-off')
    .groups.find((group) => group.control?.id === 'textoff-merged-level').control;
  assert.equal(Array.from(selector.options, (option) => option.value).join(','), 'I,II,IV,V');
  assert.equal(legacy.context, 'texto-off');
  assert.equal(legacy.module, '/texto_off/merged/index.js');
  await load(level1.module);
  await load(level2.module);
});

test('TextOff Merged confirms, submits selected chapters and summarizes the job', async () => {
  const requests = [], confirmations = [], summaries = [], statuses = [];
  const load = browserModules({
    fetch: async (url, options = {}) => {
      requests.push({ url, options });
      if (url === '/api/textoff/merged/execute') {
        return { ok: true, json: async () => ({ job: { id: 'job-textoff' } }) };
      }
      return { ok: true, json: async () => ({ job: {
        id: 'job-textoff', status: 'completed', progress: {}, results: [
          { chapter: '3', status: 'ok', pages: 7, outputs: 7, masks: 7 },
        ],
      } }) };
    },
    setTimeout: (callback) => { callback(); return 1; },
    confirmations, summaries,
  }, {
    '/_app/state/context.js': 'export function getContext() { return { provider: "ridi", manga: "Obra" }; }',
    '/_shared/messages/messages.js': `
      export async function confirmMessage(value) { globalThis.confirmations.push(value); return true; }
      export async function showMessage() {}
      export async function showOperationSummary(value) { globalThis.summaries.push(value); }
    `,
  });
  const { createMergedExecution } = await load('/texto_off/merged/execution.js');
  const runner = createMergedExecution({ onStatus: (status) => statuses.push(status), async onComplete() {} });
  await runner.execute(['3']);
  assert.equal(confirmations[0].title, 'Executar Texto Off — Legado');
  assert.deepEqual(JSON.parse(requests[0].options.body), {
    provider: 'ridi', manga: 'Obra', chapters: ['3'],
  });
  assert.equal(summaries[0].summary.items[0].status, 'Concluído');
  assert.equal(statuses.at(-1).busy, false);
  runner.dispose();
});

test('Nível II reports zero changed pixels as a review outcome, not success', async () => {
  const summaries = [];
  const load = browserModules({
    fetch: async (url) => ({ ok: true, json: async () => url.endsWith('/execute')
      ? { job: { id: 'job-no-change' } }
      : { job: { id: 'job-no-change', status: 'completed', progress: {}, results: [
        { chapter: '3', status: 'no_change', pages: 31, outputs: 31, masks: 31, text_pages: 0, changed_pixels: 0 },
      ] } } }),
    setTimeout: (callback) => { callback(); return 1; }, summaries,
  }, {
    '/_app/state/context.js': 'export function getContext() { return { provider: "ridi", manga: "Obra" }; }',
    '/_shared/messages/messages.js': `
      export async function confirmMessage() { return true; }
      export async function showMessage() {}
      export async function showOperationSummary(value) { globalThis.summaries.push(value); }
    `,
  });
  const { createMergedExecution } = await load('/texto_off/merged/execution.js');
  const runner = createMergedExecution({ async onComplete() {}, onStatus() {}, level: '2' });
  await runner.execute(['3']);
  assert.match(summaries[0].summary.breakdown, /sem alteração/);
  assert.equal(summaries[0].summary.items[0].status, 'Sem alteração — revisar');
  assert.equal(summaries[0].summary.items[0].warning, true);
  runner.dispose();
});
