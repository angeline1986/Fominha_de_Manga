export const MAX_CHAPTERS = 40;
export const TERMINAL = new Set(["completed", "partial", "blocked", "failed",
  "no_work", "interrupted"]);

export function summarizePlan(plan) {
  const chapters = plan?.chapters || [];
  const summary = { total: chapters.length, eligible: 0, blocked: 0, noWork: 0 };
  for (const chapter of chapters) {
    const status = comboState(chapter);
    if (status === "BLOCKED") summary.blocked++;
    else if (status === "NO_WORK") summary.noWork++;
    else summary.eligible++;
  }
  return summary;
}

export function stageState(chapter, stage) {
  const pages = chapter?.pages || [];
  if (!pages.length && chapter?.status === "BLOCKED") return "BLOCKED";
  if (!pages.length && chapter?.status !== "NO_WORK") return "UNKNOWN";
  const statuses = pages.map((page) => {
    const row = page.stages?.[stage];
    return row?.status || "NO_WORK";
  });
  if (!statuses.length || statuses.every((status) => status === "NO_WORK")) return "NO_WORK";
  if (statuses.some((status) => status === "BLOCKED")) return "BLOCKED";
  if (statuses.every((status) => status === "REUSED" || status === "NO_WORK")) return "REUSED";
  return "PLANNED";
}

export function comboState(chapter) {
  if (chapter?.status === "BLOCKED") return "BLOCKED";
  const stages = ["SOLIDOS", "GLASS"].map((stage) => stageState(chapter, stage));
  if (stages.includes("PLANNED") || stages.includes("REUSED")) return "PLANNED";
  if (chapter?.status === "NO_WORK") return "NO_WORK";
  return chapter?.status || "UNKNOWN";
}

export function summarizeRows(rows) {
  const summary = { total: rows.length, eligible: 0, blocked: 0 };
  rows.forEach((row) => {
    const status = comboState(row);
    if (status === "BLOCKED") summary.blocked++;
    else if (status === "PLANNED") summary.eligible++;
  });
  return summary;
}

export function resultSummary(result) {
  const pages = (result?.results || []).flatMap((chapter) => chapter.pages || []);
  const counts = { COMPOSED: 0, NO_WORK: 0, CONFLICT: 0, BLOCKED: 0, FAILED: 0, INVALID: 0 };
  pages.forEach((page) => { if (page.status in counts) counts[page.status]++; });
  const reused = pages.reduce((total, page) => total + Object.values(page.treatments || {})
    .filter((treatment) => treatment.reused).length, 0);
  const executed = pages.reduce((total, page) => total + Object.values(page.treatments || {})
    .filter((treatment) => treatment.planned).length, 0);
  return { counts, reused, executed, pages: pages.length };
}

export function resultLabel(status) {
  return ({ COMPOSED: "Composta", NO_WORK: "Sem trabalho", CONFLICT: "Conflito",
    BLOCKED: "Bloqueado", FAILED: "Falha", INVALID: "Inválido" })[status] || status || "—";
}
