# CV2-UX-07 — Unificar nomenclaturas dos tratamentos especiais

- **Prioridade:** P2
- **Status:** TODO
- **Categoria:** Interface · Nomenclatura
- **Escopo:** Laboratório, comparações e telas de tratamentos especiais da Central V2 e interface legada
- **Responsável:** A definir

**Problema:** Os mesmos tratamentos aparecem com nomes diferentes conforme a tela. “Artístico” também aparece como “Estilizado” e “Patch Balão Estilizado”; “Gradiente” aparece como “Suave” e “Gradiente Suave”. Isso dificulta reconhecer o mesmo tratamento entre páginas.

**Objetivo:** Padronizar os nomes apresentados às pessoas usuárias, mantendo os identificadores técnicos atuais neste escopo.

| Nome atual | Nome padronizado |
|---|---|
| Patch Degradê; Pincel & Retoques · Degradê | Degradê |
| Estilizado; Patch Balão Estilizado; Artístico | Artístico |
| Suave; Gradiente Suave | Gradiente |

**Escopo da revisão:**
- Conferir rótulos de botões, cabeçalhos, títulos de comparação, estados, mensagens de execução e logs apresentados nas interfaces.
- Aplicar os nomes padronizados em todas as telas ativas da Central V2 e na interface legada de tratamentos especiais.
- Manter os identificadores técnicos, rotas, nomes de algoritmos, runtimes e formatos de dados (`degrade`, `estilizado`, `gradiente_suave`) sem alteração, salvo se uma tarefa técnica separada justificar migração compatível.
- Distinguir Degradê de Gradiente: são tratamentos diferentes e não devem ser mesclados.

**Critérios de aceite:**
- [ ] Todas as ocorrências visíveis dos três tratamentos foram inventariadas nas interfaces incluídas.
- [ ] As interfaces usam consistentemente Degradê, Artístico e Gradiente.
- [ ] Nenhum texto da interface chama o tratamento Gradiente de “Suave” ou “Gradiente Suave”.
- [ ] Os identificadores e contratos técnicos existentes continuam compatíveis.
- [ ] A documentação de uso voltada à pessoa usuária reflete os nomes padronizados.
