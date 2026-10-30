export const SOMMELIER_NAME = "Bubble Sommelier";

export function aggregateSommelierProgress(job, chapters, pagesByChapter) {
  const jobProgress = job.progress || job;
  const chapterIndex = chapters.indexOf(job.chapter);
  const completedBefore = chapterIndex < 0
    ? 0
    : chapters.slice(0, chapterIndex).reduce((sum, chapter) => sum + (pagesByChapter.get(chapter) || 0), 0);
  const chapterPages = pagesByChapter.get(job.chapter) || 0;
  const completedInChapter = jobProgress.stage === "completed"
    ? chapterPages
    : Math.max(0, Math.min(chapterPages, Number(jobProgress.completed) || 0));
  const total = [...pagesByChapter.values()].reduce((sum, count) => sum + count, 0);
  const completed = Math.min(total, completedBefore + completedInChapter);
  return {
    busy: job.status !== "failed",
    title: `${SOMMELIER_NAME} · ${job.status}`,
    message: jobProgress.message || "Preparando análise…",
    percent: total ? Math.round(completed * 100 / total) : 0,
    completed,
    total,
  };
}

export function operationSummary(results) {
  return {
    headline: `${results.length} capítulo(s) analisado(s)`,
    breakdown: `${results.length} concluído(s)`,
    items: results.map((item) => ({
      chapter: item.chapter,
      status: "Concluído",
      count: `${Number(item.candidates || 0)} candidato(s)`,
      warning: false,
      details: [
        { label: "Perfil", value: item.profile_id || "—" },
        { label: "Páginas analisadas", value: String(Number(item.pages || 0)) },
        { label: "Balões", value: String(Number(item.balloons || 0)) },
        { label: "Coverage ≥ 0.75", value: String(Number(item.coverage_ge_075 || 0)) },
        { label: "Candidatos", value: String(Number(item.candidates || 0)) },
      ],
    })),
  };
}
