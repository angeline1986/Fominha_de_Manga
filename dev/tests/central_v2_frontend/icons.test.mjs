import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { browserModules } from './modules.mjs';

const frontend = fileURLToPath(new URL('../../../central_v2/frontend/', import.meta.url));
const icons = [
  'visao-geral', 'processamento', 'balanceamento', 'gerar-pdf',
  'power', 'next', 'back', 'close', 'focus-exit',
  'expand', 'collapse', 'menu', 'ruler', 'search', 'compare',
];
const iconAliases = {
  'texto-off': 'eraser-solid-full',
  'exportar-arquivos': 'cloud-arrow-up-solid-full',
  sync: 'arrows-rotate-solid-full',
  highlighter: 'highlighter-solid-full',
  'crop-simple': 'crop-simple-solid-full',
  scissors: 'scissors-solid-full',
};

test('icons use separate SVG files and CSS masks, without SVG markup in JavaScript', async () => {
  const javascript = await readFile(`${frontend}/_shared/icons/icons.js`, 'utf8');
  const css = await readFile(`${frontend}/_shared/icons/icons.css`, 'utf8');
  assert.doesNotMatch(javascript, /<svg/i);

  for (const [name, filename] of [...icons.map((name) => [name, name]), ...Object.entries(iconAliases)]) {
    await access(`${frontend}/_shared/icons/${filename}.svg`);
    assert.match(css, new RegExp(`ui-icon--${name}\\s*\\{[^}]*mask-image`, 's'));
  }

  const load = browserModules();
  const { iconMarkup } = await load('/_shared/icons/icons.js');
  assert.equal(iconMarkup('ruler'), '<span class="ui-icon ui-icon--ruler" aria-hidden="true"></span>');
  assert.equal(iconMarkup('compare'), '<span class="ui-icon ui-icon--compare" aria-hidden="true"></span>');
  assert.throws(() => iconMarkup('missing'), /Ícone desconhecido/);
});
