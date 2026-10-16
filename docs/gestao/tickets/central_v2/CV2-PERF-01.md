# CV2-PERF-01 — Reduzir o carregamento do Auto-Cleaner e Auto-Cleaner Check

- **Prioridade:** P1 (alta)
- **Status:** Parcialmente concluído
- **Categoria:** Performance · UX · Limpeza de Balões
- **Escopo:** Central V2 — Auto-Cleaner e Auto-Cleaner Check
- **Responsável:** A definir

## Contexto e causa raiz

A abertura das tabelas da obra de 65 capítulos levava aproximadamente 7–8 segundos. O principal custo era a leitura e verificação repetida de artefatos e hashes no backend. A construção da tabela no navegador era pequena em comparação. As duas telas consultavam a mesma projeção de dados, mas repetiam a requisição ao alternar entre elas.

## Implementado

- Reuso em memória da mesma consulta e de requisições em andamento entre Auto-Cleaner e Check, por Provider/Obra, com invalidação nas operações que alteram os dados e proteção contra respostas atrasadas de outro contexto.
- Reuso de leituras e resoluções redundantes limitado à mesma requisição, preservando verificações de integridade e sem cache persistente.
- Estados de carregamento que preservam contadores e espaço da tabela, além de ajuste dos filtros em 1024 px.
- Validações funcionais e medições via Chrome CDP: retorno em torno de 45 ms e nenhuma nova requisição de dados ao voltar à tela carregada.

## Pendente

- A primeira abertura ainda leva aproximadamente 2 segundos, acima da meta inicial de 1,5 segundo. A verificação de integridade dos artefatos continua sendo o custo dominante.
- Concluir o relatório consolidado de validação e a investigação do custo restante antes de declarar o item concluído.

## Critérios para concluir

- [ ] Em cinco ou mais medições via Chrome CDP, a mediana de primeira abertura fica abaixo de 1,5 segundo sem enfraquecer verificações de integridade.
- [x] O retorno sem alterações fica abaixo de 500 ms e não faz GET adicional da projeção de dados.
- [x] Busca, filtros, paginação, seleção, alternância e troca de contexto permanecem funcionais.
- [x] Estados de carregamento não mostram contadores provisórios zerados nem causam expansão abrupta da tabela.
- [x] Os filtros não ficam cortados ou sobrepostos ao botão de execução em 1024 px.
- [ ] Publicar o relatório consolidado com as evidências, medições, testes de integridade, riscos e estado do diff.

## Restrições

Preservar algoritmos de limpeza, thresholds, elegibilidade, contratos HTTP, manifests, imagens, históricos, resultados processados e validações de integridade. Não introduzir cache persistente sem política de invalidação comprovadamente segura.
