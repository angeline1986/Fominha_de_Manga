import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

function progressDocument() {
  const nodes = new Map();
  const element = {
    hidden: false,
    attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    querySelector(selector) {
      if (!nodes.has(selector)) nodes.set(selector, { textContent: '', attributes: {}, setAttribute(name, value) { this.attributes[name] = value; } });
      return nodes.get(selector);
    },
  };
  return { element, nodes, createElement() { return element; } };
}

test('shared progress bar exposes chapter count, detail and accessible percentage', async () => {
  const document = progressDocument();
  const load = browserModules({ document });
  const { createJobProgress } = await load('/_shared/progress/progress.js');
  const progress = createJobProgress();
  progress.update({
    busy: true, title: 'Auto-Merge Nível I · running', message: 'Cap. 3: Analisando imagem 104/104',
    percent: 47.5, completed: 1, total: 4,
  });

  assert.equal(document.element.hidden, false);
  assert.equal(document.nodes.get('[data-count]').textContent, '1 de 4 capítulo(s) · 48%');
  assert.equal(document.nodes.get('[data-message]').textContent, 'Cap. 3: Analisando imagem 104/104');
  const bar = document.nodes.get('progress');
  assert.equal(bar.value, 48);
  assert.equal(bar.attributes['aria-valuetext'], '48% concluído');
  progress.update({ busy: false });
  assert.equal(document.element.hidden, true);
});
