/** Laboratório: painel de navegação independente, sem execução de filtros. */
import { getContext } from "/_app/state/context.js";
import { connectLaboratorio } from "/texto_off/laboratorio/data_loader.js";
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
        <div class="lab-panel-head"><strong>Páginas</strong><div class="lab-source-toggle" role="group" aria-label="Origem das imagens"><button type="button" data-lab-source="img" class="is-active" aria-pressed="true">IMG</button><button type="button" data-lab-source="merge" aria-pressed="false">MERGE</button></div></div>
        <div class="lab-pages-body">
          <div class="lab-page-selectors">
            <select class="lab-select-chapter" data-lab-chapter aria-label="Selecionar capítulo"><option value="">Cap.</option></select>
            <select class="lab-select-page" data-lab-page aria-label="Selecionar página" disabled><option value="">Pág.</option></select>
            <button type="button" data-lab-explore class="lab-explore-button" title="Explorar arquivos da obra" aria-label="Explorar arquivos da obra">📂</button>
          </div>
          <div class="lab-page-list" data-lab-list aria-label="Páginas do capítulo"></div>
          <nav class="lab-pager" aria-label="Paginação das páginas">
            <button type="button" data-lab-prev aria-label="Página anterior" disabled>‹</button>
            <span data-lab-counter>1 / 1</span>
            <button type="button" data-lab-next aria-label="Próxima página" disabled>›</button>
          </nav>
          <div class="lab-preview" data-lab-preview hidden><img alt="Prévia da página" /></div>
          <dialog class="lab-explorer" data-lab-explorer aria-label="Explorador de arquivos"><header><strong>Arquivos da obra</strong><button type="button" data-lab-explorer-close aria-label="Fechar explorador">×</button></header><div class="lab-explorer-path" data-lab-explorer-path></div><div class="lab-explorer-list" data-lab-explorer-list></div></dialog>
        </div>
      </aside>
      <main class="lab-workspace">
        <div class="lab-toolbar"><div><strong>Laboratório</strong><div class="lab-muted">Uma imagem original · três tratamentos independentes</div></div>
          <div class="lab-tool-group"><button disabled type="button">−</button><span>40%</span><button disabled type="button">+</button><button disabled type="button">1:1</button><button disabled type="button" aria-label="Foco" title="Foco"><svg aria-hidden="true" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m13-5h3a2 2 0 0 1 2 2v3M3 16v3a2 2 0 0 0 2 2h3m13-5v3a2 2 0 0 1-2 2h-3"/></svg></button></div>
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

  // Ferramentas isoladas da tela: não interferem em outros visualizadores.
  const toolbar = root.querySelector(".lab-tool-group");
  const panel = root.querySelector(".lab-actions");
  const panelToggle = document.createElement("button");
  panelToggle.type = "button";
  panelToggle.textContent = "Painel";
  panelToggle.className = "lab-panel-toggle";
  panelToggle.setAttribute("aria-expanded", "false");
  panelToggle.setAttribute("aria-pressed", "false");
  toolbar.append(panelToggle);
  root.classList.remove("lab-panel-open");
  panel.hidden = true;
  const closePanel = document.createElement("button");
  closePanel.type = "button";
  closePanel.className = "lab-close-panel";
  closePanel.textContent = "×";
  closePanel.title = "Fechar painel";
  closePanel.setAttribute("aria-label", "Fechar painel");
  panel.querySelector(".lab-panel-head").append(closePanel);
  function setPanel(open) {
    root.classList.toggle("lab-panel-open", open);
    panel.hidden = !open;
    panelToggle.setAttribute("aria-expanded", String(open));
    panelToggle.setAttribute("aria-pressed", String(open));
  }
  panelToggle.addEventListener("click", () => setPanel(!root.classList.contains("lab-panel-open")));
  closePanel.addEventListener("click", () => setPanel(false));

  const focusButton = toolbar.querySelector("button[title='Foco'], button[aria-label='Foco']")
    || [...toolbar.querySelectorAll("button")].find((button) => button.textContent.trim() === "Foco");
  if (focusButton) {
    focusButton.disabled = false;
    focusButton.setAttribute("aria-label", "Modo Foco");
    focusButton.setAttribute("aria-pressed", "false");
    focusButton.title = "Modo Foco";
    focusButton.addEventListener("click", () => {
      const active = root.classList.toggle("lab-focus-mode");
      focusButton.setAttribute("aria-pressed", String(active));
    });
  }
  // Os botões de zoom passam a controlar a escala do espaço de visualização.
  const zoomButtons = [...toolbar.querySelectorAll("button")].filter((button) =>
    ["−", "+", "1:1"].includes(button.textContent.trim()));
  const zoomOutput = toolbar.querySelector("span");
  let zoom = 40;
  const updateZoom = () => {
    if (zoomOutput) zoomOutput.textContent = `${zoom}%`;
    root.style.setProperty("--lab-view-zoom", String(zoom / 40));
  };
  for (const button of zoomButtons) {
    button.disabled = false;
    button.addEventListener("click", () => {
      const action = button.textContent.trim();
      zoom = action === "1:1" ? 100 : Math.max(30, Math.min(200, zoom + (action === "+" ? 10 : -10)));
      updateZoom();
    });
  }
  updateZoom();

  const pageSize = 13;
  const chapterSelect = root.querySelector("[data-lab-chapter]");
  const pageSelect = root.querySelector("[data-lab-page]");
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

  // O preview segue o ponteiro e muda de lado ao encontrar bordas.
  function positionPreview(element, clientX, clientY) {
    const gap = 16, edge = 8;
    const width = element.offsetWidth || 234;
    const height = element.offsetHeight || 334;
    let left = clientX + gap;
    let top = clientY + gap;
    if (left + width + edge > window.innerWidth) left = clientX - width - gap;
    if (top + height + edge > window.innerHeight) top = clientY - height - gap;
    element.style.left = `${Math.max(edge, Math.min(left, Math.max(edge, window.innerWidth - width - edge)))}px`;
    element.style.top = `${Math.max(edge, Math.min(top, Math.max(edge, window.innerHeight - height - edge)))}px`;
  }

  function previewNearElement(element, target) {
    const rect = target.getBoundingClientRect();
    positionPreview(element, rect.right, rect.top + Math.min(rect.height / 2, 20));
  }

  function hidePreview() {
    preview.hidden = true;
    previewImage.removeAttribute("src");
  }

  function chapterPages() {
    return pagesByChapter[chapterSelect.value] || [];
  }

  function filtered() {
    return chapterPages();
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

    pageSelect.replaceChildren(new Option("Pág.", ""));
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
    chapterSelect.replaceChildren(new Option("Cap.", ""));
    Object.keys(pagesByChapter).forEach((chapter) => chapterSelect.add(new Option(chapter, chapter)));
    currentPage = 0;
    selectedName = "";
    draw();
  }

  chapterSelect.addEventListener("change", () => { currentPage = 0; selectedName = ""; draw(); });
  pageSelect.addEventListener("change", () => {
    selectedName = pageSelect.value;
    const index = filtered().findIndex((p) => p.name === selectedName);
    if (index >= 0) currentPage = Math.floor(index / pageSize);
    draw();
  });
  prev.addEventListener("click", () => { if (currentPage > 0) { currentPage--; draw(); } });
  next.addEventListener("click", () => { if (currentPage < Math.ceil(filtered().length / pageSize) - 1) { currentPage++; draw(); } });
  root.addEventListener("laboratorio:pages", loadPages);
  const sourceButtons = [...root.querySelectorAll("[data-lab-source]")];
  let currentSource = "img";
  sourceButtons.forEach((button) => button.addEventListener("click", () => {
    const source = button.dataset.labSource;
    if (source === currentSource) return;
    currentSource = source;
    sourceButtons.forEach((item) => {
      const active = item.dataset.labSource === source;
      item.classList.toggle("is-active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    root.dispatchEvent(new CustomEvent("laboratorio:source", { detail: { source } }));
  }));

  const dialog = root.querySelector("[data-lab-explorer]");
  const explorerPath = root.querySelector("[data-lab-explorer-path]");
  const explorerList = root.querySelector("[data-lab-explorer-list]");
  const explorerButton = root.querySelector("[data-lab-explore]");
  let browserController;
  let browserSerial = 0;
  let browserPath = "";
  const explorerPreview = document.createElement("aside");
  explorerPreview.className = "lab-explorer-hover-preview";
  explorerPreview.hidden = true;
  const explorerPreviewImage = document.createElement("img");
  explorerPreviewImage.alt = "Prévia do arquivo";
  explorerPreview.append(explorerPreviewImage);
  // O preview deve pertencer ao dialog para ficar na top layer, acima do backdrop.
  dialog.append(explorerPreview);
  function hideExplorerPreview() {
    explorerPreview.hidden = true;
    explorerPreviewImage.removeAttribute("src");
  }
  async function browse(path = "") {
    hideExplorerPreview();
    const { provider, manga } = getContext();
    if (!provider || !manga) { explorerList.textContent = "Selecione uma obra."; return; }
    browserController?.abort();
    browserController = new AbortController();
    const id = ++browserSerial;
    explorerList.textContent = "Carregando arquivos...";
    const params = new URLSearchParams({ provider, manga, browse: "1", path });
    try {
      const response = await fetch(`/api/textoff/laboratorio/pages?${params}`, {
        signal: browserController.signal, cache: "no-store",
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
      if (id !== browserSerial || !dialog.open) return;
      browserPath = payload.path;
      // O caminho absoluto não é exibido.
      explorerPath.textContent = `${provider}/${manga}${browserPath ? `/${browserPath}` : ""}`;
      explorerList.replaceChildren();
      if (browserPath) {
        const up = document.createElement("button");
        up.type = "button";
        up.textContent = "← Pasta anterior";
        up.addEventListener("click", () => browse(browserPath.split("/").slice(0, -1).join("/")));
        explorerList.append(up);
      }
      for (const item of payload.entries) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = `${item.type === "directory" ? "📁" : "🖼"} ${item.name}`;
        button.addEventListener("click", () => {
          if (item.type === "directory") { browse(item.path); return; }
          // Seleciona apenas arquivos presentes em IMG/<cap> ou 02_MERGE/<cap>.
          const segments = item.path.split("/");
          const isImg = segments.length === 3 && segments[0] === "IMG";
          const isMerge = segments.length === 4 && segments[0] === "FLUXO_SECUNDARIO" && segments[1] === "02_MERGE";
          if (!isImg && !isMerge) return;
          const source = isImg ? "img" : "merge";
          const chapter = segments.at(-2);
          const page = segments.at(-1);
          const choose = () => {
            if (!pagesByChapter[chapter]?.some((p) => p.name === page)) return;
            chapterSelect.value = chapter;
            selectedName = page;
            currentPage = Math.floor(chapterPages().findIndex((p) => p.name === page) / pageSize);
            draw();
            dialog.close();
          };
          if (source === currentSource) choose();
          else {
            currentSource = source;
            sourceButtons.forEach((b) => {
              b.classList.toggle("is-active", b.dataset.labSource === source);
              b.setAttribute("aria-pressed", String(b.dataset.labSource === source));
            });
            root.addEventListener("laboratorio:pages", choose, { once: true });
            root.dispatchEvent(new CustomEvent("laboratorio:source", { detail: { source } }));
          }
        });
        if (item.type === "file") {
          const showExplorerPreview = (event) => {
            if (event?.pointerType === "touch") return;
            const args = new URLSearchParams({ provider, manga, browse_image: "1", path: item.path });
            explorerPreviewImage.src = `/api/textoff/laboratorio/pages/image?${args}`;
            explorerPreview.hidden = false;
            if (event?.clientX !== undefined) {
              positionPreview(explorerPreview, event.clientX, event.clientY);
            } else {
              previewNearElement(explorerPreview, button);
            }
          };
          button.addEventListener("pointerenter", showExplorerPreview);
          button.addEventListener("pointermove", (event) => {
            if (!explorerPreview.hidden && event.pointerType !== "touch") {
              positionPreview(explorerPreview, event.clientX, event.clientY);
            }
          });
          button.addEventListener("focus", showExplorerPreview);
          button.addEventListener("pointerleave", hideExplorerPreview);
          button.addEventListener("blur", hideExplorerPreview);
        }
        explorerList.append(button);
      }
    } catch (error) {
      if (error.name !== "AbortError") explorerList.textContent = error.message;
    }
  }
  explorerButton.addEventListener("click", () => { dialog.showModal(); browse(""); });
  root.querySelector("[data-lab-explorer-close]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { browserController?.abort(); hideExplorerPreview(); });
  draw();
  const disconnect = connectLaboratorio(root);

  return () => {
    disposed = true;
    disconnect();
    browserController?.abort();
    hideExplorerPreview();
    explorerPreview.remove();
    dialog.close();
    root.removeEventListener("laboratorio:pages", loadPages);
    if (root.parentNode === container) root.remove();
    stylesheet.remove();
  };
}
