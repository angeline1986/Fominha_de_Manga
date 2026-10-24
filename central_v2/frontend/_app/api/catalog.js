export async function fetchCatalog(signal) {
  const response = await fetch("/api/catalog", {
    signal,
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(
      `Falha ao carregar catálogo (${response.status}).`,
    );
  }

  return response.json();
}
