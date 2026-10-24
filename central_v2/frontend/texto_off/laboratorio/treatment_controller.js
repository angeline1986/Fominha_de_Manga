import { getContext } from "/_app/state/context.js";
import { connectRoiSelection } from "/texto_off/laboratorio/roi_selection.js";
import { connectDegrade } from "/texto_off/laboratorio/degrade.js";
import { connectSmooth, connectStylized, connectSolid } from "/texto_off/laboratorio/tratamentos.js";

/** Integra imagem original, ROIs e os três estados experimentais independentes. */
export function connectTreatmentController({ root, navigation, workspace, image, progress }) {
  const panel = root.querySelector(".lab-actions");
  const originalPanel = root.querySelector(".lab-cards > .lab-image:first-child");
  const placeholder = originalPanel.querySelector(".lab-placeholder");
  image.className = "lab-original-image";
  image.alt = "Imagem original selecionada";
  image.hidden = true;
  originalPanel.append(image);
  const roi = connectRoiSelection({
    image, button: panel.querySelector(".lab-wide"), panel: panel.querySelector(".lab-panel-body"),
  });
  function getRequest() {
    const selected = navigation.getSelection();
    if (image.hidden || !image.naturalWidth || !selected.page) return null;
    const selections = roi.getBoxesPixels();
    if (!selections.length) return null;
    const { provider, manga } = getContext();
    if (!provider || !manga || !selected.chapter) return null;
    return { provider, manga, source: selected.source, chapter: selected.chapter,
      page: selected.page, ...(selected.path ? { path: selected.path } : {}), selections };
  }
  let progressSequence = 0;
  let progressDisposed = false;
  const activeProgress = new Map();
  function syncProgress() {
    if (progressDisposed || !activeProgress.size) {
      progress?.update({ busy: false });
      return;
    }
    const state = [...activeProgress.values()].pop();
    progress?.update({ busy: true, title: state.title,
      message: state.progress?.message || "Tratamento em andamento.",
      ...(state.progress ? { percent: state.progress.percent,
        completed: state.progress.completed, total: state.progress.total,
        countUnit: "etapa(s) verificadas" } : { indeterminate: true }) });
  }
  const treatmentProgress = {
    start(title) {
      if (progressDisposed) return null;
      const id = ++progressSequence;
      activeProgress.set(id, { title, progress: null });
      syncProgress();
      return id;
    },
    update(id, state) {
      if (progressDisposed || !activeProgress.has(id)) return;
      const entry = activeProgress.get(id);
      entry.progress = state;
      syncProgress();
    },
    finish(id) {
      if (id == null || progressDisposed) return;
      activeProgress.delete(id);
      syncProgress();
    },
  };
  const degrade = connectDegrade({
    root, button: panel.querySelector("[data-lab-degrade]"), getRequest, progress: treatmentProgress,
  });
  const stylized = connectStylized({
    root, button: panel.querySelector("[data-lab-stylized]"), getRequest, progress: treatmentProgress,
  });
  const smooth = connectSmooth({
    root, button: panel.querySelector("[data-lab-smooth]"), getRequest, progress: treatmentProgress,
  });
  const solid = connectSolid({
    root, button: panel.querySelector("[data-lab-solid]"), getRequest, progress: treatmentProgress,
  });
  const roiObserver = new MutationObserver(() => {
    degrade.invalidate();
    stylized.invalidate();
    smooth.invalidate();
    solid.invalidate();
  });
  roiObserver.observe(panel.querySelector(".lab-roi-list"), { childList: true });
  let originalLoadSerial = 0;
  let disposed = false;

  function displayOriginal() {
    const { provider, manga } = getContext();
    const selected = navigation.getSelection();
    const identity = `${provider}|${manga}|${selected.source}|${selected.path || ""}|${selected.chapter}|${selected.page}`;
    degrade.reset(identity);
    stylized.reset(identity);
    smooth.reset(identity);
    solid.reset(identity);
    const page = selected.pages.find((item) => item.name === selected.page);
    const src = page?.previewUrl || "";
    const id = ++originalLoadSerial;
    workspace.setZoomEnabled(false);
    image.hidden = true;
    image.removeAttribute("src");
    workspace.resetZoomDimensions();
    roi.setSource(`${identity}|${src}`, false);
    placeholder.hidden = false;
    if (!page) { placeholder.textContent = "Aguardando seleção da página"; return; }
    if (!src) { placeholder.textContent = "Imagem indisponível para esta página"; return; }
    placeholder.textContent = "Carregando imagem original...";
    image.onload = () => {
      if (disposed || id !== originalLoadSerial) return;
      if (!image.naturalWidth || !image.naturalHeight) {
        image.hidden = true;
        placeholder.hidden = false;
        placeholder.textContent = "Não foi possível carregar a imagem original";
        workspace.resetZoomDimensions();
        return;
      }
      image.hidden = false;
      placeholder.hidden = true;
      workspace.updateZoom();
      workspace.setZoomEnabled(true);
      roi.setSource(`${identity}|${src}`, true);
    };
    image.onerror = () => {
      if (disposed || id !== originalLoadSerial) return;
      image.hidden = true;
      placeholder.hidden = false;
      placeholder.textContent = "Não foi possível carregar a imagem original";
    };
    image.src = src;
  }

  return {
    displayOriginal,
    dispose() {
      disposed = true;
      progressDisposed = true;
      activeProgress.clear();
      progress?.update({ busy: false });
      originalLoadSerial++;
      degrade.dispose();
      roiObserver.disconnect();
      stylized.dispose();
      smooth.dispose();
      solid.dispose();
      roi.dispose();
    },
  };
}
