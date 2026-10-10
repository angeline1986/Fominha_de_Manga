import { createPdfView } from "/gerar_pdf/view.js";
export function render(container) { return createPdfView(container, "original"); }
