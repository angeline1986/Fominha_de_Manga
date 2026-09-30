export function segmentedMarkup(control) {
  const previews = (option) => option.preview ? `
              data-preview-title="${option.title}"
              data-preview-before="${option.preview.before}"
              data-preview-after="${option.preview.after}"
              aria-label="Nível ${option.value}: ${option.title}"` : "";
  return `
    <div
      class="segmented-shell"
      data-segmented="${control.id}"
      data-value="${control.defaultValue}"
    >
      <div class="segmented-header">
        <strong>${control.label}</strong>
        <span class="segmented-badge">
          NÍVEL ${control.defaultValue}
        </span>
      </div>

      <div class="segmented-card">
        <div
          class="segmented-control"
          role="group"
          aria-label="Seletor de nível de ${control.label}"
        >
          ${control.options.map((option) => `
            <button
              class="segmented-button${option.value === control.defaultValue ? " active" : ""}"
              type="button"
              data-segment-value="${option.value}"
              data-action="${option.action}"
              ${option.preview ? previews(option) : option.title ? `title="${option.title}" aria-label="Nível ${option.value}: ${option.title}"` : ""}
              aria-pressed="${option.value === control.defaultValue}"
            >
              ${option.label}
            </button>
          `).join("")}
        </div>
      </div>
    </div>
  `;
}

export function selectMergeLevel(segmentButton) {
  const segmented = segmentButton.closest("[data-segmented]");
  const buttons = segmented.querySelectorAll("[data-segment-value]");
  const value = segmentButton.dataset.segmentValue;
  const badge = segmented.querySelector(".segmented-badge");

  buttons.forEach((button) => {
    const active = button === segmentButton;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  segmented.dataset.value = value;

  if (badge) {
    badge.textContent = `NÍVEL ${value}`;
  }
}
