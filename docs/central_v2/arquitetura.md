# Arquitetura da Central V2

## Fronteiras

```text
central_v2/frontend (rotas, telas, clientes API, módulos compartilhados visuais)
  → central_v2/backend/http_handler.py
  → get_dispatch.py / post_dispatch.py / router de domínio
  → routes/*
  → orchestration/*
  → runtime V2 e/ou domínio explicitamente compartilhado
  → artifacts/manifests da V2
```

V2 possui servidor e dispatchers próprios. Não chama a V1 para executar Texto Off. A presença de imports de `processamento/limpeza_baloes/` é compartilhamento de domínio, não delegação da aplicação.

## Frontend

- `frontend/_app/router/` define rotas e ciclo de tela.
- `frontend/_app/api/` encapsula chamadas por domínio.
- `frontend/texto_off/` contém as áreas da feature.
- `frontend/_shared/` contém componentes reutilizados como zoom, foco, paginação, tabela, progresso e mensagens.

## Backend e API

`backend/http_handler.py` entrega o transporte HTTP e chama dispatchers. `get_dispatch.py` e `post_dispatch.py` selecionam domínios. Rotas Text Off incluem `textoff_merged_router.py`, `textoff_comparison.py`, `bubble_sommelier.py`, `textoff_special.py`, `special_treatments.py`, `catalog.py` e dispatch de Laboratório.

Exemplos de caminhos do router Merged: `/api/textoff/merged/execute`, `/api/textoff/merged/level1/execute`, `level2/execute`, `level3/execute` e rota de especiais por nível. O mapa definitivo está nas tabelas `GET_HANDLERS`/`POST_HANDLERS` do router e nos dispatchers; não inferir uma rota pelos nomes dos módulos.

## Orquestração, runtimes e persistência

`backend/orchestration/` contém fronteiras por domínio e `runtime/` guarda perfis/dependências de workers. `textoff_merged/stages.py` resolve nomes canônicos, aliases legados e regras de leitura/migração; `artifact-migration-registry.json` registra a autoridade de artefatos legados/canônicos. Para inputs e outputs, ver [contratos e persistência](limpeza_baloes/contratos_e_persistencia.md).

## Estados, eventos e falhas

O handler traduz respostas de rota em status HTTP e JSON. Orquestrações executam preflight, registram progressos/resultados e podem separar execução de promoção. Writers são responsáveis pelo staging/rollback local; não há um único gerenciador universal de transação do Texto Off.

## Referências

- [`http_handler.py`](../../central_v2/backend/http_handler.py)
- [`get_dispatch.py`](../../central_v2/backend/routes/get_dispatch.py)
- [`post_dispatch.py`](../../central_v2/backend/routes/post_dispatch.py)
- [Fluxo completo de Limpeza de Balões](limpeza_baloes/fluxo_completo.md)
