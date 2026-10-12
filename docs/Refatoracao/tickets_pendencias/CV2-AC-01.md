# CV2-AC-01 — Corrigir descarte de boxes pequenos `unknown`

- **Prioridade:** P2
- **Status:** A Fazer
- **Visão:** Visão de Produto · Limpeza de Balões
- **Responsável:** A definir

**Objetivo:** Preservar texto detectado em boxes pequenos `unknown` sem ampliar falsos positivos.

**Critério de Aceite:**
- [ ] Recuperar `IT'S COLD.` e `REALLY?` na Raw Mask.
- [ ] Validar a remoção final dos textos.
- [ ] Regredir falsos positivos e balões transparentes.

**Restrições (o que NÃO fazer):**
- Não reduzir globalmente `suspicious_box_min_size`.
- Não alterar autorização N1, Passo 2 ou algoritmos não relacionados.

**Links de Referência:**
`docs/Refatoracao/politica_investigacao_regressoes.md`
 `docs/archive/backlog_legacy_2026_10_12/pendencias_central_v2_legacy.md`
