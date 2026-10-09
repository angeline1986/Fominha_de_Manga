import test from 'node:test';
import assert from 'node:assert/strict';
import { Element, setup } from './special_treatments_table_helpers.mjs';

test('Artístico chapter and ROI are executable and use the shared job flow', async () => {
  const { load, tables, requests, progressStates } = setup();
  const { render } = await load('/texto_off/especiais/level7.js');
  const container = new Element(), dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const root = container.children[0], table = tables.at(-1);
  assert.equal(table.rows[0].chapter, '2');
  assert.equal(table.rows[0].pages[0], 'art.png');
  assert.equal(table.rows[0].occurrence_count, 1);
  const checkbox = table.columns[0].render(table.rows[0]);
  assert.equal(checkbox.disabled, false);
  checkbox.checked = true; checkbox.events.change();
  root.nodes['[data-execute]'].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(JSON.stringify(requests[0]),
    JSON.stringify(['comix', 'Example', 'estilizado', ['2'], false, false]));
  assert.ok(progressStates.some((state) => state.busy && state.percent === 50));
  dispose();
});

test('completed Artístico result offers confirmed reexecution', async () => {
  const { load, data, tables, requests, confirmations } = setup();
  data.estilizado.chapters[0].status = 'processed';
  data.estilizado.chapters[0].review_available = true;
  data.estilizado.chapters[0].occurrences = [{ id: 'art-1', page: 'art.png',
    roi: { x: 1, y: 2, width: 3, height: 4 }, status: 'processed',
    expected_sha256: 'current-sha', current_filter: 'Artístico', requested_filter: 'Artístico' }];
  const { render } = await load('/texto_off/especiais/level7.js');
  const container = new Element(), dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const button = tables.at(-1).columns.find((column) => column.id === 'reexecute')
    .render(tables.at(-1).rows[0]);
  assert.equal(button.disabled, false);
  button.events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(JSON.stringify(requests[0]),
    JSON.stringify(['comix', 'Example', 'estilizado', ['2'], false, true,
      [{ chapter: '2', page: 'art.png', id: 'art-1', expected_sha256: 'current-sha' }]]));
  assert.match(confirmations[0].message, /art-1/);
  dispose();
});

test('Artístico sends only the selected balloon on a shared page', async () => {
  const { load, data, tables, requests } = setup();
  const chapter = data.estilizado.chapters[0];
  chapter.status = 'processed';
  chapter.occurrences = ['A', 'B', 'C'].map((id, index) => ({ id, page: 'art.png',
    roi: { x: index * 10, y: 1, width: 4, height: 4 }, status: 'processed',
    expected_sha256: 'page-sha', current_filter: 'Artístico', requested_filter: 'Artístico' }));
  const { render } = await load('/texto_off/especiais/level7.js');
  const container = new Element(), dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const table = tables.at(-1), row = table.rows[0];
  const picker = table.columns.find((column) => column.id === 'styled_occurrence').render(row);
  const [select, detail] = picker.children;
  select.value = 'B'; select.events.change();
  assert.match(detail.textContent, /ROI 10,1/);
  table.columns.find((column) => column.id === 'reexecute').render(row).events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests[0][6].length, 1);
  assert.equal(requests[0][6][0].id, 'B');
  dispose();
});

test('missing Artístico history explains and disables reexecution', async () => {
  const { load, data, tables, requests } = setup();
  data.estilizado.chapters[0].status = 'processed';
  data.estilizado.chapters[0].reexecution_blocked = true;
  data.estilizado.chapters[0].reexecution_block_reason = 'Saída Artística anterior ausente.';
  const { render } = await load('/texto_off/especiais/level7.js');
  const container = new Element(), dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const button = tables.at(-1).columns.find((column) => column.id === 'reexecute')
    .render(tables.at(-1).rows[0]);
  assert.equal(button.disabled, true);
  assert.equal(button.textContent, 'Histórico indisponível');
  assert.match(button.title, /Saída Artística anterior ausente/);
  assert.equal(requests.length, 0);
  dispose();
});

test('page reset previews current and restored images before explicit confirmation', async () => {
  const { load, tables, restoreCalls, confirmations, body, data } = setup();
  data.estilizado.chapters[0].pages = ['other.png', 'art.png'];
  data.estilizado.chapters[0].page_count = 2;
  const { render } = await load('/texto_off/especiais/level7.js');
  const container = new Element(), dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const table = tables.at(-1), row = table.rows[0];
  const control = table.columns.find((column) => column.id === 'restore_page').render(row);
  assert.equal(control.children[0].children.length, 2);
  assert.equal(control.children[0].value, '');
  control.children[0].value = 'art.png';
  control.children[1].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  const dialog = body.children.at(-1);
  assert.match(dialog.children[1].textContent, /Todos os efeitos Artístico, Degradê e Suave/);
  const figures = dialog.children[2].children;
  assert.equal(figures[0].children[1].src, '/restore/current');
  assert.equal(figures[1].children[1].src, '/restore/restored');
  assert.equal(JSON.stringify(restoreCalls), JSON.stringify([['preview', '2', 'art.png']]));
  const accept = dialog.children[3].children[1];
  assert.equal(accept.disabled, true);
  figures[0].children[1].events.load(); figures[1].children[1].events.load();
  assert.equal(accept.disabled, false);
  accept.events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.match(confirmations[0].message, /ROIs aprovadas serão mantidas/);
  assert.equal(JSON.stringify(restoreCalls[1]), JSON.stringify(['publish', 'art.png']));
  dispose();
});
