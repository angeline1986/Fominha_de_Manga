# CV2-UX-07 — Unificar nomenclaturas dos tratamentos especiais

- **Prioridade:** P2
- **Status:** DONE (30/10/2026)
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
- [x] Rótulos visíveis da Central V2 e da interface legada usam Degradê, Artístico e Gradiente.
- [x] Mensagens recebidas dos algoritmos legados são normalizadas na apresentação das duas interfaces.
- [x] Os identificadores e contratos técnicos existentes continuam compatíveis.
- [x] A documentação ativa de uso reflete os nomes padronizados.

Os identificadores `estilizado` e `gradiente_suave`, os nomes de arquivos e os caminhos permanecem técnicos. As mensagens no domínio legado não foram modificadas; sua exibição usa os nomes padronizados.
