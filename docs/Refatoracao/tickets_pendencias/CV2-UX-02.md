# CV2-UX-02 — Restaurar a ação Sincronizar da sidebar

- **Prioridade:** P2 (sugerida)
- **Status:** DONE
- **Visão:** Visão de Produto · Visão Geral (ação transversal)
- **Responsável:** A definir

**Objetivo:** Fazer o botão Sincronizar atualizar o estado da obra selecionada conforme o contrato documentado da Central.

**Critério de Aceite:**
- [x] Confirmado que o botão existia sem ação de sincronização conectada.
- [x] Implementada a atualização do catálogo e do estado da obra selecionada pelos endpoints existentes.
- [x] Provider e Obra são preservados quando válidos; seleções removidas são limpas.
- [x] Falhas e respostas atrasadas não sobrescrevem o contexto atual.
- [x] Feedback de sucesso/falha e bloqueio de sincronizações simultâneas validados.

**Validação:** `context_selector.test.mjs` (2/2), testes de sincronização (`context_sync.test.mjs` e `shell_sync.test.mjs`, 10/10) e testes de contexto, sidebar compacta e roteamento (16/16) aprovados. `git diff --check` passou.

**Restrições (o que NÃO fazer):**
- Não alterar regras de negócio nem APIs sem necessidade demonstrada.
- Não alterar dados da obra durante uma atualização de leitura.
- Não modificar `laboratorio_one/` ou algoritmos de processamento.
- Respeitar o limite de 200 linhas físicas por arquivo de código.
- Não fazer commit ou push sem autorização.

**Links de Referência:** `docs/central_v2_menus.html` (contrato: atualizar o estado da obra selecionada); `central_v2/frontend/_shell/shell.js` (botão atual); `interface_web/app.js` (referência de `refreshStatus()` no fluxo anterior).
