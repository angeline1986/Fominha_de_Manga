# CV2-UX-03 — Padronizar tabelas e cabeçalhos no estilo Artístico

- **Prioridade:** P3 (sugerida)
- **Status:** A Fazer
- **Visão:** Visão de Produto · Visão Geral (padrão transversal de UX/UI)
- **Responsável:** A definir

**Objetivo:** Unificar as tabelas da Central V2 no padrão visual de Pincel & Retoques / Artístico, com páginas minimalistas, controles consistentes e títulos sem legendas visíveis.

**Referência visual:** Modern Enterprise SaaS UI · Minimalist Dashboard Design; usar Pincel & Retoques / Artístico como referência visual da página e da tabela.

**Critério de Aceite:**
- [ ] Inventariar e aplicar o padrão visual a todas as tabelas da Central V2.
- [ ] Manter composição coerente de página, cabeçalho, painel, busca, filtros, ações, tabela, estado vazio e paginação, conforme a referência.
- [ ] Disponibilizar o controle `Exibir` com as opções 13, 20, 30, 40, 50 e 60 itens por página.
- [ ] Remover legendas e subtítulos visíveis dos títulos das páginas; apresentar o mesmo contexto em tooltip associado ao título.
- [ ] Permitir consultar as tooltips por hover e foco de teclado, com associação acessível ao título.
- [ ] Preservar busca, filtros, seleção, ações e paginação existentes em cada feature.
- [ ] Confirmar legibilidade e uso responsivo em diferentes larguras de tela.

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
