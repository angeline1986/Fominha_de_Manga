# Algoritmos e parâmetros — Limpeza de Balões V1

**Fonte de verdade:** os algoritmos são definidos nos módulos chamados pela V1. Este documento não trata a existência de um script como prova de que toda operação da Central o chama.

## Implementações localizadas

| Código | Papel/chamada verificada | Versão / parâmetros |
|---|---|---|
| `cleaner_v2/integration.py` e pacote adjacente | V1 usa o motor por `orquestracao/textoff/merged.py` e `do_clean*()` | motor Panel Cleaner 2.11.11, perfil `outlined-text.ini`, offline, timeout total 900 s; Nível I/II compartilham algoritmo descrito em [Cleaner V2](../../central_v2/limpeza_baloes/etapas/cleaner_v2.md). |
| `bubble_cleaner.py` | ferramenta de limpeza por região; `bubble_cleaner_flow.py` chama `process_image`; balanceamento importa detecção | detector define `conf=0.55` por padrão. Máscaras e decisão de autorização são próprias deste módulo; não confundir com gate Cleaner Nível I. Thresholds completos requerem especificação campo a campo antes de reimplementação. |
| `patch_degrade_experimento.py` | base de execução chamada pelo menu e adaptadores ROI | código executável em uso por alguns caminhos V1; parâmetros dependem do processo e backend Cleaner/LaMa. Documentar sem o sufixo “experimento” não é motivo para chamá-lo de algoritmo V2. |
| `textoff_special_roi.py` | adapta seleção de ROI ao Degradê e pode aplicar aprovação de ROIs | geometria e autorização residem em helpers; política de promoção depende de `textoff_special_web.py`. Thresholds completos ainda não verificados. |
| `textoff_special_styled_roi.py` / `patch_balao_estilizado_experimento.py` | adapta máscara/seleção para Artístico | dependência direta da base Degradê; parâmetros não foram todos transcritos nesta revisão. |
| `textoff_special_transparent_roi.py` / `patch_balao_transparente_experimento.py` | seleção de tratamento Transparente | chama autorização compartilhada e helpers de transparência; não igualar à variante Legado. |
| `textoff_special_transparent_legacy_roi.py` | variante Transparente Legado | adaptador e ordem própria; não usa necessariamente o mesmo gate de autorização da variante atual. |
| `gradiente_suave/gradiente_suave.py` | executa reconstrução suave via `textoff_special_web.py` | parâmetros de reconstrução devem ser tirados do domínio e do lock local; não confirmados integralmente aqui. |
| `textoff_level3_analyzer.py` + `textoff_level3.py` | análise/agrupamento de resíduos e estado pendente | componente/caixa são gravados para inspeção; análise não limpa pixels. `textoff_level3_correction.py` implementa proposta/prévia/aprovação. |

## Contratos de máscara/ROI

`textoff_special_web.py` resolve fonte permitida, valida seleção e alvo, registra execução com artefatos e hash, e separa processamento de promoção. Cada adapter pode aplicar seleção por interseção da caixa de componente com ROI; conferir adapter específico, pois não se deve inferir máscara comum. `textoff_special_approval.py` concentra aplicação de ROIs aprovadas em casos que o chamam.

## Como concluir os parâmetros sem inferência

Para cada implementação, registrar defaults nomeados, conversões de unidades, limites e ordem de operação diretamente do código; depois ligar cada parâmetro ao campo de relatório/manifest e ao runtime lock. Campos ausentes em evidência antiga devem continuar marcados como não verificados. Os registros atuais do Cleaner Nível I/II estão em [especificação Cleaner](../../central_v2/limpeza_baloes/etapas/cleaner_v2.md).

## Referências V1

- [Visão geral](visao_geral.md)
- [Pipeline](pipeline.md)
- [`processing_web.py`](../../../interface_web/processing_web.py)
- [`textoff_special_web.py`](../../../processamento/limpeza_baloes/textoff_special_web.py)
