# TextOff Merged — consolidação, Nível III e armazenamento

Data: 30/09/2026

## Contrato de estágios

As novas execuções da Central V2 publicam cada estágio em diretórios próprios,
abaixo de `FLUXO_SECUNDARIO/04_TEXTO_OFF/`:

| Estágio | Diretório | Conteúdo |
|---|---|---|
| Nível I | `TO_MERGED_NIVEL_I/<capítulo>/` | Limpeza Cleaner V2 de todas as páginas do MERGE, máscaras, relatório e manifesto. |
| Nível II | `TO_MERGED_NIVEL_II/<capítulo>/` | Somente páginas transparentes candidatas efetivamente alteradas; máscaras e relatório da execução candidata. |
| Consolidado | `TO_MERGED_CONSOLIDADO/<capítulo>/json/` | Manifesto de referências que define a imagem vigente para cada página, sem uma cópia completa adicional. |
| Nível III | `TO_MERGED_NIVEL_III/<capítulo>/json/` | Manifesto e relatório de candidatos a balões estilizados. |

Os nomes antigos `MERGED_NIVEL_I/II/III` são aceitos somente como fallback de
leitura quando a pasta canônica ainda não existe. Novas gravações usam os
nomes `TO_MERGED_*`.

## Nível II: seleção e publicação

A seleção de páginas transparentes vem do relatório vinculado ao manifesto do
Nível I. A interface da tabela permanece organizada por capítulo e expõe a
quantidade de páginas candidatas; ao executar um capítulo, o worker recebe
somente os nomes das páginas candidatas. O processamento confere os nomes com
as imagens do MERGE e falha fechado diante de entradas ausentes ou inválidas.

O worker não salva imagem para uma página candidata se nenhum pixel mudou.
Quando há mudança visual, a composição final da página é salva sob
`TO_MERGED_NIVEL_II/<capítulo>/clean/`. Portanto, `clean_artifacts` lista
somente os arquivos adicionais realmente produzidos; `pages_total` e
`candidate_source_artifacts` descrevem o conjunto candidato processado. O
manifesto continua registrando o MERGE e a proveniência do Nível I completos.

## Consolidado virtual

O manifesto do consolidado registra uma seleção para cada imagem oficial:

- página candidata com saída alterada no Nível II: usa o arquivo do Nível II;
- demais páginas, inclusive candidatas sem alteração visual: usa o arquivo do
  Nível I.

Cada seleção guarda a origem e o SHA-256 da imagem. O resolvedor de artefatos
valida o hash ao entregar a imagem ao Nível III ou à revisão visual. O estado
consolidado só é atual quando os hashes dos manifestos I/II, os arquivos
selecionados e a lista de fontes correspondem aos dados atuais. A consolidação
é reconstruída após execuções bem-sucedidas de Nível I e II; Nível III também
pode materializá-la se estiver ausente ou desatualizada.

Esse desenho preserva o capítulo completo para análise sem armazenar outra
cópia de cada imagem do Nível I. O armazenamento incremental do Nível II fica
limitado às páginas transparentes que foram realmente modificadas.

## Nível III: análise de balões

O Nível III analisa as imagens resolvidas pelo consolidado, nunca imagens
brutas de `02_MERGE`. O MERGE e seu manifesto ainda são consultados para
validar proveniência e integridade, mas não são a entrada visual do detector.
O detector percorre recortes verticais sobrepostos para preservar detalhes em
páginas altas e registra candidatos com caixas e evidências para revisão.
As categorias experimentais incluem cor decorativa, gradiente suave e
contorno irregular. A etapa não altera pixels e seus candidatos exigem
validação visual.

O manifesto do Nível III vincula a execução aos hashes de Nível I, Nível II
vigente (quando válido), consolidado e manifesto do MERGE. A API de revisão
serve apenas páginas referenciadas pelo relatório concluído e obtidas pelo
resolvedor do consolidado.

## Validação

Cobertura automatizada inclui seleção de imagens candidatas, publicação
somente de saídas alteradas, fallback virtual para páginas do Nível I,
preferência por resultados válidos do Nível II, invalidação por alteração de
manifesto e resolução de imagens para análise/revisão. Foram executados os
testes focados de consolidação, Níveis I–III, rotas e contrato arquitetural de
limite de 200 linhas.
