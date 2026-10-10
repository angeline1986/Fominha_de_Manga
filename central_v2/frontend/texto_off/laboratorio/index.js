/** Laboratório: painel de navegação independente, sem execução de filtros. */
export function render(container) {
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/texto_off/laboratorio/style.css";
  document.head.appendChild(stylesheet);

  const root = document.createElement("section");
  root.className = "lab-page";
  root.innerHTML = `
    <div class="lab-title">LABORATÓRIO</div>
    <div class="lab-columns">
      <aside class="lab-panel lab-pages">
        <div class="lab-panel-head"><strong>Páginas</strong><span class="lab-pill">−</span></div>
        <div class="lab-pages-body">
          <div class="lab-page-selectors">
            <select data-lab-chapter aria-label="Selecionar capítulo"><option value="1">Cap. 1</option></select>
            <select data-lab-page aria-label="Selecionar página" disabled><option value="">Página</option></select>
          </div>
          <input type="search" data-lab-search placeholder="Buscar página..." aria-label="Buscar página" />
          <div class="lab-page-list" data-lab-list aria-label="Páginas do capítulo"></div>
          <nav class="lab-pager" aria-label="Paginação das páginas">
            <button type="button" data-lab-prev aria-label="Página anterior" disabled>‹</button>
            <span data-lab-counter>1 / 1</span>
            <button type="button" data-lab-next aria-label="Próxima página" disabled>›</button>
          </nav>
          <div class="lab-preview" data-lab-preview hidden><img alt="Prévia da página" /></div>
        </div>
      </aside>
      <main class="lab-workspace">
        <div class="lab-toolbar"><div><strong>Laboratório</strong><div class="lab-muted">Uma imagem original · três tratamentos independentes</div></div>
          <div class="lab-tool-group"><button disabled type="button">−</button><span>40%</span><button disabled type="button">+</button><button disabled type="button">1:1</button><button disabled type="button">Foco</button></div>
        </div>
        <div class="lab-stage">
          <div class="lab-cards">
            <section class="lab-image"><header>ORIGINAL</header><div class="lab-placeholder">Aguardando seleção da página</div></section>
            <section class="lab-image"><header>DEGRADÊ</header><div class="lab-placeholder">Aguardando execução</div></section>
            <section class="lab-image"><header>ARTÍSTICO</header><div class="lab-placeholder">Aguardando execução</div></section>
            <section class="lab-image"><header>SUAVE</header><div class="lab-placeholder">Aguardando execução</div></section>
          </div>
        </div>
      </main>
      <aside class="lab-panel lab-actions"><div class="lab-panel-head"><strong>Laboratório</strong></div>
        <div class="lab-panel-body"><strong class="lab-subtitle">Seleção de áreas</strong><button disabled class="lab-wide">Selecionar área</button>
          <p class="lab-muted">Nenhuma área selecionada.</p><hr/><strong class="lab-subtitle">Tratamentos</strong>
          <button disabled class="lab-wide">Gerar as 3 versões</button><p class="lab-muted">Filtros ainda não conectados.</p>
        </div>
      </aside>
    </div>`;
  container.replaceChildren(root);

  const pageSize = 13;
  const chapterSelect = root.querySelector("[data-lab-chapter]");
  const pageSelect = root.querySelector("[data-lab-page]");
  const search = root.querySelector("[data-lab-search]");
  const list = root.querySelector("[data-lab-list]");
  const prev = root.querySelector("[data-lab-prev]");
  const next = root.querySelector("[data-lab-next]");
  const counter = root.querySelector("[data-lab-counter]");
  const preview = root.querySelector("[data-lab-preview]");
  const previewImage = preview.querySelector("img");

  // Os dados reais serão ligados à API numa etapa separada.
  // Pode receber listas de páginas via evento, sem simular arquivos existentes.
  let pagesByChapter = {};
  let currentPage = 0;
  let selectedName = "";
  let disposed = false;

  function hidePreview() {
    preview.hidden = true;
    previewImage.removeAttribute("src");
  }

  function chapterPages() {
    return pagesByChapter[chapterSelect.value] || [];
  }

  function filtered() {
    const needle = search.value.trim().toLocaleLowerCase("pt-BR");
    return chapterPages().filter((page) => page.name.toLocaleLowerCase("pt-BR").includes(needle));
  }

  function draw() {
    hidePreview();
    const all = chapterPages();
    const rows = filtered();
    const count = Math.max(1, Math.ceil(rows.length / pageSize));
    currentPage = Math.max(0, Math.min(currentPage, count - 1));
    prev.disabled = currentPage === 0;
    next.disabled = currentPage >= count - 1;
    counter.textContent = `${currentPage + 1} / ${count}`;

    pageSelect.replaceChildren(new Option("Página", ""));
    all.forEach((page) => pageSelect.add(new Option(page.name, page.name)));
    pageSelect.disabled = all.length === 0;
    pageSelect.value = all.some((page) => page.name === selectedName) ? selectedName : "";

    list.replaceChildren();
    const subset = rows.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
    if (!all.length) {
      const empty = document.createElement("p");
      empty.className = "lab-muted lab-page-empty";
      empty.textContent = "Nenhuma página carregada.";
      list.append(empty);
    } else if (!subset.length) {
      const empty = document.createElement("p");
      empty.className = "lab-muted lab-page-empty";
      empty.textContent = "Nenhuma página encontrada.";
      list.append(empty);
    }
    subset.forEach((page) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "lab-page-entry";
      button.textContent = page.name;
      button.classList.toggle("is-selected", page.name === selectedName);
      button.addEventListener("click", () => { selectedName = page.name; draw(); });
      button.addEventListener("mouseenter", () => {
        if (!page.previewUrl) return;
        previewImage.src = page.previewUrl;
        preview.hidden = false;
      });
      button.addEventListener("mouseleave", hidePreview);
      button.addEventListener("focus", () => {
        if (!page.previewUrl) return;
        previewImage.src = page.previewUrl;
        preview.hidden = false;
      });
      button.addEventListener("blur", hidePreview);
      list.append(button);
    });
  }

  function loadPages(event) {
    if (disposed) return;
    const chapters = event.detail?.chapters;
    if (!chapters || typeof chapters !== "object" || Array.isArray(chapters)) return;
    pagesByChapter = {};
    Object.entries(chapters).forEach(([chapter, pages]) => {
      if (!Array.isArray(pages)) return;
      pagesByChapter[chapter] = pages.filter((p) => typeof p?.name === "string").map((p) => ({
        name: p.name,
        previewUrl: typeof p.previewUrl === "string" ? p.previewUrl : "",
      }));
    });
    chapterSelect.replaceChildren();
    Object.keys(pagesByChapter).forEach((chapter) => chapterSelect.add(new Option(`Cap. ${chapter}`, chapter)));
    if (!chapterSelect.options.length) chapterSelect.add(new Option("Capítulo", ""));
    currentPage = 0;
    selectedName = "";
    search.value = "";
    draw();
  }

  chapterSelect.addEventListener("change", () => { currentPage = 0; selectedName = ""; search.value = ""; draw(); });
  pageSelect.addEventListener("change", () => {
    selectedName = pageSelect.value;
    const index = filtered().findIndex((p) => p.name === selectedName);
    if (index >= 0) currentPage = Math.floor(index / pageSize);
    draw();
  });
  search.addEventListener("input", () => { currentPage = 0; draw(); });
  prev.addEventListener("click", () => { if (currentPage > 0) { currentPage--; draw(); } });
  next.addEventListener("click", () => { if (currentPage < Math.ceil(filtered().length / pageSize) - 1) { currentPage++; draw(); } });
  root.addEventListener("laboratorio:pages", loadPages);
  draw();

  return () => {
    disposed = true;
    root.removeEventListener("laboratorio:pages", loadPages);
    if (root.parentNode === container) root.remove();
    stylesheet.remove();
  };
}
