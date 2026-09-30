import { iconMarkup } from "/_shared/icons/icons.js";
import { mountContext } from "/_shell/context.js";
import { createDrillNavigation } from "/_shell/drill_navigation.js";
import { bindShutdown } from "/_shell/shutdown.js";

export function mountShell(root, onStopped) {
  root.innerHTML = `
    <div class="app-shell">
      <div class="app-body">
        <aside
          class="app-sidebar"
          id="app-sidebar"
          aria-label="Navegação principal"
        >
          <div class="app-sidebar-brand">
            <button class="sidebar-toggle" type="button" aria-label="Recolher menu" aria-expanded="true">
              ${iconMarkup("menu")}
            </button>
            <div class="sidebar-brand-copy">
              <strong>Fominha de Mangá</strong>
              <span>Central de Processamento</span>
            </div>
          </div>

          <div id="app-navigation"></div>
          <div id="app-context"></div>

          <div class="app-sidebar-actions" aria-label="Ações da Central">
            <button type="button" class="sidebar-action" data-action="sync" aria-label="Sincronizar" title="Sincronizar">
              ${iconMarkup("sync")}
            </button>

            <button type="button" class="sidebar-action sidebar-action-danger" data-action="stop-server" aria-label="Finalizar servidor" title="Finalizar servidor">
              ${iconMarkup("power")}
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
  const sidebar = root.querySelector("#app-sidebar");
  const toggle = root.querySelector(".sidebar-toggle");
  function toggleSidebar() {
    const collapsed = sidebar.classList.toggle("is-collapsed");
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.setAttribute("aria-label", collapsed ? "Expandir menu" : "Recolher menu");
  }
  toggle.addEventListener("click", toggleSidebar);
  const disposeContext = mountContext(root.querySelector("#app-context"));
  const disposeShutdown = bindShutdown(
    root.querySelector('[data-action="stop-server"]'),
    onStopped,
  );
  const drillNavigation = createDrillNavigation();
  navigation.append(drillNavigation.element);
  const context = root.querySelector("#app-context");
  const showContextOnMenu = (event) => {
    context.hidden = event.type === "menu:detail-open";
  };
  navigation.addEventListener("menu:detail-open", showContextOnMenu);
  navigation.addEventListener("menu:detail-close", showContextOnMenu);

  return () => {
    navigation.removeEventListener("menu:detail-open", showContextOnMenu);
    navigation.removeEventListener("menu:detail-close", showContextOnMenu);
    toggle.removeEventListener("click", toggleSidebar);
    drillNavigation.dispose();
    disposeContext();
    disposeShutdown();
  };
}
