export function filterSolidChapters(rows, searchValue, statusFilter) {
  const term = String(searchValue || "").trim().toLocaleLowerCase("pt-BR");
  return rows.filter((row) => (row.chapter.toLocaleLowerCase("pt-BR").includes(term)
    || row.pages.some((item) => item.name.toLocaleLowerCase("pt-BR").includes(term)))
    && (statusFilter === "all" || statusFilter === "pending" && !row.processed
      || statusFilter === "processed" && row.processed)).map((row) => ({
    ...row, displayPages: term && !row.chapter.toLocaleLowerCase("pt-BR").includes(term)
      ? row.pages.filter((item) => item.name.toLocaleLowerCase("pt-BR").includes(term))
      : row.pages,
  }));
}
