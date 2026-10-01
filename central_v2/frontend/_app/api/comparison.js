export async function fetchComparison(context, signal) {
  const response = await fetch(`/api/textoff/comparison?${new URLSearchParams(context)}`, { signal, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Não foi possível carregar a comparação.");
  return data;
}

export function comparisonImageUrl(context, page, side) {
  return `/api/textoff/comparison/image?${new URLSearchParams({ ...context, page: page.id, version: page.version, side })}`;
}
