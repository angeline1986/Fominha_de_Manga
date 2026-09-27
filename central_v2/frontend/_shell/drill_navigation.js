import { navigation } from "/_shell/navigation.js";

function rootItem(section) {
  return `
    <button
      class="drill-item drill-root-item"
      type="button"
      data-section="${section.id}"
    >
      <span>${section.label}</span>
      <span class="drill-arrow" aria-hidden="true">›</span>
    </button>
  `;
}

function segmentedMarkup(control) {
  return `
    <div
      class="segmented-card"
      data-segmented="${control.id}"
      data-value="${control.defaultValue}"
    >
      <div class="segmented-header">
        <strong>${control.label}</strong>
        <span class="segmented-badge">
          NÍVEL ${control.defaultValue}
        </span>
      </div>

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
            aria-pressed="${option.value === control.defaultValue}"
          >
            ${option.label}
          </button>
        `).join("")}
      </div>
    </div>
  `;
}

function groupMarkup(group) {
  const content = group.control?.type === "segmented"
    ? segmentedMarkup(group.control)
    : `
      <div class="drill-group-items">
        ${(group.items ?? []).map((item) => `
          <button
            class="drill-item"
            type="button"
            data-action="${item.id}"
          >
            <span>${item.label}</span>
          </button>
        `).join("")}
      </div>
    `;

  return `
    <section class="drill-group">
      <div class="drill-group-title">${group.label}</div>
      ${content}
    </section>
  `;
}

export function createDrillNavigation() {
  const element = document.createElement("div");
  element.className = "drill-navigation";

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
            ‹
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
      openSection(sectionButton.dataset.section, sectionButton);
      return;
    }

    if (event.target.closest(".drill-back")) {
      closeSection();
      return;
    }

    const segmentButton = event.target.closest("[data-segment-value]");

    if (segmentButton) {
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

    const actionButton = event.target.closest("[data-action]");

    if (actionButton) {
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

      element.dispatchEvent(
        new CustomEvent("menu:action", {
          bubbles: true,
          detail: {
            context: sectionId ?? null,
            action: actionButton.dataset.action,
            label: actionButton.textContent.trim(),
          },
        }),
      );
    }
  });

  element.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && element.classList.contains("is-detail")) {
      event.preventDefault();
      closeSection();
    }
  });

  return element;
}
