import { shutdownServer } from "/_app/api/shutdown.js";
import { confirmMessage, showMessage } from "/_shared/messages/messages.js";

export function bindShutdown(button, onStopped) {
  let pending = false;
  let disposed = false;
  async function stop() {
    if (button.disabled || pending || disposed) return;
    pending = true;
    const confirmed = await confirmMessage({
      title: "Finalizar servidor",
      message: "Finalizar a Central de Processamento e voltar ao menu do terminal?",
      confirmText: "Finalizar",
    });
    pending = false;
    if (!confirmed || disposed) return;

    const originalContent = button.innerHTML;
    button.disabled = true;
    button.textContent = "Finalizando...";

    try {
      await shutdownServer();
    } catch (error) {
      console.error("[Central V2] Falha ao finalizar servidor:", error);
      button.disabled = false;
      button.innerHTML = originalContent;
      await showMessage({ title: "Erro ao finalizar", message: "Erro ao finalizar o servidor." });
      return;
    }

    onStopped();
    if (typeof window.close === "function") window.close();
    if (window.closed) return;
    document.body.innerHTML = `
      <main class="shutdown-screen">
        <h2>Central V2 finalizada com sucesso.</h2>
        <p>Você já pode fechar esta aba.</p>
      </main>
    `;
  }

  button.addEventListener("click", stop);
  return () => {
    disposed = true;
    button.removeEventListener("click", stop);
  };
}
