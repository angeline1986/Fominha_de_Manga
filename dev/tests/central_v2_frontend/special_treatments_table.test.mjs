import test from 'node:test';
import assert from 'node:assert/strict';
import { Element, setup } from './special_treatments_table_helpers.mjs';

const tick = () => new Promise((resolve) => setImmediate(resolve));
const shown = (tables, type) => tables.at(-1).rows.filter((row) => row.type === type);
const check = (tables, row) => tables.at(-1).columns[0].render(row);

test('Degradê and Suave share the approved three-level worklist and pagination', async () => {
  const { load, tables, calls } = setup({ mockReview: true });
  for (const [level, treatment] of [['6', 'degrade'], ['8', 'gradiente_suave']]) {
    const { render } = await load(`/texto_off/especiais/level${level}.js`);
    const container = new Element(), dispose = render(container); await tick();
    const root = container.children[0], table = tables.at(-1);
    assert.equal(calls.at(-1), treatment);
    assert.match(root.className, /artistico-page/);
    assert.equal(table.columns[1].label, 'CAP.');
    assert.equal(JSON.stringify(table.rows.map((row) => row.type)), JSON.stringify(
      treatment === 'degrade' ? ['chapter', 'page', 'occurrence', 'occurrence']
        : ['chapter', 'page', 'occurrence', 'page']));
    const page = shown(tables, 'page')[0];
    table.columns[1].render(page).children[0].events.click();
    assert.equal(shown(tables, 'occurrence').length, 0);
    const chapter = shown(tables, 'chapter')[0];
    tables.at(-1).columns[1].render(chapter).children[0].events.click();
    assert.equal(JSON.stringify(tables.at(-1).rows.map((row) => row.type)), '["chapter"]');
    const footer = root.nodes['[data-footer]'].children[0];
    assert.equal(JSON.stringify(footer.children[0].children[0].children.map((item) => item.value)),
      JSON.stringify(['15', '20', '30', '40', '50']));
    assert.equal(footer.children[1].children[1].textContent, '1 / 1');
    dispose();
  }
});

test('Degradê counts independent selections and refuses a partial chapter', async () => {
  const { load, tables, requests, confirmations } = setup({ mockReview: true });
  const { render } = await load('/texto_off/especiais/level6.js');
  const container = new Element(), dispose = render(container); await tick();
  const root = container.children[0], [first, second] = shown(tables, 'occurrence');
  const choice = tables.at(-1).columns[4].render(first);
  choice.value = 'none'; choice.events.change();
  assert.equal(tables.at(-1).columns[4].render(first).value, 'none');
  assert.equal(tables.at(-1).columns[4].render(second).value, 'degrade');
  const selected = check(tables, second); selected.checked = true; selected.events.change();
  assert.equal(root.nodes['[data-count]'].textContent, '1');
  assert.equal(root.nodes['[data-execute]'].disabled, true);
  assert.match(root.nodes['[data-status]'].textContent, /por capítulo/);
  root.nodes['[data-execute]'].events.click(); await tick();
  assert.equal(requests.length, 0);
  const enable = tables.at(-1).columns[4].render(first);
  enable.value = 'degrade'; enable.events.change();
  const other = check(tables, first); other.checked = true; other.events.change();
  assert.equal(root.nodes['[data-count]'].textContent, '2');
  assert.equal(root.nodes['[data-execute]'].disabled, false);
  root.nodes['[data-execute]'].events.click(); await tick();
  assert.equal(JSON.stringify(requests[0]), JSON.stringify(['comix', 'Example', 'degrade', ['1'], false, false]));
  assert.match(confirmations[0].message, /capítulo/);
  dispose();
});

