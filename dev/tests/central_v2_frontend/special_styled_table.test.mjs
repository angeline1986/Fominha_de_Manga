import test from 'node:test';
import assert from 'node:assert/strict';
import { Element, setup } from './special_treatments_table_helpers.mjs';

const tick = () => new Promise((resolve) => setImmediate(resolve));
const occurrence = (id, status = 'pending', page = 'art.png') => ({ id, page, status,
  roi: { x: 10, y: 12, width: 20, height: 24 },
  preview: { width: 100, height: 100, sha256: 'page-sha' } });

test('Artístico expands and collapses three levels in one table', async () => {
  const { load, tables } = setup({ mockReview: true });
  const { render } = await load('/texto_off/especiais/level7.js');
  const dispose = render(new Element()); await tick();
  assert.equal(JSON.stringify(tables.at(-1).rows.map((row) => row.type)), '["chapter","page","occurrence"]');
  const page = tables.at(-1).rows[1];
  tables.at(-1).columns[1].render(page).children[0].events.click();
  assert.equal(JSON.stringify(tables.at(-1).rows.map((row) => row.type)), '["chapter","page"]');
  const chapter = tables.at(-1).rows[0];
  tables.at(-1).columns[1].render(chapter).children[0].events.click();
  assert.equal(JSON.stringify(tables.at(-1).rows.map((row) => row.type)), '["chapter"]');
  tables.at(-1).columns[1].render(chapter).children[0].events.click();
  assert.equal(JSON.stringify(tables.at(-1).rows.map((row) => row.type)), '["chapter","page"]');
  dispose();
});

test('Artístico keeps treatment choices independent and sends only selected occurrences', async () => {
  const { load, tables, data, requests } = setup({ mockReview: true });
  data.estilizado.chapters[0].occurrences = [occurrence('A'), occurrence('B'), occurrence('C', 'processed')];
  const { render } = await load('/texto_off/especiais/level7.js');
  const container = new Element(), dispose = render(container); await tick();
  const root = container.children[0];
  let table = tables.at(-1);
  const a = table.rows.find((row) => row.item?.id === 'A');
  const b = table.rows.find((row) => row.item?.id === 'B');
  const treatmentA = table.columns[4].render(a);
  treatmentA.value = 'none'; treatmentA.events.change();
  table = tables.at(-1);
  assert.equal(table.columns[4].render(a).value, 'none');
  assert.equal(table.columns[4].render(b).value, 'estilizado');
  const checkboxB = table.columns[0].render(b);
  checkboxB.checked = true; checkboxB.events.change();
  assert.equal(root.nodes['[data-count]'].textContent, '1');
  assert.equal(root.nodes['[data-execute]'].disabled, false);
  table = tables.at(-1);
  table.columns[1].render(table.rows[0]).children[0].events.click();
  assert.equal(root.nodes['[data-count]'].textContent, '1');
  tables.at(-1).columns[1].render(tables.at(-1).rows[0]).children[0].events.click();
  assert.equal(tables.at(-1).columns[0].render(b).checked, true);
  table = tables.at(-1);
  assert.equal(table.columns[0].render(a).disabled, true);
  assert.equal(table.columns[0].render(table.rows.find((row) => row.item?.id === 'C')).disabled, true);
  root.nodes['[data-execute]'].events.click(); await tick();
  assert.equal(JSON.stringify(requests[0][3]), '["2"]');
  assert.equal(JSON.stringify(requests[0][6]), JSON.stringify([{ chapter: '2', page: 'art.png', id: 'B' }]));
  dispose();
});

test('Artístico paginates chapters with the shared controls', async () => {
  const { load, data, tables } = setup({ mockReview: true });
  data.estilizado.chapters = Array.from({ length: 16 }, (_, index) => ({
    chapter: String(index + 1), pages: ['art.png'], status: 'pending',
    occurrences: [occurrence(`art-${index + 1}`)],
  }));
  const { render } = await load('/texto_off/especiais/level7.js');
  const container = new Element(), dispose = render(container); await tick();
  const footer = container.children[0].nodes['[data-footer]'].children[0];
  assert.equal(footer.children[0].children[0].value, '15');
  assert.equal(footer.children[1].children[1].textContent, '1 / 2');
  assert.equal(tables.at(-1).rows.filter((row) => row.type === 'chapter').length, 15);
  const first = tables.at(-1).rows.find((row) => row.type === 'occurrence');
  const checkbox = tables.at(-1).columns[0].render(first);
  checkbox.checked = true; checkbox.events.change();
  assert.equal(container.children[0].nodes['[data-count]'].textContent, '1');
  const currentFooter = container.children[0].nodes['[data-footer]'].children[0];
  currentFooter.children[1].children[2].events.click();
  assert.equal(tables.at(-1).rows.filter((row) => row.type === 'chapter').length, 1);
  assert.equal(container.children[0].nodes['[data-count]'].textContent, '1');
  assert.equal(container.children[0].nodes['[data-footer]'].children[0].children[1].children[1].textContent, '2 / 2');
  container.children[0].nodes['[data-footer]'].children[0].children[1].children[0].events.click();
  assert.equal(tables.at(-1).columns[0].render(first).checked, true);
  dispose();
});

