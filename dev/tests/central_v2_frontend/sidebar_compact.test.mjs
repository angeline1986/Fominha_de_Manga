import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

class ClassList {
  constructor(owner) { this.owner = owner; }
  values() { return new Set(this.owner.className.split(/\s+/).filter(Boolean)); }
  contains(value) { return this.values().has(value); }
  add(value) { const values = this.values(); values.add(value); this.owner.className = [...values].join(' '); }
  remove(value) { const values = this.values(); values.delete(value); this.owner.className = [...values].join(' '); }
  toggle(value, force) {
    const enabled = force ?? !this.contains(value);
    enabled ? this.add(value) : this.remove(value);
    return enabled;
  }
}

class Element {
  constructor(tag = 'div', parent = null) {
    this.tagName = tag;
    this.parentElement = parent;
    this.className = '';
    this.classList = new ClassList(this);
    this.dataset = {};
    this.attributes = {};
    this.listeners = new Map();
    this.children = [];
    this.style = { setProperty() {} };
    this.hidden = false;
    this.textContent = '';
  }
  set innerHTML(value) {
    this.html = value;
    if (!value.includes('drill-layer-root')) return;
    this.rootLayer = new Element('section', this);
    this.detailLayer = new Element('section', this);
    this.detailContent = new Element('div', this);
    this.sectionTitle = new Element('strong', this);
    this.backButton = new Element('button', this);
    this.roots = [...value.matchAll(/data-section="([^"]+)"/g)].map((match) => {
      const button = new Element('button', this.rootLayer);
      button.className = 'drill-root-item';
      button.dataset.section = match[1];
      return button;
    });
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  append(...items) { this.children.push(...items); }
  addEventListener(type, listener) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.push(listener);
    this.listeners.set(type, handlers);
  }
  removeEventListener(type, listener) {
    this.listeners.set(type, (this.listeners.get(type) ?? []).filter((item) => item !== listener));
  }
  dispatchEvent(event) {
    event.target ??= this;
    (this.listeners.get(event.type) ?? []).forEach((listener) => listener(event));
    if (event.bubbles) this.parentElement?.dispatchEvent(event);
    return true;
  }
  querySelector(selector) {
    return ({ '.drill-layer-root': this.rootLayer, '.drill-layer-detail': this.detailLayer,
      '.drill-detail-content': this.detailContent, '.drill-section-title': this.sectionTitle,
      '.drill-back': this.backButton })[selector] ?? null;
  }
  querySelectorAll(selector) {
    if (selector === '.drill-root-item') return this.roots ?? [];
    return [];
  }
  closest(selector) {
    if (selector === '[data-section]' && this.dataset.section) return this;
    if (selector === '[data-action]' && this.dataset.action) return this;
    if (selector === '.app-sidebar' && this.classList.contains('app-sidebar')) return this;
    return this.parentElement?.closest(selector) ?? null;
  }
  focus() { this.focused = true; }
  remove() {}
}

const browserWindow = { innerWidth: 1200, innerHeight: 800, addEventListener() {}, removeEventListener() {} };
const document = { body: new Element('body'), createElement: (tag) => new Element(tag) };
const globals = {
  document, window: browserWindow,
  CustomEvent: class { constructor(type, options = {}) { Object.assign(this, { type }, options); } },
};

test('compact sidebar exposes all six source modules as labeled original icons', async () => {
  const load = browserModules();
  const { navigation } = await load('/_shell/navigation.js');
  const { rootItem } = await load('/_shell/drill_navigation_markup.js');
  assert.deepEqual(JSON.parse(JSON.stringify(navigation.map((section) => section.id))), [
    'visao-geral', 'processamento', 'balanceamento', 'gerar-pdf', 'texto-off', 'exportar-arquivos',
  ]);
  for (const section of navigation) {
    const markup = rootItem(section);
    assert.ok(markup.includes(`ui-icon--${section.id}`));
    assert.ok(markup.includes(`aria-label="${section.label}"`));
    assert.ok(markup.includes(`title="${section.label}"`));
    assert.ok(markup.includes('drill-item-label'));
  }
});

test('compact module click expands its existing submenu without navigating first', async () => {
  const load = browserModules(globals);
  const { createDrillNavigation } = await load('/_shell/drill_navigation.js');
  const sidebar = new Element('aside');
  sidebar.className = 'app-sidebar is-collapsed';
  const navigation = new Element('div', sidebar);
  const drill = createDrillNavigation();
  drill.element.parentElement = navigation;
  drill.element.sidebar = sidebar;
  const actions = [];
  navigation.addEventListener('menu:expand-request', () => sidebar.classList.remove('is-collapsed'));
  navigation.addEventListener('menu:action', (event) => actions.push(event.detail.action));

  const module = drill.element.roots.find((button) => button.dataset.section === 'balanceamento');
  const handleClick = drill.element.listeners.get('click').at(-1);
  handleClick({ target: module });
  assert.equal(sidebar.classList.contains('is-collapsed'), false);
  assert.equal(drill.element.classList.contains('is-detail'), true);
  assert.deepEqual(actions, []);

  const sectionModule = await load('/_shell/navigation.js');
  const destination = sectionModule.navigation.find((item) => item.id === 'balanceamento')
    .groups.flatMap((group) => group.items ?? []).find((item) => item.id === 'validar-estado');
  const action = new Element('button', drill.element.detailContent);
  action.dataset.action = destination.id;
  action.textContent = destination.label;
  handleClick({ target: action });
  assert.deepEqual(actions, ['validar-estado']);

  drill.closeSection();
  handleClick({ target: module });
  assert.deepEqual(actions, ['validar-estado', 'validar-estado']);
  assert.equal(module.classList.contains('is-current'), true);
  assert.equal(module.attributes['aria-expanded'], 'true');
  drill.dispose();
});
