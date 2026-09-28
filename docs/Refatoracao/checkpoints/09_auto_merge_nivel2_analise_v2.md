# Auto-Merge Nível II — análise para implementação na V2

Data: 2026-09-27. Referências: contratos e evidências do Nível I, mapa de
manifestos, algoritmo especializado de Nível II e testes históricos da V1.
Este checkpoint registra análise; não altera código de produção.

## Objetivo do Nível II

O Nível II recebe somente `pending_segments` do manifesto
`auto_merge_level1_resolved_segments`. Busca novos cortes em cada residual com
uma estratégia segura e limitada, preservando os artefatos completos que o
Nível I já produziu. Trechos cuja cobertura foi resolvida viram novos artefatos
intermediários; qualquer parte sem caminho seguro permanece residual para o
Nível III.

Se todos os residuais forem resolvidos, a composição oficial é formada pelos
artefatos do Nível I mais os do Nível II, ordenados e validados para cobertura
contínua de `0` até `total_height`. Se restar residual, não se promove MERGE:
os resultados I e II permanecem intermediários para o Nível III.

## Estratégia algorítmica a preservar

O módulo `processamento/unificacao_imagens/image_stitcher_level2.py` contém a
busca especializada existente e deve ser tratado como referência do algoritmo,
não como uma interface de aplicação. A estratégia combina:

- faixas brancas reconhecidas pelo analisador V3, sem relaxar os thresholds V3;
- faixas de cor uniforme, aceitas por baixa variação transversal e entre linhas;
- busca de caminho seguro dentro do residual, com composição preferencialmente
  equilibrada em torno da altura-alvo;
- preferência editorial por quantidade de imagens-fonte, sem usá-la como regra
  de segurança;
- `edge chunk` abaixo da altura mínima somente como último recurso, apenas na
  borda real do residual e nunca no interior;
- avanço parcial pelo melhor prefixo seguro quando não há caminho completo;
- residual integral quando não é possível comprovar progresso seguro.

Um intervalo já dentro da altura máxima pode ser considerado resolvido sem
novo corte. Cor, equilíbrio, número de arquivos e comprimento de faixa não
substituem a prova de elegibilidade visual do corte. Nenhum caminho força corte.

## Fronteiras recomendadas na V2

1. **Consulta/autoridade:** validar provider, obra e capítulo; carregar e
   validar algoritmo/schema do manifesto I; derivar a entrada exclusivamente
   dos `pending_segments` válidos do I. Não usar `merge-attempt.json` como fonte
   alternativa de residual.
2. **Planejamento:** receber páginas, intervalos-fontes, candidatos V3 e
   configuração central; devolver plano determinístico completo, parcial ou
   sem resolução, com cortes selecionados, rejeitados e razões.
3. **Materialização:** renderizar somente intervalos aprovados usando os
   `source_spans` globais, preservando pixels e offsets exatos; nunca regravar
   artefatos do Nível I.
4. **Persistência:** gravar em staging exclusivo por tentativa e publicar
   `merge-level2-manifest.json` somente após validar arquivos, dimensões,
   intervalos e cobertura. Reexecução não remove nem substitui estágio anterior
   ou oficial; detectar colisão e falhar fechado.
5. **Promoção:** somente quando não houver residual; compor I + II sem
   rerenderização, validar continuidade/ausência de lacuna e sobreposição,
   largura/altura e identidade dos arquivos; recusar destino oficial ocupado.
6. **Orquestração e job:** processar capítulos com limite explícito de
   concorrência, progresso por capítulo, eventos no terminal e resultados
   estáveis. O handler HTTP apenas valida/transfere o comando e consulta job.
7. **Projeção V2:** expor totais, segmentos II salvos, residuais, ocorrências e
   próxima etapa; não inferir autoridade persistente a partir do estado da tela.

Cada módulo deve ter uma única responsabilidade, permanecer abaixo de 200
linhas e manter a Central V1 intacta.

