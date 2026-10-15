# CV2-AC-06 — Padronizar filtros de capítulo e página do Auto-Cleaner Check

- **Prioridade:** P2
- **Status:** TODO
- **Categoria:** UI/UX · Padronização de componentes
- **Escopo:** Central V2 — Auto-Cleaner Check
- **Referência visual e funcional:** Sidebar do Laboratório
- **Responsável:** A definir

**Objetivo:** Refatorar os seletores de capítulo e página para usar o padrão visual e de interação do Laboratório, priorizando componentes compartilhados compatíveis. O escopo inclui somente esses dois seletores; não inclui controle IMG/MERGE nem explorador de arquivos.

**Problema atual:** A sidebar apresenta o título “Páginas” com um botão de capítulo no cabeçalho, busca de páginas em linha separada e lista de páginas, sem seletor compacto de página.

**Comportamento esperado:**
- Manter o título “Páginas” e remover o botão de capítulo do cabeçalho e a busca de páginas.
- Exibir abaixo do título dois dropdowns compactos na mesma linha: `Cap. N` e `Pág.`.
- Listar somente capítulos disponíveis para a obra e páginas do capítulo selecionado.
- Manter a lista de páginas abaixo dos dropdowns e preservar nomes, ordenação, destaque, indicadores, contadores, revisão, clique e rolagem.
- Sincronizar seleção entre capítulo, dropdown de página, lista lateral e comparação ORIGINAL × PROCESSADA.
- Ao trocar capítulo, atualizar a lista e a visualização conforme a regra atual de seleção inicial; preservar carregamento e persistência das decisões do Check.
- Evitar atualizações circulares, recargas duplicadas e requisições desnecessárias ao selecionar a página ativa.

**Critérios de Aceite:**
- [ ] Reutilizar o padrão visual e de interação dos seletores do Laboratório sem acoplar diretamente as telas.
- [ ] Sincronizar seletores, lista, comparação e ocorrências ao navegar por capítulo ou página.
- [ ] Preservar classificações, indicadores, decisões aprovadas e critérios de disponibilidade das páginas.
- [ ] Confirmar que não há regressões na comparação ORIGINAL × PROCESSADA.
- [ ] Não adicionar seletor IMG/MERGE, botão de pasta ou explorador de arquivos.
- [ ] Manter independente a investigação da falha de carregamento inicial registrada em CV2-AC-05.

**Restrições:** Alterar somente componentes da Central V2 relacionados a esta tela. Não modificar a Central V1, o Laboratório além de eventual extração segura de componente compartilhado, algoritmos, imagens, máscaras, manifests, armazenamento, navegação ou persistência fora do escopo.
