import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred, mangaState, textDocument } from './modules.mjs';

async function setup(globals = {}, sources = {}) {
  const load = browserModules({ document: textDocument, ...globals }, {
    '/fixtures/other.js': 'export function render(c) { c.innerHTML = "Other"; }',
    ...sources,
  });
  const { routes } = await load('/_app/router/routes.js');
  routes.other = { module: '/fixtures/other.js' };
  const router = await load('/_app/router/router.js');
  const state = await load('/_app/state/manga_state.js');
  return { router, state, routes };
}

test('leaving summary releases its listener; returning does not duplicate it', async () => {
  const { router, state } = await setup();
  let html = '';
  let writes = 0;
  const container = {
    set innerHTML(value) { html = value; writes += 1; },
    get innerHTML() { return html; },
  };
  await router.navigate('resumo-operacao', container);
  await router.navigate('other', container);
  state.setMangaState(mangaState('A'));
  assert.equal(html, 'Other');
  await router.navigate('resumo-operacao', container);
  await router.navigate('resumo-operacao', container);
  const before = writes;
  state.setMangaState(mangaState('B'));
  assert.equal(writes, before + 1);
  router.disposePage(container);
  const disposed = writes;
  state.clearMangaState();
  assert.equal(writes, disposed);
});

test('unknown routes preserve the active page and its subscription', async () => {
  const { router, state } = await setup();
  const container = { innerHTML: '' };
  await router.navigate('resumo-operacao', container);
  await assert.rejects(router.navigate('missing', container), /Rota não encontrada/);
  state.setMangaState(mangaState('A'));
  assert.match(container.innerHTML, />A<\/strong>/);
});

test('manual merge proposal result resolves to its dedicated page', async () => {
  const { routes } = await setup();
  assert.equal(routes['merge-manual-result'].module, '/processamento/merge_manual/resultado_proposta.js');
});

test('manual merge outputs identify every intersecting source page', async () => {
  const load = browserModules();
  const { getOutputPages, getOutputPageRange, compositionMarkup } = await load('/processamento/merge_manual/resultado_proposta.js');
  const proposal = {
    source_block: { global_start: 100 },
    source_files: [
      { name: 'page-001.png', pending_height: 50 },
      { name: 'page-002.png', pending_height: 30 },
      { name: 'page-003.png', pending_height: 20 },
    ],
  };
  assert.deepEqual(getOutputPages(proposal, { global_start: 145, global_end: 175 }), [
    'page-001.png', 'page-002.png',
  ]);
  assert.equal(getOutputPageRange(proposal, { global_start: 100, global_end: 150 }), 'page-001.png');
  assert.equal(getOutputPageRange(proposal, { global_start: 150, global_end: 180 }), 'page-001.png → page-002.png');
  proposal.outputs = [
    { block: 1, file: 'block-001.png', global_start: 100, global_end: 150 },
    { block: 2, file: 'block-002.png', global_start: 150, global_end: 180 },
  ];
  const markup = compositionMarkup({ provider: 'p', manga: 'm', chapter: '1' }, proposal);
  assert.equal((markup.match(/manual-result-composition/g) || []).length, 1);
  assert.equal((markup.match(/manual-result-segment/g) || []).length, 2);
  assert.match(markup, /page-001\.png/);
  assert.match(markup, /page-001\.png → page-002\.png/);
  assert.doesNotMatch(markup, /Páginas/);
  assert.doesNotMatch(markup, /manual-result-card/);
});

test('shared image focus mode toggles with keyboard and releases its listener', async () => {
  const documentListeners = new Map();
  const classNames = new Set();
  const rootListeners = new Map();
  const buttonListeners = new Map();
  const button = { setAttribute() {}, addEventListener: (name, fn) => buttonListeners.set(name, fn), removeEventListener: (name) => buttonListeners.delete(name) };
  const root = {
    classList: { add: (name) => classNames.add(name), remove: (name) => classNames.delete(name),
      toggle: (name, enabled) => enabled ? classNames.add(name) : classNames.delete(name), contains: (name) => classNames.has(name) },
    querySelectorAll: () => [],
    addEventListener: (name, fn) => rootListeners.set(name, fn),
    removeEventListener: (name) => rootListeners.delete(name),
  };
  const document = {
    querySelector: () => null,
    body: { classList: { toggle() {}, remove() {} } },
    addEventListener: (name, fn) => documentListeners.set(name, fn),
    removeEventListener: (name) => documentListeners.delete(name),
  };
  const load = browserModules({ document });
  const { bindFocusMode } = await load('/_shared/focus_mode/focus_mode.js');
  const dispose = bindFocusMode(root, { button });
  let focusShortcutPrevented = false;
  documentListeners.get('keydown')({ key: 'f', target: { closest: () => null }, preventDefault: () => { focusShortcutPrevented = true; } });
  assert.equal(focusShortcutPrevented, true);
  assert.equal(classNames.has('is-focus-mode'), true);
  let prevented = false;
  documentListeners.get('keydown')({ key: 'Escape', target: { closest: () => null }, preventDefault: () => { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(classNames.has('is-focus-mode'), false);
  dispose();
  assert.equal(documentListeners.has('keydown'), false);
});

test('late page imports cannot overwrite the most recent navigation', async () => {
  const gate = deferred();
  const started = deferred();
  const { router, routes } = await setup({ gate: gate.promise, started: started.resolve }, {
    '/fixtures/slow.js': 'started(); await gate; export function render(c) { c.innerHTML = "Slow"; }',
  });
  routes.slow = { module: '/fixtures/slow.js' };
  const container = { innerHTML: '' };
  const pending = router.navigate('slow', container);
  await started.promise;
  await router.navigate('other', container);
  gate.resolve();
  await pending;
  assert.equal(container.innerHTML, 'Other');
});

test('disposing a container also invalidates an unfinished navigation', async () => {
  const gate = deferred();
  const started = deferred();
  const { router, routes } = await setup({ gate: gate.promise, started: started.resolve }, {
    '/fixtures/slow.js': 'started(); await gate; export function render(c) { c.innerHTML = "Slow"; }',
  });
  routes.slow = { module: '/fixtures/slow.js' };
  const container = { innerHTML: 'Initial' };
  const pending = router.navigate('slow', container);
  await started.promise;
  router.disposePage(container);
  gate.resolve();
  await pending;
  assert.equal(container.innerHTML, 'Initial');
});
