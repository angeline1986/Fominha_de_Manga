import { getContext } from "/_app/state/context.js";
import { previewSpecialPageRestore, specialPageRestoreImageUrl,
  startSpecialPageRestore, waitForTextoffJob } from "/_app/api/textoff.js";
import { confirmMessage, showMessage } from "/_shared/messages/messages.js";

function previewDialog(provider, manga, proposal) {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "special-page-restore-preview";
    dialog.setAttribute("aria-label", `Prévia da restauração de ${proposal.page}`);
    const heading = document.createElement("h2");
    heading.textContent = `Restaurar ${proposal.page}`;
    const detail = document.createElement("p");
    const check = proposal.check_compatibility || {};
    const differences = check.status === "blocked"
      ? ` Diferenças: ${check.roi_different_pixels} pixel(s) na ROI e ${check.outside_roi_different_pixels} fora dela.` : "";
    detail.textContent = `${proposal.affected_occurrences} ocorrência(s) ativa(s) voltarão a pendente. ${proposal.invalidated_runs || 0} execução(ões) histórica(s) terão seus efeitos invalidados na página. ${check.execution_compatible === false ? `Nova execução Artístico bloqueada: ${check.reason}${differences}` : ""}`;
    const images = document.createElement("div");
    images.className = "special-page-restore-images";
    const ready = new Set();
    const accept = document.createElement("button");
    accept.type = "button"; accept.className = "btn";
    accept.textContent = "Continuar"; accept.disabled = true;
    for (const [side, label] of [["current", "Estado atual"], ["restored", "Estado restaurado"]]) {
      const figure = document.createElement("figure");
      const caption = document.createElement("figcaption");
      caption.textContent = label;
      const image = document.createElement("img");
      image.alt = `${label}: ${proposal.page}`;
      image.addEventListener("load", () => { ready.add(side); accept.disabled = ready.size !== 2; });
      image.addEventListener("error", () => {
        accept.disabled = true;
        detail.textContent = "A prévia mudou ou não pôde ser carregada. Atualize e tente novamente.";
      });
      image.src = specialPageRestoreImageUrl(provider, manga, proposal, side);
      figure.append(caption, image); images.append(figure);
    }
    const actions = document.createElement("div");
    actions.className = "special-page-restore-actions";
    const cancel = document.createElement("button");
    cancel.type = "button"; cancel.className = "btn"; cancel.textContent = "Cancelar";
    cancel.addEventListener("click", () => dialog.close("cancel"));
    accept.addEventListener("click", () => dialog.close("continue"));
    actions.append(cancel, accept);
    dialog.append(heading, detail, images, actions);
    dialog.addEventListener("close", () => {
      const accepted = dialog.returnValue === "continue";
      dialog.remove(); resolve(accepted);
    }, { once: true });
    document.body.append(dialog); dialog.showModal();
  });
}

export function pageRestoreColumn({ busy, setBusy, reload }) {
  return { id: "restore_page", label: "RESTAURAR PÁGINA", render(row) {
    const wrapper = document.createElement("div");
    wrapper.className = "special-page-restore-control";
    const select = document.createElement("select");
    select.setAttribute("aria-label", `Página para restauração no capítulo ${row.chapter}`);
    for (const page of row.pages) {
      const option = document.createElement("option");
      option.value = page; option.textContent = page; select.append(option);
    }
    const button = createPageRestoreButton(row.chapter, () => select.value,
      { busy, setBusy, reload });
    wrapper.append(select, button);
    return wrapper;
  } };
}

export function createPageRestoreButton(chapter, page, { busy, setBusy, reload }) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "btn"; button.textContent = "Restaurar página";
    button.disabled = busy();
    button.addEventListener("click", async () => {
      if (busy()) return;
      setBusy(true);
      try {
        const { provider, manga } = getContext();
        const { proposal } = await previewSpecialPageRestore(provider, manga, chapter, page());
        if (!await previewDialog(provider, manga, proposal)) return;
        const confirmed = await confirmMessage({ title: "Confirmar restauração da página",
          message: `Restaurar ${proposal.page} ao SHA ${proposal.restored_sha256}? Os efeitos especiais posteriores serão invalidados. As ROIs aprovadas serão mantidas. ${proposal.check_compatibility?.execution_compatible === false ? "Nova execução Artístico ficará bloqueada até revisão da origem." : ""}`,
          confirmText: "Restaurar página" });
        if (!confirmed) return;
        const { job } = await startSpecialPageRestore(provider, manga, proposal);
        const results = await waitForTextoffJob(job);
        await showMessage({ title: "Página restaurada",
          message: `${proposal.page}: ${results[0]?.affected_occurrences || 0} ocorrência(s) pendentes. Backup: ${results[0]?.backup || "indisponível"}.` });
        await reload();
      } catch (error) {
        await showMessage({ title: "Restauração bloqueada", message: error.message });
      } finally { setBusy(false); }
    });
    return button;
}
