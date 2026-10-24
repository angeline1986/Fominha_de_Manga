/** Side-by-side Laboratory review with no publication control. */
export function createFinalReviewView() {
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "/texto_off/laboratorio/final_review.css";
  document.head.append(stylesheet);
  const dialog = document.createElement("dialog");
  dialog.className = "lab-final-review";
  dialog.setAttribute("aria-labelledby", "lab-final-review-title");
  dialog.innerHTML = `
    <header class="lab-final-review-head">
      <div><h2 id="lab-final-review-title">Comparar com Consolidado Final</h2>
        <p data-lab-review-page></p></div>
      <button type="button" class="lab-final-review-close btn" data-lab-review-close aria-label="Fechar comparação">Fechar</button>
    </header>
    <p class="lab-final-review-status" data-lab-review-status role="status" aria-live="polite"></p>
    <div class="lab-final-review-grid">
      <figure><figcaption>CONSOLIDADO FINAL ATUAL</figcaption><img data-lab-review-current alt="Imagem atual no Consolidado Final"></figure>
      <figure><figcaption>RESULTADO DO LABORATÓRIO</figcaption><img data-lab-review-candidate alt="Resultado experimental selecionado"></figure>
    </div>
    <footer class="lab-final-review-actions">
      <button type="button" class="lab-final-review-cancel btn" data-lab-review-cancel>Voltar</button>
      <button type="button" class="lab-final-review-select btn" data-lab-review-select disabled>Selecionar este resultado</button>
    </footer>`;
  document.body.append(dialog);
  return {
    dialog,
    page: dialog.querySelector("[data-lab-review-page]"),
    status: dialog.querySelector("[data-lab-review-status]"),
    current: dialog.querySelector("[data-lab-review-current]"),
    candidate: dialog.querySelector("[data-lab-review-candidate]"),
    select: dialog.querySelector("[data-lab-review-select]"),
    close: dialog.querySelector("[data-lab-review-close]"),
    cancel: dialog.querySelector("[data-lab-review-cancel]"),
    dispose() { if (dialog.open) dialog.close(); dialog.remove(); stylesheet.remove(); },
  };
}
