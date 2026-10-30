import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

test('navigation tooltip stays inside the viewport at both sidebar edges', async () => {
  const { tooltipPosition } = await browserModules()('/_shell/navigation_text_tooltip.js');
  const bounds = { width: 190, height: 28 };
  const viewport = { width: 300, height: 200 };

  assert.deepEqual({ ...tooltipPosition(
    { left: 12, width: 64, top: 80, bottom: 110 }, bounds, viewport,
  ) }, { left: 12, top: 45 });
  assert.deepEqual({ ...tooltipPosition(
    { left: 236, width: 52, top: 12, bottom: 42 }, bounds, viewport,
  ) }, { left: 98, top: 49 });
});
