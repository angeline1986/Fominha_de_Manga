export const KINDS = [
  { key: "textoff_merged", label: "TEXTO OFF — CONSOLIDADO FINAL", dest: "raws_semi-clean", unit: "imagens" },
  { key: "pdf_merge", label: "PDF_MERGE", dest: "Traducoes", unit: "PDFs" },
];
export const mb = n => `${(Number(n || 0) / 1000000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
export function invalidate(state) { state.plan = null; state.result = null; }
export async function api(path, options) {
  const resp = await fetch(path, { cache: "no-store", ...options });
  let data;
  try { data = await resp.json(); } catch { throw new Error(`Resposta inválida (HTTP ${resp.status}).`); }
  if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
  return data;
}
export function post(path, body) {
  return api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
