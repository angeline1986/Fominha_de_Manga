import { getContext } from "/_app/state/context.js";
import { startSpecialTreatments, waitForTextoffJob } from "/_app/api/textoff.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";

function friendlyError(error, treatment) {
  const message = String(error?.message || "");
  if (["degrade", "estilizado"].includes(treatment) && (message.includes("Nenhum componente autorizado intersecta")
      || message.includes("{'type':"))) {
    return "Nenhum componente elegível pôde ser tratado nas áreas selecionadas.";
  }
  const label = { degrade: "Degradê", estilizado: "Artístico",
    gradiente_suave: "Suave" }[treatment] || treatment;
  return message || `Não foi possível concluir o tratamento ${label}.`;
}

export function createSpecialTreatmentExecution({ setBusy, reload, progress, treatment, title, retryTitle }) {
  let busy = false;
  return async (chapters, retry = false, reexecute = false, selections = undefined) => {
    if (busy || !chapters.length) return;
    const confirmed = await confirmMessage({
      title: reexecute ? `Reexecutar ${retryTitle || title}`
        : retry ? `Tentar novamente ${retryTitle || title}` : `Executar ${title}`,
      message: reexecute
        ? selections?.length ? `Substituir somente ${selections[0].id} em ${selections[0].page} (ROI ${JSON.stringify(selections[0].roi)}). Filtro atual: ${selections[0].current_filter}; solicitado: ${selections[0].requested_filter}. A entrada histórica será restaurada nessa ocorrência. Confira Antes e Depois em Revisar. Continuar?`
          : `Existem resultados anteriores. A reexecução sincroniza o Manifesto Especial com o Check atual, usa as ROIs aprovadas agora e arquiva os resultados substituídos. Continuar?`
        : retry ? `Tentar novamente ${retryTitle || title} no capítulo selecionado?`
          : `Executar ${title} em ${chapters.length} capítulo(s) selecionado(s)?`,
      confirmText: reexecute ? "Reexecutar" : retry ? "Tentar novamente" : "Executar",
    });
    if (!confirmed || busy) return;
    busy = true; setBusy(true);
    progress.update({ busy: true, message: "Na fila para execução…",
      percent: 0, completed: 0, total: chapters.length });
    try {
      const { provider, manga } = getContext();
      const selected = selections?.map(({ chapter, page, id, expected_sha256 }) =>
        ({ chapter, page, id, expected_sha256 }));
      const { job } = await startSpecialTreatments(provider, manga, treatment, chapters, retry,
        reexecute, ...(selected ? [selected] : []));
      const results = await waitForTextoffJob(job, (current) => {
        progress.update({ busy: true, ...(current.progress || {}) });
      });
      await showOperationSummary({ title: `${title[0].toUpperCase()}${title.slice(1)} concluído`, summary: {
        headline: `${results.length} capítulo(s)`,
        items: results.map((item) => ({ chapter: item.chapter, status: item.status,
          count: `${item.occurrences || 0} ocorrência(s)`, warning: item.status === "failed",
          details: [{ label: "Resultado", value: item.error || item.status }] })),
      } });
    } catch (error) {
      await showMessage({ title: `Falha no ${title}`, message: friendlyError(error, treatment) });
    } finally {
      try { await reload(); } finally {
        progress.update({ busy: false });
        busy = false; setBusy(false);
      }
    }
  };
}
