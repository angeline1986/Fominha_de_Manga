import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { browserModules } from './modules.mjs';

const model = await browserModules()('/texto_off/comparison/model.js');
const root = new URL('../../../central_v2/frontend/texto_off/comparison/', import.meta.url);
const read = (file) => readFile(new URL(file, root), 'utf8');

test('triptych contract preserves zoom, shared gap, paging and searchable page names', () => {
  assert.equal(model.INITIAL_ZOOM, 40);
  assert.equal(model.TRIPTYCH_PANEL_GAP, 18);
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

test('screen exposes the fixed three-stage toolbar, page preview and focus navigation', async () => {
  const source = await read('screen.js');
  assert.match(source, /Buscar página/);
  assert.match(source, /AUDITORIA DE QUALIDADE/);
  assert.match(source, /level1/);
  assert.match(source, /level2/);
  assert.doesNotMatch(source, /Visão única|data-mode/);
  assert.match(source, /aria-label="Diminuir zoom"/);
  assert.match(source, /aria-label="Aumentar zoom"/);
  assert.match(source, /data-zoom="one"/);
  assert.match(source, /slider\.zoom\(zoom \/ 100\)/);
  assert.match(source, /comparison-canvas-viewport"><div class="comparison-state"[^]*data-viewport/);
  assert.match(source, /bindFocusMode\(element/);
  assert.match(source, /data-focus-navigation/);
  assert.match(source, /role="tooltip"/);
  assert.match(source, /Prévia da imagem original/);
  assert.match(source, /context\.chapter/);
  assert.match(source, /controller\.abort\(\)/);
  assert.match(source, /disposeFocus\(\)/);
  assert.match(source, /createResidueCatalog/);
  assert.match(source, /aria-controls="comparison-residue-panel"/);
  assert.match(source, /aria-expanded="false"/);
});

test('triptych preserves image semantics, equal columns and fixed page alignment', async () => {
  const source = await read('slider.js');
  const css = await read('style.css');
  assert.match(css, /\.comparison-origin-hidden \{ display: none/);
  assert.match(source, /TRIPTYCH_PANEL_GAP/);
  assert.match(source, /Imagem \$\{PANELS\[index\]\[1\]\}/);
  assert.match(source, /AUTO-CLEANER I/);
  assert.match(source, /AUTO-CLEANER II/);
  assert.match(source, /batch\.length !== 3/);
  assert.match(source, /image\.naturalWidth !== batch\[0\]\.naturalWidth/);
  assert.match(css, /grid-template-columns: repeat\(3, var\(--comparison-image-width\)\)/);
  assert.match(css, /\.comparison-image-panel \{[^}]*grid-template-rows: 44px/);
  assert.match(css, /\.is-focus-mode \.comparison-focus-navigation \{ display: flex/);
  assert.match(css, /\.comparison-focus-navigation \{ display: none/);
  assert.match(css, /\.comparison-stage \{[^}]*width: max-content; height: max-content;[^}]*box-sizing: border-box/);
  assert.doesNotMatch(source, /stage\.style\.(?:width|height)|viewport\.client(?:Width|Height)/);
  assert.doesNotMatch(source, /ResizeObserver/);
  assert.match(source, /getImageMetrics\(\)/);
  assert.match(source, /mountAfterOverlay\(element\)/);
  assert.match(source, /setInteractionMode\(nextMode\)/);
  assert.match(css, /\.comparison-image-holder \{ position: relative/);
  assert.doesNotMatch(css, /\.comparison-image-panel \{[^}]*overflow:\s*(?:auto|scroll)/);
  assert.match(css, /\.comparison-workspace\.has-residue-panel/);
});
