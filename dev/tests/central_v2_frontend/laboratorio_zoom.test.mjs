import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { browserModules } from './modules.mjs';

test('zoom mantém proporção natural em todos os níveis exibidos', async () => {
  const load = browserModules();
  const { zoomDimensions } = await load('/texto_off/laboratorio/zoom.js');
  const levels = [30, 40, 50, 60, 70, 80, 90, 100, 150, 200];
  const measured = levels.map((zoom) => ({ zoom, ...zoomDimensions(1600, 2400, zoom) }));

  for (const item of measured) {
    assert.equal(item.width, 1600 * item.zoom / 100);
    assert.equal(item.height, 2400 * item.zoom / 100);
    assert.equal(item.width / item.height, 2 / 3);
  }
  for (let index = 1; index < measured.length; index++) {
    const previous = measured[index - 1], current = measured[index];
    assert.equal(current.width / previous.width, current.zoom / previous.zoom);
  }
  assert.equal(measured.find((item) => item.zoom === 100).width, 1600);
  assert.equal(measured.find((item) => item.zoom === 100).height, 2400);
});

test('layout reserva quatro painéis sem piso de largura nem escala por transform', async () => {
  const css = await readFile(new URL('../../../central_v2/frontend/texto_off/laboratorio/style.css', import.meta.url), 'utf8');
  assert.match(css, /grid-template-columns:\s*repeat\(4, var\(--lab-panel-width\)\)/);
  assert.match(css, /\.lab-stage\s*\{[^}]*overflow:\s*auto/s);
  assert.match(css, /\.lab-focus-mode\.lab-panel-open \.lab-columns\s*\{[^}]*minmax\(0, 1fr\) 295px/s);
  assert.match(css, /\.lab-focus-mode \.lab-columns\s*\{[^}]*gap:\s*12px/s);
  assert.match(css, /\.lab-roi-frame \.lab-original-image\s*\{[^}]*width:\s*var\(--lab-image-width\)/s);
  assert.doesNotMatch(css, /\.lab-cards\s*\{[^}]*transform\s*:/s);
  assert.doesNotMatch(css, /\.lab-focus-mode\s+\.lab-cards/);
  assert.doesNotMatch(css, /min-width:\s*max\(/);
  assert.doesNotMatch(css, /zoom:\s*\d/);
});
