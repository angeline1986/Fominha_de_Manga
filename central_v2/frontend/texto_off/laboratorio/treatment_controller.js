import { getContext } from "/_app/state/context.js";
import { connectRoiSelection } from "/texto_off/laboratorio/roi_selection.js";
import { connectDegrade } from "/texto_off/laboratorio/degrade.js";
import { connectSmooth, connectStylized } from "/texto_off/laboratorio/tratamentos.js";

/** Integra imagem original, ROIs e os três estados experimentais independentes. */
export function connectTreatmentController({ root, navigation, workspace, image }) {
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
      page: selected.page, selections };
  }
  const degrade = connectDegrade({
    root, button: panel.querySelector("[data-lab-degrade]"), getRequest,
  });
  const stylized = connectStylized({
    root, button: panel.querySelector("[data-lab-stylized]"), getRequest,
  });
  const smooth = connectSmooth({
    root, button: panel.querySelector("[data-lab-smooth]"), getRequest,
  });
  const roiObserver = new MutationObserver(() => {
    degrade.invalidate();
    stylized.invalidate();
    smooth.invalidate();
  });
  roiObserver.observe(panel.querySelector(".lab-roi-list"), { childList: true });
  let originalLoadSerial = 0;
  let disposed = false;

  function displayOriginal() {
    const { provider, manga } = getContext();
    const selected = navigation.getSelection();
    const identity = `${provider}|${manga}|${selected.source}|${selected.chapter}|${selected.page}`;
    degrade.reset(identity);
    stylized.reset(identity);
    smooth.reset(identity);
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
      originalLoadSerial++;
      degrade.dispose();
      roiObserver.disconnect();
      stylized.dispose();
      smooth.dispose();
      roi.dispose();
    },
  };
}
