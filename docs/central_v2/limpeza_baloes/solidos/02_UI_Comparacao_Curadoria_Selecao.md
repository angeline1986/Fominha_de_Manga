# Central V2 — Contratos de interface, seleção, comparação e Curadoria

**Base:** `develop` no commit `1af79b5c`. Documento de referência para manutenção e recuperação, não certificado de homologação.

## 1. Etapa 05, contrato de UI

Arquivos `central_v2/frontend/texto_off/solidos/{index.js,table.js,inspector.js,style.css}`. Layout utiliza classes compartilhadas `auto-merge-page`, `textoff-merged-page`, `cleaner-overview`, `auto-merge-toolbar`, `auto-merge-filters`, `auto-merge-filter-button`, `auto-merge-execute` e tabela compartilhada `createTable`.

- Filtros: `All`, `Pendentes`, `Concluídos`, contagens calculadas a partir do GET `/api/textoff/solidos`.
- Busca: substring do identificador de capítulo, comparação `toLocaleLowerCase("pt-BR")`.
- Seleção por capítulo: `Set`, desabilitada para capítulo `processed`. Quando muda seleção, atualiza botão de execução.
- Checkbox do cabeçalho: seleciona capítulos elegíveis da **página atual**; não seleciona todos os resultados de todas as páginas.
- Paginação: `createPagination(13)` e controles compartilhados; seletor `Exibir` visível. Conferir paginação e mudança de tamanho em teste antes de declarar homologado.
- Colunas: `CAPÍTULO`, `MERGES`, `ÁREAS SÓLIDAS`, `PENDENTES`, `CONCLUÍDAS`, `STATUS`, `VISUALIZAR`. `merge_count` não é entregue pelo endpoint Sólidos no estado de referência: exibe `—`, não inventar quantidade.
- `processed` é determinado pela presença do manifest: significa **prévia disponível**; não significa aprovação visual, hash revalidado pelo overview, nem consolidação.
- Execução múltipla: frontend itera os capítulos selecionados sequencialmente; endpoint executa **um capítulo por POST**; indicador de progresso externo conta capítulos. O job de backend é `submit(...total=1)` por capítulo.
- Polling frontend `600ms`, `GET /api/jobs/<id>`, aguarda `completed/failed`. Execução não prossegue após falha de um capítulo.
- Proibição de reexecutar capítulo com diretório de prévia existente sem processo formal de revisão/invalidação.

### 1.1 Comparação oficial versus modal antigo

O visualizador modal criado inicialmente por `inspector.js` foi inadequado por não herdar o contrato da Central V2. O commit `934a3f4e` integrou `inspector.js` com `createComparisonScreen` e o modo `solid`. **Não restaurar o antigo `<dialog>` de comparação**, embora o nome `inspector.js` permaneça.

Na tela comparadora, nomes e contratos:
- `comparisonMode=solid`; `scope=solid`; `step=solid` (trio exato).
- Modo `pair`; `sides=["before","after"]`; rótulos `AUTO-CLEANER I` e `SÓLIDOS`.
- `INITIAL_ZOOM=40`, `MIN_ZOOM=20`, `MAX_ZOOM=200`, `ZOOM_STEP=10`; botão `1:1` devolve 100%.
- `TRIPTYCH_PANEL_GAP=18` pixels compartilhado pelo slider (usado para os painéis comparados, apesar do nome).
- `COMPARISON_PAGE_SIZE` vem de `paginationConfig.inspectionPageSize`, não deve ser duplicado com uma constante local do Sólidos. Contrato visual esperado nas revisões anteriores: 13 páginas por vez; conferir valor resolvido no arquivo `/_shared/pagination/config.js`.
- O `slider.js` exige imagens com mesmas dimensões naturais, bloqueando desalinhamento. Zoom compartilhado, navegação por setas, modo foco, prévia hover, lista lateral.
- O modo `solid` usa `createSolidCatalog()`: painel de catalogação **oculto e somente leitura**; nenhuma escrita de resíduos pela visualização.
- Servir imagens com tokens de versão vinculados aos hashes das fontes e dos resultados; não reutilizar imagem de versão antiga.
- Ícone do olho: `iconMarkup("eye")` + classes `btn comparison-open`, reutilizados da página Passo 1.

### 1.2 Observações de UI que merecem testes

