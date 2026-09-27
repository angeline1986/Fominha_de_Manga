export async function fetchCatalog() {
  const response = await fetch("/api/catalog", {
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
