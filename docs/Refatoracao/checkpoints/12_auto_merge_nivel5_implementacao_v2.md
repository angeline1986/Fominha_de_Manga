# Auto-Merge Nível V — implementação V2

Data: 2026-09-28. Continuação do checkpoint
`11_auto_merge_nivel4_implementacao_v2.md`.

## Contrato

O Nível V aceita exclusivamente resíduos de um manifesto IV atual com
algoritmo `merge_level4_directed_structural_safe_v1`. A cadeia de leitura
valida os manifestos I–IV, a proveniência SHA do IV e a partição contínua dos
resíduos III em artefatos IV e resíduos IV. Versões antigas/global não são
promovidas artificialmente para a fila V.

A composição global existente em `image_stitcher_level5.py` continua sendo
responsável pela análise exaustiva, busca por paridade, classificação SAFE e
seleção de prefixo. A V2 não altera seus parâmetros nem classificador. Artefatos
são gerados a partir das páginas-fonte somente para intervalos aprovados. Se a
composição não fechar, o prefixo SAFE pode ser salvo e o sufixo exato permanece
pendente; sem prefixo SAFE, todo o segmento permanece pendente.
Os capítulos selecionados são processados sequencialmente para limitar o pico
de memória da busca exaustiva e dos classificadores paralelos.

O estágio `MERGE_LEVEL5/<capítulo>` usa manifesto dedicado
`merge-level5-manifest.json`, algoritmo `merge_level5_global_structural_safe_v1`
e `source_level4_sha256`. Destinos existentes bloqueiam reexecução. Sem
residual, a promoção verifica cobertura, largura e proveniência de I–V antes
de copiar os artefatos já existentes para o MERGE oficial. Com residual, a
próxima etapa é Revisão Merge.

## Interface e validação

A opção V tem consulta, seleção, confirmação, barra de progresso, resumo e
acesso à pasta do estágio. A lista apresenta páginas de origem e contagem dos
resíduos, sem coordenadas em pixels.

Os testes cobrem rejeição de SHA desatualizado, fila e rotas, promoção completa
I–V e preservação de prefixo SAFE mais sufixo para revisão. A caracterização
algorítmica e os contratos históricos de autoridade do Nível V também passam.
