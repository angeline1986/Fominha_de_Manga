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
        label: "FLUXO DE LIMPEZA",
        type: "timeline",
        items: [
          { number: "01", id: "texto-off-merged-i", label: "Auto-Cleaner", icon: "sparkles",
            tooltip: "Passo 1 — Limpeza inicial" },
          { number: "02", id: "texto-off-merged-iii", label: "Mapear", icon: "diamond",
            tooltip: "Localizar balões especiais" },
          { number: "03", id: "bubble-sommelier", label: "Bubble Sommelier", icon: "circle-dot",
            tooltip: "Curadoria de balões" },
          { number: "04", id: "auto-cleaner-check", label: "Auto-Cleaner Check", icon: "compare",
            tooltip: "Revisar e aprovar áreas identificadas" },
        ],
        control: {
          type: "timeline-segmented",
          id: "textoff-transparency",
          label: "Auto-Cleaner: Transparência",
          defaultValue: "normal",
          icon: "sparkles",
          tooltip: "Tratamento de balões translúcidos",
          showBadge: false,
          hideCaption: true,
          number: "05",
          options: [
            { value: "basic", action: "texto-off-merged-ii", label: "Básica",
              tooltip: "Passo 2 — Transparência Básica" },
            { value: "normal", action: "texto-off-merged-iv", label: "Normal",
              tooltip: "Passo 3 — Transparência Normal" },
            { value: "legacy", action: "texto-off-merged-v", label: "Legada",
              tooltip: "Passo 4 — Transparência Legada" },
          ],
        },
      },
      {
        label: "PINCEL & RETOQUES DE ARTE",
        control: {
          type: "segmented",
          id: "textoff-brush",
          label: "Pincel & Retoques de Arte",
          defaultValue: "degrade",
          showBadge: false,
          hideCaption: true,
          options: [
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
        label: "LEGADO",
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
