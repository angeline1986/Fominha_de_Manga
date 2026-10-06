import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

test('failed worker error is friendly and progress closes', async () => {
  const messages = [], progress = [];
  const load = browserModules({ messages, progress, Error }, {
    '/_app/state/context.js': `export function getContext() {
      return {provider:'comix',manga:'Example'}; }`,
    '/_app/api/textoff.js': `export async function startSpecialTreatments() {
      return {job:{id:'job'}}; }
      export async function waitForTextoffJob(job, onProgress) {
        onProgress({status:'running',progress:{percent:0,total:1}});
        throw new Error("1 de 1 capítulo(s) falharam. {'type': 'RuntimeError', 'error': 'Nenhum componente autorizado intersecta as seleções.'}");
      }`,
    '/_shared/messages/messages.js': `export async function confirmMessage() { return true; }
      export async function showMessage(options) { globalThis.messages.push(options); }
      export async function showOperationSummary() { throw new Error('unexpected success'); }`,
  });
  const { createDegradeExecution } = await load('/texto_off/especiais/degrade_execution.js');
  const execute = createDegradeExecution({ setBusy() {}, reload: async () => {},
    progress: { update(value) { progress.push(value); } } });
  await execute(['1'], true);
  assert.equal(messages[0].message, 'Nenhum componente elegível pôde ser tratado nas áreas selecionadas.');
  assert.ok(progress.some((value) => value.busy));
  assert.equal(progress.at(-1).busy, false);
});
