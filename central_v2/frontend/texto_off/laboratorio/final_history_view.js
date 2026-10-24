import { createFinalReviewView } from "/texto_off/laboratorio/final_review_view.js";

/** Historical comparison reuses the Laboratory's full-page comparison layout. */
export function createFinalHistoryView() {
  const view = createFinalReviewView();
  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = "/texto_off/laboratorio/final_history.css";
  document.head.append(style);
  view.dialog.classList.add("lab-final-history-dialog");
  view.dialog.setAttribute("aria-labelledby", "lab-final-history-title");
  view.dialog.querySelector("h2").id = "lab-final-history-title";
  view.dialog.querySelector("h2").textContent = "Histórico do Consolidado Final";
  view.dialog.querySelectorAll("figcaption")[1].textContent = "VERSÃO ANTERIOR";
  view.current.alt = "Imagem atual no Consolidado Final";
  view.candidate.alt = "Versão anterior selecionada";
  view.select.textContent = "Restaurar esta versão";
  const picker = document.createElement("select");
  picker.className = "lab-final-history-picker";
  picker.setAttribute("aria-label", "Versão anterior para comparar");
  view.status.after(picker);
  return { ...view, picker, dispose() { view.dispose(); style.remove(); } };
}
