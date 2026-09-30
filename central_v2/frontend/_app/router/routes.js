export const routes = {
  "auto-merge": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel1/index.js",
  },
  "auto-merge-2": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel2/index.js",
  },
  "auto-merge-3": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel3/index.js",
  },
  "auto-merge-4": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel4/index.js",
  },
  "auto-merge-5": {
    context: "processamento",
    module: "/processamento/auto_merge/nivel5/index.js",
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
  "texto-off-merged-i": {
    context: "texto-off",
    module: "/texto_off/merged/level1.js",
  },
  "texto-off-merged-ii": {
    context: "texto-off",
    module: "/texto_off/merged/level2.js",
  },
  "texto-off-merged-iii": {
    context: "texto-off",
    module: "/texto_off/merged/level3.js",
  },
  "texto-off-merged-iv": {
    context: "texto-off",
    module: "/texto_off/merged/level4.js",
  },
  "texto-off-merged-v": {
    context: "texto-off",
    module: "/texto_off/merged/level5.js",
  },
  "texto-off-legacy": {
    context: "texto-off",
    module: "/texto_off/merged/index.js",
  },
  "texto-off-especiais-vi": {
    context: "texto-off",
    module: "/texto_off/especiais/level6.js",
  },
  "texto-off-especiais-vii": {
    context: "texto-off",
    module: "/texto_off/especiais/level7.js",
  },
  "texto-off-especiais-viii": {
    context: "texto-off",
    module: "/texto_off/especiais/level8.js",
  },
  "resumo-operacao": {
    context: "visao-geral",
    module: "/visao_geral/resumo_operacao.js",
  },
};

export function resolveRoute(action) {
  return routes[action] ?? null;
}
