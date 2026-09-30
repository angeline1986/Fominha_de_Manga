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
  const content = control
    ? segmentedMarkup(control)
    : `<div class="drill-group-items${hasSubitems ? " drill-subitem-list" : ""}">
      ${(group.items ?? []).map((item) => itemMarkup(item, hasSubitems, item.id === currentAction)).join("")}
    </div>`;
  const title = control || !group.label ? "" : `<div class="drill-group-title${hasSubitems ? " drill-group-title-subitems" : ""}">${group.label}</div>`;
  return `<section class="drill-group">${title}${content}</section>`;
}

function itemMarkup(item, hasSubitems, isCurrent) {
  const variant = item.variant ? ` drill-action-${item.variant}` : "";
  const current = isCurrent ? " is-current" : "";
  const iconName = item.icon ?? (hasSubitems ? (item.id === "validar-faixa" ? "crop-simple" : "scissors") : null);
  const icon = iconName ? iconMarkup(iconName) : "";
  const labelClass = hasSubitems ? "drill-subitem-label" : "drill-action-label";
  return `<button class="drill-item${hasSubitems ? " drill-subitem" : ""}${variant}${current}" type="button" data-action="${item.id}">
    <span class="${labelClass}">${icon}<span>${item.label}</span></span>
    ${["primary", "secondary"].includes(item.variant) ? `<span class="drill-action-arrow">${iconMarkup("next")}</span>` : ""}
  </button>`;
}
