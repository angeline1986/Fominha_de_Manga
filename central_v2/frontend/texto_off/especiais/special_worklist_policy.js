import { artisticKey } from "/texto_off/especiais/artistico_model.js";

export const WORKLISTS = {
  estilizado: { label: "Artístico", mode: "artistico", step: "artistico" },
  degrade: { label: "Degradê", mode: "degrade", step: "degrade" },
  gradiente_suave: { label: "Suave", mode: "suave", step: "suave" },
};

export function executableOccurrences(chapter, treatment) {
  const retry = chapter.status === "failed";
  return (chapter.occurrences || []).filter((item) => {
    if (treatment === "estilizado") return ["pending", "failed"].includes(item.status)
      && !item.execution_blocked;
    if (treatment === "gradiente_suave") return item.status === (retry ? "failed" : "pending");
    return retry ? ["pending", "failed"].includes(item.status) : item.status === "pending";
  });
}

export function executionSelection(chapters, treatment, selected, choices) {
  const selectedItems = [], complete = [], partial = [];
  for (const chapter of chapters) {
    const eligible = executableOccurrences(chapter, treatment);
    const chosen = eligible.filter((item) => choices.get(artisticKey(
      chapter.chapter, item.page, item.id)) !== "none" && selected.has(artisticKey(
      chapter.chapter, item.page, item.id)));
    selectedItems.push(...chosen.map((item) => ({ chapter: chapter.chapter,
      page: item.page, id: item.id, status: item.status })));
    if (chosen.length && chosen.length === eligible.length) complete.push(chapter);
    else if (chosen.length) partial.push(chapter);
  }
  const mixed = complete.some((chapter) => chapter.status === "failed")
    && complete.some((chapter) => chapter.status !== "failed");
  return { items: selectedItems, chapters: complete.map((chapter) => chapter.chapter),
    retry: complete.some((chapter) => chapter.status === "failed"),
    canExecute: !!complete.length && !partial.length && !mixed,
    reason: partial.length ? "A execução deste tratamento é por capítulo. Selecione todas as ocorrências elegíveis de cada capítulo para executar."
      : mixed ? "Execute separadamente capítulos pendentes e capítulos com falhas."
        : "" };
}
