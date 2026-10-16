# CV2-UX-01 — Redesenhar a sidebar minimizada

- **Prioridade:** P3 (média)
- **Status:** DONE
- **Visão:** Visão de Produto · Visão Geral (navegação transversal)
- **Responsável:** A definir

**Objetivo:** Tornar a sidebar minimizada mais compacta e funcional, preservando a identidade visual e a navegação completa da Central V2.

**Referência visual:** Opção A — minimalista, com navegação preservada. Os símbolos do wireframe são conceituais; a proposta deve reutilizar os ícones originais da sidebar expandida.

**Critério de Aceite:**
- [x] Sidebar compacta com 60 px, ícones centralizados, espaçamento consistente e paleta azul atual.
- [x] Exibir os seis módulos da fonte única `navigation.js` com os ícones originais.
- [x] Identificar o módulo selecionado com barra vertical azul e fundo sutil.
- [x] Manter Expandir no topo e Sincronizar/Finalizar servidor no rodapé.
- [x] Preservar Provider e Obra na sidebar expandida, sem versões compactas desses campos.
- [x] Mostrar tooltip no hover e foco; manter nomes acessíveis, teclado e estados de hover, foco, ativo e desabilitado.
- [x] Ao selecionar um ícone compacto, expandir no módulo correspondente sem trocar a página; destinos existentes continuam sendo acionados pelos subitens.
- [x] Recolher ou expandir sem apagar seleções de submenu nem o contexto de Provider e Obra.
- [x] Ajustar o modo compacto para telas menores e alturas reduzidas.
- [x] Implementar conforme a Opção A e o comportamento aprovado para submenus.

**Validação:** `sidebar_compact.test.mjs` e `router.test.mjs` aprovados (12/12). Após atualizar somente expectativas desatualizadas, `navigation_textoff.test.mjs` e `textoff_merged.test.mjs` também passaram (6/6). `navigation.js` permaneceu inalterado. `git diff --check` passou.

**Arquivos implementados:** `central_v2/frontend/_shell/shell.css`, `shell.js`, `drill_navigation.js`, `drill_navigation.css` e `drill_navigation_markup.js`. Cobertura específica em `dev/tests/central_v2_frontend/sidebar_compact.test.mjs`.

**Restrições (o que NÃO fazer):**
- Não alterar regras de negócio ou APIs.
- Não mudar o menu expandido além do necessário para manter consistência.
- Não introduzir uma linguagem de ícones diferente; reutilizar componentes, ícones e tokens existentes.
- Não modificar `laboratorio_one/` nem algoritmos de processamento.
- Respeitar o limite de 200 linhas físicas por arquivo de código.
- Não fazer commit ou push sem autorização.

**Links de Referência:** Sidebar atual em `central_v2/frontend/_shell/navigation.js`; wireframe e diretrizes aprovados registrados neste item do backlog.
