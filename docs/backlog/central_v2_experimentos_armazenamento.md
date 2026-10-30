# Backlog Central V2: armazenamento e organização de experimentos

**Prioridade:** URGENTE para EXP-02
**Status:** EXP-01 concluído; EXP-02 pendente
**Escopo:** Laboratório e tratamentos especiais da Central V2

## Situação atual

As novas execuções são gravadas dentro da pasta da obra:

```text
<obra>/FLUXO_SECUNDARIO/05_Lab_Retoques/
├── textoff_especiais_v2/<UUID>/
└── textoff_laboratorio/<UUID>/
```

Degradê, Artístico, Suave e Sólidos gravam novas execuções em `textoff_laboratorio/`; os tratamentos especiais usam `textoff_especiais_v2/`. As execuções anteriores em `Fominha_de_Manga/reports/experimentos/` e as prévias antigas de Sólidos em `<raiz de saída>/_laboratorio_solidos_previews/` continuam disponíveis para leitura. A decisão foi aplicar o novo caminho somente daqui em diante; não há migração nem exclusão dos históricos nesta etapa. O caminho efetivo está em [`run_paths.py`](../../central_v2/backend/orchestration/textoff_special/run_paths.py).

## Tickets

### EXP-01 — Gravar novas execuções na pasta da obra

**Prioridade original:** URGENTE
**Status:** CONCLUÍDO

Os quatro tratamentos do Laboratório e os tratamentos especiais gravam novas execuções nas respectivas pastas de `05_Lab_Retoques/`. A leitura dos resultados anteriores, inclusive das prévias antigas de Sólidos, foi preservada. Os dados históricos não foram movidos.

### EXP-02 — Organizar por capítulo, página e execução

**Prioridade:** URGENTE
**Status:** PENDENTE

Definir uma organização navegável por capítulo, página e tratamento dentro de `05_Lab_Retoques/`, mantendo as duas pastas atuais e o UUID de cada execução. Permitir reexecuções sem sobrescrever resultados anteriores e associar estado, logs e erros à página correta.

A hierarquia exata ainda precisa ser decidida. Antes de alterar os caminhos, especificar identificadores originais, tratamento de separadores e colisões, escrita isolada por UUID, estados terminais, falhas parciais e compatibilidade de leitura com execuções atuais e legadas. Não migrar automaticamente os históricos.

## Dependências e riscos de EXP-02

- Inventariar consumidores, rotas e tarefas afetados pela organização por capítulo e página.
- Definir identificadores canônicos e contratos de manifesto e requisição sem perder a identidade original.
- Preservar imagens, máscaras, manifestos, requisições, logs e diagnósticos.
- Garantir que retry e concorrência não sobrescrevam outra execução.
- Validar que listagem, polling, download, logs e reabertura funcionem para caminhos novos e anteriores.
- Avaliar espaço, backup e desempenho do volume por obra.

## Critérios de aceite

- [x] Novas execuções, inclusive Sólidos, são gravadas em `<obra>/FLUXO_SECUNDARIO/05_Lab_Retoques/`.
- [x] Laboratório e tratamentos especiais continuam lendo execuções antigas, inclusive prévias de Sólidos na raiz de saída.
- [ ] Caminhos permitem navegar por capítulo, página e tratamento, mantendo o UUID da execução.
- [ ] Reexecuções não sobrescrevem resultados anteriores.
- [ ] Estados, logs e erros apontam para a página e a execução corretas.
- [ ] Compatibilidade da interface com resultados atuais e legados é validada.

## Próximo passo

Detalhar EXP-02 a partir dos caminhos atuais e validar a organização proposta em dados de teste. Qualquer migração ou retirada dos diretórios históricos depende de decisão separada.
