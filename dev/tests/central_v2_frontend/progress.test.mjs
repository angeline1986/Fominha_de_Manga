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

test('shared progress component supports inline placement and page counts', async () => {
  const document = progressDocument();
  const load = browserModules({ document });
  const { createJobProgress } = await load('/_shared/progress/progress.js');
  const progress = createJobProgress('Curadoria de Balões', { inline: true, countUnit: 'páginas' });
  progress.update({ busy: true, percent: 11, completed: 2, total: 18 });

  assert.equal(document.element.className, 'job-progress job-progress--inline');
  assert.equal(document.nodes.get('[data-count]').textContent, '2 de 18 páginas · 11%');
  progress.update({ busy: false });
  assert.equal(document.element.hidden, true);
});

test('Sommelier page progress aggregates chapters and completes failed jobs cleanly', async () => {
  const document = progressDocument();
  const load = browserModules({ document }, { './review.js': 'export function renderBubbleSommelierReview() {};' });
  const { aggregateSommelierProgress } = await load('/texto_off/sommelier/index.js');
  const chapters = ['1', '2'];
  const pages = new Map([['1', 18], ['2', 12]]);
  const oneChapter = ['1'];
  const oneChapterPages = new Map([['1', 18]]);

  const start = aggregateSommelierProgress({ status: 'running', chapter: '', progress: {
    stage: 'queued', completed: 0, total: 1, message: 'Na fila',
  } }, oneChapter, oneChapterPages);
  assert.equal(start.percent, 0);
  assert.equal(aggregateSommelierProgress({ status: 'running', chapter: '1', progress: {
    stage: 'page', completed: 1, total: 18,
  } }, oneChapter, oneChapterPages).percent, 6);
  assert.equal(aggregateSommelierProgress({ status: 'running', chapter: '1', progress: {
    stage: 'page', completed: 2, total: 18,
  } }, oneChapter, oneChapterPages).percent, 11);
  const complete = aggregateSommelierProgress({ status: 'running', chapter: '1', progress: {
    stage: 'completed', completed: 1, total: 1,
  } }, oneChapter, oneChapterPages);
  assert.equal(complete.percent, 100);
  assert.equal(complete.completed, 18);

  assert.deepEqual({ ...aggregateSommelierProgress({ status: 'running', chapter: '1', progress: {
    stage: 'page', completed: 1, total: 18, message: 'Página 1/18',
  } }, chapters, pages) }, {
    busy: true, title: 'Curadoria de Balões · running', message: 'Página 1/18',
    percent: 3, completed: 1, total: 30,
  });
  assert.deepEqual({ ...aggregateSommelierProgress({ status: 'running', chapter: '2', progress: {
    stage: 'page', completed: 2, total: 12, message: 'Página 2/12',
  } }, chapters, pages) }, {
    busy: true, title: 'Curadoria de Balões · running', message: 'Página 2/12',
    percent: 67, completed: 20, total: 30,
  });
  assert.deepEqual(aggregateSommelierProgress({ status: 'failed', chapter: '2', progress: {
    stage: 'page', completed: 2, total: 12, message: 'Falha no processamento',
  } }, chapters, pages).busy, false);
});
