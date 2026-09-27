// SVG próprios da V2: geometria fixa, cor herdada do componente consumidor.
const paths = Object.freeze({
  'visao-geral': 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
  processamento: 'M4 6h16 M4 12h16 M4 18h10',
  balanceamento: 'M12 3v18 M7 21h10 M4 7h16 M6 7l-4 9h8z M18 7l-4 9h8z',
  'gerar-pdf': 'M6 3h8l4 4v14H6z M14 3v5h4',
  'texto-off': 'M4 6h16 M4 12h12 M4 18h8',
  'exportar-arquivos': 'M12 3v12 M8 11l4 4 4-4 M5 20h14',
  sync: 'M20 8a8 8 0 0 0-13-3L4 8 M4 3v5h5 M4 16a8 8 0 0 0 13 3l3-3 M15 16h5v5',
  power: 'M12 2v10 M6 5a9 9 0 1 0 12 0',
  next: 'M9 5l7 7-7 7',
  back: 'M15 5l-7 7 7 7',
  close: 'M6 6l12 12 M18 6 6 18',
  menu: 'M4 6h16 M4 12h16 M4 18h16',
});

export function iconMarkup(name) {
  const path = paths[name];
  if (!path) throw new Error(`Ícone desconhecido: ${name}`);
  return `<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${path}"/></svg>`;
}
