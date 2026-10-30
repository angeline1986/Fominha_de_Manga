export function treatmentDisplayText(value) {
  return String(value || "")
    .replaceAll("Patch Balão Estilizado", "Artístico")
    .replaceAll("Gradiente Suave", "Gradiente")
    .replaceAll("Patch Degradê", "Degradê")
    .replaceAll("Estilizado", "Artístico")
    .replaceAll("Suave", "Gradiente");
}
