import { getContext } from "/_app/state/context.js";
import { startMergedTextoff, waitForTextoffJob } from "/_app/api/textoff.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";

function summary(results) {
  const done = results.filter((item) => item.status === "ok").length;
  const failed = results.length - done;
  return {
    headline: `${results.length} capítulo(s) processado(s)`,
    breakdown: [done && `${done} concluído(s)`, failed && `${failed} com ocorrência`].filter(Boolean).join(" · "),
    items: results.map((item) => ({
      chapter: item.chapter,
      status: item.status === "ok" ? "Concluído" : "Requer atenção",
      count: `${Number(item.outputs || 0)} merge(s)`,
      warning: item.status !== "ok",
      details: [
        { label: "Cleaner V2", value: item.status === "ok" ? "Concluído" : item.error || "Falha" },
        { label: "Imagens de entrada", value: String(Number(item.pages || 0)) },
        { label: "Imagens limpas", value: String(Number(item.outputs || 0)) },
        { label: "Máscaras", value: String(Number(item.masks || 0)) },
      ],
    })),
  };
}

export function createMergedExecution({ onStatus, onComplete }) {
  let active = false;
  let disposed = false;

  async function execute(chapters) {
    if (active || disposed) return;
    if (!chapters.length) return showMessage({ title: "Nenhum capítulo selecionado", message: "Selecione ao menos um MERGE oficial válido." });
    const context = getContext();
    const confirmed = await confirmMessage({
      title: "Executar Texto Off — Merged",
      message: `O Cleaner V2 processará ${chapters.length} capítulo(s) usando os MERGEs oficiais. Resultados anteriores de Texto Off Merged serão substituídos após validação do lote.`,
      confirmText: "Executar",
    });
    const current = getContext();
    if (!confirmed || disposed || active) return;
    if (context.provider !== current.provider || context.manga !== current.manga) {
      return showMessage({ title: "Contexto alterado", message: "A obra mudou durante a confirmação. Selecione novamente." });
    }
    active = true;
    onStatus({ busy: true, title: "Texto Off — Merged", message: "Enviando execução…" });
    try {
      const { job } = await startMergedTextoff(context.provider, context.manga, chapters);
      const result = await waitForTextoffJob(job, report);
      if (disposed) return;
      await onComplete();
      await showOperationSummary({ title: "Resumo do Texto Off — Merged", summary: summary(result) });
    } catch (error) {
      if (!disposed) await showMessage({ title: "Falha no Texto Off — Merged", message: error.message });
    } finally {
      active = false;
      if (!disposed) onStatus({ busy: false, message: "" });
    }
  }

  function report(job) {
    const progress = job.progress || {};
    onStatus({ busy: true, title: `Texto Off — Merged · ${job.status}`,
      message: progress.message || "Aguardando processamento…", percent: progress.percent,
      completed: progress.completed, total: progress.total });
  }

  return { execute, dispose() { disposed = true; } };
}
