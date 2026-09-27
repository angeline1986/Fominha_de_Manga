import { fetchJob, submitLevel1 } from "/_app/api/auto_merge.js";
import { getContext } from "/_app/state/context.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function completionSummary(job) {
  const results = Array.isArray(job.results) ? job.results : [];
  const count = (statuses) => results.filter((item) => statuses.includes(item.status)).length;
  const completed = count(["promoted", "already_complete"]);
  const partial = count(["partial"]);
  const attention = count(["unresolved", "failed"]);
  const breakdown = [
    completed && `${completed} ${completed === 1 ? "concluído" : "concluídos"}`,
    partial && `${partial} ${partial === 1 ? "parcial" : "parciais"}`,
    attention && `${attention} ${attention === 1 ? "pendente" : "pendentes"}`,
  ].filter(Boolean).join(" · ");
  return {
    headline: `${results.length} ${results.length === 1 ? "capítulo processado" : "capítulos processados"}`,
    breakdown,
    items: results.map((item) => summaryItem(item)),
  };
}

function summaryItem(item) {
  const statuses = {
    promoted: "Concluído",
    partial: "Concluído parcialmente",
    unresolved: "Sem corte seguro",
    already_complete: "Já concluído",
    failed: "Requer atenção",
  };
  const residuals = (item.residuals || []).map((range) => `${range.global_start}–${range.global_end} px`);
  const reasons = (item.reason_codes || []).map((reason) => reason === "no_safe_boundary_before_max_height"
    ? "Faixa branca segura não encontrada" : String(reason).replaceAll("_", " "));
  const pendingCount = Number(item.pending_segments || residuals.length);
  return {
    chapter: item.chapter,
    status: statuses[item.status] || "Requer atenção",
    count: `${Number(item.artifacts || 0)} merges`,
    warning: ["partial", "unresolved", "failed"].includes(item.status),
    details: [
      ["Status", statuses[item.status] || "Requer atenção"],
      ["Merges salvos", String(Number(item.artifacts || 0))],
      ["Pendente", pendingCount ? `${pendingCount} ${pendingCount === 1 ? "segmento residual" : "segmentos residuais"}` : "0"],
      ["Motivo", reasons.join("; ") || item.error || "—"],
      ["Residual", residuals.join(", ") || "—"],
      ["Próxima etapa", item.next_stage || (pendingCount ? "Auto-Merge Nível II" : "—")],
    ],
  };
}

export function createLevel1Execution({ onStatus, onComplete }) {
  let disposed = false;
  let active = false;

  async function execute(chapters) {
    if (active) return;
    if (!chapters.length) {
      await showMessage({ title: "Nenhum capítulo selecionado", message: "Selecione ao menos um capítulo." });
      return;
    }
    const context = getContext();
    const { provider, manga } = context;
    const confirmed = await confirmMessage({
      title: "Confirmar",
      message: `${chapters.length} capítulo(s) selecionado(s).`,
      confirmText: "Executar",
    });
    const currentContext = getContext();
    if (!confirmed || disposed || active) return;
    if (currentContext.provider !== provider || currentContext.manga !== manga) {
      await showMessage({ title: "Contexto alterado", message: "A obra mudou durante a confirmação. Selecione os capítulos novamente." });
      return;
    }

    active = true;
    onStatus({ busy: true, message: "Enviando execução…" });
    try {
      const { job } = await submitLevel1(provider, manga, chapters);
      if (!job || typeof job.id !== "string") throw new Error("A Central não confirmou a criação do job.");
      let current = job;
      while (!disposed && !["completed", "failed"].includes(current.status)) {
        reportProgress(current);
        await delay(600);
        ({ job: current } = await fetchJob(job.id));
      }
      if (disposed) return;
      reportProgress(current);
      if (current.status === "failed") {
        await showMessage({ title: "Execução interrompida", message: current.error || "O job falhou." });
      } else {
        await onComplete();
        await showOperationSummary({ title: "Resumo da Operação", summary: completionSummary(current) });
      }
    } catch (error) {
      if (!disposed) await showMessage({ title: "Falha no Auto-Merge", message: error.message });
    } finally {
      active = false;
      if (!disposed) onStatus({ busy: false, message: "" });
    }
  }

  return {
    execute,
    dispose() { disposed = true; },
  };

  function reportProgress(job) {
    const progress = job.progress || {};
    onStatus({
      busy: true,
      title: `Auto-Merge Nível I · ${job.status}`,
      message: progress.message || (job.chapter ? `${job.chapter}: processando…` : "Na fila para execução…"),
      percent: progress.percent,
      completed: progress.completed,
      total: progress.total,
    });
  }
}
