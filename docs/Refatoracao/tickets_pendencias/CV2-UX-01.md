# CV2-UX-01 — Redesenhar a sidebar minimizada

- **Prioridade:** P3 (média)
- **Status:** A Fazer — conceito aprovado; não implementado
- **Visão:** Visão de Produto · Visão Geral (navegação transversal)
- **Responsável:** A definir

**Objetivo:** Tornar a sidebar minimizada mais compacta e funcional, preservando a identidade visual e a navegação completa da Central V2.

**Referência visual:** Opção A — minimalista, com navegação preservada. Os símbolos do wireframe são conceituais; a proposta deve reutilizar os ícones originais da sidebar expandida.

**Critério de Aceite:**
- [ ] Sidebar compacta com aproximadamente 60 px, ícones centralizados, espaçamento consistente e paleta azul atual.
- [ ] Exibir os seis módulos: Visão Geral, Processamento, Balanceamento, Gerar PDF, Limpeza de Balões e Exportar Arquivos.
- [ ] Identificar o módulo ativo com barra vertical azul e, se necessário, fundo sutil.
- [ ] Manter Expandir no topo; Atualizar e Ligar/Desligar servidor no rodapé, separados da navegação.
- [ ] Preservar Provider e Obra na sidebar expandida, sem versões compactas desses campos.
- [ ] Mostrar tooltip com nome completo no hover e foco; garantir nomes acessíveis, teclado e estados de hover, foco, ativo e desabilitado.
- [ ] Manter acessíveis destinos e submenus; definir na proposta técnica o comportamento dos menus com subitens.
- [ ] Expandir sem perder página, filtros ou contexto selecionado e sem saltos de layout.
- [ ] Confirmar responsividade e coerência visual com a sidebar atual.
- [ ] Apresentar protótipo visual ou proposta técnica antes de implementar, incluindo arquivos afetados e comportamento de submenus.

**Restrições (o que NÃO fazer):**
- Não alterar regras de negócio ou APIs.
- Não mudar o menu expandido além do necessário para manter consistência.
- Não introduzir uma linguagem de ícones diferente; reutilizar componentes, ícones e tokens existentes.
- Não modificar `laboratorio_one/` nem algoritmos de processamento.
- Respeitar o limite de 200 linhas físicas por arquivo de código.
- Não fazer commit ou push sem autorização.

**Links de Referência:** Sidebar atual em `central_v2/frontend/_shell/navigation.js`; wireframe e diretrizes aprovados registrados neste item do backlog.
