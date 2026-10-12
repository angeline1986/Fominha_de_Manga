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
