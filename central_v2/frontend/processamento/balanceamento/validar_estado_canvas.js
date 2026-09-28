import { balanceamentoImageUrl } from "/_app/api/balanceamento.js";
import { iconMarkup } from "/_shared/icons/icons.js";

export function createBalanceCanvas({ onZoom }) {
  const element = document.createElement("main");
  element.className = "balance-inspection-canvas";
  element.innerHTML = `<header class="balance-canvas-toolbar"><div><strong>Visualização dos merges selecionados</strong><span data-canvas-summary></span></div><div class="balance-canvas-controls"><div class="zoom-control"><button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button><output data-zoom-value>60%</output><button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button><button type="button" data-zoom="reset" aria-label="Visualizar em escala 1 para 1">1:1</button></div><button type="button" class="btn balance-focus-toggle" data-focus-toggle aria-label="Modo Foco" aria-pressed="false">${iconMarkup("focus-exit")} Foco</button></div></header>
    <div class="balance-canvas-viewport"><div class="balance-selected-strips" data-strips></div><p class="balance-canvas-empty" data-empty>Selecione as imagens na lista para comparar suas alturas e proporções.</p></div>
    <footer class="balance-canvas-footer"><span data-rule></span><span>Atalho de foco: F</span></footer>
    <aside class="focus-mode-dock focus-mode-compact" data-focus-dock aria-label="Controles da comparação em foco"><button type="button" data-focus-exit aria-label="Sair do Modo Foco" title="Sair do Modo Foco"><span>×</span></button><span data-focus-divider></span><div class="focus-mode-zoom"><button type="button" data-zoom="+" aria-label="Aumentar zoom">+</button><output data-dock-zoom>60%</output><button type="button" data-zoom="-" aria-label="Diminuir zoom">−</button><button type="button" data-zoom="reset" aria-label="Visualizar em escala 1 para 1">1:1</button></div></aside>`;
  const focusButton = element.querySelector("[data-focus-toggle]");
  const focusDock = element.querySelector("[data-focus-dock]");
  const dockZoom = focusDock.querySelector("[data-dock-zoom]");
  let state = { zoom: 60 };
  element.addEventListener("click", onClick);
  focusDock.addEventListener("click", onClick);

  function update(next) {
    state = { ...state, ...next };
    element.querySelector("[data-zoom-value]").textContent = `${state.zoom}%`;
    dockZoom.textContent = `${state.zoom}%`;
    element.querySelector("[data-canvas-summary]").textContent = state.chapter
      ? `Cap. ${state.chapter.chapter} · ${state.selectedMerges.length} de ${state.chapter.merges.length} merges selecionados`
      : "Selecione um capítulo para inspecionar.";
    element.querySelector("[data-rule]").textContent = state.rule?.description || "A comparação mostra a altura real de cada merge.";
    const selected = (state.chapter?.merges || []).filter((item) => state.selectedMerges.includes(item.file));
    const host = element.querySelector("[data-strips]");
    host.replaceChildren();
    const max = Math.max(1, ...selected.map((item) => Number(item.height) || 0));
    for (const item of selected) {
      const issue = (state.chapter.issues || []).find((row) => row.file === item.file);
      const card = document.createElement("figure");
      card.className = `balance-strip-card ${issue ? "is-short" : "is-ideal"}`;
      const image = document.createElement("img");
      image.src = balanceamentoImageUrl(state.provider, state.manga, state.chapter.chapter, item.file, "merge");
      const height = Number(item.height);
      const hasHeight = Number.isFinite(height) && height > 0;
      image.alt = `${item.file}, ${hasHeight ? `${height.toLocaleString("pt-BR")} pixels` : "altura indisponível"}`;
      image.loading = "lazy";
      image.draggable = false;
      const caption = document.createElement("figcaption");
      caption.innerHTML = `<span title="${escapeHtml(item.file)}">${escapeHtml(item.file)}</span><strong>${hasHeight ? `${height.toLocaleString("pt-BR")} px` : "Altura indisponível"}</strong><i style="width:${hasHeight ? Math.min(100, 100 * height / max) : 0}%"></i><small>${issue ? "Desvio de altura" : item.status === "ERRO" ? "Erro de leitura" : "Dentro da regra"}</small>`;
      card.append(image, caption); host.append(card);
    }
    element.querySelector("[data-empty]").hidden = selected.length > 0;
    host.style.zoom = String(state.zoom / 100);
  }

  function onClick(event) {
    const control = event.target.closest("[data-zoom]");
    if (!control) return;
    const zoom = control.dataset.zoom === "reset" ? 100 : Math.max(30, Math.min(120, state.zoom + (control.dataset.zoom === "+" ? 10 : -10)));
    update({ zoom }); onZoom(zoom);
  }

  update({ selectedMerges: [] });
  return { element, focusButton, focusDock, update, dispose() { element.removeEventListener("click", onClick); focusDock.removeEventListener("click", onClick); } };
}

function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]); }
