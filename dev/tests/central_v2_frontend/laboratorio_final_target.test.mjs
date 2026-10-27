import assert from 'node:assert/strict';
import test from 'node:test';
import { browserModules } from './modules.mjs';

const load = browserModules();
const { finalPageSelection } = await load('/texto_off/laboratorio/final_target.js');

test('origem Glass aponta para a página oficial no histórico', () => {
  assert.deepEqual(JSON.parse(JSON.stringify(finalPageSelection({ source: 'glass',
    chapter: '1', page: 'page-050-057_clean.png' }))),
  { chapter: '1', page: 'page-050-057.png' });
});

test('arquivo clean do Glass aponta para a página oficial no histórico', () => {
  assert.deepEqual(JSON.parse(JSON.stringify(finalPageSelection({ source: 'file', chapter: 'clean',
    page: 'page-050-057_clean.png', path: 'FLUXO_SECUNDARIO/04_TEXTO_OFF/'
      + '05_AUTO_CLEANER_TRANSPARENCIA/BASICA/1/clean/page-050-057_clean.png' }))),
  { chapter: '1', page: 'page-050-057.png' });
});

test('arquivo images do Check aponta para a página oficial no histórico', () => {
  const selection = { source: 'file', chapter: 'images', page: 'page-060-068.png',
    path: 'FLUXO_SECUNDARIO/04_TEXTO_OFF/'
      + '04_AUTO_CLEANER_CHECK/3/images/page-060-068.png' };
  assert.deepEqual(JSON.parse(JSON.stringify(finalPageSelection(selection))),
    { chapter: '3', page: 'page-060-068.png' });
});

test('arquivo fora do Glass não recebe destino presumido', () => {
  const selection = { source: 'file', chapter: 'clean', page: 'page_clean.png',
    path: 'outra_pasta/1/clean/page_clean.png' };
  assert.deepEqual(JSON.parse(JSON.stringify(finalPageSelection(selection))),
    { chapter: 'clean', page: 'page_clean.png' });
});
