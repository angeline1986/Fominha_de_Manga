import { residueCatalogStatus } from "/texto_off/comparison/residue_catalog_status.js";

export function syncResidueCatalogStatus({ query, item, catalogState, isCheck, state }) {
  const status = residueCatalogStatus(item, catalogState);
  query("[data-catalog]").disabled = !catalogState.canSaveChapter();
  query("[data-retry]").hidden = item.loadState !== "error";
  query("[data-draw]").disabled = state === "idle" || item.loadState !== "ready";
  const feedback = query("[data-feedback]");
  const sourceInfo = query("[data-source-status]");
  if (isCheck) {
    const quiet = status.feedback === "Ocorrências catalogadas."
      || status.feedback === "Nenhuma ocorrência catalogada nesta página.";
    feedback.textContent = quiet ? "" : status.feedback;
    feedback.hidden = quiet;
    sourceInfo.textContent = status.sourceStatus;
    sourceInfo.hidden = true;
    const info = query("[data-check-source-info]");
    if (info) {
      info.hidden = !status.sourceStatus;
      info.title = status.sourceStatus;
      info.setAttribute("aria-label", status.sourceStatus || "Status das fontes");
    }
  } else {
    feedback.textContent = status.feedback;
    feedback.hidden = false;
    sourceInfo.textContent = status.sourceStatus;
    sourceInfo.hidden = !status.sourceStatus;
  }
}
