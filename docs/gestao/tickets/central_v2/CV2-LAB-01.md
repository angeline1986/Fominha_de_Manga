# CV2-LAB-01 — Ordenar cartões do Laboratório pela execução

- **Prioridade:** P2
- **Status:** DONE
- **Área:** Limpeza de Balões · Laboratório

## Objetivo

Apresentar os tratamentos da página selecionada na ordem em que seus resultados foram executados, em vez da sequência fixa Degradê, Artístico, Suave e Sólidos.

## Critérios de aceite

- [x] Manter o cartão Original na primeira posição.
- [x] Ordenar os cartões com resultado pela data e hora da execução correspondente à página atual, do mais antigo ao mais recente.
- [x] Colocar cartões ainda não executados depois dos resultados, com ordem estável entre eles.
- [x] Quando um tratamento for reexecutado, usar a execução exibida no cartão para posicioná-lo; uma execução nova deve aparecer ao final dos resultados.
- [x] Ao trocar de página ou recuperar resultados existentes, reconstruir a ordem a partir dos registros persistidos, sem depender apenas da sequência de cliques da sessão.
- [x] Preservar a associação entre cartão, imagem, estado, botão de seleção e proposta para o Consolidado Final após cada mudança de posição.
- [x] Usar `finished_at` do manifesto experimental quando presente; para execuções antigas, usar a data de modificação do manifesto. Sólidos usa a data do manifesto da prévia.

## Implementação

Os cartões são identificados pelo tratamento, independentemente da posição no DOM. A consulta de recuperação valida a imagem e devolve o horário dos quatro tratamentos; resultados sem execução ficam após os demais. Nova execução entra na ordem após sua prévia ser carregada.

## Limites

Não alterar algoritmos, imagens, resultados, manifestos ou a ordem de processamento dos tratamentos. A mudança é de apresentação na página do Laboratório.
