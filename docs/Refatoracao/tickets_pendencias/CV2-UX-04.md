# CV2-UX-04 — Corrigir alinhamento da barra de progresso global

- **Prioridade:** P2
- **Status:** TODO
- **Categoria:** Interface · Componente compartilhado de progresso
- **Escopo:** Central V2 — Barra de progresso global
- **Responsável:** A definir

**Problema:** Durante a execução de Texto Off — Merged, a barra de progresso global no rodapé invade visualmente a região inferior da sidebar, não acompanha corretamente a largura da área de conteúdo e fica próxima demais da borda inferior da janela. O posicionamento sugere um problema de posição, largura ou relação com o container principal.

**Objetivo:** Alinhar a barra de progresso compartilhada exclusivamente à área principal de conteúdo, mantendo espaçamentos consistentes e responsividade para todos os processos que usam o componente.

**Comportamento esperado:**
- A barra permanece dentro dos limites da área principal, sem sobrepor a sidebar.
- Alinhamento e espaçamentos laterais e inferiores são consistentes com o layout.
- Posição e largura acompanham a abertura, o recolhimento e mudanças de largura da sidebar.
- O alinhamento permanece correto durante rolagem, redimensionamento e alteração de zoom.
- Indicadores de etapa, porcentagem e preenchimento são preservados.

**Critérios de Aceite:**
- [ ] Alinhar a barra à área de conteúdo sem invadir a sidebar.
- [ ] Manter espaçamento lateral e inferior consistente.
- [ ] Validar sidebar expandida e recolhida, diferentes resoluções, rolagem, redimensionamento e zoom.
- [ ] Preservar a responsividade e os indicadores atuais de progresso.
- [ ] Confirmar o comportamento nos demais processos que usam o componente compartilhado.

**Diretriz técnica:** Investigar `central_v2/frontend/_shared/progress/progress.js` e `progress.css`, incluindo `position: fixed`, `left`, `right`, `bottom`, cálculo de largura e relação com o container principal. Corrigir a estrutura compartilhada; não criar uma barra específica para Texto Off — Merged.

**Restrições:**
- Não alterar lógica de execução, jobs ou cálculo de progresso.
- Não criar uma implementação específica para Texto Off — Merged.

**Referência:** Captura de tela da barra global durante a execução de Texto Off — Merged.
