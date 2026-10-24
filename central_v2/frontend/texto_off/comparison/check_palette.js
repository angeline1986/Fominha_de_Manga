// Cores aprovadas para os indicadores e áreas do Auto-Cleaner Check.
export const CHECK_COLORS = Object.freeze({
  residuo_transparencia: "#0891B2",
  balao_transparente: "#0891B2",
  residuo_degrade: "#DB2777",
  residuo_gradiente: "#7C3AED",
  balao_estilizado: "#FAA307",
  residuo_balao_solido_branco: "#A7C957",
  outro: "#64748B",
});

export function checkColor(type) {
  return CHECK_COLORS[type] || CHECK_COLORS.outro;
}
