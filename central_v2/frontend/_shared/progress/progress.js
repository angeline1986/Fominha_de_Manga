export function createJobProgress() {
  const element = document.createElement("section");
  element.className = "job-progress";
  element.hidden = true;
  element.setAttribute("role", "status");
  element.setAttribute("aria-live", "polite");
  element.setAttribute("aria-label", "Progresso do processamento");
  element.innerHTML = `
    <div class="job-progress-heading">
      <strong data-title>Auto-Merge Nível I</strong>
      <span data-count>Preparando…</span>
    </div>
    <p data-message></p>
    <progress max="100" value="0" aria-label="Progresso do processamento"></progress>
  `;
  const title = element.querySelector("[data-title]");
  const count = element.querySelector("[data-count]");
  const message = element.querySelector("[data-message]");
  const bar = element.querySelector("progress");

  return {
    element,
    update(state) {
      element.hidden = !state.busy;
      title.textContent = state.title || "Auto-Merge Nível I";
      message.textContent = state.message || "Preparando processamento…";
      const percent = Math.round(Math.max(0, Math.min(100, Number(state.percent) || 0)));
      const completed = Math.max(0, Number(state.completed) || 0);
      const total = Math.max(0, Number(state.total) || 0);
      count.textContent = total
        ? `${completed} de ${total} capítulo(s) · ${percent}%`
        : "Preparando…";
      bar.value = percent;
      bar.setAttribute("aria-valuenow", String(percent));
      bar.setAttribute("aria-valuetext", `${percent}% concluído`);
    },
  };
}
