export const routes = {
  "auto-merge": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel1.js",
  },
  "auto-merge-2": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel2.js",
  },
  "auto-merge-3": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel3.js",
  },
  "auto-merge-4": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel4.js",
  },
  "auto-merge-5": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel5.js",
  },
  "validar-faixa": {
    context: "processamento",
    module: "/processamento/merge_manual/validar_faixa.js",
  },
  "novos-merges": {
    context: "processamento",
    module: "/processamento/merge_manual/novos_merges.js",
  },
  "merge-manual-result": {
    context: "processamento",
    module: "/processamento/merge_manual/resultado_proposta.js",
  },
  "validar-estado": {
    context: "processamento",
    module: "/processamento/balanceamento/validar_estado.js",
  },
  "novos-cortes": {
    context: "processamento",
    module: "/processamento/balanceamento/novos_cortes.js",
  },
  "resumo-operacao": {
    context: "visao-geral",
    module: "/visao_geral/resumo_operacao.js",
  },
};

export function resolveRoute(action) {
  return routes[action] ?? null;
}
