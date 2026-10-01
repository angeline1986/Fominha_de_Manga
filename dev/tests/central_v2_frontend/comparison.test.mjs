import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor() {
    this.nodes = new Map(); this.events = new Map(); this.attrs = {};
    this.style = { setProperty: (key, value) => { this.attrs[key] = value; } };
    this.clientWidth = 800; this.clientHeight = 600;
  }
  querySelector(key) { if (!this.nodes.has(key)) this.nodes.set(key, new Element()); return this.nodes.get(key); }
  append(value) { this.child = value; }
  replaceChildren(...children) { this.children = children; }
  setAttribute(key, value) { this.attrs[key] = value; }
  removeAttribute() {}
  addEventListener(key, fn) { this.events.set(key, fn); }
  removeEventListener(key) { this.events.delete(key); }
  dispatch(key, props = {}) { this.events.get(key)?.({ preventDefault() {}, ...props }); }
  getBoundingClientRect() { return { left: 100, width: 400 }; }
  setPointerCapture(id) { this.capture = id; }
  hasPointerCapture(id) { return this.capture === id; }
  releasePointerCapture() { this.capture = null; }
  focus() {}
  remove() { this.removed = true; }
}

async function setup(sizes = [[400, 600], [400, 600]]) {
  const frames = new Map(), states = [];
  let next = 0, image = 0, disconnected = false;
  class Image extends Element {
    constructor() { super(); [this.naturalWidth, this.naturalHeight] = sizes[image++]; }
    async decode() {}
  }
  const load = browserModules({
    document: { createElement: () => new Element() }, Image,
    requestAnimationFrame: (fn) => { frames.set(++next, fn); return next; },
    cancelAnimationFrame: (id) => frames.delete(id),
    ResizeObserver: class { observe() {} disconnect() { disconnected = true; } },
  });
  const { createSlider, splitAt } = await load('/texto_off/comparison/slider.js');
  const viewport = new Element();
  const slider = createSlider(viewport, (...state) => states.push(state));
  return { slider, viewport, frames, states, splitAt, disconnected: () => disconnected,
    flush() { const pending = [...frames.values()]; frames.clear(); pending.forEach((fn) => fn()); } };
}

test('comparison coalesces pointer movement, clamps split, supports keyboard and cleans up', async () => {
  const env = await setup();
  await env.slider.load('before', 'after');
  assert.equal(env.states.at(-1)[0], 'ready');
  env.flush();
  const handle = env.viewport.child.querySelector('.comparison-divider');
  env.viewport.dispatch('pointerdown', { pointerId: 1, button: 0, clientX: 200, clientY: 0 });
  for (const x of [250, 300, 1000]) env.viewport.dispatch('pointermove', { pointerId: 1, clientX: x });
  assert.equal(env.frames.size, 1);
  env.flush();
  assert.equal(handle.attrs['aria-valuenow'], '100');
  env.viewport.dispatch('pointercancel', { pointerId: 1 });
  assert.equal(env.viewport.capture, null);
  handle.dispatch('keydown', { key: 'Home' }); env.flush();
  assert.equal(handle.attrs['aria-valuenow'], '0');
  handle.dispatch('keydown', { key: 'ArrowRight', shiftKey: true }); env.flush();
  assert.equal(handle.attrs['aria-valuenow'], '10');
  env.slider.dispose();
  assert.equal(env.disconnected(), true);
  assert.equal(env.viewport.events.size, 0);
  assert.equal(env.frames.size, 0);
});

test('comparison refuses mismatched dimensions before enabling interaction', async () => {
  const env = await setup([[400, 600], [400, 601]]);
  await env.slider.load('before', 'after');
  assert.equal(env.states.at(-1)[0], 'error');
  assert.match(env.states.at(-1)[1], /dimensões diferentes/);
  assert.equal(env.viewport.child.hidden, true);
  env.viewport.dispatch('pointerdown', { pointerId: 1, button: 0, clientX: 200 });
  assert.equal(env.viewport.capture, undefined);
  env.slider.dispose();
});

test('comparison availability follows the calling step, not another stage', async () => {
  const { canCompare } = await browserModules()('/texto_off/comparison/launcher.js');
  const row = { cleaned: true, level2_status: 'pending', comparison_available: false };
  assert.equal(canCompare(row, '1'), true);
  assert.equal(canCompare(row, '2'), false);
  assert.equal(canCompare(row, '3'), false);
  assert.equal(canCompare({ level2_status: 'no_change' }, '2'), true);
  assert.equal(canCompare({ comparison_available: true }, '4'), true);
});
