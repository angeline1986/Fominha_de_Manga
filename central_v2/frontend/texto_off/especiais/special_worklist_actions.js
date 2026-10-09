import { iconMarkup } from "/_shared/icons/icons.js";
import { createPageRestoreButton } from "/texto_off/especiais/page_restore.js";
import { artisticDone } from "/texto_off/especiais/artistico_model.js";

function iconButton(icon, title, action, disabled = false) {
  const button = document.createElement("button");
  button.type = "button"; button.className = "btn artistico-icon-button";
  button.innerHTML = iconMarkup(icon); button.title = title;
  button.setAttribute("aria-label", title); button.disabled = disabled;
  if (action) button.addEventListener("click", action);
  return button;
}

export function createSpecialActions(row, state) {
  const wrap = document.createElement("div");
  wrap.className = "artistico-actions";
  const artistico = state.treatment === "estilizado";
  if (row.type === "chapter") {
    wrap.append(iconButton("eye", `Comparar páginas do capítulo ${row.chapter}`,
      (event) => state.review.open(row.source, event.currentTarget), !row.source.review_available));
    if (!artistico) {
      const available = (row.source.occurrences || []).some(artisticDone);
      wrap.append(iconButton("sync", `Reexecutar capítulo ${row.chapter}`,
        () => state.reexecuteChapter(row.chapter), !available || state.busy()));
    }
  } else if (row.type === "page") {
    wrap.append(iconButton("eye", `Revisar página ${row.page}`,
      (event) => state.review.open(row.source, event.currentTarget, { page: row.page }),
      !row.source.review_available || !row.occurrences.some(artisticDone)));
    if (artistico) {
      const restore = createPageRestoreButton(row.chapter, () => row.page, state.restore);
      restore.classList.add("artistico-icon-button"); restore.innerHTML = iconMarkup("back");
      restore.title = `Restaurar página ${row.page}`;
      restore.setAttribute("aria-label", restore.title); wrap.append(restore);
    }
  } else {
    const item = row.item;
    if (artistico) {
      const allowed = artisticDone(item) && !!item.expected_sha256 && !item.reexecution_blocked;
      const rerun = iconButton("sync", `Reexecutar ${item.id} em ${row.page}`,
        () => state.reexecute(row.chapter, item), !allowed || state.busy());
      if (!allowed) rerun.title = item.reexecution_block_reason || "Histórico verificável indisponível.";
      wrap.append(rerun);
    } else {
      wrap.append(iconButton("sync", `Reexecução individual indisponível para ${item.id}; use a ação do capítulo`, null, true));
    }
    wrap.append(iconButton("eye", `Revisar ${item.id} em ${row.page}`,
      (event) => state.review.open(row.source, event.currentTarget,
        { page: row.page, occurrence: item.id }), !row.source.review_available || !artisticDone(item)));
  }
  return wrap;
}
