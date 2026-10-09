export const artisticKey = (chapter, page, id) => JSON.stringify([chapter, page, id]);
export const artisticEligible = (item) => ["pending", "failed"].includes(item.status)
  && !item.execution_blocked;
export const artisticDone = (item) => ["processed", "no_change"].includes(item.status);

export function artisticGroups(chapters, query, filter) {
  const term = query.trim().toLocaleLowerCase("pt-BR");
  return chapters.map((chapter) => {
    const pages = chapter.pages.map((name) => {
      const all = (chapter.occurrences || []).filter((item) => item.page === name);
      const occurrences = all
        .filter((item) => filter === "all" || (filter === "completed"
          ? artisticDone(item) : !artisticDone(item)))
        .filter((item) => !term || `${chapter.chapter} ${name} ${item.id} balão ${String(
          all.findIndex((entry) => entry.id === item.id) + 1).padStart(2, "0")}`
          .toLocaleLowerCase("pt-BR").includes(term));
      return { name, occurrences };
    }).filter((page) => page.occurrences.length);
    return { chapter, pages, occurrences: pages.flatMap((page) => page.occurrences) };
  }).filter((group) => group.occurrences.length);
}

export function artisticCounts(chapters) {
  const items = chapters.flatMap((chapter) => chapter.occurrences || []);
  return { all: items.length, pending: items.filter((item) => !artisticDone(item)).length,
    completed: items.filter(artisticDone).length };
}

export function artisticSelected(chapters, selected, choices) {
  return chapters.flatMap((chapter) => (chapter.occurrences || [])
    .filter((item) => artisticEligible(item) &&
      choices.get(artisticKey(chapter.chapter, item.page, item.id)) !== "none" &&
      selected.has(artisticKey(chapter.chapter, item.page, item.id)))
    .map((item) => ({ chapter: chapter.chapter, page: item.page, id: item.id,
      status: item.status })));
}
