# Limpeza de Balões — Central V1

**Objetivo:** descrever a implementação legada e localizar seus fluxos atuais.\
**Manual de reconstrução:** [Central V1](../../reconstrucao/central_v1.md). Os limites abaixo são por subfluxo, não uma ausência geral de especificação.

## Componentes

| Camada | Arquivos e responsabilidades observadas |
|---|---|
| Interface/HTTP | `interface_web/processing_web.py`, `interface_web/textoff_special.js`, `textoff_compare.js`, `textoff_qc_studio.js` |
| Orquestração Merged | `orquestracao/textoff/merged.py`; coordena chamada Cleaner para Texto Off Merged |
| Domínio legado | `processamento/limpeza_baloes/textoff_compare.py`, `textoff_level3.py`, `textoff_level3_analyzer.py`, `textoff_level3_correction.py`, `textoff_special_web.py` |
| Motor Cleaner | `processamento/limpeza_baloes/cleaner_v2/` |
| Tratamentos | `patch_degrade_experimento.py`, `textoff_special_roi.py`, adaptadores de transparente/estilizado/gradiente e variantes legadas |

## Entradas e saídas

A Central recebe contexto da obra/capítulo e seleção do usuário por interface ou ação HTTP. Os domínios resolvem os caminhos em `FLUXO_SECUNDARIO/04_TEXTO_OFF/` e os insumos a partir do estágio indicado. A localização concreta varia com o fluxo (Original, Merged, correção assistida ou Especial); não existe neste inventário um contrato único que cubra todos eles.

O Cleaner de lote recebe imagens, pasta de saída, estágio de origem e callback opcional de progresso; a integração publica diretório de saída e manifesto depois de validar a rodada. O código Merged V1 importa `clean_chapter` do pacote Cleaner V2. Tratamentos especiais produzem resultado intermediário e usam `promote_special_result()` para promoção; regras de promoção diferem por tratamento.

## Algoritmos e parâmetros

Não inferir que o V1 tenha um algoritmo único de limpeza. O fluxo comum de Cleaner executa o motor N1+N2; receitas e parâmetros confirmados estão no [manual de componentes compartilhados](../../reconstrucao/componentes_compartilhados.md) e na [página do Cleaner](../../central_v2/limpeza_baloes/etapas/cleaner_v2.md). Os scripts chamados `experimento` permanecem ativos em alguns caminhos e devem ser tratados conforme chamadas reais, não pelo nome.

O fluxo de Nível III e correção assistida possui filas, análise residual, prévias e propostas em `textoff_level3*.py`; cada contrato de proposta e seu destino precisam ser documentados junto aos escritores antes de reconstrução completa.

## Persistência e integridade

O código contém gravação atômica, SHA-256 e manifestos em caminhos distintos. Não declarar proteção universal: `textoff_special_web.py`, correção assistida e Cleaner têm escritores diferentes. A auditoria de hash deve mapear por escritor e consumidor.

## Referências

- [Pipeline V1](pipeline.md)
- [Algoritmos e parâmetros](algoritmos_e_parametros.md)
- [Matriz V1/V2](../../arquitetura/limpeza_baloes_v1_v2.md)
- Código: `interface_web/processing_web.py`, `orquestracao/textoff/merged.py`, `processamento/limpeza_baloes/`.
