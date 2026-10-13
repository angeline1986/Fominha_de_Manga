import test from 'node:test';
import assert from 'node:assert/strict';
import { setup } from './special_treatments_table_helpers.mjs';

test('shared pagination keeps its original contract on other pages', async () => {
  const { load } = setup();
  const { createPaginationControls } = await load('/_shared/pagination/pagination.js');
  const footer = createPaginationControls({ page: 1, pages: 5, start: 1, end: 15, total: 65 }, () => {});
  assert.equal(footer.children[0].textContent, '1–15 de 65');
  assert.equal(footer.children[1].children[1].textContent, '1 / 5');
  assert.equal(footer.children[1].children[0].textContent, '<<');
});

test('pagination keeps previous and next disabled at the page boundaries', async () => {
  const { load } = setup();
  const { createPaginationControls } = await load('/_shared/pagination/pagination.js');
  for (const [page, pages, previous, next] of [
    [1, 5, true, false], [3, 5, false, false], [5, 5, false, true], [1, 1, true, true],
  ]) {
    const footer = createPaginationControls({ page, pages, start: 1, end: 15, total: 65 }, () => {});
    const actions = footer.children[1].children;
    assert.equal(actions[0].disabled, previous);
    assert.equal(actions[1].textContent, `${page} / ${pages}`);
    assert.equal(actions[2].disabled, next);
  }
});

test('page size control exposes the approved options and emits the chosen size', async () => {
  const { load } = setup();
  const { createPageSizeControl } = await load('/_shared/pagination/pagination.js');
  let selected;
  const control = createPageSizeControl((size) => { selected = size; });
  assert.deepEqual(control.select.children.map((option) => option.value),
    ['13', '20', '30', '40', '50', '60']);
  control.select.value = '40';
  control.select.events.change();
  assert.equal(selected, 40);
});
