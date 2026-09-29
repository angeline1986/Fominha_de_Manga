import { fetchJob, openAutoMergeFolder, submitLevel3 } from "/_app/api/auto_merge.js";
import { getContext } from "/_app/state/context.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function reasonText(reason) {
  const labels = {
    continuous_scene_too_long: "Cena contínua extensa; revisão estrutural necessária",
    strong_diagonal_crossing: "Linha diagonal atravessa o corte",
    connected_component_crossing: "Elementos visuais atravessam o corte",
    text_like_region: "Texto ou efeito visual próximo ao corte",
    structural_evidence_inconclusive: "Evidência estrutural inconclusiva",
  };
  return labels[reason] || String(reason || "").replaceAll("_", " ") || "—";
}

function summary(job) {
  const results = Array.isArray(job.results) ? job.results : [];
  const promoted = results.filter((item) => item.status === "promoted").length;
  const partial = results.filter((item) => item.status === "partial").length;
  const failed = results.filter((item) => item.status === "failed").length;
  return {
    headline: `${results.length} ${results.length === 1 ? "capítulo processado" : "capítulos processados"}`,
    breakdown: [promoted && `${promoted} concluído(s)`, partial && `${partial} parcial(is)`,
      failed && `${failed} com ocorrência`].filter(Boolean).join(" · "),
    items: results.map((item) => ({
      chapter: item.chapter,
      status: item.status === "promoted" ? "Concluído" : item.status === "partial" ? "Concluído parcialmente" : "Requer atenção",
      count: `${Number(item.resolved_segments || 0)} merges`,
      warning: item.status !== "promoted",
      details: [
        { label: "Status", value: item.status === "promoted" ? "Concluído" : "Concluído parcialmente", warning: item.status !== "promoted" },
        { label: "Merges salvos", value: String(Number(item.resolved_segments || 0)), files: item.saved_files || [], kind: "saved" },
        { label: "Pendente", value: item.pending_files?.length
          ? `${item.pending_files.length} ${item.pending_files.length === 1 ? "imagem" : "imagens"}`
          : `${Number(item.pending_segments || 0)} segmento(s) residual(is)`,
        files: item.pending_files || [], kind: "pending" },
        { label: "Motivo", value: (item.reason_codes || []).map(reasonText).join("; ") || item.error || "—" },
        { label: "Próxima etapa", value: item.next_stage || "—" },
      ],
      actions: [{ label: "Abrir pasta", level: 3 }],
    })),
  };
}

export function createLevel3Execution({ onStatus, onComplete }) {
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
      title: "Executar Auto-Merge Nível III",
      message: `Executar para ${chapters.length} capítulo(s) selecionado(s)? Somente cortes comprovados como seguros serão usados.`,
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
      const { job } = await submitLevel3(context.provider, context.manga, chapters);
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
        await showOperationSummary({ title: "Resumo da Operação", summary: summary(result),
          onAction: async (item, action) => {
            try {
              await openAutoMergeFolder(context.provider, context.manga, item.chapter, action.level);
            } catch (error) {
              await showMessage({ title: "Falha ao abrir pasta", message: error.message });
            }
          } });
      }
    } catch (error) {
      if (!disposed) await showMessage({ title: "Falha no Auto-Merge Nível III", message: error.message });
    } finally {
      active = false;
      if (!disposed) onStatus({ busy: false, message: "" });
    }
  }

  function report(job) {
    const progress = job.progress || {};
    onStatus({ busy: true, title: `Auto-Merge Nível III · ${job.status}`,
      message: progress.message || "Aguardando processamento…", percent: progress.percent,
      completed: progress.completed, total: progress.total });
  }

  return { execute, dispose() { disposed = true; } };
}
