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
    label: "Texto Off",
    defaultAction: "texto-off-merged-i",
    groups: [
      {
        label: "MERGED",
        control: {
          type: "segmented",
          id: "textoff-merged-level",
          label: "Merged",
          defaultValue: "I",
          options: [
            { value: "I", action: "texto-off-merged-i", label: "I" },
            { value: "II", action: "texto-off-merged-ii", label: "II" },
          ],
        },
      },
      {
        label: "OUTROS RESULTADOS",
        items: [
          { id: "texto-off-legacy", label: "Legado" },
        ],
      },
      {
        label: "RESULTADOS & LIMPEZA",
        items: [
          { id: "comparar-resultados", label: "Comparar Resultados" },
          { id: "correcao-assistida", label: "Correção Assistida" },
          { id: "casos-especiais", label: "Casos Especiais" },
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
