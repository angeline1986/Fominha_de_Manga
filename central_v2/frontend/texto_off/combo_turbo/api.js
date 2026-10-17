const jsonRequest = async (url, options = {}) => {
  const response = await fetch(url, { cache: "no-store", ...options });
  const payload = await response.json();
  if (!response.ok) {
    const error = new Error(payload.error || `Falha HTTP ${response.status}`);
    error.status = response.status;
    error.reason = payload.reason || payload.reason_code;
    error.payload = payload;
    throw error;
  }
  return payload;
};

export function fetchChapterOverview(provider, manga) {
  const query = new URLSearchParams({ provider, manga });
  return jsonRequest(`/api/textoff/merged/level1?${query}`);
}

export function planCombo(provider, manga, chapters) {
  return jsonRequest("/api/combo-turbo/plan", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, manga, chapters }),
  });
}

export function startCombo(provider, manga, chapters, planToken) {
  return jsonRequest("/api/combo-turbo/jobs", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, manga, chapters, plan_token: planToken }),
  });
}

export function fetchComboJob(url) { return jsonRequest(url); }
export function fetchComboResult(url) { return jsonRequest(url); }

export function describeError(error) {
  if (error.reason === "PERSISTED_RESULT_INVALID" || error.reason === "SOURCE_SIGNATURE_CHANGED") {
    return "O resultado foi alterado ou ficou obsoleto; atualize o planejamento.";
  }
  if (error.status === 409 || error.reason === "PLAN_CONTEXT_CHANGED") {
    return "As fontes ou o plano mudaram. Planeje a seleção novamente.";
  }
  if (/execução Combo/i.test(error.message) || /job Combo/i.test(error.message)) {
    return "Já existe uma execução Combo para esta obra.";
  }
  return error.message || "Falha de comunicação com a Central.";
}
