import { iconMarkup } from "/_shared/icons/icons.js";
import { renderMergeManualSession } from "/processamento/merge_manual/session_view.js";

const filters = [["all", "Todos"], ["pending", "Pendentes"], ["resolved", "Resolvidos"]];

export function createMergeManualView() {
  const element = document.createElement("section");
  element.className = "manual-merge-page";
  element.innerHTML = `
    <header><h1 title="Selecione capítulos para configurar as faixas de páginas.">Merge Manual</h1></header>
    <div class="manual-merge-toolbar">
      <label><span class="visually-hidden">Buscar capítulo</span><input type="search" data-search placeholder="Buscar capítulo..."></label>
      <div class="manual-merge-filters" role="group" aria-label="Filtrar capítulos">
        ${filters.map(([key, label], index) => `<button type="button" data-filter="${key}" aria-pressed="${index === 0}">${label}</button>`).join("")}
      </div><span class="manual-merge-count" data-count></span>
    </div>
    <p class="manual-merge-message" role="status" aria-live="polite"></p>
    <div class="manual-merge-table-card" data-table></div>
    <div class="manual-merge-sessions" data-sessions></div>
  `;
  const search = element.querySelector("[data-search]");
  const tableHost = element.querySelector("[data-table]");
  const sessionsHost = element.querySelector("[data-sessions]");
  const message = element.querySelector(".manual-merge-message");
  const count = element.querySelector("[data-count]");
  let state = { status: "idle", chapters: [] };
  let sessions = new Map();
  let filter = "all";
  let tableExpanded = true;

  function filteredRows() {
    const term = search.value.trim().toLocaleLowerCase("pt-BR");
    return (state.chapters || []).filter((row) =>
      String(row.chapter).toLocaleLowerCase("pt-BR").includes(term)
      && (filter === "all" || row.status === filter));
  }

  function initialSession(row) {
    const block = row.pending_blocks?.[0];
    return { blockIndex: 0, start: block?.first_page || "", end: block?.last_page || "", zoom: 112, expanded: true };
  }

  function drawTable() {
    tableHost.replaceChildren();
    const rows = filteredRows();
    count.textContent = `${rows.length} capítulo(s) · ${state.summary?.pending || 0} pendente(s)`;
    const table = document.createElement("table");
    table.className = `manual-merge-table${tableExpanded ? "" : " is-collapsed"}`;
    table.innerHTML = `<thead><tr><th>Capítulo</th><th>Resíduos / pendências</th><th>Blocos</th><th>Status</th><th class="manual-merge-action-heading"><button type="button" class="manual-merge-expand" data-toggle aria-label="${tableExpanded ? "Recolher tabela de capítulos" : "Expandir tabela de capítulos"}" aria-expanded="${tableExpanded}">${iconMarkup(tableExpanded ? "collapse" : "expand")}</button></th></tr></thead><tbody ${tableExpanded ? "" : "hidden"}></tbody>`;
    const body = table.tBodies[0];
    for (const row of rows) {
      const tr = body.insertRow();
      tr.className = sessions.has(row.chapter) ? "is-selected" : "";
      tr.tabIndex = 0;
      tr.innerHTML = `<td><button type="button" class="manual-merge-row-button"></button></td><td></td><td></td><td><span class="manual-merge-badge ${row.status}">${statusLabel(row.status)}</span></td><td></td>`;
      tr.cells[0].firstElementChild.textContent = `Cap. ${row.chapter}`;
      tr.cells[1].textContent = row.status === "pending" ? `${row.pending_pages} página(s)`
        : row.status === "resolved" ? "Sem residual" : row.error || "Estado inválido";
      tr.cells[2].textContent = row.blocks_count || "—";
      tr.addEventListener("click", () => toggleSession(row));
      tr.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggleSession(row); }
      });
      body.append(tr);
    }
    tableHost.append(table);
    table.querySelector("[data-toggle]").addEventListener("click", toggleTable);
    if (!rows.length && state.status === "ready") tableHost.textContent = "Nenhum capítulo corresponde ao filtro.";
  }

  function toggleSession(row) {
    const current = sessions.get(row.chapter);
    const shouldExpand = !current || !current.expanded;
    if (shouldExpand) for (const [chapter, session] of sessions) {
      sessions.set(chapter, { ...session, expanded: false, focusMode: false });
    }
    sessions.set(row.chapter, current ? { ...current, expanded: shouldExpand, focusMode: false } : initialSession(row));
    tableExpanded = false;
    draw();
  }

  function toggleTable() { tableExpanded = !tableExpanded; drawTable(); }

  function drawSessions() {
    [...sessionsHost.children].forEach((session) => session.disposeFocusMode?.());
    sessionsHost.replaceChildren();
    for (const row of filteredRows()) {
      if (sessions.has(row.chapter)) sessionsHost.append(createSession(row));
    }
  }

  function createSession(row) {
    return renderMergeManualSession({
      row, session: sessions.get(row.chapter), provider: state.provider, manga: state.manga,
      onToggle: () => {
        const current = sessions.get(row.chapter);
        sessions.set(row.chapter, { ...current, expanded: !current.expanded, focusMode: false });
        draw();
      },
      onChange: (next) => {
        sessions.set(row.chapter, next);
        const current = [...sessionsHost.children].find((item) => item.dataset.chapter === row.chapter);
        current?.disposeFocusMode?.();
        current?.replaceWith(createSession(row));
      },
      onOpenCuts: (detail) => sessionsHost.dispatchEvent(new CustomEvent("merge-manual:open-cuts", { bubbles: true, detail })),
    });
  }

  function draw() {
    for (const button of element.querySelectorAll("[data-filter]")) {
      const active = button.dataset.filter === filter;
      button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active));
    }
    drawTable(); drawSessions();
  }

  function onSearch() { draw(); }
  function onFilter(event) { filter = event.currentTarget.dataset.filter; draw(); }
  search.addEventListener("input", onSearch);
  element.querySelectorAll("[data-filter]").forEach((button) => button.addEventListener("click", onFilter));
  return {
    element,
    update(next) {
      if (state.provider !== next.provider || state.manga !== next.manga) { sessions.clear(); search.value = ""; filter = "all"; }
      state = next;
      for (const chapter of sessions.keys()) if (!(state.chapters || []).some((row) => row.chapter === chapter)) sessions.delete(chapter);
      message.textContent = next.status === "idle" ? "Selecione uma obra para carregar os resíduos do Merge Manual."
        : next.status === "loading" ? `Carregando capítulos de ${next.manga}…`
          : next.status === "error" ? next.error : "";
      draw();
    },
    dispose() {
      [...sessionsHost.children].forEach((session) => session.disposeFocusMode?.());
      search.removeEventListener("input", onSearch);
      element.querySelectorAll("[data-filter]").forEach((button) => button.removeEventListener("click", onFilter));
    },
  };
}

function statusLabel(status) {
  return status === "pending" ? "Pendente" : status === "resolved" ? "Resolvido" : "Revisar";
}
