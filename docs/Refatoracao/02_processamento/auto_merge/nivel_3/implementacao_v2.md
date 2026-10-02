# Auto-Merge Nível III — implementação V2

Data: 2026-09-27. Continuação do checkpoint
`09_auto_merge_nivel2_analise_v2.md`.

## Contrato

O Nível III recebe exclusivamente `pending_segments` de um manifesto Nível II
V2 válido. A leitura confirma o algoritmo/schema, o SHA do manifesto I, a
presença e altura dos artefatos II e a partição contínua dos resíduos I por
artefatos e resíduos II. Manifestos antigos sem proveniência ou com intervalos
inconsistentes não são elegíveis.

O classificador estrutural existente em
`processamento/unificacao_imagens/image_stitcher_level3.py` permanece dono das
decisões SAFE/UNSAFE/INCONCLUSIVE e da busca local. A V2 só prepara janelas
locais com margem suficiente para reproduzir a busca limitada sem manter a
imagem residual inteira na memória. Materializa exclusivamente intervalos
aprovados, a partir dos PNGs originais e offsets globais conferidos.

O estágio `MERGE_LEVEL3/<capítulo>` usa manifesto dedicado
`merge-level3-manifest.json`, algoritmo `merge_level3_structural_safe_v1` e
`source_level2_sha256`. Reexecuções colidem com o estágio anterior; não há
limpeza automática. Um residual permanece pendente quando não há corte SAFE.
Sem residual, a V2 valida a cobertura e a largura de I + II + III antes de
promover os arquivos existentes, sem renderizar novamente os estágios I e II.

## Interface

A opção III do seletor de níveis abre uma consulta própria. A tabela apresenta
capítulo, quantidade de imagens, quantidade de resíduos e páginas de origem;
não mostra coordenadas em pixels. A execução é explícita, usa o job/progresso
compartilhado e apresenta resumo com arquivos salvos, pendências, motivo,
próxima etapa e acesso à pasta do Nível III.

## Validação

Testes V2 cobrem proveniência desatualizada, consulta HTTP, seleção, offsets de
materialização entre páginas, execução parcial sem promoção e composição
completa I + II + III. O ensaio do capítulo 6 de `ridi/Teste Things that
deserve to die` foi feito em cópia temporária, usando as páginas-fonte e os
manifestos atuais; PNGs I/II foram substituídos por fixtures de dimensões
compatíveis, pois a execução não chegou à promoção. O candidato em `232.211`
foi classificado como `UNSAFE` por cruzamento de componente; a busca local não
encontrou alternativa SAFE. O resultado correto foi preservar
`220.211–239.342` como residual com motivo `continuous_scene_too_long`, sem
artefato Level III e sem criar MERGE oficial. O diretório de dados da obra não
foi alterado pelo ensaio.

Verificações: suíte V2 (55 testes), frontend (31 testes), contratos estruturais
históricos do Nível III (38 testes) e testes novos de execução/consulta (6
testes). A suíte V2 foi repetida fora do sandbox porque cinco testes sobem
servidores HTTP locais.
