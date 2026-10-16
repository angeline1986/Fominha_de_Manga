# Pipeline de Limpeza de Balões — Central V1

O mapa de fluxo e contratos completos desta página foi ampliado no [manual de reconstrução V1](../../reconstrucao/central_v1.md). Esta página preserva o inventário por operação e suas incertezas específicas.

## Fluxos localizados

| Fluxo | Entrada de interface/orquestração | Executor/domínio | Situação documental |
|---|---|---|---|
| Texto Off Original | `interface_web/processing_web.py`; chamadas `do_clean()` | `processamento/limpeza_baloes/cleaner_v2/integration.py` | Chamada confirmada; validação/persistência por manifesto precisa de mapa ponta a ponta. |
| Texto Off Merged | `do_clean_merged()` e `orquestracao/textoff/merged.py` | `clean_chapter()` | Chamada e motor confirmados; comportamento de compatibilidade V1 deve ser rastreado na integração atual. |
| Comparação | `/api/textoff-compare` e UI `textoff_compare.js` | `textoff_compare.py` | Estado projetado dos artefatos disponíveis; critérios completos de elegibilidade a documentar. |
| Resíduo / Nível III | `/api/textoff-level3` e ações do handler | `textoff_level3.py`, `textoff_level3_analyzer.py` | Fila, classificação/análise, proposta e aprovação distribuídas em três módulos. |
| Correção assistida | rotas/ações do handler e `textoff_qc_studio.js` | `textoff_level3_correction.py` | Há proposta, prévia e aprovação; revisar schema no escritor e no consumidor. |
| Tratamentos especiais | `/api/textoff-special/*` | `textoff_special_web.py` e adaptadores | Fluxo em duas ações: produzir resultado e promover; as regras variam por tratamento. |

## Fluxo confirmado para uma operação especial

1. A interface seleciona uma imagem ou envia a fonte e uma lista de regiões.
2. `process_special_image(payload, manga_path)` valida/resgata a fonte e executa o adaptador de tratamento.
3. O domínio escreve artefatos temporários/relatório e retorna metadados do processamento.
4. `promote_special_result(payload, manga_path)` revalida o resultado e decide se é permitido publicá-lo no alvo oficial.

O código de `textoff_special_web.py` possui caminhos de promoção que variam conforme tratamento. Não presumir que todo resultado especial possa ser aplicado ou que uma promoção seja idempotente sem revisar seus branches.

## Fluxo Cleaner Merged

```text
Handler V1 / ação do menu
  → orquestracao/textoff/merged.py ou do_clean_merged()
  → clean_chapter(source_images, target, source_stage=...)
  → Panel Cleaner offline + autorização/nível adicional da integração
  → validar resultado de capítulo
  → publicar saída e manifesto
```

Timeout, runtime, manifest e rollback estão descritos em [Cleaner compartilhado](../../central_v2/limpeza_baloes/etapas/cleaner_v2.md), que separa o algoritmo do workflow de chamada da V1.

## Lacunas de reconstrução

- Matriz endpoint → ação/job → função → artefatos está documentada para as rotas TextOff principais no manual; o inventário de payloads de todas as ações e endpoints gerais ainda não está completo.
- Schemas legados e aceitação de formatos antigos precisam ser confirmados por amostras de manifestos e parsers atuais.
- Os algoritmos especiais possuem variantes e arquivos históricos; só imports ativos definem o uso vigente.
