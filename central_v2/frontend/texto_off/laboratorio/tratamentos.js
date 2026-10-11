import {
  executeSmoothLaboratory,
  executeStylizedLaboratory,
} from "/_app/api/laboratorio.js";

function connectTreatment({ root, button, getRequest, cardIndex, statusSelector,
                           label, execute }) {
  const panel = root.querySelector(`.lab-cards > .lab-image:nth-child(${cardIndex})`);
  const placeholder = panel.querySelector(".lab-placeholder");
  const image = document.createElement("img");
  image.className = "lab-treatment-image";
  image.alt = `Prévia experimental ${label}`;
  image.hidden = true;
  panel.append(image);
  const note = root.querySelector(statusSelector);
  let controller = null, serial = 0, sourceKey = "";

  function clear() {
    serial++;
    controller?.abort();
    controller = null;
    image.hidden = true;
    image.removeAttribute("src");
    placeholder.hidden = false;
    placeholder.textContent = "Aguardando execução";
    note.textContent = "Selecione uma página e pelo menos uma área.";
    button.disabled = false;
  }

  function reset(key) {
    if (sourceKey === key) return;
    sourceKey = key;
    clear();
  }

  async function run() {
    const payload = getRequest();
    if (!payload) {
      note.textContent = "Selecione uma imagem carregada e pelo menos uma área.";
      return;
    }
    const id = ++serial;
    controller = new AbortController();
    button.disabled = true;
    image.hidden = true;
    image.removeAttribute("src");
    placeholder.hidden = false;
    placeholder.textContent = `Processando ${label}...`;
    note.textContent = "Processamento experimental em andamento.";
    try {
      const result = await execute(payload, controller.signal);
      if (id !== serial) return;
      image.onload = () => {
        if (id !== serial) return;
        image.hidden = false;
        placeholder.hidden = true;
        note.textContent = `Prévia ${label} pronta. Nenhum arquivo oficial foi alterado.`;
      };
      image.onerror = () => {
        if (id !== serial) return;
        placeholder.textContent = `Falha ao abrir a prévia ${label}.`;
        note.textContent = "O resultado experimental não pôde ser exibido.";
      };
      image.src = result.image_url;
    } catch (error) {
      if (id === serial && error.name !== "AbortError") {
        placeholder.textContent = `${label} não concluído: ${error.message}`;
        note.textContent = "O resultado dos outros tratamentos foi preservado.";
      }
    } finally {
      if (id === serial) button.disabled = false;
    }
  }

  button.addEventListener("click", run);
  return {
    reset,
    invalidate: clear,
    dispose() {
      serial++;
      controller?.abort();
      button.removeEventListener("click", run);
      image.remove();
    },
  };
}

export function connectStylized(options) {
  return connectTreatment({ ...options, cardIndex: 3,
    statusSelector: "[data-lab-stylized-status]", label: "Artístico",
    execute: executeStylizedLaboratory });
}

export function connectSmooth(options) {
  return connectTreatment({ ...options, cardIndex: 4,
    statusSelector: "[data-lab-smooth-status]", label: "Suave",
    execute: executeSmoothLaboratory });
}
