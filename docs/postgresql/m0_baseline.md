# M0 — Baseline e preservação do estado

**Data da inspeção:** 2026-10-23
**Branch:** `develop`
**HEAD:** `dc4975f775d08ddec207471d2adb1ef3ed7440a7` (`chore: checkpoint pending workspace changes`)
**Remoto configurado:** `origin` → `https://github.com/angeline1986/Fominha_de_Manga.git`
**Escopo:** diagnóstico somente de leitura; nenhum tratamento, teste, migration ou alteração funcional foi executado.

## Estado inicial do Git

O worktree estava `develop...origin/develop` (metadados locais; não foi feito fetch) com as alterações preexistentes abaixo:

| Estado | Caminho |
|---|---|
| modificado | `central_v2/frontend/_shell/navigation.js` |
| modificado | `dev/tests/central_v2_frontend/navigation_textoff.test.mjs` |
| modificado | `dev/tests/central_v2_frontend/textoff_merged.test.mjs` |
| modificado | `docs/central_v2/limpeza_baloes/README.md` |
| submódulo modificado | `download/mangago_downloader` |
| não rastreado | `docs/central_v2/limpeza_baloes/funcionalidades_fora_sidebar.md` |

Estado interno inicial do submódulo: `main`, commit `f1f2da0c6e1802362026c5cc79f7c0a1a526d7ec`, rastreando `origin/main`; alterações locais em `.gitignore` e `README.md`, diretório não rastreado `.venv-test/` e dois patches não rastreados (`lezhin_blob_capture_revisao.patch`, `lezhin_iniciar_browser_revisao.patch`). Nada foi alterado ou normalizado.

## Arquivos ignorados relevantes observados

O `git status --short --ignored` revelou, entre outros:

- Backups: `.bl13_local_backups/`, `.check_paginas_header_backup/`, `.check_v3_patch_backup/`, `.cleaner_pipeline_backups/`, `.sidebar_check_*_backup/`.
- Backups pontuais `.bak` em `central_v2/backend/` e `central_v2/frontend/`, além de cópias `.before_*` em `processamento/limpeza_baloes/`.
- Configuração local ignorada `gui_config.json`; seu conteúdo não foi lido.
- Ambientes virtuais, `node_modules`, modelos locais do Sommelier, caches, `reports/`, `dev/artifacts/`, `dev/archive/` e snapshots `.zip` ignorados.

São estado local preexistente e não foram usados como destino dos relatórios. A lista completa estava visível no status ignorado da inspeção; nenhum desses itens foi apagado, aberto ou movido.

## Configuração e raiz operacional

`config/data_paths.py` define `FOMINHA_DATA_ROOT` como override e, sem override, usa `~/Documents/FominhaData`; `OUTPUT_ROOT` é `DATA_ROOT/output`. A raiz padrão existe e contém cinco árvores `04_TEXTO_OFF`. O inventário medido está sob o caminho relativo `output/<provider>/<obra>/FLUXO_SECUNDARIO/04_TEXTO_OFF/`. O tamanho reportado pelo sistema para `output/` é aproximadamente 60 GB.

Não foram registrados valores de segredos nem conteúdo de configurações ignoradas. O documento-base `plano_milestones_postgresql_fominha_de_manga_v3.md` não foi encontrado no repositório nem em `Downloads` no caminho esperado; o escopo aplicado veio do pedido colado.

## Persistência e compatibilidade observadas

- `central_v2/backend/orchestration/textoff_merged/artifact-migration-registry.json`: `migration_mode=dual_write`, `dual_write_enabled=true`, `legacy_read_enabled=true`, `new_read_enabled=true`, `read_authority=legacy`. Os cinco mappings persistentes — Auto-Cleaner I, Mapear, input consolidado do Mapear, Sommelier e Nível II — estão marcados `validated=false`.
- `stages.py`: nomes canônicos `TO_MERGED_NIVEL_I/II/III` e `TO_MERGED_CONSOLIDADO`, aliases históricos `MERGED_NIVEL_*`, novos destinos e resolução condicional por `CENTRAL_V2_LEVEL1_NUMBERED`.
- `artifact_migration.py`: resolução usa o lado indicado pelo registry; cópia shadow substitui a árvore de destino e remove backup temporário após sucesso. Esse mecanismo não foi invocado.
- Atenção para auditoria futura: `stages.py::_resolve_stage_chapter` pode mover diretórios antigos de Pincel para o destino com `os.replace` durante resolução. Um scanner estritamente somente leitura não deve chamar esse resolver.
- Busca estática no código Python e manifests de dependências não encontrou integração PostgreSQL (`psycopg`, `asyncpg`, SQLAlchemy ou configuração PostgreSQL). Não foi criado banco.

## Backup e recuperação existentes

Há backups locais ignorados (conteúdo e restaurabilidade não verificados) e mecanismos específicos no código: writers que promovem diretórios staged com rollback local, backup de `07_CONSOLIDADO_FINAL` e manifesto de tratamento na restauração especial, registro de histórico e hashes em manifests, e snapshots/reexecução de Sólidos. A semântica varia por writer; não foi comprovado um backup integral e restaurável do acervo, nem foi feita restauração neste diagnóstico. Não há backup PostgreSQL porque a persistência ainda não existe.

## Resultado M0

- Estado tracked, untracked, submódulo e ignorados relevantes registrados sem alterações.
- Nenhum arquivo operacional foi excluído ou alterado.
- Nenhum tratamento, teste, migration ou processamento de imagem foi executado.
- O status após gerar os relatórios é o abaixo; os novos arquivos são somente documentação em `docs/postgresql/`.

```text
## develop...origin/develop
 M central_v2/frontend/_shell/navigation.js
 M dev/tests/central_v2_frontend/navigation_textoff.test.mjs
 M dev/tests/central_v2_frontend/textoff_merged.test.mjs
 M docs/central_v2/limpeza_baloes/README.md
 m download/mangago_downloader
?? docs/central_v2/limpeza_baloes/funcionalidades_fora_sidebar.md
?? docs/postgresql/
```

Estado interno final do submódulo continuou: `main...origin/main`, `.gitignore` e `README.md` modificados localmente, `.venv-test/` e dois patches não rastreados.

## Fontes principais

- `config/data_paths.py`
- `central_v2/backend/orchestration/textoff_merged/artifact-migration-registry.json`
- `central_v2/backend/orchestration/textoff_merged/artifact_migration.py`
- `central_v2/backend/orchestration/textoff_merged/stages.py`
- `central_v2/AGENTS.md`
- `docs/backlog/postgresql_pipeline_limpeza.md`