1. Seleção parcial em `table.js` do Sólidos usa checkbox genérico que define `checked`, mas não atribui `indeterminate`. **Não assumir que o comportamento indeterminado está pronto na etapa 05**.
2. `createPageSizeControl` no `table.js` atual só dispara `actions.changePage(0)`, enquanto o modelo foi criado com `createPagination(13)`. **Investigar** se a escolha de tamanho realmente altera a paginação; não confundir “o seletor aparece” com “o seletor funciona”.
3. O botão visualizar fica desabilitado quando `row.processed` é falso.
4. O estado `processed` do overview verifica apenas se o arquivo manifest existe; o endpoint de imagem impõe validação mais rigorosa de identidade e hash. Sintoma possível: olho habilitado, mas comparação indisponível; investigar integridade do manifest.
5. Não trocar zoom, régua, foco e paginação por implementações locais que reintroduzam rolagem cumulativa ou repetição de GET ao selecionar a mesma página.

## 2. Curadoria de Balões: seleção em lote

Arquivo: `central_v2/frontend/texto_off/sommelier/index.js`. Commit corretivo `1af79b5c`.

### 2.1 Estado e regras exatas
- `selected = new Set()` mantém identificadores de capítulos em memória durante filtros/paginação.
- Filtros `All`, `Do` (não analisados), `Done` (analisados) e `Candidato` (analisados com `candidates > 0`).
- Cabeçalho da primeira coluna renderiza um checkbox via função `header()`.
- `eligible = page.rows.filter(row => row.merge_valid !== false)`: **página atual**, sem capítulos explicitamente inválidos.
- `checked = eligible.length > 0 && count === eligible.length`, com `count = eligible.filter(row => selected.has(row.chapter)).length`.
- `indeterminate = count > 0 && count < eligible.length`.
- `disabled = executionBusy || eligible.length === 0`.
- Ao mudar checkbox do cabeçalho, adiciona ou remove somente os `eligible` visíveis dessa página e chama `draw()`.
- Checkbox individual: `checked = selected.has(row.chapter)`; desabilitado durante execução ou `merge_valid === false`; mutação no Set seguida de `draw()` atualiza cabeçalho.
- Alterar filtros ou busca redefine a página de exibição, mas preserva Set; ao alterar obra/contexto, limpa seleção, perfil, busca e filtro.
- Botão Executar depende de `selected.size > 0`, `profile.value !== ""` e ausência de `executionBusy`.
- Valores de perfil disponíveis neste arquivo: `poc_a_v1` e `poc_b_v1`; não mudar perfil automaticamente ao usar marcar todos.
- `startBubbleSommelier(provider,manga,chapters,profile.value)` recebe todos os IDs do Set, inclusive os selecionados em outras páginas.
- `aggregateSommelierProgress` soma quantidades de páginas/merges por capítulo; não interpretar esse agregado como número de balões detectados.
- Após sucesso, limpa seleção e recarrega overview; em falha, apresenta `showMessage`.

### 2.2 Critérios de regressão
- Marcar todos com 13 linhas, ir à próxima página, marcar linhas, retornar: seleção anterior permanece.
- Desmarcar todos em uma página não altera seleção de outra.
- Marcação individual alterna indeterminado do cabeçalho.
- Buscar ou filtrar não seleciona itens ocultos.
- Ao executar, selecionar perfil obrigatório, desabilitar controles necessários; total corresponde ao Set, sem incluir merge inválido.
- Trocar de obra limpa estado; reabrir revisão retorna à tabela sem contaminar seleção.

## 3. Mapa de arquivos de UI de impacto

| Arquivo | Responsabilidade |
|---|---|
| `frontend/texto_off/solidos/index.js` | Toolbar, filtros, busca, Set selecionado, jobs e integração visual. |
| `frontend/texto_off/solidos/table.js` | Colunas, checkbox por página, paginação e botão visualizar. |
| `frontend/texto_off/solidos/inspector.js` | Abre e fecha comparação de capítulo, integra viewer compartilhado. |
| `frontend/texto_off/solidos/style.css` | Ajustes de estilo restritos ao Sólidos. |
| `frontend/texto_off/comparison/model.js` | Configuração `solid`, limites de zoom e estilos dos painéis. |
| `frontend/texto_off/comparison/screen.js` | Sidebar, foco, navegação, carregamento de imagens, escolha de catálogo. |
| `frontend/texto_off/comparison/solid_catalog.js` | Adaptação read-only, sem catalogação. |
| `frontend/texto_off/comparison/slider.js` | Renderização sincronizada, validação de dimensões naturais. |
| `frontend/texto_off/sommelier/index.js` | Curadoria, checkbox do cabeçalho, execução em lote. |
| `frontend/texto_off/merged/view.js` | Padrão de tela referencial Auto-Cleaner Passo 1. |
| `frontend/texto_off/comparison/launcher.js` | Ícone e classes de comparação oficial. |

## 4. Limite deste documento

Não generalizar automaticamente o novo checkbox da Curadoria para todas as páginas. Há tabelas com elegibilidade e estados de execução diferentes. Inspecionar cada tela, documentar seu contrato e testar os casos acima antes de propagar a mudança.
