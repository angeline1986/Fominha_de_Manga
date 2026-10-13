# CV2-UX-03 — Padronizar tabelas e cabeçalhos no estilo Artístico

- **Prioridade:** P3 (sugerida)
- **Status:** DONE
- **Visão:** Visão de Produto · Visão Geral (padrão transversal de UX/UI)
- **Responsável:** A definir

**Objetivo:** Unificar as tabelas da Central V2 no padrão visual de Pincel & Retoques / Artístico, com páginas minimalistas, controles consistentes e títulos sem legendas visíveis.

**Referência visual:** Modern Enterprise SaaS UI · Minimalist Dashboard Design; usar Pincel & Retoques / Artístico como referência visual da página e da tabela.

**Critério de Aceite:**
- [x] Inventariar e aplicar o padrão visual a todas as tabelas da Central V2.
- [x] Manter composição coerente de página, cabeçalho, painel, busca, filtros, ações, tabela, estado vazio e paginação, conforme a referência.
- [x] Disponibilizar o controle `Exibir` com as opções 13, 20, 30, 40, 50 e 60 itens por página.
- [x] Remover legendas e subtítulos visíveis dos títulos das páginas; apresentar o mesmo contexto em tooltip associado ao título.
- [x] Permitir consultar as tooltips por hover e foco de teclado, com associação acessível ao título.
- [x] Preservar busca, filtros, seleção, ações e paginação existentes em cada feature.
- [x] Confirmar legibilidade e uso responsivo em diferentes larguras de tela.

**Restrições (o que NÃO fazer):**
- Não alterar regras de negócio, significado dos filtros ou APIs.
- Não remover informações explicativas; mover o contexto de legenda para tooltip.
- Não modificar `laboratorio_one/` nem algoritmos de processamento.
- Respeitar o limite de 200 linhas físicas por arquivo de código.
- Não fazer commit ou push sem autorização.

**Links de Referência:** `central_v2/frontend/texto_off/especiais/artistico_table.js`; `central_v2/frontend/texto_off/especiais/artistico.css`.

## Verificação final — 12/10/2026

- A suíte completa na revisão atual teve **137/138 testes aprovados**. Três falhas de `special_degrade_review.test.mjs` vinham de mock/expectativas desatualizados para a tabela Artístico (`styledPreviewImageUrl`, elementos do toolbar e coluna `actions`). O teste foi atualizado sem alterar componentes; agora passa **3/3**.
- A falha restante, `button_contract.test.mjs`, já existe em `HEAD`: aponta botões sem classe de componente em `exportar_arquivos/browser.js` e `texto_off/laboratorio/roi_selection.js`. A execução da suíte sobre um arquivo extraído de `HEAD` reproduziu a mesma falha. Não pertence ao escopo deste ticket e não foi alterada.
- A mudança do padrão de 15 para 20 foi conferida nos consumidores: Auto-Merge I–V, Texto Off Merged, Sommelier e Artístico usam o valor compartilhado e seus controles oferecem as opções aprovadas. Comparação fixa 13 itens e a lista de Balanceamento fixa 9; Gerar PDF mantém paginação própria e 13 como padrão. Não foi encontrada quebra de consumidores.
- `sommelier/index.js` já tinha **319 linhas em `HEAD`** (320 atualmente) e `gerar_pdf/view.js`, **247 linhas em `HEAD`** (247 atualmente); ambos ultrapassavam o limite antes deste ticket. Nenhuma refatoração foi iniciada.
- **Validação visual em navegador permanece pendente.**

## Encerramento — 13/10/2026

- Os ajustes finais de largura dos campos de busca e do seletor Perfil foram concluídos. Os placeholders de busca somente por capítulo foram padronizados para `Capítulo`; a busca do Pincel & Retoques manteve a indicação de capítulo, página e ocorrência.
- A conferência em navegador mediu 240 px para as buscas no desktop e 120 px para o Perfil, alinhado verticalmente aos demais controles. No mobile, os campos se adaptam à largura disponível sem rolagem horizontal na toolbar da Curadoria.
- Testes direcionados de Auto-Merge, Cleaner, Texto Off, tratamentos especiais e paginação: **28/28 aprovados**. `git diff --check` passou.
- Com esses ajustes e as entregas anteriores deste ticket, os critérios de aceite estão concluídos.
