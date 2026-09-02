# Merge Review — Estabilização V1

## Objetivo

Estabilizar o fluxo de Revisão Merge sem desfazer as melhorias visuais e de diagnóstico do estado `d77dc49`.

## Correções aplicadas

- Unifica a definição de capítulo pendente no frontend usando `merge_state == "pendente"`, `merge_failed` ou `review`.
- Corrige o uso indevido de `pending` em inglês.
- Remove o fallback silencioso que podia trocar o capítulo selecionado pelo primeiro item da fila.
- Faz o diagnóstico estruturado devolver somente `ch.name`.
- Mantém o diagnóstico estruturado de falha de proposta.
- Restaura a ordem conservadora de avaliação dos fins naturais.
- Restaura a proteção de altura mínima do bloco seguinte.
- Remove a estratégia experimental de absorção automática de cortes.
- Preserva melhorias de UI, PDF Merge, abertura de pasta e mensagens.

## Fora do escopo

Esta versão não altera os thresholds de `std`, `edge` ou `score` e não implementa revisão manual por trecho. Uma proposta sem candidato seguro deve continuar falhando de forma determinística e diagnosticável.
