# Validação final M0 / M1 — PostgreSQL

**Data da revisão:** 2026-10-23
**Parecer:** **M0 APROVADO · M1 APROVADO para handoff ao M2 de desenho · M2 NÃO INICIADO**

## Resultado

O rastreio estático do M1 foi ampliado para registrar autoridade, produtores, leitores conhecidos, dependências indiretas e regras de aprovação/invalidação de cada contrato Onda 1. Também separa fatos observados, propostas arquiteturais e bloqueios de implementação/cutover. O detalhamento está em [m1_decisoes_arquiteturais.md](m1_decisoes_arquiteturais.md). Os dados de apoio estão no [inventário](m1_inventario.md), [catálogo JSON](m1_matriz_json.md), [matriz de diretórios](m1_matriz_diretorios.md), [matriz de dependências](m1_matriz_dependencias.md), [duplicações](m1_duplicacoes.md), [riscos](m1_riscos_pendencias.md) e [baseline](m0_baseline.md).

M1 está aprovado como diagnóstico e pacote de propostas para iniciar o desenho do M2. Esse parecer não aprova cutover de autoridade, alteração de writers, migração de dados ou eliminação de paths/arquivos. Esses atos dependem das decisões e critérios da seção “Bloqueios para implementação/cutover” no documento arquitetural.

## Critérios de aceite

- [x] Produtores e leitores mapeados para os contratos encontrados no código; readers/writers externos e manuais sem evidência foram explicitamente delimitados.
- [x] Contratos Onda 1 descritos com authority atual, artefatos, dependências e regras de aprovação/invalidação observadas.
- [x] Dependências de JSONs, `TO_*`, `IMG`, `02_MERGE`, staging, Reset, Combo e consumidores downstream identificadas.
- [x] Propostas documentadas para identidade de artefatos, retenção, deduplicação, substituição da autoridade JSON e imutabilidade de publicados.
- [x] Decisões comprovadas, propostas sujeitas a aprovação e bloqueios de cutover separados.
- [x] Parecer final: M0 APROVADO; M1 APROVADO para handoff ao M2 de desenho.

## Evidências quantitativas e de autoridade

- Cinco árvores `04_TEXTO_OFF` foram inspecionadas: quatro obras e a árvore de teste `mangago/Teste Candy YumYum`. São 2.285 JSONs TextOff, 25 nomes-base e 16 diretórios `TO_*` em quatro obras; a árvore de teste não contém `TO_*`.
- Catálogos físicos: 2.285 JSONs de TextOff (`m1_json_inventory.csv`), 147 manifests de origem `02_MERGE` (`m1_input_json_inventory.csv`) e 70 JSONs em 11 runs de staging especial (`m1_preview_json_inventory.csv`).
- SHA-256 cobriu 83.164 imagens nos roots `IMG`, `02_MERGE`, `04_TEXTO_OFF` e previews: 25.785 hashes distintos, 24.411 grupos duplicados, 57.379 ocorrências excedentes e 39.070.074.956 bytes (~36,38 GiB) de excedente teórico. Ver [m1_duplicacoes.md](m1_duplicacoes.md) e `m1_duplicate_image_groups.csv`. Hash igual não autoriza eliminação.
- A registry confirma cinco mappings persistentes em dual-write, todos com `read_authority=legacy` e `validated=false`. Check é `NEW_STAGE` filesystem; Ocorrências é auxiliar legacy marcada `NOT_APPLICABLE`; os previews são `TRANSIENT_PREVIEW` em staging. Nenhuma dessas classificações representa autoridade PostgreSQL.
- Foi comprovado leitor do consolidado final em `processamento/exportacao/exportador.py`. Foram identificados também readers de comparação, Reset, Mapear, Glass, Check, especiais e Combo. O código do repositório não comprova a ausência de readers em instalações antigas, scripts externos ou operação manual.

## Lacunas remanescentes e alcance do parecer

- Busca em `central_v2/` e `processamento/` encontrou `bubble_cleaner_flow.py` como writer legado para `ORIGINAL`, sem reader ativo encontrado para essa árvore. O helper `manifests.py::_clean_manifest` lê `MERGED`; `processamento/limpeza_baloes/textoff_level3*.py` é um fluxo NIVEL3 legado distinto de Mapear V2. Consumers fora do repositório continuam sem evidência verificável.
- A política de retenção, a identidade canônica entre obras parecidas, os prazos de rollback, o owner de cada consumidor externo e os critérios de cutover são escolhas arquiteturais; não podem ser decididos pela leitura do código.
- O plano-base v3 citado no histórico não foi localizado. Para esta validação, os critérios fornecidos pelo pedido atual foram usados como referência. Se v3 continuar sendo normativo, confirmar/registrar essa referência antes do cutover.

Essas lacunas foram incorporadas ao mapa como dependências explicitamente desconhecidas e não impedem o handoff de desenho do M2. Elas impedem iniciar implementação/cutover que altere autoridade ou remova legado até que owners e decisões estejam registrados.

## M0 — APROVADO

[m0_baseline.md](m0_baseline.md) registra branch, HEAD, alterações preexistentes, submódulo, itens ignorados relevantes, raiz operacional, registry e limites da inspeção. Nesta análise não houve tratamento, teste, migration, alteração de código, modificação de dados/imagens, exclusão, movimentação, commit ou push. Não há prova de restore integral nem backup global verificável; isso é requisito de implementação/cutover, não alteração do baseline.

## Recomendação

Encerrar o M1 com este parecer e iniciar o M2 somente no escopo de desenho arquitetural. Antes de qualquer implementação/cutover, registrar as decisões propostas e os owners/bloqueios listados em [m1_decisoes_arquiteturais.md](m1_decisoes_arquiteturais.md). Nenhuma atividade de M2 foi executada nesta análise.
