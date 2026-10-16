# Limpeza de Balões: limites entre Central V1 e Central V2

**Escopo:** arquitetura de software e processamento de Limpeza de Balões.\
**Fonte de verdade:** código presente na branch `develop`; inventário verificado em 2026-10-16.\
**Referência da mudança recente de atalhos:** commit `cef3cd42` (`cef3cd4227012f3ef9410587103eda6a8448e870`).

## Objetivo

Localizar as implementações por versão e evitar atribuir um fluxo à V2 só porque ambas as interfaces usam nomes como Texto Off ou Laboratório.

## Matriz de rastreabilidade

| Item | Central V1 | Central V2 | Módulo de domínio / observação |
|---|---|---|---|
| Interface e transporte | `interface_web/`; handler principal em `interface_web/processing_web.py` | `central_v2/frontend/`; rotas/adaptadores em `central_v2/backend/routes/` | Não compartilhados. |
| Orquestração de Texto Off | ações e jobs em `interface_web/processing_web.py`; helpers em `orquestracao/textoff/merged.py` | `central_v2/backend/orchestration/textoff_merged/` e `textoff_special/` | V2 tem jobs, rotas e persistência próprios. |
| Cleaner de lote | `orquestracao/textoff/merged.py` chama `processamento/limpeza_baloes/cleaner_v2/integration.py` | `central_v2/backend/orchestration/textoff_merged/cleaner.py` delega a `cleaner_v2.integration` | Integração e motor são compartilhados. |
| Autorização de balões transparentes | imports em processos especiais e integração do Cleaner V2 | `level1_worker.py` e `transparency_artifacts.py` importam `cleaner_v2.balloon_authorization` | Política comum; uso e publicação dos resultados diferem por fluxo. |
| Tratamentos especiais | interface `interface_web/textoff_special.js`; domínio `processamento/limpeza_baloes/textoff_special_web.py` e adaptadores | frontend e rotas V2 dedicados; domínio V2 adapta/importa algoritmos em `processamento/limpeza_baloes/` | Algoritmos específicos têm adaptações. Ver [módulos compartilhados](modulos_compartilhados_limpeza_baloes.md). |
| Laboratório | UI e ações sob `interface_web/`; confirmar subfluxos em `processing_web.py` | `central_v2/frontend/texto_off/laboratorio/` e `central_v2/backend/routes/laboratorio_*.py` | UIs e contratos HTTP não são intercambiáveis. |
| Sommelier | não identificado como recurso ativo V1 no código revisado | `central_v2/runtime/bubble_sommelier/`, backend `bubble_sommelier/`, frontend `texto_off/sommelier/` | V2 exclusiva. |
| Manifestos e persistência | `processing_web.py`, `textoff_special_web.py`, `textoff_level3*` e pastas `FLUXO_SECUNDARIO/04_TEXTO_OFF/` | `central_v2/backend/orchestration/textoff_merged/` e `textoff_special/` | Schemas, autoridade e layout não são presumidos iguais. |
| Consolidação final | **Não verificado** como contrato V1 único; há diversos diretórios e manifestos legados | `final_consolidated.py`, `final_consolidated_manifest.py`, `consolidated.py` | Comparar cada contrato antes de afirmar equivalência. |
| Restauração | helpers e estado em módulos V1; mapa completo pendente | `special_page_restore*.py` controla proposta, validação, backup e restauração de página | A implementação V2 é própria; não generalizar para toda restauração. |
| Atalhos do Laboratório | depende da tela e do handler ativos; **não verificado** para cobertura equivalente | `workspace_controls.js` trata Esc/F; `page_navigation.js` trata setas | Commit de referência `cef3cd42`; os limites são detalhados em `central_v2/interfaces/atalhos.md`. |

## Fluxos em alto nível

### V1

```text
Central legada (interface_web)
  → handler/jobs em processing_web.py
  → orquestração raiz (orquestracao/textoff)
  → módulos de domínio em processamento/limpeza_baloes
  → pastas/manifestos da obra
```

### V2

```text
Central V2 frontend
  → API e estado próprios
  → rotas em central_v2/backend/routes
  → orquestração/domínio V2
  → módulos de domínio compartilhados quando importados explicitamente
  → artefatos e manifestos do fluxo V2
```

Esses desenhos identificam fronteiras, não cada ação nem todos os estados de falha. Os detalhes verificados estão nas páginas de cada versão.

## Lacunas registradas

- A matriz de parâmetros em nível de cada estágio ainda precisa ser concluída comparando os manifests, defaults do código e perfis de runtime.
- Não foi demonstrado que schemas ou resultados V1 e V2 sejam equivalentes byte a byte.
- A cobertura de atalhos da V1 permanece não verificada; não se atribuem a ela as garantias da V2.
- Os módulos V1 de merge e limpeza variam entre fluxos, e a documentação histórica contém propostas de migração que não descrevem necessariamente o comportamento atual.

## Referências

- [Central V1](../central_v1/README.md)
- [Central V2](../central_v2/README.md)
- [Módulos compartilhados](modulos_compartilhados_limpeza_baloes.md)
- [Código V1](../../interface_web/processing_web.py)
- [Código V2](../../central_v2/backend/routes/textoff_merged.py)
