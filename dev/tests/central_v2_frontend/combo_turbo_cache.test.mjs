import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred } from './modules.mjs';

function setup() {
  const pending = deferred();
  const metrics = { overviewCalls: 0, planCalls: 0 };
  const load = browserModules({ metrics, pending: pending.promise }, {
    '/_app/state/context.js': `let context={provider:null,manga:null}; const listeners=new Set();
      export function getContext(){return context}
      export function subscribeContext(fn){listeners.add(fn);return ()=>listeners.delete(fn)}
      export function setContext(provider,manga){context={provider,manga};listeners.forEach(fn=>fn(context))}`,
    '/_app/state/cleaner_revision.js': `let listener;
      export function subscribeCleanerInvalidation(fn) { listener = fn; }
      export function invalidate(provider, manga) { listener(provider, manga); }`,
    '/texto_off/combo_turbo/api.js': `export async function fetchChapterOverview() {
      globalThis.metrics.overviewCalls++; return { chapters: [{ chapter: '1' }] };
    }`,
    '/texto_off/combo_turbo/planning.js': `export async function preflightAll() {
      globalThis.metrics.planCalls++; return globalThis.pending;
    }`,
  });
  return load('/texto_off/combo_turbo/cache.js').then((module) => {
    return load('/_app/state/cleaner_revision.js').then((revision) => ({ ...module,
      invalidation: revision.invalidate, pending,
      setContext: (provider, manga) => load('/_app/state/context.js').then((state) => state.setContext(provider, manga)),
      get overviewCalls() { return metrics.overviewCalls; }, get planCalls() { return metrics.planCalls; } }));
  });
}

test('Combo Turbo caches rows and shares the active plan request by provider and manga', async () => {
  const cache = await setup();
  const options = {};
  const first = cache.loadComboRows('comix', 'A', options);
  const duplicate = cache.loadComboRows('comix', 'A', options);
  assert.equal(first, duplicate);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(cache.overviewCalls, 1);
  assert.equal(cache.planCalls, 1);
  cache.pending.resolve([{ chapter: '1', status: 'PLANNED', pages: [] }]);
  assert.deepEqual(await first, [{ chapter: '1', status: 'PLANNED', pages: [] }]);
  assert.equal(await cache.loadComboRows('comix', 'A'), await first);
  assert.equal(cache.planCalls, 1);
  await cache.loadComboRows('comix', 'B');
  assert.equal(cache.planCalls, 2);
});

test('relevant invalidation clears only the affected work cache', async () => {
  const cache = await setup();
  cache.loadComboRows('comix', 'A');
  cache.pending.resolve([{ chapter: '1', status: 'PLANNED', pages: [] }]);
  await cache.loadComboRows('comix', 'A');
  cache.invalidation('comix', 'B');
  assert.equal(cache.planCalls, 1);
  cache.invalidation('comix', 'A');
  await cache.loadComboRows('comix', 'A');
  assert.equal(cache.planCalls, 2);
});

test('manual refresh bypasses valid cached rows and plans again', async () => {
  const cache = await setup();
  const initial = cache.loadComboRows('comix', 'A');
  await new Promise((resolve) => setTimeout(resolve, 0));
  cache.pending.resolve([{ chapter: '1', status: 'PLANNED', pages: [] }]);
  await initial;
  await cache.loadComboRows('comix', 'A', { refresh: true });
  assert.equal(cache.overviewCalls, 2);
  assert.equal(cache.planCalls, 2);
});

test('switching manga discards the previous work cache', async () => {
  const cache = await setup();
  await cache.setContext('comix', 'A');
  const first = cache.loadComboRows('comix', 'A');
  await new Promise((resolve) => setTimeout(resolve, 0));
  cache.pending.resolve([{ chapter: '1', status: 'PLANNED', pages: [] }]);
  await first;
  await cache.setContext('comix', 'B');
  await cache.loadComboRows('comix', 'A');
  assert.equal(cache.planCalls, 2);
});
