import test from 'node:test';
import assert from 'node:assert/strict';
import { Element, setup } from './special_treatments_table_helpers.mjs';

test('three routes reuse one table; executable treatments enable pending selection', async () => {
  const { load, calls, tables } = setup();
  for (const [level, treatment, count, pages] of [
    ['6', 'degrade', 2, 1], ['7', 'estilizado', 0, 0], ['8', 'gradiente_suave', 11, 2],
  ]) {
    const { render } = await load(`/texto_off/especiais/level${level}.js`);
    const container = new Element();
    const dispose = render(container);
    await new Promise((resolve) => setImmediate(resolve));
    const root = container.children[0];
    const table = tables.at(-1);
    assert.equal(calls.at(-1), treatment);
    assert.match(root.className, /cleaner-overview sommelier-page/);
    assert.equal(table.rows.length, count ? 1 : 0);
    if (count) {
      assert.equal(table.rows[0].page_count, pages);
      assert.equal(table.rows[0].occurrence_count, count);
    }
    assert.match(root.markup, /data-execute disabled/);
    assert.doesNotMatch(root.markup, /data-summary/);
    const footer = root.nodes['[data-results]'].children.at(-1);
    const sizeLabel = footer.children[0];
    const size = sizeLabel.children[0];
    assert.equal(footer.className, 'pagination');
    assert.equal(sizeLabel.textContent, 'Exibir:');
    assert.deepEqual(size.children.map((item) => item.value),
      ['15', '20', '30', '40', '50']);
    assert.equal(size.value, '15');
    if (count) {
      assert.equal(footer.children[1].children[0].textContent, '<<');
      assert.equal(footer.children[1].children[1].textContent, '1 / 1');
      assert.equal(footer.children[1].children[2].textContent, '>>');
      assert.equal(footer.children[1].children[0].disabled, true);
      assert.equal(footer.children[1].children[2].disabled, true);
    } else assert.equal(footer.children.length, 1);
    assert.equal(table.columns.map((column) => column.label).join('|'),
      treatment === 'degrade' ? '|Capítulo|PÁGINAS|OCORRÊNCIAS|STATUS|AÇÃO|REVISAR'
        : treatment === 'gradiente_suave' ? '|Capítulo|PÁGINAS|OCORRÊNCIAS|STATUS|AÇÃO|REVISAR'
          : '|Capítulo|PÁGINAS|OCORRÊNCIAS|STATUS');
    if (count) {
      if (treatment === 'degrade') {
        const review = table.columns.at(-1).render(table.rows[0]);
        assert.equal(review.disabled, true);
        assert.match(review.markup, /ui-icon--eye/);
        assert.equal(review.events.click, undefined);
      }
      const checkbox = table.columns[0].render(table.rows[0]);
      if (treatment === 'degrade') {
        checkbox.checked = true; checkbox.events.change();
        assert.equal(root.nodes['[data-execute]'].disabled, false);
      } else if (treatment === 'gradiente_suave') assert.equal(checkbox.disabled, true);
      root.nodes['[data-query]'].value = table.rows[0].chapter;
      root.nodes['[data-query]'].events.input();
      assert.equal(tables.at(-1).columns[0].render(tables.at(-1).rows[0]).checked,
        treatment === 'degrade');
    } else assert.equal(table.options.emptyMessage, 'Nenhum tratamento artístico pendente.');
    dispose();
  }
});

test('Degradê submits chapter intent once and reloads after completion', async () => {
  const { load, tables, requests, calls } = setup();
  const { render } = await load('/texto_off/especiais/level6.js');
  const container = new Element();
  const dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const root = container.children[0];
  const checkbox = tables.at(-1).columns[0].render(tables.at(-1).rows[0]);
  checkbox.checked = true; checkbox.events.change();
  const execute = root.nodes['[data-execute]'];
  execute.events.click(); execute.events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests.length, 1);
  assert.equal(JSON.stringify(requests[0]), JSON.stringify(['comix', 'Example', 'degrade', ['1'], false, false]));
  assert.equal(calls.length, 2);
  assert.ok(root.nodes['.auto-merge-toolbar'].afterElement);
  assert.ok(requests.length && requests[0][4] === false);
  assert.equal(execute.disabled, true);
  dispose();
});

