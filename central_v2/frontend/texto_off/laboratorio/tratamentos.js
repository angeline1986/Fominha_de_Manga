import {
  executeSmoothLaboratory,
  executeStylizedLaboratoryJob,
} from "/_app/api/laboratorio.js";

function connectTreatment({ root, button, getRequest, cardIndex, label, execute, progress }) {
  const panel = root.querySelector(`.lab-cards > .lab-image:nth-child(${cardIndex})`);
  const placeholder = panel.querySelector(".lab-placeholder");
  const image = document.createElement("img");
  image.className = "lab-treatment-image";
  image.alt = `Prévia experimental ${label}`;
  image.hidden = true;
  panel.append(image);
  let serial = 0, sourceKey = "";
  const controllers = new Set();

  function setState(state, message, busy = false) {
    placeholder.dataset.state = state;
    placeholder.setAttribute("aria-busy", String(busy));
    placeholder.textContent = message;
    placeholder.hidden = state === "running";
  }

  function clear() {
    serial++;
    image.hidden = true;
    image.removeAttribute("src");
    setState("waiting", "Aguardando execução");
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
      setState("waiting", "Selecione uma imagem carregada e pelo menos uma área.");
      return;
    }
    const id = ++serial;
    const snapshot = JSON.stringify(payload);
    const active = new AbortController();
    controllers.add(active);
    button.disabled = true;
    image.hidden = true;
    image.removeAttribute("src");
    setState("running", `Executando ${label}…`, true);
    const progressRun = progress?.start(`Executando ${label}`);
    try {
      const result = await execute(payload, active.signal, (state) => {
        if (progressRun != null) progress?.update?.(progressRun, state);
      });
      if (!isCurrent(id, snapshot)) return;
      image.onload = () => {
        if (!isCurrent(id, snapshot)) return;
        image.hidden = false;
        setState("completed", "Concluído");
      };
      image.onerror = () => {
        if (!isCurrent(id, snapshot)) return;
        image.hidden = true;
        setState("failed", `Falha ao abrir a prévia ${label}.`);
      };
      image.src = result.image_url;
    } catch (error) {
      if (isCurrent(id, snapshot) && error.name !== "AbortError") {
        setState("failed", `${label} não concluído: ${error.message}`);
      }
    } finally {
      progress?.finish(progressRun);
      controllers.delete(active);
      if (id === serial) button.disabled = false;
    }
  }

  function isCurrent(id, snapshot) {
    return id === serial && JSON.stringify(getRequest()) === snapshot;
  }

  button.addEventListener("click", run);
  return {
    reset,
    invalidate: clear,
    dispose() {
      serial++;
      controllers.forEach((controller) => controller.abort());
      button.removeEventListener("click", run);
      image.remove();
    },
  };
}

export function connectStylized(options) {
  return connectTreatment({ ...options, cardIndex: 3,
    label: "Artístico",
    execute: executeStylizedLaboratoryJob });
}

export function connectSmooth(options) {
  return connectTreatment({ ...options, cardIndex: 4,
    label: "Suave",
    execute: executeSmoothLaboratory });
}
