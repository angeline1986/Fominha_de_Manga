const iconNames = new Set([
  "visao-geral", "processamento", "balanceamento", "gerar-pdf", "texto-off",
  "exportar-arquivos", "sync", "power", "next", "back", "close",
  "focus-exit", "expand", "collapse", "menu", "ruler", "search", "compare", "highlighter",
  "crop-simple", "scissors", "check", "eye", "comparison",
]);

export function iconMarkup(name) {
  if (!iconNames.has(name)) throw new Error(`Ícone desconhecido: ${name}`);
  return `<span class="ui-icon ui-icon--${name}" aria-hidden="true"></span>`;
}
