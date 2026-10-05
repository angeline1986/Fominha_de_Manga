import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

class Element {
  constructor() {
    this.children = []; this.events = new Map(); this.attrs = {};
    this.classList = { add() {}, remove() {}, toggle() {} };
  }
  querySelector(selector) {
    this.nodes ??= new Map();
    if (!this.nodes.has(selector)) this.nodes.set(selector, new Element());
    return this.nodes.get(selector);
  }
  addEventListener(name, fn) { this.events.set(name, fn); }
  removeEventListener(name) { this.events.delete(name); }
  setAttribute(name, value) { this.attrs[name] = value; }
  replaceChildren(...items) { this.children = items; items.forEach((item) => { item.parentElement = this; }); }
  append(item) { this.children.push(item); item.parentElement = this; }
  after(item) { this.afterItem = item; item.parentElement = this.parentElement; }
  remove() { this.removed = true; }
}

test('Antes & Depois menu action resolves to the read-only triptych audit screen', async () => {
  const audit = {};
  const sources = {
    '/_app/state/context.js': 'export const getContext = () => ({ provider: "comix", manga: "Gazing at you" }); export const subscribeContext = () => () => {};',
    '/_app/api/textoff.js': 'export const fetchMergedTextoff = async () => ({ provider: "comix", manga: "Gazing at you", chapters: [] });',
    '/texto_off/merged/view.js': `export const createMergedView = (onExecute, options) => {
      globalThis.audit.options = options;
      return { element: globalThis.viewElement, update(state) { globalThis.audit.state = state; }, dispose() {} };
    };`,
  };
  const load = browserModules({
    document: { createElement: () => new Element() }, AbortController, audit,
    viewElement: new Element(),
  }, sources);
  const { navigation } = await load('/_shell/navigation.js');
  const menu = navigation.find((section) => section.id === 'texto-off');
  const action = menu.groups[3].items.find((item) => item.label === 'Antes & Depois').id;
  const { resolveRoute } = await load('/_app/router/routes.js');
  assert.equal(action, 'texto-off-quality-audit');
  assert.notEqual(action, 'texto-off-merged-i');
  assert.equal(resolveRoute(action).module, '/texto_off/comparison/audit.js');

  const router = await load('/_app/router/router.js');
  const container = new Element();
  await router.navigate(action, container);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(audit.options.title, 'Auditoria de Qualidade — Antes & Depois');
  assert.equal(audit.options.mode, 'overview');
  assert.equal(audit.options.comparisonMode, 'before_after');
  assert.equal(audit.options.showExecute, false);
  assert.equal(audit.options.selectionEnabled, false);
  assert.equal(audit.state.status, 'ready');
});
