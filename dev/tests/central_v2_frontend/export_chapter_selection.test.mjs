import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.children = []; this.listeners = {}; this.hidden = false;
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  dispatch(type) { this.listeners[type]?.(); }
  querySelectorAll(selector) {
    const tags = selector.split(',').map(tag => tag.trim());
    const descendants = this.children.flatMap(child => [child, ...child.querySelectorAll(selector)]);
    return descendants.filter(child => tags.includes(child.tag));
  }
}

test('filtra os dois conteúdos pelos capítulos marcados e respeita a seleção manual', async () => {
  const load = browserModules();
  const { chapterCatalog, filesForChapters } =
    await load('/exportar_arquivos/chapter_selection.js');
  const sources = {
    textoff_merged: [
      { path: '1/page-a.png' }, { path: '1/page-b.png' }, { path: '2/page-c.png' },
    ],
    pdf_merge: [{ path: '1/1.pdf' }, { path: '3/3.pdf' }],
  };
  const catalog = chapterCatalog(sources, { textoff_merged: ['1/page-b.png', '2/page-c.png'] });
  assert.deepEqual(JSON.parse(JSON.stringify(catalog.chapters)),
    [['1', 2], ['2', 1], ['3', 1]]);
  assert.deepEqual(JSON.parse(JSON.stringify(filesForChapters(catalog, new Set(['2'])))), {
    textoff_merged: ['2/page-c.png'], pdf_merge: [],
  });
});

test('checkboxes e ações selecionam capítulos antes da exportação', async () => {
  const load = browserModules({ document: { createElement: tag => new Element(tag) } });
  const { chapterCatalog, createChapterSelection } =
    await load('/exportar_arquivos/chapter_selection.js');
  const container = new Element();
  let changes = 0;
  const picker = createChapterSelection(container, () => { changes++; });
  assert.match(container.children[3].children[0].textContent, /Simule a exportação/);
  assert.equal(container.children[2].children[0].disabled, true);
  picker.show(chapterCatalog({ textoff_merged: [
    { path: '1/a.png' }, { path: '2/b.png' },
  ] }, {}));
  const actions = container.children[2];
  const list = container.children[3];
  list.children[0].children[0].checked = false;
  list.children[0].children[0].dispatch('change');
  assert.deepEqual(JSON.parse(JSON.stringify(picker.fileSelection())),
    { textoff_merged: ['2/b.png'] });
  actions.children[1].dispatch('click');
  assert.equal(picker.hasSelection(), false);
  actions.children[0].dispatch('click');
  assert.equal(picker.hasSelection(), true);
  assert.equal(changes, 3);
  picker.clear();
  assert.match(list.children[0].textContent, /Simule a exportação/);
});
