import { resolveRoute } from "/_app/router/routes.js";

const pages = new WeakMap();

function lifecycle(container) {
  if (!pages.has(container)) {
    pages.set(container, { revision: 0, cleanup: null });
  }
  return pages.get(container);
}

export function disposePage(container) {
  const page = lifecycle(container);
  page.revision += 1;
  const cleanup = page.cleanup;
  page.cleanup = null;
  cleanup?.();
}

export async function navigate(action, container) {
  const route = resolveRoute(action);

  if (!route) {
    throw new Error(`Rota não encontrada: ${action}`);
  }

  const page = lifecycle(container);
  const revision = ++page.revision;
  const pageModule = await import(route.module);

  if (revision !== page.revision) return;

  if (typeof pageModule.render !== "function") {
    throw new Error(
      `Página da rota ${action} não exporta render().`,
    );
  }

  disposePage(container);
  const cleanup = pageModule.render(container);
  page.cleanup = typeof cleanup === "function" ? cleanup : null;
}
