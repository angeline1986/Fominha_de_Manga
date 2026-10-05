import { iconMarkup } from "/_shared/icons/icons.js";

export function segmentedMarkup(control) {
  const selected = control.options.find((option) => option.value === control.defaultValue);
  const badgeFormat = control.badgeFormat ?? "NÍVEL {value}";
  const previews = (option) => option.preview ? `
              data-preview-title="${option.title}"
              data-preview-before="${option.preview.before}"
              data-preview-after="${option.preview.after}"
              aria-label="${option.label}: ${option.title}"`
    : option.tooltip ? ` title="${option.tooltip}" data-tooltip="${option.tooltip}"
              aria-description="${option.tooltip}" aria-label="${option.label}: ${option.tooltip}"`
      : (option.title || option.caption) ? `title="${option.title ?? option.caption}" aria-label="${option.label}: ${option.title ?? option.caption}"` : "";
  const accessibleLabel = control.ariaLabel ?? control.label;
  const headerTooltip = control.tooltip
    ? ` title="${control.tooltip}" data-tooltip="${control.tooltip}" aria-description="${control.tooltip}" tabindex="0"`
    : "";
  return `
    <div
      class="segmented-shell${control.options.some((option) => option.caption) ? " segmented-shell--captioned" : ""}"
      data-segmented="${control.id}"
      data-value="${control.defaultValue}"
      data-badge-format="${badgeFormat}"
    >
      <div class="segmented-header">
        <strong${headerTooltip} aria-label="${accessibleLabel}">${control.icon ? iconMarkup(control.icon) : ""}${control.label}</strong>
        ${control.showBadge === false ? "" : `<span class="segmented-badge">${badgeFormat.replace("{value}", control.defaultValue)}</span>`}
      </div>

      <div class="segmented-card">
        <div
          class="segmented-control"
          role="group"
          aria-label="${control.ariaLabel ?? `Opções de ${control.label}`}"
        >
          ${control.options.map((option) => `
            <button
              class="segmented-button${option.value === control.defaultValue ? " active" : ""}"
              type="button"
              data-segment-value="${option.value}"
              data-action="${option.action}"
              ${previews(option)}
              aria-pressed="${option.value === control.defaultValue}"
            >
              ${control.plainLabels ? option.label : `<span class="segmented-option-content">${option.icon ? iconMarkup(option.icon) : ""}<span>${option.label}</span></span>`}
            </button>
          `).join("")}
        </div>
        ${control.hideCaption !== true && control.options.some((option) => option.caption) ? `<div class="segmented-caption"><strong data-segment-caption>${selected?.caption ?? ""}</strong></div>` : ""}
      </div>
    </div>
  `;
}

export function selectMergeLevel(segmentButton, control) {
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
    badge.textContent = segmented.dataset.badgeFormat.replace("{value}", value);
  }

  const caption = segmented.querySelector("[data-segment-caption]");
  if (caption) {
    caption.textContent = control.options.find((option) => option.value === value)?.caption ?? "";
  }
}
