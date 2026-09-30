import { getContext } from "/_app/state/context.js";
import { startMergedTextoff, waitForTextoffJob } from "/_app/api/textoff.js";
import { confirmMessage, showMessage, showOperationSummary } from "/_shared/messages/messages.js";

function summary(results, level) {
  const done = results.filter((item) => item.status === "ok").length;
  const unchanged = results.filter((item) => item.status === "no_change").length;
  const failed = results.filter((item) => item.status === "failed").length;
  return {
    headline: `${results.length} capítulo(s) processado(s)`,
    breakdown: [done && `${done} concluído(s)`, unchanged && `${unchanged} sem alteração`,
      failed && `${failed} com ocorrência`].filter(Boolean).join(" · "),
    items: results.map((item) => ({
      chapter: item.chapter,
      status: item.status === "ok" ? "Concluído" : item.status === "no_change" ? "Sem alteração — revisar" : "Requer atenção",
      count: level === "3" ? `${Number(item.candidate_count || 0)} candidato(s)`
        : `${Number(item.outputs || 0)} merge(s)`,
      warning: item.status !== "ok",
      details: [
        { label: level === "3" ? "Análise Nível III" : item.text_pages !== undefined ? "Resultado Nível II" : "Cleaner V2",
          value: item.status === "ok" ? "Concluído" : item.status === "no_change" ? "Nenhum pixel alterado; revise máscaras e resultado." : item.error || "Falha" },
        ...(level === "3" ? [{ label: "Candidatos a balão estilizado", value: String(Number(item.candidate_count || 0)) }] : []),
        ...(level === "3" ? Object.entries(item.candidate_types || {}).map(([kind, count]) => ({
          label: ({ soft_gradient: "Candidatos com gradiente", saturated_styled: "Candidatos com cor decorativa",
            irregular_outline: "Candidatos com contorno irregular" })[kind] || "Outros candidatos",
          value: String(Number(count || 0)),
        })) : []),
        ...(level === "3" ? [{ label: "MERGES analisados", value: String(Number(item.pages || 0)) }] : [
          { label: "Imagens de entrada", value: String(Number(item.pages || 0)) },
          { label: "Imagens limpas", value: String(Number(item.outputs || 0)) },
          { label: "Máscaras", value: String(Number(item.masks || 0)) },
        ]),
        ...(item.transparent_balloons !== undefined ? [{
          label: "Balões transparentes preservados para Nível II",
          value: String(Number(item.transparent_balloons || 0)),
        }] : []),
        ...(Array.isArray(item.level2_pending_pages) ? [{
          label: "Páginas encaminhadas ao Nível II",
          value: item.level2_pending_pages.length ? item.level2_pending_pages.join(", ") : "Nenhuma",
        }] : []),
        ...(item.transparent_page_count !== undefined ? [{
          label: "Páginas com balões transparentes processadas",
          value: `${Number(item.transparent_page_count || 0)} de ${Number(item.pages || 0)}`,
        }] : []),
        ...(Array.isArray(item.transparent_pages) && item.transparent_pages.length ? [{
          label: "Páginas candidatas do Nível II",
          value: item.transparent_pages.join(", "),
        }] : []),
        ...(item.text_pages !== undefined ? [{ label: "Páginas com texto detectado", value: String(Number(item.text_pages || 0)) }] : []),
        ...(item.changed_pixels !== undefined ? [{ label: "Pixels alterados", value: String(Number(item.changed_pixels || 0)) }] : []),
      ],
      actions: level === "3" && item.status === "ok" && Number(item.candidate_count || 0) > 0
        ? [{ id: "review", label: "Ver candidatos" }] : [],
    })),
  };
}

export function createMergedExecution({ onStatus, onComplete, onReview, level = "" }) {
  const levelLabel = ({ "1": "I", "2": "II", "3": "III" })[level] || "";
  const flowLabel = levelLabel ? `Merged Nível ${levelLabel}` : "Legado";
  let active = false;
  let disposed = false;

  async function execute(chapters) {
    if (active || disposed) return;
    if (!chapters.length) return showMessage({ title: "Nenhum capítulo selecionado", message: "Selecione ao menos um MERGE oficial válido." });
    const context = getContext();
    const confirmed = await confirmMessage({
      title: `Executar Texto Off — ${flowLabel}`,
      message: level === "3"
        ? `O Nível III analisará ${chapters.length} capítulo(s) a partir dos MERGES originais em recortes sobrepostos, sem alterar as imagens.`
        : `O Cleaner V2 processará ${chapters.length} capítulo(s) usando os MERGEs oficiais.`,
      confirmText: "Executar",
    });
    const current = getContext();
    if (!confirmed || disposed || active) return;
    if (context.provider !== current.provider || context.manga !== current.manga) {
      return showMessage({ title: "Contexto alterado", message: "A obra mudou durante a confirmação. Selecione novamente." });
    }
    active = true;
    onStatus({ busy: true, title: `Texto Off — ${flowLabel}`, message: "Enviando execução…" });
    try {
      const { job } = await startMergedTextoff(context.provider, context.manga, chapters, level);
      const result = await waitForTextoffJob(job, report);
      if (disposed) return;
      await onComplete();
      await showOperationSummary({ title: `Resumo do Texto Off — ${flowLabel}`, summary: summary(result, level),
        onAction: (item, action) => {
          if (action.id === "review") onReview?.(item.chapter);
        } });
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
