import { iconMarkup } from "/_shared/icons/icons.js";
import { bindHoverPreview } from "/_shell/hover_preview.js";
import { segmentedMarkup, selectMergeLevel } from "/_shell/merge_levels.js";
import { navigation } from "/_shell/navigation.js";

function itemIconMarkup(action) {
  const iconClass = action === "validar-faixa"
    ? "fa-solid fa-crop-simple text-xs text-slate-400"
    : "fa-solid fa-scissors text-xs text-sky-600";
  return `<i class="drill-subitem-icon ${iconClass}" aria-hidden="true"></i>`;
}

function rootItem(section) {
  return `
    <button
      class="drill-item drill-root-item"
      type="button"
      data-section="${section.id}"
    >
      ${iconMarkup(section.id)}
      <span class="drill-item-label">${section.label}</span>
      <span class="drill-arrow">${iconMarkup("next")}</span>
    </button>
  `;
}

function groupMarkup(group) {
  const hasSubitems = (group.items ?? []).length > 0;
  const content = group.control?.type === "segmented"
    ? segmentedMarkup(group.control)
    : `
      <div class="drill-group-items${hasSubitems ? " drill-subitem-list" : ""}">
        ${(group.items ?? []).map((item) => `
          <button
            class="drill-item${hasSubitems ? " drill-subitem" : ""}"
            type="button"
            data-action="${item.id}"
          >
            ${group.linear ? `<span class="drill-subitem-label">${itemIconMarkup(item.id)}${item.label}</span>` : `<span>${item.label}</span>`}
          </button>
        `).join("")}
      </div>
    `;

  const title = group.control?.type === "segmented"
    ? ""
    : `<div class="drill-group-title${hasSubitems ? " drill-group-title-subitems" : ""}">${group.label}</div>`;

  return `
    <section class="drill-group">
      ${title}
      ${content}
    </section>
  `;
}

export function createDrillNavigation() {
  const element = document.createElement("div");
  element.className = "drill-navigation";
  const disposePreview = bindHoverPreview(element);

  element.innerHTML = `
    <div class="drill-stage">
      <section class="drill-layer drill-layer-root">
        <div class="drill-heading">
          <strong>Menu principal</strong>
        </div>

        <nav class="drill-list" aria-label="Menu principal">
          ${navigation.map(rootItem).join("")}
        </nav>
      </section>

      <section class="drill-layer drill-layer-detail" inert>
        <div class="drill-heading drill-detail-heading">
          <button
            class="drill-back"
            type="button"
            aria-label="Voltar ao menu principal"
          >
            ${iconMarkup("back")}
          </button>

          <strong class="drill-section-title"></strong>
        </div>

        <div class="drill-detail-content"></div>
      </section>
    </div>
  `;

  const rootLayer = element.querySelector(".drill-layer-root");
  const detailLayer = element.querySelector(".drill-layer-detail");
  const detailContent = element.querySelector(".drill-detail-content");
  const sectionTitle = element.querySelector(".drill-section-title");
  const backButton = element.querySelector(".drill-back");

  let trigger = null;

  function openSection(sectionId, sourceButton) {
    const section = navigation.find((item) => item.id === sectionId);

    if (!section) {
      return;
    }

    trigger = sourceButton;
    sectionTitle.textContent = section.label;
    detailContent.innerHTML = section.groups.map(groupMarkup).join("");

    rootLayer.inert = true;
    detailLayer.inert = false;
    element.classList.add("is-detail");

    backButton.focus();
  }

  function closeSection() {
    element.classList.remove("is-detail");

    rootLayer.inert = false;
    detailLayer.inert = true;

    const previousTrigger = trigger;
    trigger = null;

    previousTrigger?.focus();
  }

  element.addEventListener("click", (event) => {
    const sectionButton = event.target.closest("[data-section]");

    if (sectionButton) {
      const section = navigation.find((item) => item.id === sectionButton.dataset.section);
      openSection(sectionButton.dataset.section, sectionButton);
      if (section?.defaultAction) dispatchAction(section.defaultAction, section.label, section.id);
      return;
    }

    if (event.target.closest(".drill-back")) {
      closeSection();
      return;
    }

    const segmentButton = event.target.closest("[data-segment-value]");

    if (segmentButton) {
      selectMergeLevel(segmentButton);
    }

    const actionButton = event.target.closest("[data-action]");

    if (actionButton) {
      element.querySelectorAll(".drill-subitem.is-current").forEach((item) => item.classList.remove("is-current"));
      actionButton.classList.add("is-current");
      const sectionId = navigation.find((section) =>
        section.groups.some((group) => {
          const itemMatch = (group.items ?? []).some(
            (item) => item.id === actionButton.dataset.action,
          );

          const controlMatch = (group.control?.options ?? []).some(
            (option) => option.action === actionButton.dataset.action,
          );

          return itemMatch || controlMatch;
        })
      )?.id;

      dispatchAction(actionButton.dataset.action, actionButton.textContent.trim(), sectionId);
    }
  });

  function dispatchAction(action, label, context) {
    element.dispatchEvent(new CustomEvent("menu:action", {
      bubbles: true,
      detail: { context: context ?? null, action, label },
    }));
  }

  element.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && element.classList.contains("is-detail")) {
      event.preventDefault();
      closeSection();
    }
  });

  return { element, dispose: disposePreview };
}
