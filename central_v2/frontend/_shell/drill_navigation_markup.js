import { iconMarkup } from "/_shared/icons/icons.js";
import { segmentedMarkup } from "/_shell/merge_levels.js";

export function rootItem(section) {
  return `<button class="drill-item drill-root-item" type="button" data-section="${section.id}">
    ${iconMarkup(section.id)}
    <span class="drill-item-label">${section.label}</span>
    <span class="drill-arrow">${iconMarkup("next")}</span>
  </button>`;
}

export function groupMarkup(group, { selectedValues = new Map(), currentAction = null } = {}) {
  const hasSubitems = (group.items ?? []).length > 0;
  const control = group.control?.type === "segmented"
    ? { ...group.control, defaultValue: selectedValues.get(group.control.id) ?? group.control.defaultValue }
    : null;
  const content = group.type === "timeline"
    ? timelineMarkup(group, selectedValues, currentAction)
    : control
      ? segmentedMarkup(control)
      : `<div class="drill-group-items${hasSubitems ? " drill-subitem-list" : ""}">
      ${(group.items ?? []).map((item) => itemMarkup(item, hasSubitems, item.id === currentAction)).join("")}
    </div>`;
  const title = control && group.type !== "timeline" || !group.label ? "" : `<div class="drill-group-title${hasSubitems ? " drill-group-title-subitems" : ""}">${group.label}</div>`;
  return `<section class="drill-group">${title}${content}</section>`;
}

function timelineMarkup(group, selectedValues, currentAction) {
  const items = (group.items ?? []).map((item) => timelineItemMarkup(
    item, item.id === currentAction,
  )).join("");
  const control = { ...group.control,
    defaultValue: selectedValues.get(group.control.id) ?? group.control.defaultValue };
  return `<ol class="cleaning-timeline" aria-label="${group.label}">${items}${timelineControlMarkup(control)}</ol>`;
}

function timelineItemMarkup(item, isCurrent) {
  const tooltip = item.tooltip ?? "";
  const described = tooltip
    ? ` title="${tooltip}" data-tooltip="${tooltip}" aria-description="${tooltip}" aria-label="${item.label} — ${tooltip}"`
    : ` aria-label="${item.label}"`;
  return `<li class="cleaning-timeline-item">
    <span class="cleaning-timeline-number" aria-hidden="true">${item.number}</span>
    <button class="cleaning-timeline-card${isCurrent ? " is-current" : ""}" type="button" data-action="${item.id}"${described}>
      ${iconMarkup(item.icon)}<span>${item.label}</span>
    </button>
  </li>`;
}

function timelineControlMarkup(control) {
  return `<li class="cleaning-timeline-item cleaning-timeline-item-control">
    <span class="cleaning-timeline-number" aria-hidden="true">${control.number}</span>
    <div class="cleaning-timeline-control">
      ${segmentedMarkup(control)}
      ${control.options.map((option) => `<button class="cleaning-timeline-next" type="button" data-selected-value="${option.value}" data-action="${option.action}" aria-label="Abrir ${option.label}" title="Abrir ${option.label}">${iconMarkup("next")}</button>`).join("")}
    </div>
  </li>`;
}

function itemMarkup(item, hasSubitems, isCurrent) {
  const variant = item.variant ? ` drill-action-${item.variant}` : "";
  const current = isCurrent ? " is-current" : "";
  const iconName = item.variant === "sommelier" ? null : (item.icon ?? (hasSubitems ? (item.id === "validar-faixa" ? "crop-simple" : "scissors") : null));
  const icon = iconName ? iconMarkup(iconName) : "";
  const labelClass = hasSubitems ? "drill-subitem-label" : "drill-action-label";
  const caption = item.caption
    ? `<small class="drill-action-caption">${item.caption}</small>`
    : "";
  const arrow = item.arrow || ["primary", "secondary"].includes(item.variant);
  const tooltip = item.tooltip ?? item.title;
  const title = tooltip ? ` title="${tooltip}"` : "";
  const description = item.tooltip ? ` data-tooltip="${item.tooltip}" aria-description="${item.tooltip}"` : "";
  return `<button class="drill-item${hasSubitems ? " drill-subitem" : ""}${variant}${current}" type="button" data-action="${item.id}"${title}${description}>
    <span class="${labelClass}">${icon}<span class="drill-action-copy"><span>${item.label}</span>${caption}</span></span>
    ${arrow ? `<span class="drill-action-arrow">${iconMarkup("next")}</span>` : ""}
  </button>`;
}
