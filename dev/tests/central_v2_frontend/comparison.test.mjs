import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor() {
    this.nodes = new Map(); this.events = new Map(); this.attrs = {};
    this.className = "";
    this.classList = {
      contains: (name) => this.className.split(/\s+/).includes(name),
      add: (name) => { if (!this.className.split(/\s+/).includes(name)) this.className = `${this.className} ${name}`.trim(); },
      toggle: (name, force) => {
        const classes = new Set(this.className.split(/\s+/).filter(Boolean));
        if (force ?? !classes.has(name)) classes.add(name); else classes.delete(name);
        this.className = [...classes].join(" ");
      },
    };
    this.style = { setProperty: (key, value) => { this.attrs[key] = value; } };
    this.clientWidth = 800; this.clientHeight = 600;
  }
  querySelector(key) { if (!this.nodes.has(key)) this.nodes.set(key, new Element()); return this.nodes.get(key); }
  querySelectorAll(key) {
    if (key === '.comparison-image-panel') {
      if (!this.panels) this.panels = Array.from({ length: 3 }, () => {
        const panel = new Element(); panel.nodes.set('.comparison-image-holder', new Element());
        panel.nodes.set('[data-stage-status]', new Element()); return panel;
      });
      return this.panels;
    }
    return [];
  }
  append(value) { this.child = value; }
  prepend(value) { this.firstChild = value; }
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
  closest() { return this.canvas || null; }
  remove() { this.removed = true; }
}

async function setup(sizes = [[400, 600], [400, 600], [400, 600]], step = '1') {
  const states = [];
  let image = 0;
  class Image extends Element {
    constructor() { super(); [this.naturalWidth, this.naturalHeight] = sizes[image++]; }
    async decode() {}
  }
  const load = browserModules({
    document: { createElement: () => new Element() }, Image,
  });
  const { createSlider } = await load('/texto_off/comparison/slider.js');
  const viewport = new Element();
  viewport.canvas = { scrollTop: 120, scrollLeft: 45 };
  const slider = createSlider(viewport, (...state) => states.push(state), step);
  return { slider, viewport, canvas: viewport.canvas, states };
}

test('triptych loads three aligned images and applies one zoom to all columns', async () => {
  const env = await setup();
  await env.slider.load(['original', 'level1', 'level2'], 'Nível II: com alterações');
  assert.equal(env.states.at(-1)[0], 'ready');
  assert.equal(env.canvas.scrollTop, 0);
  assert.equal(env.canvas.scrollLeft, 0);
  const stage = env.viewport.child;
  const frame = stage.child;
  assert.equal(frame.style.width, '516px');
  assert.equal(frame.style.height, '284px');
  env.slider.zoom(1);
  assert.equal(frame.style.width, '1236px');
  assert.equal(frame.style.height, '644px');
  assert.deepEqual(frame.panels.map((panel) => panel.style.width), ['400px', '400px', '400px']);
  assert.deepEqual(frame.panels.map((panel) => panel.style.width), ['400px', '400px', '400px']);
  assert.equal(env.slider.getImageMetrics().zoom, 1);
  env.slider.dispose();
});

test('comparison refuses mismatched dimensions before enabling interaction', async () => {
  const env = await setup([[400, 600], [400, 600], [400, 601]]);
  await env.slider.load(['original', 'level1', 'level2']);
  assert.equal(env.states.at(-1)[0], 'error');
  assert.match(env.states.at(-1)[1], /dimensões diferentes/);
  assert.equal(env.viewport.child.child.hidden, true);
  env.viewport.dispatch('pointerdown', { pointerId: 1, button: 0, clientX: 200 });
  assert.equal(env.viewport.capture, undefined);
  env.slider.dispose();
});

test('triptych exposes metrics and mounts residue selection on the active result stage', async () => {
  const env = await setup(undefined, '2');
  await env.slider.load(['original', 'level1', 'level2']);
  const metrics = env.slider.getImageMetrics();
  assert.equal(metrics.naturalWidth, 400); assert.equal(metrics.naturalHeight, 600);
  assert.equal(metrics.zoom, 0.4); assert.equal(metrics.mode, 'triptych');
  const overlay = new Element();
  env.slider.mountAfterOverlay(overlay);
  assert.equal(env.viewport.child.child.panels[2].nodes.get('.comparison-image-holder').child, overlay);
  assert.equal(overlay.classList.contains('comparison-after-overlay'), true);
  env.slider.setInteractionMode('residue-selection');
  assert.equal(env.viewport.child.child.classList.contains('is-residue-selection'), true);
  env.slider.setInteractionMode('normal');
  assert.equal(env.viewport.child.child.classList.contains('is-residue-selection'), false);
  env.slider.dispose();
});

test('triptych availability follows the valid Level I prerequisite', async () => {
  const { canCompare } = await browserModules()('/texto_off/comparison/launcher.js');
  const row = { cleaned: true, level2_status: 'pending', comparison_available: false };
  assert.equal(canCompare(row, '1'), true);
  assert.equal(canCompare(row, '2'), true);
  assert.equal(canCompare(row, '3'), false);
  assert.equal(canCompare({ level2_status: 'no_change' }, '2'), false);
  assert.equal(canCompare({ comparison_available: true }, '4'), true);
});

test('comparison launcher replaces the table view and removes it on close or disposal', async () => {
  const added = [];
  const context = { provider: 'comix', manga: 'Manga' };
  let closeScreen, screenDisposals = 0, screenRemovals = 0, restored = 0, unsubscribed = 0;
  class Button extends Element {
    click() { this.events.get('click')?.(); }
  }
  const origin = new Element();
  origin.parentElement = { scrollTop: 73 };
  origin.classList = {
    values: new Set(), add(name) { this.values.add(name); }, remove(name) { this.values.delete(name); },
    contains(name) { return this.values.has(name); },
  };
  origin.after = (node) => added.push(node);
  const focus = { isConnected: true, focus() { restored += 1; } };
  const screenElement = { remove() { screenRemovals += 1; } };
  const load = browserModules({
    document: { createElement: () => new Button() },
    createTestScreen(_context, onBack) {
      closeScreen = onBack;
      return { element: screenElement, start() {}, dispose() { screenDisposals += 1; } };
    },
    getTestContext: () => context,
    subscribeTestContext: () => () => { unsubscribed += 1; },
  }, {
    '/_app/state/context.js': 'export const getContext = () => getTestContext(); export const subscribeContext = (fn) => subscribeTestContext(fn);',
    '/_shared/icons/icons.js': 'export const iconMarkup = (name) => name;',
    '/texto_off/comparison/screen.js': 'export const createComparisonScreen = (...args) => createTestScreen(...args);',
  });
  const { createComparisonLauncher } = await load('/texto_off/comparison/launcher.js');
  const launcher = createComparisonLauncher(origin, '1');
  const button = launcher.column.render({ chapter: '12', cleaned: true });
  button.isConnected = true; button.focus = focus.focus;
  button.click();
  assert.equal(origin.classList.contains('comparison-origin-hidden'), true);
  assert.equal(added.length, 1);
  assert.equal(added[0], screenElement);
  closeScreen();
  assert.equal(screenRemovals, 1);
  assert.equal(origin.classList.contains('comparison-origin-hidden'), false);
  assert.equal(origin.parentElement.scrollTop, 73);
  assert.equal(restored, 1);
  assert.equal(unsubscribed, 1);
  button.click(); launcher.dispose();
  assert.equal(screenDisposals, 2);
  assert.equal(screenRemovals, 2);
});
