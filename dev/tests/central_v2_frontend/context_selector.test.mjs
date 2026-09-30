import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

class ElementStub {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.attributes = new Map();
    this.classList = {
      values: new Set(),
      toggle(name, force) { force ? this.values.add(name) : this.values.delete(name); },
      contains(name) { return this.values.has(name); },
    };
  }
  append(...children) { this.children.push(...children); }
  setAttribute(name, value) { this.attributes.set(name, value); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  addEventListener() {}
}

function findAll(element, predicate) {
  return [ ...(predicate(element) ? [element] : []), ...element.children.flatMap((child) => findAll(child, predicate)) ];
}

test('provider and work names appear inside their comboboxes with accessible names', async () => {
  const load = browserModules({ document: { createElement: (tag) => new ElementStub(tag) } });
  const { createContextSelector } = await load('/_shell/context_selector.js');
  const selector = createContextSelector({
    provider: 'comix', manga: 'Gazing at you',
    catalog: { comix: ['Gazing at you'] },
  });
  const triggers = findAll(selector, (element) => element.className === 'context-combobox-trigger');
  assert.equal(selector.children.length, 2);
  assert.equal(triggers.length, 2);
  assert.deepEqual(triggers.map((trigger) => trigger.getAttribute('aria-label')),
    ['Provider: comix', 'Obra: Gazing at you']);
  assert.deepEqual(triggers.map((trigger) => trigger.children.map((child) => child.textContent)), [
    ['Provider', 'comix'], ['Obra', 'Gazing at you'],
  ]);
});

test('unselected fields use their field name instead of Selecionar', async () => {
  const load = browserModules({ document: { createElement: (tag) => new ElementStub(tag) } });
  const { createContextSelector } = await load('/_shell/context_selector.js');
  const selector = createContextSelector({ provider: '', manga: '', catalog: { comix: [] } });
  const triggers = findAll(selector, (element) => element.className === 'context-combobox-trigger');
  assert.deepEqual(triggers.map((trigger) => trigger.getAttribute('aria-label')),
    ['Provider', 'Obra']);
  assert.deepEqual(triggers.map((trigger) => trigger.children[1].textContent), ['', '']);
  assert.deepEqual(triggers.map((trigger) => trigger.classList.contains('is-empty')), [true, true]);
  assert.equal(triggers[1].disabled, true);
});
