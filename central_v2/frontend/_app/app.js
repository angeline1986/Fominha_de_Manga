import { initializeContext } from "/_app/context/context_controller.js";
import { navigate } from "/_app/router/router.js";
import { mountShell } from "/_shell/shell.js";

const root = document.querySelector("#app");

if (!root) {
  throw new Error("Elemento raiz #app não encontrado.");
}

async function bootstrap() {
  const context = await initializeContext();
  mountShell(root, context);

  const pageContent = root.querySelector("#page-content");

  if (!pageContent) {
    throw new Error("Container #page-content não encontrado.");
  }

  root.addEventListener("menu:action", async (event) => {
    try {
      await navigate(event.detail.action, pageContent);
    } catch (error) {
      console.error(
        "[Central V2] Falha ao navegar.",
        error,
      );
    }
  });
}

bootstrap().catch((error) => {
  console.error("Falha ao inicializar a Central V2.", error);
});
