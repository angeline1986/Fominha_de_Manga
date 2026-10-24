# Limpeza de Balões — Central V2

**Fonte de verdade:** implementação `central_v2/`; domínios comuns explicitados na matriz de imports.\
**Status:** inventário por etapa. Para a visão executável de ponta a ponta e parâmetros rastreados, consulte os [manuais de reconstrução V2](../../reconstrucao/central_v2.md) e de [componentes compartilhados](../../reconstrucao/componentes_compartilhados.md). Permanecem explícitas as lacunas específicas listadas nesses manuais.

## Fluxo e etapas

- [Fluxo completo](fluxo_completo.md): ordem, precondições e fronteiras das etapas.
- [Contratos, artefatos e persistência](contratos_e_persistencia.md): caminhos, vínculos e mecanismos verificados.
- [Laboratório](laboratorio.md): arquitetura, ferramentas, navegação, seleção e foco.
- [Funcionalidades fora do sidebar](funcionalidades_fora_sidebar.md): registro do Combo Turbo e do Texto Off Legado; código preservado.
- [Cleaner V2](etapas/cleaner_v2.md): motor, integrações, parâmetros confirmados e manifest.
- [Bubble Sommelier](etapas/bubble_sommelier.md): detecção e candidato.
- [Auto-Cleaner Check](etapas/auto_cleaner_check.md): propostas e decisões persistidas.
- [Sólidos](etapas/solidos.md): execução baseada em decisões aprovadas.
- [Tratamentos especiais](etapas/tratamentos_especiais.md): adapters, revisão e promoção.
- [Consolidação e restauração](etapas/consolidacao.md): manifests intermediários/finais e restore.
- [Algoritmos especiais compartilhados](../../arquitetura/algoritmos_especiais_compartilhados.md): parâmetros dos adapters que V2 importa.
- [Atalhos de teclado](../interfaces/atalhos.md): cobertura e restrições confirmadas no código.

## Matriz de rastreabilidade V2

| Etapa | API/backend | Motor/algoritmo | Entrada/saída e persistência |
|---|---|---|---|
| Merge / visão por estágios | `routes/textoff_merged.py`, `orchestration/textoff_merged/query.py` e `overview.py` | níveis de composição e consulta são domínios V2; não confundir com V1 Auto-Merge | consome fontes/manifestos reconhecidos pelo resolvedor V2; etapas de merge estão fora do detalhamento algorítmico deste pacote documental. |
| Sommelier | `routes/bubble_sommelier.py`, `orchestration/bubble_sommelier/` | runtime Node em `central_v2/runtime/bubble_sommelier/` | artefatos de análise e revisão no fluxo V2; schema de cada relatório está pendente de página dedicada. |
| Auto-Cleaner I / Texto Off | `orchestration/textoff_merged/level1_worker.py`, `cleaner.py`, `level1_cleaner.py` | Panel Cleaner + gate compartilhado | `TO_MERGED_NIVEL_I/<capítulo>/` com `clean/`, `mask/`, `json/`; integração lê e valida artefatos e manifest. |
| Auto-Cleaner II | `level2.py`, `level2_process.py`, `level2_validation.py`, compartilhado `cleaner_v2/level2.py` | refinamento de máscara/LaMa local | saída Nível II e manifest com fontes, páginas e resultado por página. |
| Consolidado I/II | `consolidated.py` | seleção de artefato por página a partir das etapas válidas | `TO_MERGED_CONSOLIDADO/<capítulo>/json/clean-manifest.json`; referências e hashes ligam fontes/etapas. |
| Auto-Cleaner Check | `auto_cleaner_check*.py`, rota dedicada | extração, geometria e consulta de resultados | manifest de diagnóstico; precisa de dados e fontes atuais para aceitar resposta. |
| Solids | `routes/solid_stage.py`, `orchestration/textoff_merged/solid_stage.py` | análise/curadoria de sólidos | etapa própria e fontes de comparação validadas; o detalhe do algoritmo é pendente. |
| Especiais | `textoff_special/` e `textoff_merged/special_*` | adapters V2 para tratamentos em `processamento/limpeza_baloes/` | propostas, autoria/revisão e manifest próprios; variam por tratamento. |
| Consolidado final | `final_consolidated.py`, `final_consolidated_manifest.py` | composição de resultados em diretório final | `final-manifest.json`, schema `textoff_consolidado_final_manifest_v1`; valida SHA-256 em leitura. |
| Restauração de página | `special_page_restore*.py` | inspeção/proposta/validação/backup/promoção V2 | compara hashes de página/manifests e invalida execuções afetadas; restaura uma página após revalidar. |

Não considerar nomes de estágio como especificação de imagem ou algoritmo: verificar os manifests e writers usados pela operação corrente.