## Invariantes e cenários de caracterização

- Residual vazio ou manifesto I ausente/inválido: não executar II.
- Capítulo já promovido ou destino oficial existente: não sobrescrever.
- Manifesto I alterado entre planejamento e publicação: rejeitar resultado
  obsoleto; o manifesto II deve registrar a origem exata consumida.
- Caminho completo: I + II recompõem exatamente a altura total em ordem.
- Caminho parcial: prefixos seguros são materializados; o restante continua
  pendente, sem lacuna nem sobreposição na partição.
- Nenhum caminho: nenhum artefato inventado e residual preservado.
- `edge chunk`: permitido só no início/fim do residual e sob a política
  existente; proibido internamente.
- Materialização entre páginas e no meio de uma página: pixels e offsets
  idênticos à fonte.
- Falha na escrita/publicação: não deixa manifesto que declare sucesso, não
  apaga artefatos anteriores e não toca na fonte ou no MERGE oficial.
- Vários residuais: nenhum deles pode desaparecer ao intercalar segmentos
  resolvidos e pendentes.
- Reexecução após staging parcial: colisão controlada; sem limpeza ampla.

Os testes históricos úteis são `test_merge_level2.py`,
`test_merge_level2_direct_promotion_safety.py`,
`test_merge_level2_state_machine.py` e `test_merge_level2_state_consistency.py`.

## Resumo de execução e comparação visual com a V1

O resumo da V2 segue agora a hierarquia usada pela V1: capítulo expansível,
linhas de status/merges/pendências/motivo/residual/próxima etapa e listas
recolhíveis de arquivos salvos e pendentes. Os nomes são enviados a partir dos
artefatos materializados e das páginas-fonte cobertas pelo residual; intervalos
são formatados com separadores locais. A ação “Abrir pasta” usa uma rota V2
restrita aos diretórios de estágio dos níveis I e II.

Os valores de saída observados nos prints não são tratados como diferença
cosmética: Nível I mostra 23 merges e 79 imagens pendentes na V1, contra 27 e
três intervalos residuais na V2; no Nível II os prints mostram 3 merges/61
imagens e 4 merges/um segmento residual, respectivamente. O resumo agora
apresenta cada métrica com seu significado e os arquivos associados. Igualar os
totais exigiria uma análise separada dos planos e entradas de cada execução;
esta alteração não muda algoritmos nem artefatos da V1. Os filtros do Nível I
também mantêm os conceitos próprios da consulta de registros da V2, em vez de
renomear estados sem equivalência comprovada com `novo`, `pendente_review` e
`parcial` da V1.

Ao executar um capítulo que já possui um estágio Nível I, a V2 agora lê o
manifesto válido e reapresenta arquivos/resíduos sem reprocessar nem sobrescrever
o estágio. Registro inválido, artefatos ausentes ou estágio completo sem MERGE
oficial continuam como ocorrência para revisão. Os valores do resumo ficam
alinhados à direita como na V1.
As fixtures antigas que não fornecem o manifesto I atual devem ser substituídas
por contratos explícitos de Nível I, mantendo os asserts funcionais de pixels,
residuais e promoção segura.

## Lacunas observadas na V1

- `validate_merge_level2()` vive em `interface_web/processing_web.py` e mistura
  validação de autoridade, busca, limpeza do diretório, materialização,
  manifesto, atualização do estado transitório e promoção.
- Antes de executar, a V1 remove PNGs existentes do diretório MERGE_LEVEL2; a
  V2 não deve adotar essa política destrutiva.
- O manifesto V1 identifica `source_auto_merge_manifest` pelo nome, sem hash
  de proveniência equivalente ao vínculo explícito III→II. A V2 deve associar
  o resultado ao conteúdo exato de I e recusar entrada obsoleta.
- O leitor de estado da V1 combina manifests de estágio com
  `merge-attempt.json`; a V2 deve separar manifestos autoritativos, estado
  transitório e DTO de consulta.
