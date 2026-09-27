import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

function reply(payload) {
  return { ok: true, json: async () => payload };
}

async function setup({ confirmed = true, results = [{ chapter: '1', status: 'promoted', artifacts: 12 }] } = {}) {
  const requests = [];
  const messages = [];
  const confirmations = [];
  const summaries = [];
  const states = [];
  let completed = 0;
  const load = browserModules({
    fetch: async (url, options) => {
      requests.push({ url, options });
      if (options.method === 'POST') return reply({ job: { id: 'abc', status: 'queued' } });
      return reply({ job: {
        id: 'abc', status: 'completed', chapter: '1', progress: {},
        results,
      } });
    },
    setTimeout: (callback) => { callback(); return 1; },
    messages,
    confirmations,
    summaries,
  }, {
    '/_app/state/context.js': 'export function getContext() { return { provider: "comix", manga: "Obra" }; }',
    '/_shared/messages/messages.js': `
      export async function confirmMessage(value) { globalThis.confirmations.push(value); return ${confirmed}; }
      export async function showMessage(value) { globalThis.messages.push(value); }
      export async function showOperationSummary(value) { globalThis.summaries.push(value); }
    `,
  });
  const { createLevel1Execution } = await load('/processamento/auto_merge/execution.js');
  const runner = createLevel1Execution({ onStatus: (value) => states.push(value), onComplete: async () => { completed += 1; } });
  return { runner, requests, states, messages, confirmations, summaries, get completed() { return completed; } };
}

test('execution confirms selection, polls its job and refreshes results', async () => {
  const app = await setup();
  await app.runner.execute(['1', '2']);
  assert.equal(app.requests[0].url, '/api/auto-merge/level1/execute');
  assert.deepEqual(JSON.parse(app.requests[0].options.body), {
    provider: 'comix', manga: 'Obra', chapters: ['1', '2'],
  });
  assert.equal(app.requests[1].url, '/api/jobs/abc');
  assert.equal(app.completed, 1);
  assert.equal(app.confirmations[0].title, "Confirmar");
  assert.equal(app.confirmations[0].message, "2 capítulo(s) selecionado(s).");
  assert.equal(app.summaries[0].title, "Resumo da Operação");
  assert.equal(app.summaries[0].summary.items[0].status, "Concluído");
  assert.equal(app.states.at(-1).busy, false);
  app.runner.dispose();
});

test('cancelled execution does not create a job', async () => {
  const app = await setup({ confirmed: false });
  await app.runner.execute(['1']);
  assert.equal(app.requests.length, 0);
  assert.equal(app.completed, 0);
  app.runner.dispose();
});

test('partial execution produces a per-chapter operation summary', async () => {
  const app = await setup({ results: [{
    chapter: '11', status: 'partial', artifacts: 12, pending_segments: 1,
    residuals: [{ global_start: 6200, global_end: 20200 }],
    reason_codes: ['no_safe_boundary_before_max_height'], next_stage: 'Auto-Merge Nível II',
  }] });
  await app.runner.execute(['11']);
  const { summary } = app.summaries[0];
  assert.equal(summary.headline, '1 capítulo processado');
  assert.equal(summary.breakdown, '1 parcial');
  assert.deepEqual(JSON.parse(JSON.stringify(summary.items[0])), {
    chapter: '11', status: 'Concluído parcialmente', count: '12 merges', warning: true,
    details: [
      ['Status', 'Concluído parcialmente'], ['Merges salvos', '12'],
      ['Pendente', '1 segmento residual'],
      ['Motivo', 'Faixa branca segura não encontrada'], ['Residual', '6200–20200 px'],
      ['Próxima etapa', 'Auto-Merge Nível II'],
    ],
  });
  app.runner.dispose();
});
