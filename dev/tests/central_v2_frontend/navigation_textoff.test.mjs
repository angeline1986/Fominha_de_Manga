import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

test('Limpeza de Balões presents the four-step flow and separate brush group', async () => {
  const load = browserModules();
  const { navigation } = await load('/_shell/navigation.js');
  const { groupMarkup } = await load('/_shell/drill_navigation_markup.js');
  const menu = navigation.find((section) => section.id === 'texto-off');
  const [timeline, brush, audit, legacy] = menu.groups;

  assert.equal(menu.defaultAction, 'texto-off-merged-i');
  assert.equal(timeline.label, 'FLUXO DE LIMPEZA');
  assert.equal(timeline.type, 'timeline');
  assert.deepEqual(JSON.parse(JSON.stringify(timeline.items.map((item) => [item.number, item.label, item.id]))), [
    ['01', 'Auto-Cleaner', 'texto-off-merged-i'],
    ['02', 'Mapear', 'texto-off-merged-iii'],
    ['03', 'Bubble Sommelier', 'bubble-sommelier'],
  ]);
  assert.equal(timeline.control.number, '04');
  assert.equal(timeline.control.label, 'Auto-Cleaner: Transparência');
  assert.deepEqual(JSON.parse(JSON.stringify(timeline.control.options.map((option) => [option.label, option.action]))), [
    ['Básica', 'texto-off-merged-ii'],
    ['Normal', 'texto-off-merged-iv'],
    ['Legada', 'texto-off-merged-v'],
  ]);

  const timelineMarkup = groupMarkup(timeline);
  assert.match(timelineMarkup, /cleaning-timeline/);
  assert.match(timelineMarkup, /ui-icon--sparkles/);
  assert.match(timelineMarkup, /ui-icon--diamond/);
  assert.match(timelineMarkup, /ui-icon--circle-dot/);
  for (const text of [
    '01', '02', '03', '04', 'Auto-Cleaner', 'Mapear', 'Bubble Sommelier',
    'Auto-Cleaner: Transparência', 'Básica', 'Normal', 'Legada',
  ]) assert.match(timelineMarkup, new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  for (const tooltip of [
    'Passo 1 — Limpeza inicial', 'Localizar balões especiais', 'Curadoria de balões',
    'Tratamento de balões translúcidos', 'Passo 2 — Transparência Básica',
    'Passo 3 — Transparência Normal', 'Passo 4 — Transparência Legada',
  ]) {
    assert.ok(timelineMarkup.includes(`data-tooltip="${tooltip}"`));
    assert.ok(timelineMarkup.includes(`aria-description="${tooltip}"`));
  }
  assert.doesNotMatch(timelineMarkup, /data-action="[^"]+"[^>]*>[^<]*Executar/);

  assert.equal(brush.label, 'PINCEL & RETOQUES DE ARTE');
  assert.equal(Array.from(brush.control.options, (option) => option.label).join('|'), 'Degradê|Artístico|Suave');
  const brushMarkup = groupMarkup(brush);
  assert.doesNotMatch(brushMarkup, /Mapear/);
  for (const preview of ['degrade', 'estilizado', 'gradiente_suave']) {
    assert.match(brushMarkup, new RegExp(`${preview}_antes\\.png`));
    assert.match(brushMarkup, new RegExp(`${preview}_depois\\.png`));
  }

  const auditMarkup = groupMarkup(audit);
  assert.match(auditMarkup, /drill-action-primary/);
  assert.match(auditMarkup, /drill-action-secondary/);
  assert.match(auditMarkup, /ui-icon--compare/);
  assert.match(auditMarkup, /ui-icon--highlighter/);
  assert.equal(audit.items.map((item) => item.label).join('|'), 'Antes & Depois|Correção Assistida');
  assert.equal(legacy.label, 'LEGADO');
  assert.match(groupMarkup(legacy), /Texto Off Legado/);
});
