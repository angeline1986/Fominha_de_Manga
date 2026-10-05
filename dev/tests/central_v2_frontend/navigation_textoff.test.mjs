import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

test('Limpeza de Balões renders captions and keeps special hover previews in Pincel', async () => {
  const load = browserModules();
  const { navigation } = await load('/_shell/navigation.js');
  const { groupMarkup } = await load('/_shell/drill_navigation_markup.js');
  const menu = navigation.find((section) => section.id === 'texto-off');
  const autoGroup = menu.groups[1];
  const brushGroup = menu.groups[2];

  const autoMarkup = groupMarkup(autoGroup);
  assert.match(autoMarkup, /Auto-Cleaner/);
  assert.match(autoMarkup, /PASSO 1\/4/);
  const passButtons = autoMarkup.match(/<button[\s\S]*?<\/button>/g);
  assert.deepEqual(passButtons.map((button) => button.replace(/<[^>]+>/g, '').trim()), ['1', '2', '3', '4']);
  assert.ok(passButtons.every((button) => !/Balões|Transparência/.test(button.replace(/<[^>]+>/g, ''))));
  assert.match(autoMarkup, /Balões sólidos \(padrão\)/);

  const brushMarkup = groupMarkup(brushGroup);
  assert.match(brushMarkup, /Pincel &amp; Retoques de Arte|Pincel & Retoques de Arte/);
  assert.match(brushMarkup, /Localizar balões especiais/);
  for (const preview of ['degrade', 'estilizado', 'gradiente_suave']) {
    assert.match(brushMarkup, new RegExp(`${preview}_antes\\.png`));
    assert.match(brushMarkup, new RegExp(`${preview}_depois\\.png`));
  }

  const audit = groupMarkup(menu.groups[3]);
  assert.match(audit, /drill-action-primary/);
  assert.match(audit, /drill-action-secondary/);
  assert.match(audit, /ui-icon--compare/);
  assert.match(audit, /ui-icon--highlighter/);
  const legacy = groupMarkup(menu.groups[4]);
  assert.doesNotMatch(legacy, /OUTROS/);
  assert.match(legacy, /Texto Off Legado/);
  assert.match(legacy, /drill-action-muted/);
});
