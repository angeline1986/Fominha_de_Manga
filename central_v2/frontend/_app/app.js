import { initializeContext } from "/_app/context/context_controller.js";
import { disposePage, navigate } from "/_app/router/router.js";
import { mountShell } from "/_shell/shell.js";

const root = document.querySelector("#app");

if (!root) {
  throw new Error("Elemento raiz #app não encontrado.");
}

async function bootstrap() {
  await initializeContext();
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
    }
  }
  root.addEventListener("menu:action", onAction);
}

bootstrap().catch((error) => {
  console.error("Falha ao inicializar a Central V2.", error);
});
