# ADR-001 — Origem das imagens Texto Off na exportação

**Data:** 2026-10-25
**Status:** Aceito
**Ticket:** [BL-04](../../gestao/tickets/central_v2/BL-04.md)

## Contexto

A saída `04_TEXTO_OFF/MERGED` pode ser anterior às correções publicadas no Consolidado Final. O identificador interno `textoff_merged` e o rótulo antigo da interface sugeriam, incorretamente, que a exportação lia essa pasta.

## Decisão

O conteúdo **Texto Off — Consolidado Final** usa exclusivamente os PNGs de `<obra>/FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL/<capítulo>/`. Eles são copiados para `raws_semi-clean/<capítulo>/` no destino escolhido. `textoff_merged` permanece apenas como chave interna do contrato da API; a interface mostra a origem física retornada pelo exportador. PDFs continuam tendo origem própria em `03_PDF_MERGE`.

## Evidências

- [`exportador.py`](../../../processamento/exportacao/exportador.py) define `07_CONSOLIDADO_FINAL` como origem e limita a seleção a PNGs diretamente nas pastas de capítulo. A simulação calcula SHA-256; a execução recalcula e rejeita mudanças desde a simulação.
- [`test_exportacao.py`](../../../dev/tests/test_exportacao.py) usa imagens diferentes em `textoff_merged/`, `04_TEXTO_OFF/MERGED/` e `07_CONSOLIDADO_FINAL/` e confirma que os bytes copiados vêm do último caminho.
- Em `comix/Gazing at you_v2`, a leitura de 65 `final-manifest.json` pelo validador do Consolidado Final conferiu SHA-256 de 1.220 páginas: nenhuma falha e nenhuma diferença entre as páginas do manifesto e os PNGs elegíveis.
- Uma simulação somente leitura para `1/page-001-009.png` registrou como origem o PNG em `07_CONSOLIDADO_FINAL/1/`.

## Limite da decisão

A conferência completa dos manifestos acima documenta o estado dessa obra na data indicada. O exportador protege a consistência entre simulação e cópia por hash, mas não relê `final-manifest.json` em cada exportação.
