export function pageNavigationMarkup(search = false) {
  return `<div class="comparison-check-selects">
    <label><span class="visually-hidden">Capítulo</span><select data-check-chapter aria-label="Capítulo"></select></label>
    <label><span class="visually-hidden">Página</span><select data-check-page aria-label="Página"></select></label>
  </div>${search ? `<label class="comparison-search"><span class="visually-hidden">Buscar página pelo nome</span>
    <input data-search type="search" placeholder="Buscar página"></label>` : ""}`;
}

export function createPageNavigation(root, { chapter, chapters, onChapterChange, onPageChange }) {
  const chapterSelect = root.querySelector("[data-check-chapter]");
  const pageSelect = root.querySelector("[data-check-page]");
  const eligible = Array.isArray(chapters) ? chapters : [];
  const available = eligible.some((item) => String(item.chapter) === String(chapter))
    ? eligible : [{ chapter }, ...eligible];
  for (const item of available) {
    const option = document.createElement("option");
    option.value = String(item.chapter);
    option.textContent = `Cap. ${item.chapter}`;
    chapterSelect.append(option);
  }
  chapterSelect.value = String(chapter);
  chapterSelect.addEventListener("change", () => {
    if (chapterSelect.value !== String(chapter)) onChapterChange?.(chapterSelect.value);
  });
  pageSelect.addEventListener("change", () => onPageChange?.(Number(pageSelect.value)));
  return {
    setPages(pages, selectedIndex = 0) {
      pageSelect.replaceChildren();
      pages.forEach((page, index) => {
        const option = document.createElement("option");
        option.value = String(index);
        option.textContent = String(page.name ?? page.page_id).replace(/^page-/, "Pág. ").replace(/\.png$/i, "");
        pageSelect.append(option);
      });
      pageSelect.disabled = pages.length === 0;
      pageSelect.value = pages.length ? String(selectedIndex) : "";
    },
    selectPage(index) { pageSelect.value = String(index); },
    setChapterBlocked(blocked) {
      chapterSelect.disabled = blocked;
      chapterSelect.title = blocked ? "Salve as alterações antes de trocar de capítulo." : "";
    },
  };
}
