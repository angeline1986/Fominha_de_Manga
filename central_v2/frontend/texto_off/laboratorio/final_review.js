import { applyFinalLaboratory, getFinalLaboratoryProposal } from "/_app/api/laboratorio.js";
import { confirmMessage } from "/_shared/messages/messages.js";

const TREATMENTS = ["degrade", "estilizado", "gradiente_suave", "solidos"];
const LABELS = { degrade: "Degradê", estilizado: "Artístico",
  gradiente_suave: "Suave", solidos: "Sólidos" };

/** Select a completed card; the backend binds its result to one final-page version. */
export function connectFinalReview(root, revealPanel = () => {}) {
  const note = root.querySelector("[data-lab-final-selection]");
  const applyButton = root.querySelector("[data-lab-final-apply]");
  const buttons = new Map(TREATMENTS.map((name) =>
    [name, root.querySelector(`[data-lab-final-select="${name}"]`)]));
  const candidates = new Map();
  const handlers = new Map();
  let selected = null;
  let pending = null;
  let applying = false;
  let disposed = false;

  function message(value) {
    note.textContent = value;
    note.hidden = !value;
  }

  function render() {
    for (const [treatment, button] of buttons) {
      const chosen = selected?.treatment === treatment;
      button.hidden = !candidates.has(treatment);
      button.disabled = applying;
      button.setAttribute("aria-pressed", String(chosen));
      button.textContent = chosen ? "Selecionado" : "Selecionar";
      const description = chosen
        ? `${LABELS[treatment]} selecionado para o Consolidado Final`
        : `Selecionar ${LABELS[treatment]} para o Consolidado Final`;
      button.setAttribute("aria-label", description);
      button.title = description;
    }
    applyButton.hidden = !selected;
    applyButton.disabled = applying;
  }

  function discard() {
    pending?.controller.abort();
    pending = null;
    selected = null;
    render();
  }

  function clear(treatment) {
    if (!TREATMENTS.includes(treatment)) return;
    const wasSelected = selected?.treatment === treatment;
    const wasPending = pending?.candidate.treatment === treatment;
    candidates.delete(treatment);
    if (wasSelected || wasPending) {
      discard();
      message("");
    }
    render();
  }

  function ready(treatment, request, runId) {
    clear(treatment);
    if (disposed || !TREATMENTS.includes(treatment) || typeof runId !== "string" || !runId) return;
    const { provider, manga, chapter, page } = request;
    if (![provider, manga, chapter, page].every((value) => typeof value === "string" && value)) return;
    candidates.set(treatment, { provider, manga, chapter, page, treatment, run_id: runId });
    render();
  }

  function validProposal(proposal, candidate) {
    return proposal && proposal.provider === candidate.provider
      && proposal.manga === candidate.manga && proposal.treatment === candidate.treatment
      && proposal.run_id === candidate.run_id
      && ["chapter", "page", "version", "current_sha256", "candidate_sha256"]
        .every((key) => typeof proposal[key] === "string" && proposal[key]);
  }

  async function select(treatment) {
    const candidate = candidates.get(treatment);
    if (!candidate || disposed || applying) return;
    if (selected?.candidate === candidate) {
      discard();
      message("");
      return;
    }
    discard();
    const session = { candidate, controller: new AbortController() };
    pending = session;
    revealPanel();
    message(`Conferindo o destino de ${LABELS[treatment]} no Consolidado Final…`);
    note.scrollIntoView?.({ block: "nearest" });
    try {
      const proposal = await getFinalLaboratoryProposal(candidate, session.controller.signal);
      if (pending !== session || candidates.get(treatment) !== candidate || disposed) return;
      if (!validProposal(proposal, candidate)) throw new Error("Proposta incompleta ou divergente.");
      selected = { ...proposal, candidate };
      message(`${LABELS[treatment]} selecionado · Cap. ${proposal.chapter} · ${proposal.page}. A versão anterior será preservada.`);
    } catch (error) {
      if (pending === session && !disposed && error.name !== "AbortError") {
        message(`Não foi possível selecionar: ${error.message}`);
      }
    } finally {
      if (pending === session) pending = null;
      render();
    }
  }

  async function applySelection() {
    const choice = selected;
    if (!choice || applying || disposed) return;
    applying = true;
    render();
    try {
      message("Conferindo se a versão final ainda é a mesma…");
      const latest = await getFinalLaboratoryProposal(choice.candidate);
      if (selected !== choice || disposed) return;
      if (!validProposal(latest, choice.candidate) || latest.version !== choice.version
          || latest.current_sha256 !== choice.current_sha256
          || latest.candidate_sha256 !== choice.candidate_sha256) {
        discard();
        message("O Consolidado Final ou o resultado mudou. Selecione o tratamento novamente.");
        return;
      }
      const confirmed = await confirmMessage({ title: "Aplicar no Consolidado Final",
        message: `Substituir a página inteira ${choice.page} (Cap. ${choice.chapter}) pelo resultado ${LABELS[choice.treatment]}? A versão anterior será arquivada.`,
        confirmText: "Aplicar imagem" });
      if (selected !== choice || disposed) return;
      if (!confirmed) {
        message(`${LABELS[choice.treatment]} selecionado · Cap. ${choice.chapter} · ${choice.page}.`);
        return;
      }
      message("Aplicando a imagem e registrando o histórico…");
      const fields = Object.fromEntries(["provider", "manga", "chapter", "page", "treatment", "run_id"]
        .map((key) => [key, choice[key]]));
      await applyFinalLaboratory({ ...fields, version: choice.version, confirmed: true });
      if (selected !== choice || disposed) return;
      selected = null;
      candidates.delete(choice.treatment);
      message(`${LABELS[choice.treatment]} aplicado ao Consolidado Final · Cap. ${choice.chapter} · ${choice.page}.`);
    } catch (error) {
      if (selected !== choice || disposed) return;
      discard();
      message(error.status === 409 || /PROPOSTA_OBSOLETA/.test(error.message)
        ? "O Consolidado Final mudou. Selecione o tratamento novamente."
        : `Não foi possível aplicar: ${error.message}`);
    } finally {
      applying = false;
      render();
    }
  }

  for (const [treatment, button] of buttons) {
    const handler = () => select(treatment);
    handlers.set(button, handler);
    button.addEventListener("click", handler);
  }
  applyButton.addEventListener("click", applySelection);
  render();
  return { ready, clear, getSelection: () => selected && { ...selected },
    dispose() {
      disposed = true;
      discard();
      for (const [button, handler] of handlers) button.removeEventListener("click", handler);
      applyButton.removeEventListener("click", applySelection);
    } };
}
