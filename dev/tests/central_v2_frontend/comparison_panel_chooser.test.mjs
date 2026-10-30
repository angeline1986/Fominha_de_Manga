import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

test('Quadros keeps two selected and restores their order from view state', async () => {
  const { bindPanelChooser, panelChooserMarkup } = await browserModules()('/texto_off/comparison/panel_chooser.js');
  assert.equal(panelChooserMarkup('level1'), '');
  assert.match(panelChooserMarkup('before_after'), /Quadros/);

  const keys = ['original', 'level1', 'level2', 'final'];
  const labels = ['Original', 'Auto-Cleaner I', 'Auto-Cleaner II', 'Consolidado Final'];
  const inputs = keys.map((key, index) => ({ dataset: { panel: key }, checked: true,
    nextElementSibling: { textContent: labels[index] }, closest() { return this; } }));
  const listeners = new Map();
  const attributes = new Map();
  const button = { addEventListener: (event, fn) => listeners.set(`button:${event}`, fn),
    removeEventListener: (event) => listeners.delete(`button:${event}`),
    setAttribute: (key, value) => attributes.set(key, value), focus() { this.focused = true; } };
  const choices = { hidden: true };
  const root = { querySelector: (selector) => selector === '[data-panel-button]' ? button : choices,
    querySelectorAll: () => inputs, addEventListener: (event, fn) => listeners.set(`root:${event}`, fn),
    removeEventListener: (event) => listeners.delete(`root:${event}`) };
  const calls = [];
  const chooser = bindPanelChooser({ querySelector: () => root },
    { setVisiblePanels: (panels) => calls.push([...panels]) }, ['final', 'original']);

  assert.deepEqual(Array.from(chooser.selected()), ['original', 'final']);
  assert.deepEqual(inputs.map((input) => input.disabled), [true, false, false, true]);
  assert.match(attributes.get('aria-label'), /Original, Consolidado Final/);
  inputs[0].checked = false;
  listeners.get('root:change')({ target: inputs[0] });
  assert.deepEqual(Array.from(chooser.selected()), ['original', 'final']);
  assert.equal(inputs[0].checked, true);

  inputs[2].checked = true;
  listeners.get('root:change')({ target: inputs[2] });
  inputs[0].checked = false;
  listeners.get('root:change')({ target: inputs[0] });
  assert.deepEqual(Array.from(chooser.selected()), ['level2', 'final']);
  assert.deepEqual(calls.at(-1), ['level2', 'final']);
  listeners.get('button:click')();
  assert.equal(attributes.get('aria-expanded'), 'true');
  listeners.get('root:keydown')({ key: 'Escape', preventDefault() {}, stopPropagation() {} });
  assert.equal(choices.hidden, true);
  assert.equal(button.focused, true);
  chooser.dispose();
  assert.equal(listeners.size, 0);
});

class Element {
  constructor() {
    this.nodes = new Map();
    this.style = { setProperty() {} };
    this.classList = { toggle() {} };
  }
  set innerHTML(value) { this.markup = value; }
  querySelector(selector) {
    if (!this.nodes.has(selector)) this.nodes.set(selector, new Element());
    return this.nodes.get(selector);
  }
  querySelectorAll(selector) {
    if (selector !== '.comparison-image-panel') return [];
    this.panels ??= Array.from({ length: (this.markup.match(/<figure /g) || []).length }, () => new Element());
    return this.panels;
  }
  append(child) { this.child = child; }
  replaceChildren(...children) { this.children = children; }
  remove() {}
  removeAttribute() {}
  closest() { return this.canvas; }
}

test('hiding audit panels changes width without reloading or moving the viewport', async () => {
  let decoded = 0;
  class Image extends Element {
    naturalWidth = 400;
    naturalHeight = 600;
    async decode() { decoded++; }
  }
  const load = browserModules({ document: { createElement: () => new Element() }, Image });
  const { createSlider } = await load('/texto_off/comparison/slider.js');
  const viewport = new Element();
  viewport.canvas = { scrollTop: 90, scrollLeft: 25 };
  const slider = createSlider(viewport, () => {}, 'before_after');
  await slider.load(['original', 'level1', 'level2', 'final']);
  const frame = viewport.child.child;
  assert.equal(frame.style.width, '694px');
  viewport.canvas.scrollTop = 140;
  slider.setVisiblePanels(['original', 'final']);
  assert.equal(frame.style.width, '338px');
  assert.deepEqual(frame.panels.map((panel) => panel.hidden), [false, true, true, false]);
  assert.equal(frame.style.gridTemplateColumns, 'repeat(2, var(--comparison-image-width))');
  assert.equal(viewport.canvas.scrollTop, 140);
  assert.equal(slider.getZoom(), 0.4);
  slider.setVisiblePanels(['original', 'level2', 'final']);
  assert.equal(frame.style.width, '516px');
  assert.equal(decoded, 4);
  slider.dispose();
});
