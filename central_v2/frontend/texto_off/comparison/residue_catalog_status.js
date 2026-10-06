export function residueCatalogStatus(item, catalogState) {
  const dirtyPages = catalogState.dirtyPageCount();
  const feedback = item.loadState === "loading" ? "Carregando ocorrências desta página…"
    : item.loadState === "error" ? `Falha ao carregar: ${item.error || "tente novamente."}`
      : catalogState.isSaving() ? "Salvando catálogo do capítulo…"
        : item.saveState === "error" ? `Falha ao catalogar capítulo: ${item.error || "tente novamente."}`
          : dirtyPages ? `Há alterações não catalogadas em ${dirtyPages} página(s) do capítulo.`
            : item.persisted ? "Ocorrências catalogadas."
              : "Nenhuma ocorrência catalogada nesta página.";
  const stale = item.staleSources || [];
  const unavailable = Object.entries(item.sourceStatus || {})
    .filter(([, source]) => source.status !== "available")
    .map(([name, source]) => `${sourceLabel(name)}: ${source.status === "invalid" ? "inválida" : "indisponível"}`);
  const sourceStatus = stale.length
    ? `Fontes alteradas após a decisão salva: ${stale.map(sourceLabel).join(", ")}. A decisão do Check continua vigente.`
    : unavailable.length ? `Fontes sem resultados utilizáveis: ${unavailable.join("; ")}.` : "";
  return { feedback, sourceStatus };
}

function sourceLabel(name) {
  return ({ mapear: "Mapear", sommelier: "Sommelier",
    residue_occurrences: "Catálogo manual" })[name] || name;
}
