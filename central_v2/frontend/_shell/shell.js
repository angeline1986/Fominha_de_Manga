import { createDrillNavigation } from "/_shell/drill_navigation.js";

export function mountShell(root) {
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
        </aside>

        <main class="app-content" id="page-content" tabindex="-1">
          <h1>Central V2</h1>
          <p>Estrutura inicial da nova Central de Processamento.</p>
        </main>
      </div>
    </div>
  `;

  const navigation = root.querySelector("#app-navigation");
  navigation.append(createDrillNavigation());
}
