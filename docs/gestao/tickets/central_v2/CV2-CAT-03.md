# CV2-CAT-03 — Integrar Lezhinus ao catálogo da Central V2

- **Prioridade:** P2
- **Status:** DO
- **Categoria:** Integração de providers · Catálogo
- **Escopo:** Central V2 — Sidebar e catálogo de obras
- **Responsável:** A definir

**Problema:** Lezhinus já está disponível em Exportar Arquivos → Obras para Download e pode ser cadastrado em `lezhinus.json`, mas o catálogo da Central V2 só reconhece `comix`, `mangago` e `ridi`. Assim, obras Lezhinus com diretórios de processamento válidos não aparecem na seleção de provider e obra da sidebar.

**Objetivo:** Integrar Lezhinus ao catálogo de obras da Central V2 para permitir selecionar e acessar suas obras pela sidebar.

**Critérios de Aceite:**
- [ ] Lezhinus aparece no seletor de providers da sidebar.
- [ ] Obras em `OUTPUT_ROOT/lezhinus` com estrutura válida de `IMG` são listadas pelo catálogo.
- [ ] O contexto da obra Lezhinus permanece correto durante a navegação.
- [ ] Comix, Mangago e Ridi continuam funcionando sem regressões.
- [ ] Obras existentes são reconhecidas sem renomear ou migrar pastas.
- [ ] Dependências específicas dos fluxos são verificadas antes de habilitar compatibilidade nesses fluxos.

**Restrições:**
- Não alterar a Central V1.
- Não modificar algoritmos de download ou processamento.
- Não renomear pastas existentes nem alterar os JSONs de obras cadastradas.
- Não presumir que a inclusão no catálogo garante compatibilidade com todos os fluxos de processamento.

**Referências:** `central_v2/backend/state/catalog.py`; Exportar Arquivos → Obras para Download; `lezhinus.json`.
