/** Derive a visible final-page identity for a selected Glass clean image. */
export function finalPageSelection(selection) {
  const { source, path, chapter, page } = selection;
  if (source !== "file" || typeof path !== "string" || chapter !== "clean"
      || typeof page !== "string" || !page.endsWith("_clean.png")) {
    return { chapter, page };
  }
  const parts = path.split("/");
  if (parts.length !== 7 || parts[0] !== "FLUXO_SECUNDARIO"
      || parts[1] !== "04_TEXTO_OFF" || parts[2] !== "05_AUTO_CLEANER_TRANSPARENCIA"
      || !["BASICA", "NORMAL", "LEGADA"].includes(parts[3])
      || !parts[4] || parts[5] !== "clean" || parts[6] !== page) {
    return { chapter, page };
  }
  return { chapter: parts[4], page: `${page.slice(0, -10)}.png` };
}
