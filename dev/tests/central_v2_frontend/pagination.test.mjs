import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

const rows = Array.from({ length: 65 }, (_, i) => i + 1);

test('65 records have five pages with bounded navigation and no missing rows', async () => {
  const load = browserModules();
  const { createPagination } = await load('/_shared/pagination/model.js');
  const pagination = createPagination();
  const collected = [];
  for (let page = 1; page <= 5; page++) {
    const selected = pagination.select(rows);
    assert.equal(selected.page, page);
    assert.equal(selected.pages, 5);
    assert.equal(selected.rows.length, page === 5 ? 5 : 15);
    collected.push(...selected.rows);
    pagination.move(1);
  }
  assert.deepEqual(collected, rows);
  assert.equal(pagination.select(rows).page, 5);
  pagination.move(-100);
  assert.equal(pagination.select(rows).page, 1);
});

test('shrinking and empty results clamp the current page; reset returns to first', async () => {
  const load = browserModules();
  const { createPagination } = await load('/_shared/pagination/model.js');
  const pagination = createPagination();
  pagination.select(rows);
  pagination.move(4);
  const reduced = pagination.select(rows.slice(0, 17));
  assert.equal(reduced.page, 2);
  assert.equal(reduced.start, 16);
  assert.equal(reduced.end, 17);
  pagination.reset();
  assert.equal(pagination.select(rows).page, 1);
  const empty = pagination.select([]);
  assert.equal(empty.start, 0);
  assert.equal(empty.end, 0);
  assert.equal(empty.page, 1);
  assert.equal(empty.rows.length, 0);
});

test('changing the shared configuration affects independent lists', async () => {
  const load = browserModules({}, {
    '/_shared/pagination/config.js': 'export const paginationConfig = Object.freeze({ pageSize: 20 });',
  });
  const { createPagination } = await load('/_shared/pagination/model.js');
  const first = createPagination();
  const second = createPagination();
  assert.equal(first.select(rows).rows.length, 20);
  assert.equal(second.select(rows).rows.length, 20);
  first.move(1);
  assert.equal(first.select(rows).start, 21);
  assert.equal(second.select(rows).start, 1);
});
