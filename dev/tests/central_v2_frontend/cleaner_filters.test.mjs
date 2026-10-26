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
  assert.equal(matchesStage({ retouch: { laboratory: true } }, 'retouch'), true);
  assert.equal(matchesStage({ retouch: { laboratory: true } }, 'retouch', ['laboratory']), true);
});

test('Glass has a live count and Laboratório can be selected among retouches', async () => {
  const element = () => ({ children: [], classList: { toggle() {} }, setAttribute() {},
    addEventListener(_event, action) { this.click = action; },
    append(child) { this.children.push(child); },
    replaceChildren(...children) { this.children = children; } });
  const { createStageFilters } = await browserModules({ document: { createElement: element } })
    ('/texto_off/merged/stage_filters.js');
  const container = element();
  const visible = createStageFilters(container, () => {});
  visible.draw([{ stages: { glass: true }, retouch: { laboratory: true } }]);
  const [main, secondary] = container.children;
  const glassButton = main.children.find((button) => button.textContent.startsWith('Glass'));
  assert.equal(glassButton.textContent, 'Glass (1)');
  assert.equal(glassButton.disabled, false);
  glassButton.click();
  assert.equal(visible.matches({ stages: { glass: true } }), true);
  assert.equal(visible.matches({ stages: { glass: false } }), false);
  main.children.find((button) => button.textContent.startsWith('Retoque')).click();
  visible.draw([{ stages: { glass: true }, retouch: { laboratory: true } }]);
  assert.equal(secondary.hidden, false);
  assert.equal(secondary.children.at(-1).textContent, 'Laboratório');
  secondary.children.at(-1).click();
  assert.equal(visible.matches({ retouch: { laboratory: true } }), true);
  assert.equal(visible.matches({ retouch: { artistic: true } }), false);
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

test('outcome filter pills use approved labels without renaming table columns', async () => {
  const container = { replaceChildren(...children) { this.children = children; },
    append(button) { this.children.push(button); } };
  const document = { createElement: () => ({ classList: { toggle() {} }, setAttribute() {},
    addEventListener() {} }) };
  const { drawOutcomeFilters, OUTCOME_FILTERS } = await browserModules({ document })
    ('/texto_off/merged/outcome_filters.js');
  drawOutcomeFilters(container, [], 'all', () => {});
  assert.equal(container.children.map((button) => button.textContent).join(','),
    'All (0),Do (0),Done (0),No Change (0),Resíduo');
  assert.equal(Array.from(OUTCOME_FILTERS, ([, label]) => label).join(','),
    'ALL,Pendente,Concluído,Inalterado,Resíduo');
});
