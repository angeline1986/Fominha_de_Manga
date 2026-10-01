import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { browserModules } from './modules.mjs';

const model = await browserModules()('/texto_off/comparison/model.js');
const root = new URL('../../../central_v2/frontend/texto_off/comparison/', import.meta.url);
const read = (file) => readFile(new URL(file, root), 'utf8');

test('comparison visual contract sets zoom, modes, gap, paging and searchable page names', () => {
  assert.equal(model.INITIAL_ZOOM, 40);
  assert.equal(model.SIDE_BY_SIDE_GAP, 18);
  assert.equal(Array.from(model.COMPARISON_MODES).join(','), 'split,side');
  assert.equal(model.COMPARISON_PAGE_SIZE, 13);
  assert.equal(model.clampZoom(40, '+'), 50);
  assert.equal(model.clampZoom(40, '-'), 30);
  assert.equal(model.clampZoom(40, 'one'), 100);
  assert.equal(model.clampZoom(20, '-'), 20);
  assert.equal(model.clampZoom(200, '+'), 200);
  const pages = Array.from({ length: 18 }, (_, i) => ({ name: `página-${i + 1}.png` }));
  assert.equal(model.pageComparisonItems(pages, 1).end, 13);
  assert.equal(model.pageComparisonItems(pages, 2).start, 14);
  assert.equal(model.pageComparisonItems(pages, 2).end, 18);
  assert.equal(model.filterComparisonPages(pages, 'PÁGINA-2').length, 1);
});

test('screen exposes accessible toolbar, chapter context, image preview and focus navigation', async () => {
  const source = await read('screen.js');
  assert.match(source, /Buscar página/);
  assert.match(source, /aria-label="Modo de comparação"/);
  assert.match(source, /data-mode="split"/);
  assert.match(source, /data-mode="side"/);
  assert.match(source, /aria-label="Diminuir zoom"/);
  assert.match(source, /aria-label="Aumentar zoom"/);
  assert.match(source, /data-zoom="one"/);
  assert.match(source, /bindFocusMode\(element/);
  assert.match(source, /data-focus-navigation/);
  assert.match(source, /role="tooltip"/);
  assert.match(source, /Prévia da imagem original/);
  assert.match(source, /context\.chapter/);
  assert.match(source, /controller\.abort\(\)/);
  assert.match(source, /disposeFocus\(\)/);
});

test('slider preserves image semantics, split interaction and exact side gap', async () => {
  const source = await read('slider.js');
  const css = await read('style.css');
  assert.match(css, /\.comparison-origin-hidden \{ display: none/);
  assert.match(source, /SIDE_BY_SIDE_GAP/);
  assert.match(source, /"Imagem original"/);
  assert.match(source, /"Imagem Auto Cleaner"/);
  assert.match(source, /AUTO CLEANER/);
  assert.match(source, /aria-label="Divisor Antes e Depois"/);
  assert.match(source, /pair\[0\]\.naturalWidth !== pair\[1\]\.naturalWidth/);
  assert.match(css, /--comparison-side-gap: 18px/);
  assert.match(css, /width: calc\(50% - var\(--comparison-side-gap\) \/ 2\)/);
  assert.match(css, /\.is-focus-mode \.comparison-focus-navigation \{ display: flex/);
  assert.match(css, /\.comparison-focus-navigation \{ display: none/);
  assert.match(css, /\.comparison-stage \{[^}]*width: max-content; height: max-content;[^}]*box-sizing: border-box/);
  assert.doesNotMatch(source, /stage\.style\.(?:width|height)|viewport\.client(?:Width|Height)/);
  assert.doesNotMatch(source, /ResizeObserver/);
});
