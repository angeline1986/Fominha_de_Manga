# CV2-AM-01 — Organizar filtros e contagens do Auto-Merge Nível I

- **Prioridade:** P2 (sugerida)
- **Status:** A Fazer
- **Visão:** Visão de Produto · Processamento · Auto-Merge Nível I
- **Responsável:** A definir

**Objetivo:** Tornar claros os capítulos ainda não processados e os que já tiveram o merge do Nível I identificado, com contagem visível em cada filtro.

**Critério de Aceite:**
- [ ] Renomear o filtro `Todos` para `All`.
- [ ] Exibir `DO` e `Done` logo após `All`, nesta ordem.
- [ ] Renomear `MERGE identificado` para `Done` e posicioná-lo imediatamente após `DO`.
- [ ] O filtro `DO` exibe capítulos sem merge do Nível I registrado com sucesso.
- [ ] O filtro `Done` exibe capítulos com merge do Nível I registrado com sucesso.
- [ ] Preservar os demais filtros atuais após `All`, `DO` e `Done`.
- [ ] Mostrar a quantidade junto ao nome de cada filtro, incluindo `All (n)`, seguindo o padrão dos demais níveis de Auto-Merge.
- [ ] Calcular as contagens a partir dos capítulos carregados para a obra selecionada e atualizá-las ao trocar Provider ou Obra.
- [ ] Confirmar que contagens, filtros, busca e seleção de capítulos permanecem coerentes entre si.

**Restrições (o que NÃO fazer):**
- Não alterar o algoritmo ou os resultados do Auto-Merge Nível I.
- Não alterar os filtros ou contratos dos Níveis II a V.
- Não modificar `laboratorio_one/` nem algoritmos de processamento.
- Respeitar o limite de 200 linhas físicas por arquivo de código.
- Não fazer commit ou push sem autorização.

**Links de Referência:** `central_v2/frontend/processamento/auto_merge/nivel1/view.js`; `central_v2/frontend/processamento/auto_merge/shared/registros.js`; padrão de contagens em `central_v2/frontend/processamento/auto_merge/shared/filtros_estado.js`.
