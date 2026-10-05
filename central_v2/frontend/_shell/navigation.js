export const navigation = [
  {
    id: "visao-geral",
    label: "Visão Geral",
    groups: [
      {
        label: "NAVEGAÇÃO",
        items: [
          { id: "resumo-operacao", label: "Resumo da Operação" },
        ],
      },
      {
        label: "VALIDAÇÃO",
        items: [
          { id: "validar-imagens", label: "Validar Imagens" },
        ],
      },
    ],
  },
  {
    id: "processamento",
    label: "Processamento",
    groups: [
      {
        label: "AUTO MERGE",
        control: {
          type: "segmented",
          id: "auto-merge-level",
          label: "Auto Merge",
          defaultValue: "I",
          options: [
            { value: "I", action: "auto-merge", label: "I" },
            { value: "II", action: "auto-merge-2", label: "II" },
            { value: "III", action: "auto-merge-3", label: "III" },
            { value: "IV", action: "auto-merge-4", label: "IV" },
            { value: "V", action: "auto-merge-5", label: "V" },
          ],
        },
      },
      {
        label: "MERGE MANUAL",
        linear: true,
        items: [
          { id: "validar-faixa", label: "Validar Faixa" },
          { id: "novos-merges", label: "Novos Merges" },
        ],
      },
    ],
  },
  {
    id: "balanceamento",
    label: "Balanceamento",
    defaultAction: "validar-estado",
    groups: [
      {
        label: "VALIDAÇÃO",
        items: [
          { id: "validar-estado", label: "Validar Estado" },
        ],
      },
      {
        label: "AJUSTES",
        items: [
          { id: "novos-cortes", label: "Novos Cortes" },
        ],
      },
    ],
  },
  {
    id: "gerar-pdf",
    label: "Gerar PDF",
    groups: [
      {
        label: "ORIGEM DE GERAÇÃO",
        items: [
          { id: "pdf-originais", label: "Imagens Originais" },
          { id: "pdf-mescladas", label: "Imagens Mescladas" },
        ],
      },
    ],
  },
  {
    id: "texto-off",
    label: "Limpeza de Balões",
    defaultAction: "texto-off-merged-i",
    groups: [
      {
        label: "BUBBLE SOMMELIER",
        items: [
          { id: "bubble-sommelier", label: "Curadoria de balões", title: "Pré-análise antes da limpeza", variant: "sommelier", arrow: true },
        ],
      },
      {
        label: "AUTO-CLEANER",
        control: {
          type: "segmented",
          id: "textoff-auto-cleaner",
          label: "Auto-Cleaner",
          defaultValue: "1",
          badgeFormat: "PASSO {value}/4",
          plainLabels: true,
          hideCaption: true,
          options: [
            { value: "1", action: "texto-off-merged-i", label: "1", caption: "Balões sólidos (padrão)" },
            { value: "2", action: "texto-off-merged-ii", label: "2", caption: "Balões transparentes" },
            { value: "3", action: "texto-off-merged-iv", label: "3", caption: "Transparência normal" },
            { value: "4", action: "texto-off-merged-v", label: "4", caption: "Transparência legada" },
          ],
        },
      },
      {
        label: "PINCEL & RETOQUES DE ARTE",
        control: {
          type: "segmented",
          id: "textoff-brush",
          label: "Pincel & Retoques de Arte",
          defaultValue: "mapear",
          showBadge: false,
          options: [
            { value: "mapear", action: "texto-off-merged-iii", label: "Mapear", caption: "Localizar balões especiais" },
            { value: "degrade", action: "texto-off-especiais-vi", label: "Degradê", caption: "Preenchimento em degradê", title: "Patch Degradê",
              preview: { before: "/texto_off/especiais/assets/degrade_antes.png", after: "/texto_off/especiais/assets/degrade_depois.png" } },
            { value: "artistico", action: "texto-off-especiais-vii", label: "Artístico", caption: "Balões ilustrados / arte", title: "Patch Balão Estilizado",
              preview: { before: "/texto_off/especiais/assets/estilizado_antes.png", after: "/texto_off/especiais/assets/estilizado_depois.png" } },
            { value: "suave", action: "texto-off-especiais-viii", label: "Suave", caption: "Suavização de gradiente", title: "Gradiente Suave",
              preview: { before: "/texto_off/especiais/assets/gradiente_suave_antes.png", after: "/texto_off/especiais/assets/gradiente_suave_depois.png" } },
          ],
        },
      },
      {
        label: "AUDITORIA DE QUALIDADE",
        items: [
          { id: "texto-off-quality-audit", label: "Antes & Depois", variant: "primary", icon: "compare" },
          { id: "correcao-assistida", label: "Correção Assistida", variant: "secondary", icon: "highlighter" },
        ],
      },
      {
        label: "",
        items: [
          { id: "texto-off-legacy", label: "Texto Off Legado", variant: "muted", icon: "sync" },
        ],
      },
    ],
  },
  {
    id: "exportar-arquivos",
    label: "Exportar Arquivos",
    groups: [
      {
        label: "EXECUÇÃO",
        items: [
          { id: "simular-exportar", label: "Simular e Exportar" },
          { id: "destino-local", label: "Destino Local" },
        ],
      },
    ],
  },
];
