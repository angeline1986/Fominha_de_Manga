import { applyFinalLaboratory, getFinalLaboratoryProposal } from "/_app/api/laboratorio.js";
import { confirmMessage } from "/_shared/messages/messages.js";
import { createFinalReviewView } from "/texto_off/laboratorio/final_review_view.js";

const TREATMENTS = ["degrade", "estilizado", "gradiente_suave", "solidos"];
const LABELS = { degrade: "Degradê", estilizado: "Artístico",
  gradiente_suave: "Suave", solidos: "Sólidos" };

/** Review selection stays local; publication will revalidate the exact version. */
export function connectFinalReview(root) {
  const view = createFinalReviewView();
  const note = root.querySelector("[data-lab-final-selection]");
  const applyButton = root.querySelector("[data-lab-final-apply]");
  const buttons = new Map(TREATMENTS.map((name) =>
    [name, root.querySelector(`[data-lab-review="${name}"]`)]));
  const candidates = new Map();
  const handlers = new Map();
  let selected = null;
  let active = null;
  let disposed = false;
  let applying = false;

  function closeReview() { if (view.dialog.open) view.dialog.close(); }

  function clear(treatment) {
    if (!TREATMENTS.includes(treatment)) return;
    candidates.delete(treatment);
    buttons.get(treatment).hidden = true;
    if (selected?.treatment === treatment) {
      selected = null;
      note.hidden = true;
      note.textContent = "";
      applyButton.hidden = true;
    }
    if (active?.treatment === treatment) closeReview();
  }

  function ready(treatment, request, runId) {
    clear(treatment);
    if (disposed || !TREATMENTS.includes(treatment) || typeof runId !== "string" || !runId) return;
    const { provider, manga, chapter, page } = request;
    if (![provider, manga, chapter, page].every((item) => typeof item === "string" && item)) return;
    candidates.set(treatment, { provider, manga, chapter, page,
      treatment, run_id: runId });
    buttons.get(treatment).hidden = false;
  }

  function prepareView(candidate) {
    view.page.textContent = `Cap. ${candidate.chapter} · ${candidate.page} · ${LABELS[candidate.treatment]}`;
    view.status.textContent = "Validando as imagens e a versão final…";
    view.select.disabled = true;
    for (const image of [view.current, view.candidate]) {
      image.onload = null;
      image.onerror = null;
      image.removeAttribute("src");
    }
    view.dialog.showModal();
  }

  async function open(treatment) {
    const candidate = candidates.get(treatment);
    if (!candidate || disposed || view.dialog.open) return;
    selected = null;
    note.textContent = "";
    note.hidden = true;
    applyButton.hidden = true;
    const controller = new AbortController();
    const review = { treatment, candidate, controller, proposal: null, loaded: 0 };
    active = review;
    prepareView(candidate);
    try {
      const proposal = await getFinalLaboratoryProposal(candidate, controller.signal);
      if (active !== review || candidates.get(treatment) !== candidate || disposed) return;
      if (proposal.run_id !== candidate.run_id || proposal.treatment !== treatment
          || !proposal.version || !proposal.current_image_url || !proposal.candidate_image_url) {
        throw new Error("Resposta de comparação incompleta.");
      }
      review.proposal = proposal;
      view.page.textContent = `Cap. ${proposal.chapter} · ${proposal.page} · ${LABELS[treatment]}`;
      view.status.textContent = "Carregando comparação…";
      for (const [image, url] of [[view.current, proposal.current_image_url],
        [view.candidate, proposal.candidate_image_url]]) {
        image.onload = () => {
          if (active !== review || disposed) return;
          review.loaded++;
          if (review.loaded === 2) {
            view.status.textContent = "Compare a página inteira antes de selecionar.";
            view.select.disabled = false;
          }
        };
        image.onerror = () => {
          if (active !== review || disposed) return;
          view.select.disabled = true;
          view.status.textContent = "A prévia mudou ou não pôde ser carregada. Reabra a comparação.";
        };
        image.src = url;
      }
    } catch (error) {
      if (active !== review || disposed || error.name === "AbortError") return;
      view.status.textContent = error.message || "Não foi possível comparar as imagens.";
    }
  }

  async function choose() {
    if (!active?.proposal || active.loaded !== 2 || view.select.disabled) return;
    const review = active;
    view.select.disabled = true;
    view.status.textContent = "Conferindo se o Consolidado Final ainda é o mesmo…";
    try {
      const latest = await getFinalLaboratoryProposal(review.candidate, review.controller.signal);
      if (active !== review || disposed) return;
      if (latest.version !== review.proposal.version) {
        view.status.textContent = "A versão final mudou. Reabra a comparação.";
        return;
      }
      selected = { ...review.proposal };
      note.textContent = `${LABELS[selected.treatment]} selecionado após comparação · Cap. ${selected.chapter} · ${selected.page}`;
      note.hidden = false;
      applyButton.hidden = false;
      closeReview();
    } catch (error) {
      if (active === review && !disposed && error.name !== "AbortError") {
        view.status.textContent = error.message || "A versão final não pôde ser conferida.";
      }
    }
  }

  function onClose() {
    if (view.dialog.open) return;
    active?.controller.abort();
    active = null;
  }

  async function applySelection() {
    if (!selected || applying || disposed) return;
    const review = selected;
    applying = true;
    applyButton.disabled = true;
    try {
      const confirmed = await confirmMessage({ title: "Aplicar no Consolidado Final",
        message: `Substituir a página inteira ${review.page} (Cap. ${review.chapter}) pelo resultado ${LABELS[review.treatment]}? A versão anterior será arquivada.`,
        confirmText: "Aplicar imagem" });
      if (!confirmed || selected !== review || disposed) return;
      note.textContent = "Aplicando a imagem e registrando o histórico…";
      const fields = Object.fromEntries(["provider", "manga", "chapter", "page", "treatment", "run_id"]
        .map((key) => [key, review[key]]));
      await applyFinalLaboratory({ ...fields, version: review.version, confirmed: true });
      if (disposed || selected !== review) return;
      selected = null;
      applyButton.hidden = true;
      note.textContent = `${LABELS[review.treatment]} aplicado ao Consolidado Final · Cap. ${review.chapter} · ${review.page}`;
    } catch (error) {
      if (disposed || selected !== review) return;
      selected = null;
      applyButton.hidden = true;
      note.textContent = error.status === 409
        ? "O Consolidado Final mudou. Compare as imagens novamente."
        : `Não foi possível aplicar: ${error.message}`;
    } finally {
      applying = false;
      applyButton.disabled = false;
    }
  }

  for (const [treatment, button] of buttons) {
    const handler = () => open(treatment);
    handlers.set(button, handler);
    button.addEventListener("click", handler);
  }
  view.select.addEventListener("click", choose);
  view.close.addEventListener("click", closeReview);
  view.cancel.addEventListener("click", closeReview);
  view.dialog.addEventListener("close", onClose);
  applyButton.addEventListener("click", applySelection);

  return {
    ready, clear,
    getSelection: () => selected && { ...selected },
    dispose() {
      disposed = true;
      active?.controller.abort();
      for (const [button, handler] of handlers) button.removeEventListener("click", handler);
      view.select.removeEventListener("click", choose);
      view.close.removeEventListener("click", closeReview);
      view.cancel.removeEventListener("click", closeReview);
      view.dialog.removeEventListener("close", onClose);
      applyButton.removeEventListener("click", applySelection);
      view.dispose();
    },
  };
}
