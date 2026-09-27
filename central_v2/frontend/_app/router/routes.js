export const routes = {
  "resumo-operacao": {
    context: "visao-geral",
    module: "/visao_geral/resumo_operacao.js",
  },
};

export function resolveRoute(action) {
  return routes[action] ?? null;
}
