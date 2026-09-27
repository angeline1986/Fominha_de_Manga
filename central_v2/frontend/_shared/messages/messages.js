import { iconMarkup } from "/_shared/icons/icons.js";
let queue = Promise.resolve();
let sequence = 0;

function openMessage({ title, message, confirm = false, confirmText = "OK", cancelText = "Cancelar" }) {
  return new Promise((resolve) => {
    const previousFocus = document.activeElement;
    const dialog = document.createElement("dialog");
    const id = `message-${++sequence}`;
    dialog.className = "message-dialog";
    dialog.setAttribute("aria-labelledby", `${id}-title`);
    dialog.setAttribute("aria-describedby", `${id}-body`);
    dialog.innerHTML = `
      <div class="message-heading">
        <h2 id="${id}-title"></h2>
        <button type="button" data-close aria-label="Fechar">${iconMarkup("close")}</button>
      </div>
      <p id="${id}-body"></p>
      <div class="message-actions">
        <button type="button" data-cancel></button>
        <button type="button" data-accept></button>
      </div>
    `;
    dialog.querySelector("h2").textContent = title;
    dialog.querySelector("p").textContent = message;
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
