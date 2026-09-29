import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

test('TextOff menu separates explicit Merged levels from the Legacy flow', async () => {
  const load = browserModules();
  const { resolveRoute } = await load('/_app/router/routes.js');
  const level1 = resolveRoute('texto-off-merged-i');
  const level2 = resolveRoute('texto-off-merged-ii');
  const legacy = resolveRoute('texto-off-legacy');
  assert.equal(level1.context, 'texto-off');
  assert.equal(level1.module, '/texto_off/merged/level1.js');
  assert.equal(level2.context, 'texto-off');
  assert.equal(level2.module, '/texto_off/merged/level2.js');
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
