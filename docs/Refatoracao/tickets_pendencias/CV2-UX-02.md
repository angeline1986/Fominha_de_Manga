# CV2-UX-02 — Restaurar a ação Sincronizar da sidebar

- **Prioridade:** P2 (sugerida)
- **Status:** Em Investigação
- **Visão:** Visão de Produto · Visão Geral (ação transversal)
- **Responsável:** A definir

**Objetivo:** Fazer o botão Sincronizar atualizar o estado da obra selecionada conforme o contrato documentado da Central.

**Critério de Aceite:**
- [ ] Reproduzir o problema em ambiente isolado e registrar evidência.
- [ ] Comparar o comportamento com a HEAD anterior antes de classificar como regressão; sem evidência, manter em investigação.
- [ ] Definir a ação do botão com base no contrato existente: atualizar o estado da obra selecionada.
- [ ] Ao acionar Sincronizar, atualizar o catálogo e recarregar o estado da obra mantendo Provider e Obra selecionados quando ainda disponíveis.
- [ ] Comunicar falhas de sincronização sem perder o contexto atual.

**Restrições (o que NÃO fazer):**
- Não alterar regras de negócio nem APIs sem necessidade demonstrada.
- Não alterar dados da obra durante uma atualização de leitura.
- Não modificar `laboratorio_one/` ou algoritmos de processamento.
- Respeitar o limite de 200 linhas físicas por arquivo de código.
- Não fazer commit ou push sem autorização.

**Links de Referência:** `docs/central_v2_menus.html` (contrato: atualizar o estado da obra selecionada); `central_v2/frontend/_shell/shell.js` (botão atual); `interface_web/app.js` (referência de `refreshStatus()` no fluxo anterior).
