async function requestJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Falha HTTP ${response.status}`);
  return body;
}

export function executeStylizedLaboratory(payload, signal) {
  return requestJson("/api/textoff/laboratorio/estilizado/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export function executeSmoothLaboratory(payload, signal) {
  return requestJson("/api/textoff/laboratorio/gradiente_suave/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}
