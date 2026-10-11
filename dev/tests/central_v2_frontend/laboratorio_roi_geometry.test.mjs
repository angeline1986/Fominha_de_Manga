import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

test('pontos sobre a imagem geram as mesmas coordenadas normalizadas em qualquer zoom', async () => {
  const load = browserModules();
  const { normalizedPoint, boxesToNaturalPixels } = await load('/texto_off/laboratorio/roi_selection.js');
  const expected = { x: 0.2, y: 0.3 };
  for (const renderedWidth of [480, 640, 1600, 2560]) {
    const renderedHeight = renderedWidth * 1.5;
    const rect = { left: 173, top: 81, width: renderedWidth, height: renderedHeight };
    const point = normalizedPoint(rect.left + renderedWidth * expected.x,
      rect.top + renderedHeight * expected.y, rect);
    assert.ok(Math.abs(point.x - expected.x) < 1e-12);
    assert.ok(Math.abs(point.y - expected.y) < 1e-12);
  }
  const pixels = boxesToNaturalPixels([{ x: .2, y: .3, w: .1, h: .2 }], 1600, 2400);
  assert.deepEqual(JSON.parse(JSON.stringify(pixels)), [
    { x: 320, y: 720, width: 160, height: 480 },
  ]);
});

test('conversão natural limita as bordas e não acumula erro de arredondamento', async () => {
  const load = browserModules();
  const { boxesToNaturalPixels } = await load('/texto_off/laboratorio/roi_selection.js');
  const selection = [{ x: .91, y: .89, w: .2, h: .2 }];
  for (let repeat = 0; repeat < 5; repeat++) {
    assert.deepEqual(JSON.parse(JSON.stringify(boxesToNaturalPixels(selection, 101, 203))), [
      { x: 92, y: 181, width: 9, height: 22 },
    ]);
  }
});
