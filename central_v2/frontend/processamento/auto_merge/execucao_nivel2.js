import { fetchJob, submitLevel2 } from "/_app/api/auto_merge.js";
import { getContext } from "/_app/state/context.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function summary(job) {
  const results = Array.isArray(job.results) ? job.results : [];
  const complete = results.filter((item) => item.status === "promoted").length;
  const partial = results.filter((item) => item.status === "partial").length;
  const failed = results.filter((item) => item.status === "failed").length;
  return {
    headline: `${results.length} ${results.length === 1 ? "capítulo processado" : "capítulos processados"}`,
    breakdown: [complete && `${complete} concluído(s)`, partial && `${partial} parcial(is)`,
      failed && `${failed} com ocorrência`].filter(Boolean).join(" · "),
    items: results.map((item) => ({
      chapter: item.chapter,
      status: item.status === "promoted" ? "Concluído" : item.status === "partial" ? "Concluído parcialmente" : "Requer atenção",
      count: `${Number(item.resolved_segments || 0)} merges`,
      warning: item.status !== "promoted",
      details: [
        ["Status", item.status],
        ["Merges salvos", String(Number(item.resolved_segments || 0))],
        ["Residual para próxima etapa", String(Number(item.pending_segments || 0))],
        ["Próxima etapa", item.next_stage || "—"],
        ["Ocorrência", item.error || "—"],
      ],
    })),
  };
}

export function createLevel2Execution({ onStatus, onComplete }) {
  let active = false;
  let disposed = false;

  async function execute(chapters) {
    if (active || disposed) return;
    if (!chapters.length) {
      await showMessage({ title: "Nenhum capítulo selecionado", message: "Selecione ao menos um capítulo pendente." });
      return;
    }
    const context = getContext();
    const confirmed = await confirmMessage({
      title: "Confirmar",
      message: `${chapters.length} capítulo(s) selecionado(s).`,
      confirmText: "Executar",
    });
    const current = getContext();
    if (!confirmed || disposed || active) return;
    if (context.provider !== current.provider || context.manga !== current.manga) {
      await showMessage({ title: "Contexto alterado", message: "A obra mudou durante a confirmação. Selecione novamente." });
      return;
    }
    active = true;
    onStatus({ busy: true, message: "Enviando execução…" });
    try {
      const { job } = await submitLevel2(context.provider, context.manga, chapters);
      if (!job?.id) throw new Error("A Central não confirmou a criação do job.");
      let result = job;
      while (!disposed && !["completed", "failed"].includes(result.status)) {
        report(result);
        await delay(600);
        ({ job: result } = await fetchJob(job.id));
      }
      if (disposed) return;
      report(result);
      if (result.status === "failed") {
        await showMessage({ title: "Execução interrompida", message: result.error || "O job falhou." });
      } else {
        await onComplete();
        await showOperationSummary({ title: "Resumo da Operação", summary: summary(result) });
      }
    } catch (error) {
      if (!disposed) await showMessage({ title: "Falha no Auto-Merge Nível II", message: error.message });
    } finally {
      active = false;
      if (!disposed) onStatus({ busy: false, message: "" });
    }
  }

  function report(job) {
    const progress = job.progress || {};
    onStatus({ busy: true, title: `Auto-Merge Nível II · ${job.status}`,
      message: progress.message || "Aguardando processamento…", percent: progress.percent,
      completed: progress.completed, total: progress.total });
  }

  return { execute, dispose() { disposed = true; } };
}
