import { iconMarkup } from "/_shared/icons/icons.js";
let queue = Promise.resolve();
let sequence = 0;

function openMessage({ title, message = "", confirm = false, confirmText = "OK", cancelText = "Cancelar", summary = null, onAction = null }) {
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
    if (summary) renderSummary(dialog, summary, confirmText, id, onAction);
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

function renderSummary(dialog, summary, closeText, id, onAction) {
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
    for (const detail of item.details || []) {
      const group = document.createElement("div");
      group.className = "message-summary-detail-group";
      const row = document.createElement("div");
      row.className = "message-summary-row";
      const label = document.createElement("span");
      const value = document.createElement("strong");
      label.className = "message-summary-label";
      value.className = `message-summary-value${detail.warning ? " is-warning" : ""}`;
      label.textContent = detail.label;
      value.textContent = detail.value;
      row.append(label, value);
      if (detail.files?.length) {
        const listId = `${id}-files-${item.chapter}-${detail.kind}`;
        const toggle = document.createElement("button");
        toggle.className = `message-summary-toggle is-${detail.kind}`;
        toggle.type = "button";
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-controls", listId);
        toggle.setAttribute("aria-label", `Mostrar arquivos: ${detail.label}`);
        toggle.textContent = "⌄";
        const files = document.createElement("ul");
        files.id = listId;
        files.className = `message-summary-files is-${detail.kind}`;
        files.hidden = true;
        for (const fileName of detail.files) {
          const file = document.createElement("li");
          file.textContent = fileName;
          files.append(file);
        }
        toggle.addEventListener("click", () => {
          const expanded = files.hidden;
          files.hidden = !expanded;
          toggle.setAttribute("aria-expanded", String(expanded));
          toggle.setAttribute("aria-label", `${expanded ? "Ocultar" : "Mostrar"} arquivos: ${detail.label}`);
        });
        row.append(toggle);
        group.append(row, files);
      } else {
        const spacer = document.createElement("span");
        spacer.className = "message-summary-toggle-spacer";
        row.append(spacer);
        group.append(row);
      }
      rows.append(group);
    }
    if (item.actions?.length) {
      const actions = document.createElement("div");
      actions.className = "message-summary-actions-inline";
      for (const action of item.actions) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "message-summary-folder-action";
        button.textContent = action.label;
        button.addEventListener("click", () => onAction?.(item, action));
        actions.append(button);
      }
      rows.append(actions);
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

export function showOperationSummary({ title = "Resumo da Operação", summary, closeText = "Fechar", onAction }) {
  return enqueue({ title, summary, confirm: false, confirmText: closeText, onAction });
}
