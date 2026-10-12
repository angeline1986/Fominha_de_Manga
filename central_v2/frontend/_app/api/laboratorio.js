async function requestJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(body.error || `Falha HTTP ${response.status}`);
    error.body = body;
    error.status = response.status;
    throw error;
  }
  return body;
}

function post(url, payload, signal) {
  return requestJson(url, {method: "POST",
    headers: {"Content-Type": "application/json", Accept: "application/json"},
    body: JSON.stringify(payload), signal});
}

export function executeDegradeLaboratory(payload, signal) {
  return post("/api/textoff/laboratorio/degrade/execute", payload, signal);
}

export function getDegradeAuthorizationCandidates(runId, signal) {
  return post("/api/textoff/laboratorio/degrade/authorization-candidates",
    {run_id: runId}, signal);
}

export function confirmDegradeLaboratory(payload, signal) {
  return post("/api/textoff/laboratorio/degrade/authorize", payload, signal);
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