test('Suave retry selects only failed occurrences and keeps the chapter contract', async () => {
  const { load, tables, data, requests } = setup({ mockReview: true });
  const chapter = data.gradiente_suave.chapters[0];
  chapter.status = 'failed';
  chapter.occurrences[0].status = 'failed';
  chapter.occurrences[1].status = 'pending';
  const { render } = await load('/texto_off/especiais/level8.js');
  const container = new Element(), dispose = render(container); await tick();
  const failed = shown(tables, 'occurrence')[0];
  assert.equal(check(tables, failed).disabled, false);
  const pending = chapter.occurrences[1];
  assert.equal(tables.at(-1).columns[4].render({ type: 'occurrence',
    chapter: '1', page: pending.page, item: pending }).value, 'gradiente_suave');
  const box = check(tables, failed); box.checked = true; box.events.change();
  assert.equal(container.children[0].nodes['[data-count]'].textContent, '1');
  assert.equal(container.children[0].nodes['[data-execute]'].disabled, false);
  container.children[0].nodes['[data-execute]'].events.click(); await tick();
  assert.equal(JSON.stringify(requests[0]), JSON.stringify(['comix', 'Example', 'gradiente_suave', ['1'], true, false]));
  dispose();
});

test('chapter reexecution and occurrence review target supported scopes', async () => {
  const { load, tables, requests, reviewOpens, confirmations, data } = setup({ mockReview: true });
  data.gradiente_suave.chapters[0].review_available = true;
  const { render } = await load('/texto_off/especiais/level8.js');
  const dispose = render(new Element()); await tick();
  const chapter = shown(tables, 'chapter')[0];
  const chapterActions = tables.at(-1).columns[5].render(chapter).children;
  chapterActions[0].events.click({ currentTarget: chapterActions[0] });
  assert.equal(reviewOpens[0].row.chapter, '1');
  chapterActions[1].events.click(); await tick();
  assert.equal(JSON.stringify(requests[0]), JSON.stringify(['comix', 'Example', 'gradiente_suave', ['1'], false, true]));
  assert.match(confirmations[0].message, /imagem vigente do Consolidado Final/);
  const occurrence = shown(tables, 'occurrence')[0];
  const actions = tables.at(-1).columns[5].render(occurrence).children;
  assert.equal(actions[0].disabled, true);
  assert.match(actions[0].title, /indisponível/);
  actions[1].events.click({ currentTarget: actions[1] });
  assert.equal(JSON.stringify(reviewOpens.at(-1).target),
    JSON.stringify({ page: occurrence.page, occurrence: occurrence.item.id }));
  dispose();
});

test('Suave preview crops the real page by ROI and search finds occurrences', async () => {
  const { load, tables, images, body, data } = setup({ mockReview: true });
  const { render } = await load('/texto_off/especiais/level8.js');
  const container = new Element(), dispose = render(container); await tick();
  const occurrence = shown(tables, 'occurrence')[0];
  const trigger = tables.at(-1).columns[1].render(occurrence).children[0];
  trigger.events.pointerenter(); images[0].onload();
  assert.equal(images[0].url, '/preview/1/b.png?id=smooth-0&sha=page-sha');
  assert.equal(body.children.at(-1).children[1].draws.length, 1);
  assert.match(body.children.at(-1).children[2].textContent, /ROI 1,2 · 3×4/);
  const query = container.children[0].nodes['[data-query]'];
  query.value = data.gradiente_suave.chapters[0].occurrences[1].id;
  query.events.input();
  assert.equal(shown(tables, 'occurrence')[0].item.id, query.value);
  dispose();
});

test('Degradê paginates chapters and retains occurrence selection across redraws', async () => {
  const { load, tables, data } = setup({ mockReview: true });
  const template = data.degrade.chapters[0];
  data.degrade.chapters = Array.from({ length: 16 }, (_, index) => ({
    ...template, chapter: String(index + 1), occurrences: template.occurrences.map((item) => ({
      ...item, id: `${item.id}-${index + 1}` })),
  }));
  const { render } = await load('/texto_off/especiais/level6.js');
  const container = new Element(), dispose = render(container); await tick();
  const root = container.children[0], first = shown(tables, 'occurrence')[0];
  const selected = check(tables, first); selected.checked = true; selected.events.change();
  assert.equal(root.nodes['[data-count]'].textContent, '1');
  let footer = root.nodes['[data-footer]'].children[0];
  assert.equal(footer.children[1].children[1].textContent, '1 / 2');
  footer.children[1].children[2].events.click();
  assert.equal(shown(tables, 'chapter').length, 1);
  assert.equal(root.nodes['[data-count]'].textContent, '1');
  footer = root.nodes['[data-footer]'].children[0];
  footer.children[1].children[0].events.click();
  assert.equal(check(tables, first).checked, true);
  assert.equal(shown(tables, 'chapter').length, 15);
  dispose();
});
