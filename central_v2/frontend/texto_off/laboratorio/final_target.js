/** Derive the final-page identity for known TextOff file layouts. */
export function finalPageSelection(selection) {
  const { source, path, chapter, page } = selection;
  if (source === "glass" && typeof page === "string" && page.endsWith("_clean.png")) {
    return { chapter, page: `${page.slice(0, -10)}.png` };
  }
  if (source !== "file" || typeof path !== "string" || typeof page !== "string") {
    return { chapter, page };
  }
  const parts = path.split("/");
  if (parts[0] !== "FLUXO_SECUNDARIO" || parts[1] !== "04_TEXTO_OFF") {
    return { chapter, page };
  }
  if (parts.length === 6 && parts[2] === "04_AUTO_CLEANER_CHECK"
      && parts[3] && parts[4] === "images" && parts[5] === page
      && chapter === "images") return { chapter: parts[3], page };
  if (parts.length === 7 && parts[2] === "05_AUTO_CLEANER_TRANSPARENCIA"
      && ["BASICA", "NORMAL", "LEGADA"].includes(parts[3])
      && parts[4] && parts[5] === "clean" && parts[6] === page
      && chapter === "clean" && page.endsWith("_clean.png")) {
    return { chapter: parts[4], page: `${page.slice(0, -10)}.png` };
  }
  return { chapter, page };
}
