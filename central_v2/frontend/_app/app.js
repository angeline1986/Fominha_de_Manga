import { initializeContext } from "/_app/context/context_controller.js";
import { disposePage, navigate } from "/_app/router/router.js";
import { mountShell } from "/_shell/shell.js";
import { showMessage } from "/_shared/messages/messages.js";

const root = document.querySelector("#app");
const STARTUP_TIMEOUT_MS = 12000;

if (!root) {
  throw new Error("Elemento raiz #app não encontrado.");
}

function showLoading() {
  root.innerHTML = `<main class="startup-screen" role="status" aria-live="polite">
    <div class="startup-card"><h1>Central V2</h1><p>Carregando a Central…</p></div>
  </main>`;
}

function showStartupError(error) {
  root.innerHTML = `<main class="startup-screen" role="alert">
    <div class="startup-card">
      <h1>Não foi possível abrir a Central</h1>
      <p>Falha ao carregar os dados iniciais. Tente novamente.</p>
      <p class="startup-detail"></p>
      <button class="btn" type="button" data-startup-retry>Tentar novamente</button>
    </div>
  </main>`;
  root.querySelector(".startup-detail").textContent = error.message || "Erro desconhecido.";
  root.querySelector("[data-startup-retry]").addEventListener("click", bootstrap, { once: true });
}

async function loadContextOnce() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), STARTUP_TIMEOUT_MS);
  try {
    await initializeContext(controller.signal);
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error("O carregamento do catálogo demorou demais.");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function bootstrap() {
  showLoading();
  try {
    await loadContextOnce();
  } catch {
    try {
      await new Promise((resolve) => setTimeout(resolve, 500));
      await loadContextOnce();
    } catch (error) {
      console.error("Falha ao inicializar a Central V2.", error);
      showStartupError(error);
      return;
    }
  }

  try {
    mountApplication();
  } catch (error) {
    console.error("Falha ao montar a Central V2.", error);
    showStartupError(error);
  }
}

function mountApplication() {
  const disposeShell = mountShell(root, () => {
    disposePage(pageContent);
    disposeShell();
    root.removeEventListener("menu:action", onAction);
  });

  const pageContent = root.querySelector("#page-content");

  if (!pageContent) {
    throw new Error("Container #page-content não encontrado.");
  }

  async function onAction(event) {
    try {
      await navigate(event.detail.action, pageContent);
    } catch (error) {
      console.error(
        "[Central V2] Falha ao navegar.",
        error,
      );
      await showMessage({
        title: "Não foi possível abrir a tela",
        message: error.message || "Ocorreu um erro ao carregar esta página.",
      });
    }
  }
  root.addEventListener("menu:action", onAction);
}

bootstrap();
