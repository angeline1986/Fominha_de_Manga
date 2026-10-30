let tooltipSequence = 0;

export function tooltipPosition(anchor, bounds, viewport) {
  const margin = 12;
  const gap = 7;
  const maxLeft = Math.max(margin, viewport.width - bounds.width - margin);
  const left = Math.max(margin, Math.min(
    anchor.left + (anchor.width - bounds.width) / 2, maxLeft,
  ));
  const above = anchor.top - bounds.height - gap;
  const below = anchor.bottom + gap;
  const top = above >= margin
    ? above : Math.min(below, Math.max(margin, viewport.height - bounds.height - margin));
  return { left, top };
}

export function bindNavigationTextTooltips(container) {
  const tooltip = document.createElement("aside");
  tooltip.className = "navigation-text-tooltip";
  tooltip.id = `navigation-text-tooltip-${++tooltipSequence}`;
  tooltip.setAttribute("role", "tooltip");
  tooltip.hidden = true;
  document.body.append(tooltip);
  let active = null;

  function show(anchor) {
    if (active === anchor) return;
    hide();
    active = anchor;
    tooltip.textContent = anchor.dataset.tooltip;
    tooltip.hidden = false;
    const position = tooltipPosition(
      anchor.getBoundingClientRect(), tooltip.getBoundingClientRect(),
      { width: window.innerWidth, height: window.innerHeight },
    );
    tooltip.style.left = `${position.left}px`;
    tooltip.style.top = `${position.top}px`;
    anchor.setAttribute("aria-describedby", tooltip.id);
  }

  function hide() {
    active?.removeAttribute("aria-describedby");
    active = null;
    tooltip.hidden = true;
  }

  function onEnter(event) {
    const anchor = event.target.closest("[data-tooltip]");
    if (anchor && container.contains(anchor) && !anchor.contains(event.relatedTarget)) show(anchor);
  }

  function onLeave(event) {
    const anchor = event.target.closest("[data-tooltip]");
    if (anchor === active && !active.contains(event.relatedTarget)) hide();
  }

  function onFocus(event) {
    const anchor = event.target.closest("[data-tooltip]");
    if (anchor && container.contains(anchor)) show(anchor);
  }

  function onBlur(event) {
    if (active && !active.contains(event.relatedTarget)) hide();
  }

  container.addEventListener("pointerover", onEnter);
  container.addEventListener("pointerout", onLeave);
  container.addEventListener("focusin", onFocus);
  container.addEventListener("focusout", onBlur);
  container.addEventListener("click", hide, true);
  window.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);

  return () => {
    hide();
    tooltip.remove();
    container.removeEventListener("pointerover", onEnter);
    container.removeEventListener("pointerout", onLeave);
    container.removeEventListener("focusin", onFocus);
    container.removeEventListener("focusout", onBlur);
    container.removeEventListener("click", hide, true);
    window.removeEventListener("scroll", hide, true);
    window.removeEventListener("resize", hide);
  };
}
