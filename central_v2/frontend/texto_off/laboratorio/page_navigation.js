import { positionPreview, previewNearElement } from "/texto_off/laboratorio/preview_position.js";
import { getContext, subscribeContext } from "/_app/state/context.js";

/** Seleção de origem, capítulo, página e navegação paginada do Laboratório. */
export function connectPageNavigation(root, { beforeDraw = () => {}, afterDraw = () => {} } = {}) {
  const pageSize = 13;
  const chapterSelect = root.querySelector("[data-lab-chapter]");
  const pageSelect = root.querySelector("[data-lab-page]");
  const list = root.querySelector("[data-lab-list]");
  const prev = root.querySelector("[data-lab-prev]");
  const next = root.querySelector("[data-lab-next]");
  const counter = root.querySelector("[data-lab-counter]");
  const preview = root.querySelector("[data-lab-preview]");
  const previewImage = preview.querySelector("img");
  let pagesByChapter = {};
  let currentPage = 0;
  let selectedName = "";
  let currentSource = "img";
  let selectedFile = null;

  function chapterPages() { return selectedFile ? [selectedFile] : pagesByChapter[chapterSelect.value] || []; }
  function syncSourceButtons() {
    root.querySelectorAll("[data-lab-source]").forEach((button) => {
      const active = button.dataset.labSource === currentSource;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
  }
  function hidePreview() {
    preview.hidden = true;
    previewImage.removeAttribute("src");
  }
  function draw() {
    beforeDraw();
    hidePreview();
    const all = chapterPages();
    const rows = chapterPages();
    const count = Math.max(1, Math.ceil(rows.length / pageSize));
    currentPage = Math.max(0, Math.min(currentPage, count - 1));
    prev.disabled = currentPage === 0;
    next.disabled = currentPage >= count - 1;
    counter.textContent = `${currentPage + 1} / ${count}`;

    pageSelect.replaceChildren(new Option("Pág.", ""));
    all.forEach((page) => pageSelect.add(new Option(page.name, page.name)));
    pageSelect.disabled = all.length === 0;
    pageSelect.value = all.some((page) => page.name === selectedName) ? selectedName : "";
    list.replaceChildren();
    const subset = rows.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
    if (!all.length || !subset.length) {
      const empty = document.createElement("p");
      empty.className = "lab-muted lab-page-empty";
      empty.textContent = all.length ? "Nenhuma página encontrada." : "Nenhuma página carregada.";
      list.append(empty);
    }
    subset.forEach((page) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "lab-page-entry";
      button.textContent = page.name;
      button.classList.toggle("is-selected", page.name === selectedName);
      button.addEventListener("click", () => { selectedName = page.name; draw(); });
      button.addEventListener("pointerenter", (event) => {
        if (!page.previewUrl || event.pointerType === "touch") return;
        previewImage.src = page.previewUrl;
        preview.hidden = false;
        positionPreview(preview, event.clientX, event.clientY);
      });
      button.addEventListener("pointermove", (event) => {
        if (!preview.hidden && event.pointerType !== "touch") {
          positionPreview(preview, event.clientX, event.clientY);
        }
      });
      button.addEventListener("pointerleave", hidePreview);
      button.addEventListener("focus", () => {
        if (!page.previewUrl) return;
        previewImage.src = page.previewUrl;
        preview.hidden = false;
        previewNearElement(preview, button);
      });
      button.addEventListener("blur", hidePreview);
      list.append(button);
    });
    afterDraw();
  }

  function loadPages(event) {
    if (selectedFile) return;
    const chapters = event.detail?.chapters;
    if (!chapters || typeof chapters !== "object" || Array.isArray(chapters)) return;
    pagesByChapter = {};
    Object.entries(chapters).forEach(([chapter, pages]) => {
      if (!Array.isArray(pages)) return;
      pagesByChapter[chapter] = pages.filter((page) => typeof page?.name === "string").map((page) => ({
        name: page.name,
        previewUrl: typeof page.previewUrl === "string" ? page.previewUrl : "",
      }));
    });
    chapterSelect.replaceChildren(new Option("Cap.", ""));
    Object.keys(pagesByChapter).forEach((chapter) => chapterSelect.add(new Option(chapter, chapter)));
    currentPage = 0;
    selectedName = "";
    draw();
  }
  function setSource(source, notify = true) {
    if (!["img", "merge"].includes(source)) return;
    const wasFile = Boolean(selectedFile);
    selectedFile = null;
    if (wasFile) {
      chapterSelect.replaceChildren(new Option("Cap.", ""));
      selectedName = "";
      currentPage = 0;
    }
    currentSource = source;
    syncSourceButtons();
    if (wasFile) draw();
    if (notify) root.dispatchEvent(new CustomEvent("laboratorio:source", { detail: { source } }));
  }

  const unsubscribeContext = subscribeContext(({ provider, manga }) => {
    if (!selectedFile || (selectedFile.provider === provider && selectedFile.manga === manga)) return;
    currentSource = selectedFile.previousSource;
    selectedFile = null;
    pagesByChapter = {};
    selectedName = "";
    chapterSelect.replaceChildren(new Option("Cap.", ""));
    syncSourceButtons();
    draw();
  });

  chapterSelect.addEventListener("change", () => { currentPage = 0; selectedName = ""; draw(); });
  pageSelect.addEventListener("change", () => {
    selectedName = pageSelect.value;
    const index = chapterPages().findIndex((page) => page.name === selectedName);
    if (index >= 0) currentPage = Math.floor(index / pageSize);
    draw();
  });
  prev.addEventListener("click", () => { if (currentPage > 0) { currentPage--; draw(); } });
  next.addEventListener("click", () => {
    if (currentPage < Math.ceil(chapterPages().length / pageSize) - 1) { currentPage++; draw(); }
  });
  root.querySelectorAll("[data-lab-source]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.labSource !== currentSource) setSource(button.dataset.labSource);
    });
  });
  root.addEventListener("laboratorio:pages", loadPages);

  function onPaginationKey(event) {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key) || event.defaultPrevented || event.repeat
        || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || !root.isConnected) return;
    if (event.target instanceof Element && event.target.closest(
      'input, textarea, select, button, [contenteditable], [role="slider"], [role="dialog"], [role="listbox"]'
    )) return;
    if (document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')) return;
    const button = event.key === 'ArrowLeft' ? prev : next;
    if (button.disabled) return;
    event.preventDefault();
    button.click();
  }
  document.addEventListener('keydown', onPaginationKey);

  return {
    draw,
    getSelection() {
      if (selectedFile) return { source: "file", chapter: selectedFile.chapter,
        page: selectedName, path: selectedName ? selectedFile.path : "",
        pages: [{ name: selectedFile.name, previewUrl: selectedFile.previewUrl }] };
      return { source: currentSource, chapter: chapterSelect.value,
        page: selectedName, pages: chapterPages() };
    },
    setSource,
    selectFile(file) {
      const { provider, manga } = getContext();
      const previousSource = selectedFile?.previousSource || currentSource;
      selectedFile = { ...file, provider, manga, previousSource };
      currentSource = "file";
      chapterSelect.replaceChildren(new Option(file.folderLabel, file.chapter));
      chapterSelect.value = file.chapter;
      selectedName = file.name;
      currentPage = 0;
      syncSourceButtons();
      draw();
    },
    selectPage(chapter, page) {
      if (!pagesByChapter[chapter]?.some((item) => item.name === page)) return false;
      chapterSelect.value = chapter;
      selectedName = page;
      currentPage = Math.floor(chapterPages().findIndex((item) => item.name === page) / pageSize);
      draw();
      return true;
    },
    dispose() {
      unsubscribeContext();
      root.removeEventListener("laboratorio:pages", loadPages);
      document.removeEventListener('keydown', onPaginationKey);
    },
  };
}
