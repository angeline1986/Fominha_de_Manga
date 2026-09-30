import { iconMarkup } from "/_shared/icons/icons.js";
import { bindHoverPreview } from "/_shell/hover_preview.js";
import { selectMergeLevel } from "/_shell/merge_levels.js";
import { groupMarkup, rootItem } from "/_shell/drill_navigation_markup.js";
import { navigation } from "/_shell/navigation.js";

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
  const selectedValues = new Map();
  const lastActions = new Map();

  function openSection(sectionId, sourceButton) {
    const section = navigation.find((item) => item.id === sectionId);

    if (!section) {
      return;
    }

    trigger = sourceButton;
    element.dispatchEvent(new CustomEvent("menu:detail-open", { bubbles: true }));
    sectionTitle.textContent = section.label;
    element.classList.toggle("is-limpeza-baloes", sectionId === "texto-off");
    const state = { selectedValues, currentAction: lastActions.get(sectionId) };
    detailContent.innerHTML = section.groups.map((group) => groupMarkup(group, state)).join("");

    rootLayer.inert = true;
    detailLayer.inert = false;
    element.classList.add("is-detail");

    backButton.focus();
  }

  function closeSection() {
    element.classList.remove("is-detail");
    element.classList.remove("is-limpeza-baloes");
    element.dispatchEvent(new CustomEvent("menu:detail-close", { bubbles: true }));

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
      const action = section && (lastActions.get(section.id) ?? section.defaultAction);
      if (action) dispatchAction(action, actionLabel(section, action), section.id);
      return;
    }

    if (event.target.closest(".drill-back")) {
      closeSection();
      return;
    }

    const segmentButton = event.target.closest("[data-segment-value]");

    if (segmentButton) {
      const control = segmentButton.closest("[data-segmented]");
      selectMergeLevel(segmentButton, controlForSegment(control.dataset.segmented));
      selectedValues.set(control.dataset.segmented, segmentButton.dataset.segmentValue);
    }

    const actionButton = event.target.closest("[data-action]");

    if (actionButton) {
      element.querySelectorAll(".drill-subitem.is-current").forEach((item) => item.classList.remove("is-current"));
      actionButton.classList.add("is-current");
      const section = sectionForAction(actionButton.dataset.action);
      const sectionId = section?.id;
      if (sectionId) lastActions.set(sectionId, actionButton.dataset.action);

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

function sectionForAction(action) {
  return navigation.find((section) => section.groups.some((group) =>
    (group.items ?? []).some((item) => item.id === action)
      || (group.control?.options ?? []).some((option) => option.action === action)));
}

function controlForSegment(id) {
  return navigation.flatMap((section) => section.groups)
    .find((group) => group.control?.id === id)?.control;
}

function actionLabel(section, action) {
  for (const group of section.groups) {
    const item = (group.items ?? []).find((candidate) => candidate.id === action);
    const option = group.control?.options?.find((candidate) => candidate.action === action);
    if (item || option) return item?.label ?? option.label;
  }
  return section.label;
}
