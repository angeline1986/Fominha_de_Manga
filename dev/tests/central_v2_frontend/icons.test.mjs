import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { browserModules } from './modules.mjs';

const frontend = fileURLToPath(new URL('../../../central_v2/frontend/', import.meta.url));
const icons = [
  'visao-geral', 'processamento', 'balanceamento', 'gerar-pdf', 'texto-off',
  'exportar-arquivos', 'sync', 'power', 'next', 'back', 'close', 'focus-exit',
  'expand', 'collapse', 'menu', 'ruler',
];

test('icons use separate SVG files and CSS masks, without SVG markup in JavaScript', async () => {
  const javascript = await readFile(`${frontend}/_shared/icons/icons.js`, 'utf8');
  const css = await readFile(`${frontend}/_shared/icons/icons.css`, 'utf8');
  assert.doesNotMatch(javascript, /<svg/i);

  for (const name of icons) {
    await access(`${frontend}/_shared/icons/${name}.svg`);
    assert.match(css, new RegExp(`ui-icon--${name}\\s*\\{[^}]*mask-image`, 's'));
  }

  const load = browserModules();
  const { iconMarkup } = await load('/_shared/icons/icons.js');
  assert.equal(iconMarkup('ruler'), '<span class="ui-icon ui-icon--ruler" aria-hidden="true"></span>');
  assert.throws(() => iconMarkup('missing'), /Ícone desconhecido/);
});
