import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

test('navigation resolves the Level III page', async () => {
  const load = browserModules();
  const { resolveRoute } = await load('/_app/router/routes.js');
  assert.equal(resolveRoute('auto-merge-3').module, '/processamento/auto_merge/nivel3.js');
});

test('Level III confirms, polls, summarizes and opens its own stage', async () => {
  const requests = [];
  const confirmations = [];
  const summaries = [];
  const load = browserModules({
    fetch: async (url, options = {}) => {
      requests.push({ url, options });
      if (url === '/api/auto-merge/level3/execute') return { ok: true, json: async () => ({ job: { id: 'job-3' } }) };
      if (url === '/api/jobs/job-3') return { ok: true, json: async () => ({ job: {
        id: 'job-3', status: 'completed', progress: {}, results: [{
          chapter: '6', status: 'partial', resolved_segments: 1,
          saved_files: ['page-221-l3.png'], pending_files: ['page-240.png'],
          reason_codes: ['continuous_scene_too_long'], next_stage: 'Auto-Merge Nível IV',
        }],
      } }) };
      return { ok: true, json: async () => ({ ok: true }) };
    },
    setTimeout: (callback) => { callback(); return 1; },
    confirmations,
    summaries,
  }, {
    '/_app/state/context.js': 'export function getContext() { return { provider: "ridi", manga: "Teste" }; }',
    '/_shared/messages/messages.js': `
      export async function confirmMessage(value) { globalThis.confirmations.push(value); return true; }
      export async function showMessage() {}
      export async function showOperationSummary(value) { globalThis.summaries.push(value); }
    `,
  });
  const { createLevel3Execution } = await load('/processamento/auto_merge/execucao_nivel3.js');
  const runner = createLevel3Execution({ onStatus() {}, async onComplete() {} });
  await runner.execute(['6']);
  assert.equal(confirmations[0].title, 'Executar Auto-Merge Nível III');
  assert.deepEqual(JSON.parse(requests[0].options.body), {
    provider: 'ridi', manga: 'Teste', chapters: ['6'],
  });
  assert.equal(summaries[0].summary.items[0].details.at(-1).value, 'Auto-Merge Nível IV');
  await summaries[0].onAction(summaries[0].summary.items[0], { level: 3 });
  assert.equal(requests.at(-1).url, '/api/auto-merge/open-folder');
  assert.equal(JSON.parse(requests.at(-1).options.body).level, 3);
  runner.dispose();
});
