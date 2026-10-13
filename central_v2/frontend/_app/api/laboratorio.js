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

export async function executeStylizedLaboratoryJob(payload, signal, onProgress) {
  const { job } = await post("/api/textoff/laboratorio/estilizado/job", payload, signal);
  if (!job?.id) throw new Error("O servidor não retornou o job do Artístico.");
  let current = job;
  while (true) {
    if (signal?.aborted) throw new DOMException("Cancelado", "AbortError");
    onProgress?.(current.progress || {});
    if (current.status === "failed") {
      throw new Error(current.error || "Tratamento Artístico não concluído.");
    }
    if (current.status === "completed") {
      const result = current.results?.[0];
      if (!result?.image_url) throw new Error("Resultado Artístico indisponível.");
      return result;
    }
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => { signal?.removeEventListener("abort", aborted); resolve(); }, 500);
      const aborted = () => { clearTimeout(timer); reject(new DOMException("Cancelado", "AbortError")); };
      signal?.addEventListener("abort", aborted, { once: true });
      if (signal?.aborted) aborted();
    });
    ({ job: current } = await requestJson(`/api/jobs/${encodeURIComponent(job.id)}`,
      { signal, cache: "no-store" }));
  }
}

export async function executeSmoothLaboratoryJob(payload, signal, onProgress) {
  const { job } = await post("/api/textoff/laboratorio/gradiente_suave/job", payload, signal);
  if (!job?.id) throw new Error("O servidor não retornou o job do Suave.");
  let current = job;
  while (true) {
    if (signal?.aborted) throw new DOMException("Cancelado", "AbortError");
    onProgress?.(current.progress || {});
    if (current.status === "failed") {
      throw new Error(current.error || "Tratamento Suave não concluído.");
    }
    if (current.status === "completed") {
      const result = current.results?.[0];
      if (!result?.image_url) throw new Error("Resultado Suave indisponível.");
      return result;
    }
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => { signal?.removeEventListener("abort", aborted); resolve(); }, 500);
      const aborted = () => { clearTimeout(timer); reject(new DOMException("Cancelado", "AbortError")); };
      signal?.addEventListener("abort", aborted, { once: true });
      if (signal?.aborted) aborted();
    });
    ({ job: current } = await requestJson(`/api/jobs/${encodeURIComponent(job.id)}`,
      { signal, cache: "no-store" }));
  }
}
