import { fetchJob, openAutoMergeFolder, submitLevel4 } from "/_app/api/auto_merge.js";
import { getContext } from "/_app/state/context.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function summary(job) {
  const rows = Array.isArray(job.results) ? job.results : [];
  const promoted = rows.filter((row) => row.status === "promoted").length;
  const partial = rows.filter((row) => row.status === "partial").length;
  const failed = rows.filter((row) => row.status === "failed").length;
  return { headline: `${rows.length} ${rows.length === 1 ? "capítulo processado" : "capítulos processados"}`,
    breakdown: [promoted && `${promoted} concluído(s)`, partial && `${partial} parcial(is)`,
      failed && `${failed} com ocorrência`].filter(Boolean).join(" · "),
    items: rows.map((row) => ({ chapter: row.chapter,
      status: row.status === "promoted" ? "Concluído" : row.status === "partial" ? "Concluído parcialmente" : "Requer atenção",
      count: `${Number(row.resolved_segments || 0)} merges`, warning: row.status !== "promoted",
      details: [{ label: "Status", value: row.status === "promoted" ? "Concluído" : "Concluído parcialmente", warning: row.status !== "promoted" },
        { label: "Merges salvos", value: String(Number(row.resolved_segments || 0)), files: row.saved_files || [], kind: "saved" },
        { label: "Pendente", value: `${Number(row.pending_segments || 0)} segmento(s) residual(is)`, files: row.pending_files || [], kind: "pending" },
        { label: "Motivo", value: (row.reason_codes || []).join("; ") || row.error || "—" },
        { label: "Próxima etapa", value: row.next_stage || "—" }], actions: [{ label: "Abrir pasta", level: 4 }] })) };
}

export function createLevel4Execution({ onStatus, onComplete }) {
  let active = false, disposed = false;
  async function execute(chapters) {
    if (active || disposed) return;
    if (!chapters.length) { await showMessage({ title: "Nenhum capítulo selecionado", message: "Selecione ao menos um capítulo pendente." }); return; }
    const context = getContext();
    const confirmed = await confirmMessage({ title: "Executar Auto-Merge Nível IV",
      message: `Executar para ${chapters.length} capítulo(s) selecionado(s)? Somente composições estruturais SAFE serão usadas.`, confirmText: "Executar" });
    const current = getContext();
    if (!confirmed || disposed || active) return;
    if (context.provider !== current.provider || context.manga !== current.manga) {
      await showMessage({ title: "Contexto alterado", message: "A obra mudou durante a confirmação. Selecione novamente." }); return;
    }
    active = true; onStatus({ busy: true, message: "Enviando execução…" });
    try {
      const { job } = await submitLevel4(context.provider, context.manga, chapters);
      if (!job?.id) throw new Error("A Central não confirmou a criação do job.");
      let result = job;
      while (!disposed && !["completed", "failed"].includes(result.status)) {
        report(result); await delay(600); ({ job: result } = await fetchJob(job.id));
      }
      if (disposed) return;
      report(result);
      if (result.status === "failed") await showMessage({ title: "Execução interrompida", message: result.error || "O job falhou." });
      else {
        await onComplete();
        await showOperationSummary({ title: "Resumo da Operação", summary: summary(result),
          onAction: async (item, action) => {
            try { await openAutoMergeFolder(context.provider, context.manga, item.chapter, action.level); }
            catch (error) { await showMessage({ title: "Falha ao abrir pasta", message: error.message }); }
          } });
      }
    } catch (error) {
      if (!disposed) await showMessage({ title: "Falha no Auto-Merge Nível IV", message: error.message });
    } finally { active = false; if (!disposed) onStatus({ busy: false, message: "" }); }
  }
  function report(job) {
    const progress = job.progress || {};
    onStatus({ busy: true, title: `Auto-Merge Nível IV · ${job.status}`,
      message: progress.message || "Aguardando processamento…", percent: progress.percent,
      completed: progress.completed, total: progress.total });
  }
  return { execute, dispose() { disposed = true; } };
}
