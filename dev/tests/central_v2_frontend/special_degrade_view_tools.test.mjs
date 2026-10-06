import test from 'node:test';
import assert from 'node:assert/strict';
import { browserModules } from './modules.mjs';

class Element {
  constructor() { this.children = []; this.events = {}; this.dataset = {}; this.attrs = {}; }
  append(item) { this.children.push(item); }
  setAttribute(key, value) { this.attrs[key] = value; }
  getAttribute(key) { return this.attrs[key]; }
  hasAttribute(key) { return key in this.attrs || key === 'data-view' && 'view' in this.dataset; }
  addEventListener(key, callback) { this.events[key] = callback; }
  removeEventListener(key) { delete this.events[key]; }
  querySelectorAll(selector) { return selector === '[data-view]' ? this.children.filter((item) => item.dataset.view) : []; }
  closest() { return this; }
  remove() { this.removed = true; }
}

test('Degradê display controls switch shared slider view and ruler', async () => {
  const load = browserModules({ document: { createElement: () => new Element() } }, {
    '/_shared/icons/icons.js': `export function iconMarkup() { return '<svg></svg>'; }`,
  });
  const { bindDegradeViewTools } = await load('/texto_off/comparison/degrade_view_tools.js');
  const host = new Element(), views = [], rulers = [];
  const dispose = bindDegradeViewTools(host, { setView: (value) => views.push(value),
    setRulers: (value) => rulers.push(value) });
  const controls = host.children[0];
  assert.equal(controls.children[1].getAttribute('aria-pressed'), 'true');
  controls.events.click({ target: controls.children[0] });
  controls.events.click({ target: controls.children[2] });
  controls.events.click({ target: controls.children[1] });
  assert.deepEqual(views, ['before', 'after', 'dual']);
  assert.equal(controls.children[1].getAttribute('aria-pressed'), 'true');
  controls.events.click({ target: controls.children[3] });
  controls.events.click({ target: controls.children[3] });
  assert.deepEqual(rulers, [true, false]);
  dispose();
  assert.equal(controls.removed, true);
});