test('Artístico finds the displayed balloon label and resets the chapter page', async () => {
  const { load, data, tables } = setup({ mockReview: true });
  data.estilizado.chapters[0].occurrences = [occurrence('A'), occurrence('B')];
  const { render } = await load('/texto_off/especiais/level7.js');
  const container = new Element(), dispose = render(container); await tick();
  const query = container.children[0].nodes['[data-query]'];
  query.value = 'Balão 02'; query.events.input();
  assert.equal(tables.at(-1).rows.filter((row) => row.type === 'occurrence').length, 1);
  assert.equal(tables.at(-1).rows.find((row) => row.type === 'occurrence').item.id, 'B');
  dispose();
});

test('review and reexecution target the clicked occurrence', async () => {
  const { load, data, tables, requests, reviewOpens } = setup({ mockReview: true });
  const chapter = data.estilizado.chapters[0];
  chapter.review_available = true;
  chapter.occurrences = [occurrence('A', 'processed'), occurrence('B', 'processed')]
    .map((item) => ({ ...item, expected_sha256: 'a'.repeat(64),
      current_filter: 'textoff_special_roi_styled_v1', requested_filter: 'textoff_special_roi_styled_v1' }));
  const { render } = await load('/texto_off/especiais/level7.js');
  const dispose = render(new Element()); await tick();
  const table = tables.at(-1), row = table.rows.find((item) => item.item?.id === 'B');
  const actions = table.columns[5].render(row).children;
  actions[1].events.click({ currentTarget: actions[1] });
  assert.equal(JSON.stringify(reviewOpens[0].target), JSON.stringify({ page: 'art.png', occurrence: 'B' }));
  actions[0].events.click(); await tick();
  assert.equal(requests[0][6][0].id, 'B');
  dispose();
});

test('preview uses the selected occurrence image and ROI', async () => {
  const { load, tables, images, body } = setup({ mockReview: true });
  const { render } = await load('/texto_off/especiais/level7.js');
  const dispose = render(new Element()); await tick();
  const table = tables.at(-1), row = table.rows.find((item) => item.type === 'occurrence');
  const trigger = table.columns[1].render(row).children[0];
  trigger.events.pointerenter();
  assert.equal(images[0].url, '/preview/2/art.png?id=art-1&sha=page-sha');
  assert.equal(body.children.at(-1).hidden, false);
  images[0].onload();
  assert.match(body.children.at(-1).children[2].textContent, /ROI 1,2 · 3×4/);
  assert.equal(body.children.at(-1).children[1].draws.length, 1);
  trigger.events.pointerleave();
  assert.equal(body.children.at(-1).hidden, true);
  dispose();
});

test('page restore sends only the clicked page to the verified flow', async () => {
  const { load, data, tables, restoreCalls, body } = setup({ mockReview: true });
  data.estilizado.chapters[0].pages = ['art.png', 'other.png'];
  data.estilizado.chapters[0].occurrences.push(occurrence('other-1', 'processed', 'other.png'));
  const { render } = await load('/texto_off/especiais/level7.js');
  const dispose = render(new Element()); await tick();
  const table = tables.at(-1), page = table.rows.find((row) => row.type === 'page' && row.page === 'other.png');
  table.columns[5].render(page).children[1].events.click(); await tick();
  assert.equal(JSON.stringify(restoreCalls), JSON.stringify([['preview', '2', 'other.png']]));
  assert.match(body.children.at(-1).children[1].textContent, /ocorrência\(s\) ativa\(s\).*execução\(ões\) histórica\(s\)/);
  dispose();
});
