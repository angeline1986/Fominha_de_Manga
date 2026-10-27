import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

test('cartões seguem a execução da página e preservam Original', async () => {
  const names = ['degrade', 'estilizado', 'gradiente_suave', 'solidos'];
  const original = { name: 'original' };
  const cards = new Map(names.map((name) => [name, { name }]));
  const container = {
    children: [original, ...cards.values()],
    querySelector(selector) { return cards.get(selector.match(/"([^"]+)"/)?.[1]); },
    append(card) {
      this.children = this.children.filter((item) => item !== card);
      this.children.push(card);
    },
  };
  const root = { querySelector: () => container };
  const { connectCardOrder } = await browserModules()('/texto_off/laboratorio/card_order.js');
  const order = connectCardOrder(root);
  order.setPage('cap1/page1');
  order.complete('solidos', 300);
  order.complete('estilizado', 100);
  order.complete('degrade', 200);
  assert.deepEqual(container.children.map((item) => item.name),
    ['original', 'estilizado', 'degrade', 'solidos', 'gradiente_suave']);
  order.complete('estilizado', 400);
  assert.deepEqual(container.children.map((item) => item.name),
    ['original', 'degrade', 'solidos', 'estilizado', 'gradiente_suave']);
  order.setPage('cap1/page2');
  assert.deepEqual(container.children.map((item) => item.name), ['original', ...names]);
});
