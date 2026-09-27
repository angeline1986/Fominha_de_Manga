import { resolveRoute } from "/_app/router/routes.js";

export async function navigate(action, container) {
  const route = resolveRoute(action);

  if (!route) {
    throw new Error(`Rota não encontrada: ${action}`);
  }

  const pageModule = await import(route.module);

  if (typeof pageModule.render !== "function") {
    throw new Error(
      `Página da rota ${action} não exporta render().`,
    );
  }

  pageModule.render(container);
}
