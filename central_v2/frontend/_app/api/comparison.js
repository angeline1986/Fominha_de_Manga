const CONTEXT_PARAMS = ["provider", "manga", "chapter", "step", "comparisonMode", "scope", "layout"];

function comparisonParams(context, extra = {}) {
  const params = new URLSearchParams();
  for (const key of CONTEXT_PARAMS) {
    const value = context[key];
    if (value != null) params.set(key, String(value));
  }
  for (const [key, value] of Object.entries(extra)) {
    if (value != null) params.set(key, String(value));
  }
  return params;
}

export async function fetchComparison(context, signal) {
  const query = comparisonParams(context);
  const response = await fetch(`/api/textoff/comparison?${query}`, { signal, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Não foi possível carregar a comparação.");
  return data;
}

export function comparisonImageUrl(context, page, side) {
  const query = comparisonParams(context, { page: page.id, version: page.version, side });
  return `/api/textoff/comparison/image?${query}`;
}
