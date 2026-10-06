import { getContext } from "/_app/state/context.js";
import { startSpecialTreatments, waitForTextoffJob } from "/_app/api/textoff.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";

function friendlyError(error) {
  const message = String(error?.message || "");
  if (message.includes("Nenhum componente autorizado intersecta") || message.includes("{'type':")) {
    return "Nenhum componente elegível pôde ser tratado nas áreas selecionadas.";
  }
  return message || "Não foi possível concluir o tratamento Degradê.";
}

export function createDegradeExecution({ setBusy, reload, progress }) {
  let busy = false;
  return async (chapters, retry = false) => {
    if (busy || !chapters.length) return;
    const confirmed = await confirmMessage({
      title: retry ? "Tentar novamente o tratamento Degradê" : "Executar tratamento Degradê",
      message: retry ? "Tentar novamente o tratamento Degradê no capítulo selecionado?"
        : `Executar tratamento Degradê em ${chapters.length} capítulo(s) selecionado(s)?`,
      confirmText: retry ? "Tentar novamente" : "Executar",
    });
    if (!confirmed || busy) return;
    busy = true; setBusy(true);
    progress.update({ busy: true, message: "Na fila para execução…",
      percent: 0, completed: 0, total: chapters.length });
    try {
      const { provider, manga } = getContext();
      const { job } = await startSpecialTreatments(provider, manga, "degrade", chapters, retry);
      const results = await waitForTextoffJob(job, (current) => {
        progress.update({ busy: true, ...(current.progress || {}) });
      });
      await showOperationSummary({ title: "Tratamento Degradê concluído", summary: {
        headline: `${results.length} capítulo(s)`,
        items: results.map((item) => ({ chapter: item.chapter, status: item.status,
          count: `${item.occurrences || 0} ocorrência(s)`, warning: item.status === "failed",
          details: [{ label: "Resultado", value: item.error || item.status }] })),
      } });
    } catch (error) {
      await showMessage({ title: "Falha no tratamento Degradê", message: friendlyError(error) });
    } finally {
      try { await reload(); } finally {
        progress.update({ busy: false });
        busy = false; setBusy(false);
      }
    }
  };
}
