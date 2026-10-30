# CV2-AC-07 — Sincronizar a cor das caixas de seleção com os bullets do Auto-Cleaner Check

- **Prioridade:** P2
- **Status:** DONE
- **Visão:** Limpeza de Balões
- **Responsável:** A definir

**Objetivo:** Facilitar a associação entre cada área marcada sobre a imagem e seu item correspondente no sidebar direito do Auto-Cleaner Check.

**Melhoria solicitada:** A caixa/contorno da área selecionada deve usar a mesma cor do bullet do item correspondente em “Áreas nesta página”. A cor deve continuar vinculada à área quando seu tipo/status for alterado no sidebar.

**Paleta verificada no frontend:** Transparente `#0891B2`; Degradê `#DB2777`; Gradiente `#7C3AED`; Estilizado `#FAA307`; Branco sólido `#A7C957`; Outro / não identificado `#64748B`. As caixas, seus números, os itens da revisão e os bullets consultam a mesma paleta. Implementação, testes automatizados e validação visual concluídos.

**Critérios de Aceite:**
- [x] Cada área desenhada ou selecionada na imagem usa a cor do bullet correspondente no sidebar direito.
- [x] A identificação numérica da área mantém associação visual clara com o respectivo item do sidebar.
- [x] Alterar o tipo/status da área atualiza a cor correspondente sem perder a associação entre imagem e sidebar.
- [x] A aparência continua legível em áreas sobrepostas e nos estados de foco/seleção.
