# Central V2

**Escopo:** aplicação independente em `central_v2/`. A V2 não usa a interface nem o workflow HTTP da V1 para executar limpeza. Ela importa alguns domínios compartilhados de `processamento/limpeza_baloes/`.

## Código

- Frontend: `central_v2/frontend/texto_off/` e módulos compartilhados em `central_v2/frontend/_shared/`.
- Rotas e contratos: `central_v2/backend/routes/`.
- Orquestração: `central_v2/backend/orchestration/textoff_merged/` e `textoff_special/`.
- Runtime isolado: `central_v2/runtime/textoff/` e `central_v2/runtime/bubble_sommelier/`.
- Domínios compartilhados: `processamento/limpeza_baloes/`, importados explicitamente.
- [Arquitetura V2](arquitetura.md): UI, API, rotas, orquestração e runtimes.

## Limpeza de Balões

Comece pelo [índice do fluxo V2](limpeza_baloes/README.md), depois consulte [pipeline](limpeza_baloes/fluxo_completo.md), [contratos e persistência](limpeza_baloes/contratos_e_persistencia.md), [Laboratório](limpeza_baloes/laboratorio.md) e [atalhos](interfaces/atalhos.md).

| Etapa | Backend principal | Frontend principal |
|---|---|---|
| Merge e consultas de etapas | `backend/routes/textoff_merged.py`; `backend/orchestration/textoff_merged/` | `frontend/texto_off/merged/` |
| Sommelier | `backend/routes/bubble_sommelier.py`; `backend/orchestration/bubble_sommelier/`; runtime dedicado | `frontend/texto_off/sommelier/` |
| Auto-Cleaner Check | `backend/orchestration/textoff_merged/auto_cleaner_check*.py`; rotas de tratamento | `frontend/texto_off/check/` |
| Tratamentos especiais | `backend/routes/textoff_special.py`, `special_treatments.py`, `backend/orchestration/textoff_special/` | `frontend/texto_off/especiais/` |
| Laboratório | `backend/routes/laboratorio_*.py` | `frontend/texto_off/laboratorio/` |
| Sólidos | `backend/routes/laboratorio_solidos.py`, estado e domínio | `frontend/texto_off/solidos/` |
| Consolidação final/restauração | `backend/orchestration/textoff_merged/final_consolidated*.py`, `consolidated.py`, `special_page_restore*.py` | consumida pelas etapas e visões V2 |

## Limites

Rotas, estado de navegação e writers de artefatos V2 são próprios. As dependências de domínio comuns estão listadas em [módulos compartilhados](../arquitetura/modulos_compartilhados_limpeza_baloes.md). Não transportar resultados, parâmetros ou garantias de V1 para V2 sem verificar o código e o manifesto específico.

Para reconstrução passo a passo, consulte o [manual Central V2](../reconstrucao/central_v2.md) e o [manual de componentes compartilhados](../reconstrucao/componentes_compartilhados.md). Os inventários detalhados desta pasta continuam como referências por etapa.
