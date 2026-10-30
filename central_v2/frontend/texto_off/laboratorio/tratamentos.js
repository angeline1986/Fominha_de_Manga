import {
  executeSmoothLaboratoryJob,
  executeSolidLaboratory,
  executeStylizedLaboratoryJob,
} from "/_app/api/laboratorio.js";
import { treatmentDisplayText } from "/_shared/treatment_names.js";

function connectTreatment({ root, button, getRequest, cardIndex, label, treatment,
  execute, progress, review, order }) {
  const panel = root.querySelector(`[data-lab-card="${treatment}"]`)
    || root.querySelector(`.lab-cards > .lab-image:nth-child(${cardIndex})`);
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
    placeholder.setAttribute("aria-label", message);
    placeholder.title = message;
    placeholder.textContent = message;
    placeholder.hidden = false;
  }

  function clear() {
    serial++;
    review?.clear(treatment);
    order?.clear(treatment);
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
    review?.clear(treatment);
    order?.clear(treatment);
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
        review?.ready(treatment, payload, result.run_id);
        order?.complete(treatment);
      };
      image.onerror = () => {
        if (!isCurrent(id, snapshot)) return;
        image.hidden = true;
        setState("failed", `Falha ao abrir a prévia ${label}.`);
      };
      image.src = result.image_url;
    } catch (error) {
      if (isCurrent(id, snapshot) && error.name !== "AbortError") {
        setState("failed", treatmentDisplayText(`${label} não concluído: ${error.message}`));
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

  function restore(result, identity, expectedSerial) {
    if (serial !== expectedSerial || !result?.run_id || !result.image_url
        || result.treatment !== treatment) return false;
    const id = ++serial;
    image.onload = () => {
      if (id !== serial) return;
      image.hidden = false;
      setState("completed", "Resultado recuperado");
      review?.ready(treatment, identity, result.run_id);
      order?.complete(treatment, result.completed_at);
    };
    image.onerror = () => {
      if (id !== serial) return;
      image.hidden = true;
      setState("failed", "Não foi possível reabrir o resultado salvo.");
    };
    image.src = result.image_url;
    return true;
  }

  button.addEventListener("click", run);
  return {
    reset,
    invalidate: clear,
    revision: () => serial,
    restore,
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
    label: "Artístico", treatment: "estilizado",
    execute: executeStylizedLaboratoryJob });
}

export function connectSolid(options) {
  return connectTreatment({ ...options, cardIndex: 5,
    label: "Sólidos", treatment: "solidos", execute: executeSolidLaboratory });
}

export function connectSmooth(options) {
  return connectTreatment({ ...options, cardIndex: 4,
    label: "Gradiente", treatment: "gradiente_suave",
    execute: executeSmoothLaboratoryJob });
}
