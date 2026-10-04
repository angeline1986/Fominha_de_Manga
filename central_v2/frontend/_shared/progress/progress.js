export function createJobProgress(defaultTitle = "Auto-Merge Nível I", options = {}) {
  const element = document.createElement("section");
  element.className = options.inline ? "job-progress job-progress--inline" : "job-progress";
  element.hidden = true;
  element.setAttribute("role", "status");
  element.setAttribute("aria-live", "polite");
  element.setAttribute("aria-label", "Progresso do processamento");
  element.innerHTML = `
    <div class="job-progress-heading">
      <strong data-title></strong>
      <span data-count>Preparando…</span>
    </div>
    <p data-message></p>
    <progress max="100" value="0" aria-label="Progresso do processamento"></progress>
  `;
  const title = element.querySelector("[data-title]");
  const count = element.querySelector("[data-count]");
  const message = element.querySelector("[data-message]");
  const bar = element.querySelector("progress");
  title.textContent = defaultTitle;

  return {
    element,
    update(state) {
      element.hidden = !state.busy;
      title.textContent = state.title || defaultTitle;
      message.textContent = state.message || "Preparando processamento…";
      const percent = Math.round(Math.max(0, Math.min(100, Number(state.percent) || 0)));
      const completed = Math.max(0, Number(state.completed) || 0);
      const total = Math.max(0, Number(state.total) || 0);
      const unit = state.countUnit || options.countUnit || "capítulo(s)";
      count.textContent = total
        ? `${completed} de ${total} ${unit} · ${percent}%`
        : "Preparando…";
      bar.value = percent;
      bar.setAttribute("aria-valuenow", String(percent));
      bar.setAttribute("aria-valuetext", `${percent}% concluído`);
    },
  };
}
