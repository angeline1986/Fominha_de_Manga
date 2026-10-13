import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules, deferred } from './modules.mjs';

class FakeElement {
  constructor() {
    this.listeners = new Map(); this.attributes = new Map(); this.children = [];
    this.classList = { toggle() {}, contains: () => false }; this.disabled = false;
  }
  addEventListener(name, listener) { this.listeners.set(name, listener); }
  removeEventListener(name) { this.listeners.delete(name); }
  setAttribute(name, value) { this.attributes.set(name, value); }
  removeAttribute(name) { this.attributes.delete(name); }
  append(element) { this.children.push(element); }
}

test('sidebar sync button runs once and exposes discreet result feedback', async () => {
  const pending = deferred(); let calls = 0; let timerId = 0;
  const clearedTimers = [];
  const elements = new Map(['#app-navigation', '#app-sidebar', '.sidebar-toggle',
    '[data-action="sync"]', '#app-context', '[data-action="stop-server"]']
    .map((selector) => [selector, new FakeElement()]));
  const root = { innerHTML: '', querySelector: (selector) => elements.get(selector) };
  const load = browserModules({ calls: () => { calls += 1; }, pending: pending.promise,
    setTimeout: () => ++timerId, clearTimeout: (id) => clearedTimers.push(id) }, {
    '/_shared/icons/icons.js': 'export function iconMarkup() { return "icon"; }',
    '/_shell/context.js': 'export function mountContext() { return () => {}; }',
    '/_shell/drill_navigation.js': 'export function createDrillNavigation() { return { element: {}, closeSection() {}, dispose() {} }; }',
    '/_shell/shutdown.js': 'export function bindShutdown() { return () => {}; }',
    '/_app/context/context_controller.js': 'export function synchronizeContext() { globalThis.calls(); return globalThis.pending; }',
  });
  const { mountShell } = await load('/_shell/shell.js');
  const dispose = mountShell(root);
  const button = elements.get('[data-action="sync"]'); const click = button.listeners.get('click');
  const first = click();
  assert.equal(button.disabled, true);
  assert.equal(button.attributes.get('aria-label'), 'Sincronizando…');
  await click(); assert.equal(calls, 1);
  pending.resolve(); await first;
  assert.equal(button.disabled, false);
  assert.equal(button.title, 'Sincronização concluída');
  assert.equal(button.attributes.has('aria-busy'), false);
  dispose();
  assert.equal(button.listeners.has('click'), false);
  assert.deepEqual(clearedTimers, [null, 1]);
});
