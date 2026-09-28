# Auto-Merge Nível IV — implementação V2

Data: 2026-09-27. Continuação do checkpoint
`10_auto_merge_nivel3_implementacao_v2.md`.

## Contrato

O Nível IV consome somente `residual_pending_segments` de um manifesto III
V2 válido. A leitura exige o algoritmo `merge_level3_structural_safe_v1`,
SHA atual do manifesto II, artefatos III presentes e partição exata dos
resíduos II em artefatos e pendências III.

O classificador `find_global_safe_composition` de
`image_stitcher_level4.py` permanece responsável por shortlist, validação
estrutural e composição SAFE. A V2 renderiza cada residual autorizado a partir
das páginas-fonte, grava os intervalos aprovados em `MERGE_LEVEL4/<capítulo>`
com criação exclusiva e preserva sem alteração o residual não resolvido.
Manifestos III alterados e destinos ocupados bloqueiam a execução.

O manifesto IV usa `merge_level4_directed_structural_safe_v1` e registra
`source_level3_sha256`, artefatos SAFE, resíduos e diagnósticos. Com residual,
a próxima etapa é o Nível V. Sem residual, a promoção valida a cobertura e a
largura de I + II + III + IV e copia os artefatos existentes para o MERGE
oficial, sem renderizar de novo os níveis anteriores.

## Interface e validação

A opção IV possui consulta própria, seleção explícita, progresso de job,
confirmação, resumo e acesso à pasta do estágio. A lista mostra capítulos,
imagens abrangidas, quantidade de segmentos e páginas de origem; não apresenta
coordenadas em pixels.

Testes cobrem leitura/proveniência, consulta, rotas HTTP, promoção da composição
completa e preservação do residual quando a composição global não fecha. A
caracterização algorítmica existente (`test_merge_level4_contract.py`) também
continua passando. A validação com a obra de teste depende de executar os
Níveis III e IV nela em sequência; nenhum dado da obra de teste foi alterado
nesta implementação.
