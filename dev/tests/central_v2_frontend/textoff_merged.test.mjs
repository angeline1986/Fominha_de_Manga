import test from 'node:test';
import assert from 'node:assert/strict';
import { access } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { browserModules } from './modules.mjs';

const frontend = fileURLToPath(new URL('../../../central_v2/frontend/', import.meta.url));

test('Limpeza de Balões maps all cleaner and brush choices to their existing routes', async () => {
  const load = browserModules();
  const { resolveRoute, routes } = await load('/_app/router/routes.js');
  const level1 = resolveRoute('texto-off-merged-i');
  const level2 = resolveRoute('texto-off-merged-ii');
  const level3 = resolveRoute('texto-off-merged-iii');
  const legacy = resolveRoute('texto-off-legacy');
  assert.equal(level1.context, 'texto-off');
  assert.equal(level1.module, '/texto_off/merged/level1.js');
  assert.equal(level2.context, 'texto-off');
  assert.equal(level2.module, '/texto_off/merged/level2.js');
  assert.equal(level3.module, '/texto_off/merged/level3.js');
  await load(level3.module);
  for (const [level, numeral] of [['IV', '4'], ['V', '5']]) {
    const route = resolveRoute(`texto-off-merged-${level.toLowerCase()}`);
    assert.equal(route.context, 'texto-off');
    assert.equal(route.module, `/texto_off/merged/level${numeral}.js`);
    await load(route.module);
  }
  const { navigation } = await load('/_shell/navigation.js');
  const menu = navigation.find((section) => section.id === 'texto-off');
  assert.equal(menu.label, 'Limpeza de Balões');
  const auto = menu.groups.find((group) => group.control?.id === 'textoff-auto-cleaner').control;
  assert.equal(Array.from(auto.options, (option) => option.action).join(','), [
    'texto-off-merged-i', 'texto-off-merged-ii', 'texto-off-merged-iv', 'texto-off-merged-v',
  ].join(','));
  assert.equal(auto.badgeFormat, 'PASSO {value}/4');
  const brush = menu.groups.find((group) => group.control?.id === 'textoff-brush').control;
  assert.equal(Array.from(brush.options, (option) => option.action).join(','), [
    'texto-off-merged-iii', 'texto-off-especiais-vi', 'texto-off-especiais-vii', 'texto-off-especiais-viii',
  ].join(','));
  assert.equal(brush.options[0].label, 'Mapear');
  for (const option of [...auto.options, ...brush.options]) {
    assert.ok(resolveRoute(option.action), `Rota ausente para ${option.action}`);
  }
  for (const option of brush.options.slice(1)) {
    assert.ok(option.preview, `Preview ausente para ${option.label}`);
    await access(`${frontend}${option.preview.before}`);
    await access(`${frontend}${option.preview.after}`);
  }
  assert.equal(menu.groups.find((group) => group.label === 'AUDITORIA DE QUALIDADE')
    .items.map((item) => item.label).join('|'), 'Antes & Depois|Correção Assistida');
  const auditAction = menu.groups.find((group) => group.label === 'AUDITORIA DE QUALIDADE')
    .items.find((item) => item.label === 'Antes & Depois').id;
  assert.equal(auditAction, 'texto-off-quality-audit');
  assert.notEqual(auditAction, 'texto-off-merged-i');
  assert.equal(resolveRoute(auditAction).module, '/texto_off/comparison/audit.js');
  assert.equal(menu.groups.find((group) => group.items?.[0]?.id === 'texto-off-legacy').label, '');
  assert.equal(legacy.context, 'texto-off');
  assert.equal(legacy.module, '/texto_off/merged/index.js');
  await load(level1.module);
  await load(level2.module);
});

test('captioned segmented controls update pass, selected action and caption together', async () => {
  const load = browserModules();
  const { navigation } = await load('/_shell/navigation.js');
  const control = navigation.find((section) => section.id === 'texto-off').groups
    .find((group) => group.control?.id === 'textoff-auto-cleaner').control;
  const { segmentedMarkup, selectMergeLevel } = await load('/_shell/merge_levels.js');
  const markup = segmentedMarkup(control);
  assert.match(markup, /PASSO 1\/4/);
  assert.match(markup, /Balões sólidos \(padrão\)/);

  const buttons = control.options.map((option, index) => ({
    dataset: { segmentValue: option.value },
    classList: { toggle(name, active) { this[name] = active; } },
    setAttribute(name, value) { this[name] = value; },
    index,
  }));
  const badge = { textContent: '' }, caption = { textContent: '' };
  const segmented = {
    dataset: { badgeFormat: control.badgeFormat },
    querySelectorAll: () => buttons,
    querySelector: (selector) => selector === '.segmented-badge' ? badge : caption,
  };
  buttons[2].closest = () => segmented;
  selectMergeLevel(buttons[2], control);
  assert.equal(buttons[2].classList.active, true);
  assert.equal(buttons[0].classList.active, false);
  assert.equal(buttons[2]['aria-pressed'], 'true');
  assert.equal(badge.textContent, 'PASSO 3/4');
  assert.equal(caption.textContent, 'Transparência normal');
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

test('Nível III summarizes candidates and analyzed MERGEs without clean/mask counts', async () => {
  const requests = [], summaries = [];
  const load = browserModules({
    fetch: async (url) => {
      requests.push(url);
      const payload = url.endsWith('/execute')
        ? { job: { id: 'job-level3' } }
        : { job: { id: 'job-level3', status: 'completed', progress: {}, results: [
          { chapter: '1', status: 'ok', pages: 18, candidate_count: 3,
            candidate_types: { soft_gradient: 1, irregular_outline: 2 } },
        ] } };
      return { ok: true, json: async () => payload };
    },
    setTimeout: (callback) => { callback(); return 1; }, summaries,
  }, {
    '/_app/state/context.js': 'export function getContext() { return { provider: "comix", manga: "Gazing at you" }; }',
    '/_shared/messages/messages.js': `
      export async function confirmMessage() { return true; }
      export async function showMessage() {}
      export async function showOperationSummary(value) { globalThis.summaries.push(value); }
    `,
  });
  const { createMergedExecution } = await load('/texto_off/merged/execution.js');
  const runner = createMergedExecution({ async onComplete() {}, onStatus() {}, level: '3' });
  await runner.execute(['1']);
  const item = summaries[0].summary.items[0];
  assert.equal(item.count, '3 candidato(s)');
  assert.equal(item.details.map(({ label }) => label).join('|'),
    'Análise Nível III|Candidatos a balão estilizado|Candidatos com gradiente|Candidatos com contorno irregular|MERGES analisados');
  assert.equal(item.actions[0].id, 'review');
  assert.equal(item.actions[0].label, 'Ver candidatos');
  assert.equal(requests[0], '/api/textoff/merged/level3/execute');
  runner.dispose();
});
