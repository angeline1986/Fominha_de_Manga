import assert from "node:assert/strict";
import test from "node:test";
import { browserModules } from "./modules.mjs";

function element() {
  return {
    children: [], attributes: {}, listeners: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(name, callback) { this.listeners[name] = callback; },
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; },
  };
}

test("saved proposal page list uses shared inspection page size and navigation", async () => {
  const document = { createElement: element, addEventListener() {} };
  const load = browserModules({ document });
  const { createSavedPagePagination } = await load("/processamento/merge_manual/propostas_salvas_paginacao.js");
  const pages = Array.from({ length: 30 }, (_, index) => `page-${String(index + 1).padStart(3, "0")}.png`);
  const list = { innerHTML: "" }, controls = element();
  const pagination = createSavedPagePagination(() => {});

  pagination.render(list, controls, pages, pages[0]);
  assert.match(list.innerHTML, /page-001\.png/);
  assert.match(list.innerHTML, /page-013\.png/);
  assert.doesNotMatch(list.innerHTML, /page-014\.png/);
  assert.equal(controls.children[0].className, "pagination");

  pagination.show(pages[27], pages);
  pagination.render(list, controls, pages, pages[27]);
  assert.match(list.innerHTML, /page-027\.png/);
  assert.match(list.innerHTML, /page-030\.png/);
  assert.doesNotMatch(list.innerHTML, /page-026\.png/);
});

test("saved proposal viewer exposes standard zoom, focus, and panel controls", async () => {
  const load = browserModules();
  const { savedProposalToolbar, savedProposalFooter } = await load("/processamento/merge_manual/propostas_salvas_visualizador.js");
  const markup = savedProposalToolbar("13", "page-094.png", 0, 9, 40, false);
  assert.match(markup, /data-zoom="-"/);
  assert.match(markup, /data-zoom="\+"/);
  assert.match(markup, /data-zoom="one"/);
  assert.match(markup, /data-focus-toggle/);
  assert.match(markup, /data-panel-toggle[^>]+aria-expanded="false"/);
  assert.match(markup, /1 de 9/);
  assert.match(savedProposalFooter(0, 9), /data-focus-prev[^>]+disabled/);
  assert.match(savedProposalFooter(0, 9), /data-focus-next/);
});

test("saved proposal review opens with the original and keeps the page search absent", async () => {
  const load = browserModules();
  const { pageLabel, savedProposalImagesMarkup, savedProposalReviewMarkup } = await load("/processamento/merge_manual/propostas_salvas_revisao.js");
  const input = { provider: "comix", manga: "Radiant Darkness", chapter: "13", chapters: ["10", "13"],
    currentPage: "page-094.png", pages: ["page-094.png", "page-095.png"], items: [],
    selectedId: "", previewed: false, zoom: 40, panelOpen: false };
  const markup = savedProposalReviewMarkup(input);
  assert.equal(pageLabel("page-094.png"), "Pág. 094");
  assert.match(markup, /data-back-table/);
  assert.match(markup, /Pág\. 094/);
  assert.match(markup, /Página original page-094\.png/);
  assert.match(markup, /saved-review-viewport/);
  assert.doesNotMatch(markup, /data-search|Buscar página/);

  const selected = { proposal_id: "abc", proposal: { outputs: [{ file: "block-001.png" }] } };
  const images = savedProposalImagesMarkup({ ...input, selected, previewed: true });
  assert.match(images, /Página original page-094\.png/);
  assert.match(images, /SAÍDA · block-001\.png/);
});

test("selecting a range leaves only the next pending pages in the review list", async () => {
  const load = browserModules();
  const { pendingForChapter, pagesFor } = await load("/processamento/merge_manual/propostas_salvas_model.js");
  const { savedProposalTableMarkup } = await load("/processamento/merge_manual/propostas_salvas_tabela.js");
  const items = [
    { chapter: "13", status: "FAIXA_SELECIONADA", proposal: { source_files: [{ name: "page-045.png" }] } },
    { chapter: "13", status: "ALTERNATIVA_SUBSTITUIDA", proposal: { source_files: [{ name: "page-046.png" }] } },
    { chapter: "13", status: "PROPOSTA_GERADA", proposal: { source_files: [{ name: "page-059.png" }, { name: "page-060.png" }] } },
  ];
  assert.deepEqual(Array.from(pagesFor(pendingForChapter(items, "13"))), ["page-059.png", "page-060.png"]);
  const table = savedProposalTableMarkup(items);
  assert.match(table, /Faixas confirmadas/);
  assert.match(table, /Cap\. 13<\/td><td>1<\/td><td>1<\/td><td>—<\/td>/);
});