test('failed Degradê is selectable and sends explicit retry with progress', async () => {
  const { load, data, tables, requests, progressStates, confirmations } = setup();
  data.degrade.chapters[0].status = 'failed';
  const { render } = await load('/texto_off/especiais/level6.js');
  const container = new Element();
  const dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const root = container.children[0];
  const checkbox = tables.at(-1).columns[0].render(tables.at(-1).rows[0]);
  assert.equal(checkbox.disabled, false);
  checkbox.checked = true; checkbox.events.change();
  const execute = root.nodes['[data-execute]'];
  assert.equal(execute.textContent, 'Tentar novamente');
  execute.events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests[0][4], true);
  assert.match(confirmations[0].message, /Tentar novamente/);
  assert.ok(progressStates.some((state) => state.busy && state.percent === 50));
  assert.equal(progressStates.at(-1).busy, false);
  dispose();
});

test('pending Suave is selectable and submits through shared job progress', async () => {
  const { load, data, tables, requests, progressStates } = setup();
  data.gradiente_suave.chapters[0].status = 'pending';
  const { render } = await load('/texto_off/especiais/level8.js');
  const container = new Element();
  const dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const root = container.children[0];
  const checkbox = tables.at(-1).columns[0].render(tables.at(-1).rows[0]);
  assert.equal(checkbox.disabled, false);
  checkbox.checked = true; checkbox.events.change();
  const execute = root.nodes['[data-execute]'];
  assert.equal(execute.disabled, false);
  execute.events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests[0][2], 'gradiente_suave');
  assert.equal(requests[0][4], false);
  assert.ok(progressStates.some((state) => state.busy && state.percent === 50));
  dispose();
});

test('failed Suave is selectable for explicit retry', async () => {
  const { load, data, tables, requests, confirmations } = setup();
  data.gradiente_suave.chapters[0].status = 'failed';
  const { render } = await load('/texto_off/especiais/level8.js');
  const container = new Element();
  const dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const root = container.children[0];
  const checkbox = tables.at(-1).columns[0].render(tables.at(-1).rows[0]);
  assert.equal(checkbox.disabled, false);
  checkbox.checked = true; checkbox.events.change();
  root.nodes['[data-execute]'].events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests[0][2], 'gradiente_suave');
  assert.equal(requests[0][4], true);
  assert.match(confirmations[0].message, /Tentar novamente/);
  dispose();
});

test('completed Suave offers deliberate reexecution with prior-results confirmation', async () => {
  const { load, tables, requests, confirmations } = setup();
  const { render } = await load('/texto_off/especiais/level8.js');
  const container = new Element();
  const dispose = render(container);
  await new Promise((resolve) => setImmediate(resolve));
  const button = tables.at(-1).columns.find((column) => column.id === 'reexecute')
    .render(tables.at(-1).rows[0]);
  assert.equal(button.disabled, false);
  button.events.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests[0][4], false);
  assert.equal(requests[0][5], true);
  assert.match(confirmations[0].message, /Existem resultados anteriores/);
  assert.match(confirmations[0].message, /Check atual/);
  assert.match(confirmations[0].message, /ROIs aprovadas agora/);
  dispose();
});

test('search by page and status filters restrict chapter rows', async () => {
  const { load, tables } = setup();
  const { renderSpecialTable, matchesSpecialRow } = await load('/texto_off/especiais/table.js');
  assert.equal(matchesSpecialRow({ chapter: '1', pages: ['a.png'], status: 'pending' }, 'a.png', 'pending'), true);
  assert.equal(matchesSpecialRow({ chapter: '1', pages: ['a.png'], status: 'failed' }, '', 'completed'), false);
  const container = new Element();
  const dispose = renderSpecialTable(container, 'gradiente_suave');
  await new Promise((resolve) => setImmediate(resolve));
  const root = container.children[0];
  const query = root.nodes['[data-query]'];
  query.value = 'missing.png'; query.events.input();
  assert.equal(tables.at(-1).rows.length, 0);
  query.value = 'b.png'; query.events.input();
  assert.equal(tables.at(-1).rows.length, 1);
  const buttons = root.nodes['[data-filters]'].children;
  buttons[1].events.click();
  assert.equal(tables.at(-1).rows.length, 0);
  root.nodes['[data-filters]'].children[2].events.click();
  assert.equal(tables.at(-1).rows.length, 1);
  const size = root.nodes['[data-results]'].children.at(-1).children[0].children[0];
  size.value = '20'; size.events.change();
  assert.equal(size.value, '20');
  dispose();
});
