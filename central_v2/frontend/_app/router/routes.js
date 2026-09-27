export const routes = {
  "auto-merge": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel1.js",
  },
  "resumo-operacao": {
    context: "visao-geral",
    module: "/visao_geral/resumo_operacao.js",
  },
};

export function resolveRoute(action) {
  return routes[action] ?? null;
}
