import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

test('cleaner stage filters use independent booleans and combine retouch types with OR', async () => {
  const { matchesStage } = await browserModules()('/texto_off/merged/stage_filters.js');
  const row = { stages: { ac1: true, ac2: false, map: true }, retouch: { artistic: true } };
  assert.equal(matchesStage(row, 'all'), true);
  assert.equal(matchesStage(row, 'ac1'), true);
  assert.equal(matchesStage(row, 'ac2'), false);
  assert.equal(matchesStage(row, 'map'), true);
  assert.equal(matchesStage(row, 'retouch', ['degrade']), false);
  assert.equal(matchesStage(row, 'retouch', ['degrade', 'artistic']), true);
  assert.equal(matchesStage(row, 'retouch', []), true);
  assert.equal(matchesStage({}, 'retouch'), false);
  assert.equal(matchesStage({}, 'ac4'), false);
});

test('outcome filters distinguish unchanged from unavailable and use recorded residue', async () => {
  const { matchesOutcome, OUTCOME_FILTERS } = await browserModules()('/texto_off/merged/outcome_filters.js');
  assert.equal(Array.from(OUTCOME_FILTERS, ([, label]) => label).join(','), 'ALL,Pendente,Concluído,Inalterado,Resíduo');
  assert.equal(matchesOutcome({ level2_status: 'pending' }, 'pending'), true);
  assert.equal(matchesOutcome({ cleaner_status: 'processed' }, 'processed'), true);
  assert.equal(matchesOutcome({ cleaner_status: 'no_change' }, 'unchanged'), true);
  assert.equal(matchesOutcome({ level2_status: 'no_candidates' }, 'unchanged'), false);
  assert.equal(matchesOutcome({ level2_status: 'missing_level1' }, 'pending'), false);
  assert.equal(matchesOutcome({ cleaned: true, deferred_components: 2 }, 'residue'), true);
  assert.equal(matchesOutcome({ cleaned: false, deferred_components: 2 }, 'residue'), false);
  assert.equal(matchesOutcome({ level2_status: 'invalid_merge' }, 'all'), true);
});