- A V1 pode promover Nível II direto quando não há pendências; esse caso deve
  continuar independente da Review e compor os artefatos existentes sem
  rerenderizá-los.

## Decisões pendentes antes da implementação

- Definir schema e nome do algoritmo V2 para o manifesto II, incluindo hash e
  caminho relativo do manifesto I de origem.
- Definir política de concorrência por capítulo e limites de memória para
  `analyze_uniform_color_bands`, que concatena amostras de todas as páginas.
- Confirmar se a validação do Nível I real em
  `comix/Gazing at you_centrav2` será pré-condição para ensaio integrado do II.
- Caracterizar fixtures sintéticas cobrindo todos os casos de segurança acima;
  nenhum teste do Nível II deve executar contra a obra real sem solicitação
  explícita e plano de validação revisado.

## Estado

### Obra de validação indicada — inspeção somente de leitura

Provider `comix`, obra `Gazing at you_centrav2`:

- Capítulo `1`: manifesto I válido, 90 imagens-fonte, 16 artefatos I presentes
  e um residual `48.921–63.277` (14.356 px). Ainda não há diretório/manifesto
  Nível II nem MERGE oficial. SHA-256 do manifesto I inspecionado:
  `289eb8b52ad0a0596fd4ec2f60401deea75485250631fa9f0bc908d447f91180`.
- Capítulo `2`: manifesto I completo e MERGE oficial reconhecido; não é elegível
  para reprocessamento no Nível II.

A inspeção não abriu nem alterou imagens, não gravou artefatos e não executou
Auto-Merge. A altura residual excede `max_chunk_height` de 12.000 px, portanto
exige ao menos uma decisão de corte segura. Esse fato não prevê se o algoritmo
conseguirá resolver o residual.

Em reconsulta posterior, antes de implementar a tabela V2, a mesma obra retornou
somente o capítulo `11`, com 71 imagens, 12 artefatos I presentes e residual
`0–15.789` (15.789 px); o capítulo 1 deixou de aparecer como elegível. A causa
da diferença entre as duas leituras não foi determinada. Ambas foram somente
de leitura. A interface deve exibir sempre o estado do manifesto atual, sem
assumir que a lista de elegíveis fica fixa entre consultas.

Na obra de comparação `ridi/Teste Things that deserve to die`, capítulo `6`,
uma inspeção somente de leitura encontrou 3 `pending_segments` no manifesto I.
A rotina de projeção da V1 `_analyze_merge_partition()` reconstrói 2 segmentos
agrupados a partir das imagens e a tabela V1 exibe esse valor. Já a execução
V1 de `validate_merge_level2()` lê a lista `pending_segments` do manifesto I,
portanto recebe 3. A V2 mantém a contagem alinhada com a entrada efetiva da
execução (3); a tabela não reanalisa imagens para imitar a projeção divergente
da V1. A região é apresentada por nomes de páginas, sem coordenadas em pixels.

### Caracterização sintética concluída

`dev/tests/test_auto_merge_level2_characterization.py` cobre sete contratos do
solver/detector: residual curto sem corte, caminho completo equilibrado, avanço
parcial com sufixo preservado, ausência de caminho, edge chunk apenas na borda,
faixa uniforme colorida não branca e preferência de arquivos sem autoridade
para ultrapassar o máximo. Resultado: 7/7 testes passaram. As fontes foram
temporárias e nenhuma rotina da Central V1 foi modificada.

A camada V2 agora inclui seleção e execução por job, leitura autoritativa dos
residuais I, materialização isolada, manifesto II com SHA do manifesto I,
consulta da página e promoção I+II validada. Testes sintéticos validam o caminho
parcial, preservação das fontes e promoção completa. Nenhum processamento real
foi executado. A obra indicada pode servir à validação controlada após revisar a
tela e confirmar novamente o manifesto e o destino oficial antes de iniciar.
