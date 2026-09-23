(() => {
  "use strict";

  const DEFAULTS = Object.freeze({
    min: 30,
    max: 200,
    step: 10,
    reset: 100
  });

  function normalizeOptions(options = {}) {
    return {
      min: Number.isFinite(options.min) ? options.min : DEFAULTS.min,
      max: Number.isFinite(options.max) ? options.max : DEFAULTS.max,
      step: Number.isFinite(options.step) && options.step > 0
        ? options.step
        : DEFAULTS.step,
      reset: Number.isFinite(options.reset) ? options.reset : DEFAULTS.reset
    };
  }

  function clampZoom(value, options = {}) {
    const config = normalizeOptions(options);
    const numeric = Number(value);
    const safeValue = Number.isFinite(numeric) ? numeric : config.reset;
    const stepped = Math.round(safeValue / config.step) * config.step;
    return Math.max(config.min, Math.min(config.max, stepped));
  }

  function setZoom(value, {
    images = [],
    label = null,
    options = {}
  } = {}) {
    const zoom = clampZoom(value, options);

    const targets = Array.isArray(images) ? images : [images];
    targets.forEach(target => {
      const image = typeof target === "string"
        ? document.querySelector(target)
        : target;

      if (image) image.style.width = `${zoom}%`;
    });

    const labelNode = typeof label === "string"
      ? document.querySelector(label)
      : label;

    if (labelNode) labelNode.textContent = `${zoom}%`;

    return zoom;
  }

  function bindZoomControls({
    selector,
    getZoom,
    setZoom: applyZoom,
    options = {}
  } = {}) {
    if (!selector || typeof getZoom !== "function" || typeof applyZoom !== "function") {
      return;
    }

    const config = normalizeOptions(options);

    document.querySelectorAll(selector).forEach(button => {
      button.onclick = () => {
        const action = String(button.dataset.z || "");
        const current = Number(getZoom());

        if (action.endsWith("in")) {
          applyZoom(current + config.step);
          return;
        }

        if (action.endsWith("out")) {
          applyZoom(current - config.step);
          return;
        }

        applyZoom(config.reset);
      };
    });
  }

  function syncScroll(first, second) {
    if (!first || !second) return () => {};

    let locked = false;

    const sync = (source, target) => {
      if (locked) return;
      locked = true;

      const sourceX = Math.max(1, source.scrollWidth - source.clientWidth);
      const sourceY = Math.max(1, source.scrollHeight - source.clientHeight);

      target.scrollLeft =
        (source.scrollLeft / sourceX) *
        Math.max(0, target.scrollWidth - target.clientWidth);

      target.scrollTop =
        (source.scrollTop / sourceY) *
        Math.max(0, target.scrollHeight - target.clientHeight);

      requestAnimationFrame(() => {
        locked = false;
      });
    };

    const firstHandler = () => sync(first, second);
    const secondHandler = () => sync(second, first);

    first.addEventListener("scroll", firstHandler, { passive: true });
    second.addEventListener("scroll", secondHandler, { passive: true });

    return () => {
      first.removeEventListener("scroll", firstHandler);
      second.removeEventListener("scroll", secondHandler);
    };
  }

  window.FominhaViewer = Object.freeze({
    DEFAULTS,
    clampZoom,
    setZoom,
    bindZoomControls,
    syncScroll
  });
})();
