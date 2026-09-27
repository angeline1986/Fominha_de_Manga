import {
  changeManga,
  changeProvider,
} from "/_app/context/context_controller.js";
import { createContextSelector } from "/_shell/context_selector.js";
import { createDrillNavigation } from "/_shell/drill_navigation.js";

export function mountShell(root, context) {
  root.innerHTML = `
    <div class="app-shell">
      <div class="app-body">
        <aside
          class="app-sidebar"
          id="app-sidebar"
          aria-label="Navegação principal"
        >
          <div class="app-sidebar-brand">
            <strong>Fominha de Mangá</strong>
            <span>Central de Processamento</span>
          </div>

          <div id="app-navigation"></div>
          <div id="app-context"></div>

          <div class="app-sidebar-actions" aria-label="Ações da Central">
            <button type="button" class="sidebar-action" data-action="sync">
              <span aria-hidden="true">↻</span>
              <span>Sincronizar</span>
            </button>

            <button type="button" class="sidebar-action sidebar-action-danger" data-action="stop-server">
              <span aria-hidden="true">⏻</span>
              <span>Finalizar servidor</span>
            </button>
          </div>
        </aside>

        <main class="app-content" id="page-content" tabindex="-1">
          <h1>Central V2</h1>
          <p>Estrutura inicial da nova Central de Processamento.</p>
        </main>
      </div>
    </div>
  `;

  const navigation = root.querySelector("#app-navigation");
  const contextRoot = root.querySelector("#app-context");

  navigation.append(createDrillNavigation());

  function renderContext(currentContext) {
    contextRoot.replaceChildren(
      createContextSelector(currentContext, {
        onProviderChange(provider) {
          const nextContext = changeProvider(provider);
          renderContext(nextContext);
        },

        async onMangaChange(manga) {
          try {
            const { context: nextContext } =
              await changeManga(manga);

            renderContext(nextContext);
          } catch (error) {
            console.error(
              "[Central V2] Falha ao carregar estado da obra.",
              error,
            );
          }
        },
      }),
    );
  }

  renderContext(context);
}
