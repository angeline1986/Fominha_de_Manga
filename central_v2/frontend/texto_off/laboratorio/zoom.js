/** Geometria compartilhada: 100% representa um pixel CSS por pixel natural. */
export function zoomDimensions(naturalWidth, naturalHeight, percent) {
  const scale = Math.max(30, Math.min(200, Number(percent) || 30)) / 100;
  return {
    scale,
    width: naturalWidth * scale,
    height: naturalHeight * scale,
  };
}
