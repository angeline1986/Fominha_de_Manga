import { getFinalLaboratoryHistory, restoreFinalLaboratory } from "/_app/api/laboratorio.js";
import { confirmMessage } from "/_shared/messages/messages.js";
import { createFinalHistoryView } from "/texto_off/laboratorio/final_history_view.js";

const FIELDS = ["provider", "manga", "chapter", "page"];
const ORIGINS = { LABORATORIO: "Laboratório", PINCEL_DEGRADE: "Degradê",
  PINCEL_ARTISTICO: "Artístico", PINCEL_SUAVE: "Gradiente",
  AUTO_CLEANER: "Auto-Cleaner", AUTO_CLEANER_TRANSPARENCIA: "Auto-Cleaner II",
  AUTO_CLEANER_COMBO_TURBO: "Combo Turbo" };

export function connectFinalHistory(root, getPage) {
  const button = root.querySelector("[data-lab-final-history]");
  const view = createFinalHistoryView();
  let active = null;
  let disposed = false;
  let restoring = false;

  function pageChanged() {
    active?.controller.abort();
    active = null;
    if (view.dialog.open) view.dialog.close();
    const identity = getPage();
    button.hidden = !FIELDS.every((key) => typeof identity[key] === "string" && identity[key]);
  }

  function close() { if (view.dialog.open) view.dialog.close(); }

  function clearImages() {
    for (const image of [view.current, view.candidate]) {
      image.onload = null;
      image.onerror = null;
      image.removeAttribute("src");
    }
    view.select.disabled = true;
  }

  function showImages(session) {
    clearImages();
    const revision = session.history.revisions.find(
      (item) => item.revision_id === view.picker.value);
    if (!revision) {
      view.status.textContent = "Não há versões anteriores verificáveis para esta página.";
      return;
    }
    session.revision = revision;
    session.loaded = 0;
    view.status.textContent = "Carregando comparação…";
    for (const [image, url] of [[view.current, session.history.current_image_url],
      [view.candidate, revision.image_url]]) {
      image.onload = () => {
        if (active !== session || disposed) return;
        session.loaded++;
        if (session.loaded === 2) {
          view.status.textContent = "Compare a página inteira antes de restaurar.";
          view.select.disabled = false;
        }
      };
      image.onerror = () => {
        if (active !== session || disposed) return;
        view.select.disabled = true;
        view.status.textContent = "A prévia mudou ou não pôde ser carregada. Reabra o histórico.";
      };
      image.src = url;
    }
  }

  async function open() {
    if (disposed || active || button.hidden) return;
    const identity = getPage();
    if (!FIELDS.every((key) => identity[key])) return;
    const session = { identity, controller: new AbortController(), history: null,
      revision: null, loaded: 0 };
    active = session;
    view.page.textContent = `Cap. ${identity.chapter} · ${identity.page}`;
    view.status.textContent = "Consultando o histórico verificável…";
    view.picker.replaceChildren();
    clearImages();
    view.dialog.showModal();
    try {
      const history = await getFinalLaboratoryHistory(identity, session.controller.signal);
      if (active !== session || disposed) return;
      session.history = history;
      for (const [index, revision] of history.revisions.entries()) {
        const option = document.createElement("option");
        option.value = revision.revision_id;
        const label = ORIGINS[revision.origin] || revision.origin || "Origem desconhecida";
        option.textContent = `${index + 1}. ${label} · ${revision.sha256.slice(0, 12)}`;
        view.picker.append(option);
      }
      view.picker.disabled = !history.revisions.length;
      showImages(session);
    } catch (error) {
      if (active === session && !disposed && error.name !== "AbortError") {
        view.status.textContent = error.message || "Não foi possível consultar o histórico.";
      }
    }
  }

  async function restore() {
    const session = active;
    const revision = session?.revision;
    if (!session?.history || !revision || session.loaded !== 2 || restoring
        || view.select.disabled || disposed) return;
    restoring = true;
    view.select.disabled = true;
    try {
      const confirmed = await confirmMessage({ title: "Restaurar versão anterior",
        message: `Restaurar ${session.identity.page} (Cap. ${session.identity.chapter})? A imagem atual será guardada no histórico.`,
        confirmText: "Restaurar imagem" });
      if (!confirmed || active !== session || disposed || session.revision !== revision) return;
      view.status.textContent = "Restaurando e registrando a versão atual no histórico…";
      await restoreFinalLaboratory({ ...session.identity, version: session.history.version,
        revision_id: revision.revision_id, confirmed: true });
      if (active !== session || disposed) return;
      view.status.textContent = "Versão restaurada. Reabra o histórico para ver o estado atual.";
      view.picker.disabled = true;
      clearImages();
    } catch (error) {
      if (active === session && !disposed) view.status.textContent = error.status === 409
        ? "O Consolidado Final mudou. Reabra o histórico."
        : `Não foi possível restaurar: ${error.message}`;
    } finally {
      restoring = false;
      if (active === session && session.loaded === 2 && view.picker.disabled === false
          && !view.status.textContent.startsWith("Versão restaurada")) view.select.disabled = false;
    }
  }

  function onClose() { active?.controller.abort(); active = null; }
  button.addEventListener("click", open);
  view.picker.addEventListener("change", () => { if (active?.history) showImages(active); });
  view.select.addEventListener("click", restore);
  view.close.addEventListener("click", close);
  view.cancel.addEventListener("click", close);
  view.dialog.addEventListener("close", onClose);
  pageChanged();
  return { pageChanged, dispose() {
    disposed = true;
    active?.controller.abort();
    button.removeEventListener("click", open);
    view.dispose();
  } };
}
