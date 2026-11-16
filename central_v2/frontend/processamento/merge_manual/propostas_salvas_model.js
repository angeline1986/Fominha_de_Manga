export function isPending(item) {
  return item.status === "PROPOSTA_GERADA";
}

export function pendingForChapter(proposals, chapter) {
  return proposals.filter((item) => item.chapter === chapter && isPending(item));
}

export function pagesFor(items) {
  return [...new Set(items.flatMap((item) => (item.proposal?.source_files || []).map((source) => source.name)))]
    .sort((a, b) => a.localeCompare(b, "pt-BR", { numeric: true }));
}
