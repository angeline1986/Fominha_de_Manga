import { iconMarkup } from "/_shared/icons/icons.js";
let queue = Promise.resolve();
let sequence = 0;

function openMessage({ title, message = "", confirm = false, confirmText = "OK", cancelText = "Cancelar", summary = null }) {
  return new Promise((resolve) => {
    const previousFocus = document.activeElement;
    const dialog = document.createElement("dialog");
    const id = `message-${++sequence}`;
    dialog.className = `message-dialog${summary ? " message-summary-dialog" : ""}`;
    dialog.setAttribute("aria-labelledby", `${id}-title`);
    dialog.setAttribute("aria-describedby", summary ? `${id}-summary` : `${id}-body`);
    dialog.innerHTML = `
      <div class="message-heading">
        <div><span class="message-caption" data-caption hidden>PROCESSAMENTO</span><h2 id="${id}-title"></h2></div>
        <button type="button" data-close aria-label="Fechar">${iconMarkup("close")}</button>
      </div>
      <p id="${id}-body"></p>
      <div id="${id}-summary" class="message-summary" data-summary hidden>
        <div class="message-summary-batch"><strong data-headline></strong><span data-breakdown></span></div>
        <div class="message-summary-items" data-items></div>
      </div>
      <div class="message-actions">
        <button type="button" data-cancel></button>
        <button type="button" data-accept></button>
      </div>
    `;
    dialog.querySelector("h2").textContent = title;
    const body = dialog.querySelector("p");
    body.textContent = message;
    body.hidden = !message;
    if (summary) renderSummary(dialog, summary, confirmText);
    const cancel = dialog.querySelector("[data-cancel]");
    const accept = dialog.querySelector("[data-accept]");
    cancel.textContent = cancelText;
    cancel.hidden = !confirm;
    accept.textContent = confirmText;
    function finish(accepted) { dialog.close(accepted ? "accepted" : "dismissed"); }
    cancel.addEventListener("click", () => finish(false));
    accept.addEventListener("click", () => finish(true));
    dialog.querySelector("[data-close]").addEventListener("click", () => finish(false));
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finish(false);
    });
    dialog.addEventListener("click", (event) => {
      const bounds = dialog.getBoundingClientRect();
      if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right
        || event.clientY < bounds.top || event.clientY > bounds.bottom)) finish(false);
    });
    dialog.addEventListener("close", () => {
      dialog.remove();
      if (previousFocus?.isConnected) previousFocus.focus();
      resolve(dialog.returnValue === "accepted");
    }, { once: true });
    document.body.append(dialog);
    dialog.showModal();
    (confirm ? cancel : accept).focus();
  });
}

function renderSummary(dialog, summary, closeText) {
  dialog.querySelector("[data-caption]").hidden = false;
  const container = dialog.querySelector("[data-summary]");
  container.hidden = false;
  dialog.querySelector("[data-headline]").textContent = summary.headline || "";
  dialog.querySelector("[data-breakdown]").textContent = summary.breakdown || "";
  dialog.querySelector("[data-accept]").textContent = closeText;
  const list = dialog.querySelector("[data-items]");
  for (const item of summary.items || []) {
    const details = document.createElement("details");
    details.className = "message-summary-item";
    const heading = document.createElement("summary");
    const chapter = document.createElement("span");
    const status = document.createElement("strong");
    const count = document.createElement("span");
    chapter.textContent = `Cap. ${item.chapter}`;
    status.textContent = item.status || "—";
    status.className = item.warning ? "is-warning" : "";
    count.textContent = item.count || "";
    heading.append(chapter, status, count);
    details.append(heading);
    const rows = document.createElement("div");
    rows.className = "message-summary-details";
    for (const [labelText, valueText] of item.details || []) {
      const row = document.createElement("div");
      const label = document.createElement("span");
      const value = document.createElement("strong");
      label.textContent = labelText;
      value.textContent = valueText;
      row.append(label, value);
      rows.append(row);
    }
    details.append(rows);
    list.append(details);
  }
}

function enqueue(options) {
  const pending = queue.then(() => openMessage(options));
  queue = pending.catch(() => {});
  return pending;
}

export function confirmMessage(options) {
  return enqueue({ ...options, confirm: true, confirmText: options.confirmText || "Confirmar" });
}

export function showMessage(options) {
  return enqueue({ ...options, confirm: false });
}

export function showOperationSummary({ title = "Resumo da Operação", summary, closeText = "Fechar" }) {
  return enqueue({ title, summary, confirm: false, confirmText: closeText });
}
