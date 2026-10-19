# Auditoria técnica: migração definitiva das pastas Texto Off

**Data:** 18/10/2026

**Branch:** `develop`

**HEAD observado:** `cbc7d4b8`

**Escopo:** levantamento estático do código, manifests, testes e comparação somente leitura dos espelhos em `FominhaData/output/comix/Gazing at you`.

**Resultado:** auditoria documental; nenhum código, imagem ou manifesto operacional foi alterado. Nenhum tratamento foi executado.

## 1. Conclusão executiva

A migração ainda **não está pronta para descontinuar `TO_MERGED_*` nem para desligar o mecanismo de espelhamento**.

Fatos comprovados no código:

- `artifact-migration-registry.json` define `migration_mode=dual_write`, `dual_write_enabled=true` e `read_authority=legacy`. Os cinco pares registrados são Auto-Cleaner, Mapear, entrada consolidada do Mapear, Bubble Sommelier e Nível II. Todos estão `validated: false` e `migration_status: mapped`.
- Os estágios gravam nos caminhos registrados como `legacy_path`; após a publicação, `mirror_stage_chapter()` copia a árvore para `target_path` com `shutil.copytree(..., copy_function=shutil.copy2)`. Leitores selecionam a autoridade do registry, atualmente o lado legado.
- As pastas novas não são uma autoridade uniforme: `01_AUTO_CLEANER` pode ser usada pelo Nível I quando `CENTRAL_V2_LEVEL1_NUMBERED=1`, enquanto os demais leitores ainda podem selecionar o caminho legado pelo registry. Esse modo também não executa o espelhamento normal do Nível I.
- Há leituras literais fora do resolver comum, por exemplo `BUBBLE_SOMMELIER` em `bubble_sommelier/artifacts.py`, `MERGED` em `manifests.py` e nomes de estágio em `central_v2/runtime/textoff/README.md`/ferramentas de comparação. Os alias físicos `MERGED_NIVEL_I/II/III` também são aceitos pelo resolver.
- Manifests centrais em geral usam referências internas relativas e SHA-256, mas guardam nomes de estágio e caminhos relativos que hoje incluem `TO_MERGED_*`. Manifests e provas dos tratamentos especiais também persistem alguns caminhos absolutos. Uma renomeação exige compatibilidade de leitura; o hash do conteúdo não muda com a mudança de diretório, mas o resolvedor e as verificações de proveniência podem deixar de localizar ou aceitar o artefato.

### Comparação dos espelhos no conjunto observado

Foi executada apenas a comparação de leitura `validate_stage_chapter()` nos capítulos existentes em `Gazing at you`; ela compara caminhos, tamanhos e SHA-256, sem escrever artefatos.

| Estágio registrado | Capítulos | Resultado | Diferenças observadas |
|---|---:|---|---|
| Auto-Cleaner (`TO_MERGED_NIVEL_I` → `01_AUTO_CLEANER`) | 65 | 63 `MATCH`, 2 `MISMATCH` | Capítulos 1 e 16: somente `.DS_Store` foi reportado como diferente; os arquivos funcionais comparados coincidiram. |
| Nível II (`TO_MERGED_NIVEL_II` → `05_AUTO_CLEANER_TRANSPARENCIA/BASICA`) | 4 | 3 `MATCH`, 1 `MISSING_TARGET` | Capítulo 6 não possui árvore-alvo. |
| Mapear (`TO_MERGED_NIVEL_III` → `02_MAPEAR`) | 65 | 65 `MATCH` | Nenhuma diferença reportada. |
| Consolidado de entrada (`TO_MERGED_CONSOLIDADO` → `02_MAPEAR/INPUT_CONSOLIDADO`) | 65 | 64 `MATCH`, 1 `MISMATCH` | Capítulo 1: somente `.DS_Store` foi reportado como diferente. |
| Bubble Sommelier (`BUBBLE_SOMMELIER` → `03_BUBBLE_SOMMELIER`) | 65 | 65 `MATCH` | Nenhuma diferença reportada. |

Os estados no registry continuam `validated: false`; a comparação acima é evidência local para uma obra, não uma validação da biblioteca completa. O comparador inclui `.DS_Store` na árvore e por isso pode marcar diferença de metadado do macOS como `MISMATCH`.

## 2. Inventário de diretórios

Os caminhos abaixo são relativos a `FLUXO_SECUNDARIO/04_TEXTO_OFF`, exceto quando indicado. “Pode descontinuar” significa a pasta legada específica, após migrar leitores e preservar histórico; não significa apagar dados nesta auditoria.

| Diretório | Status / autoridade atual | Escrita e conteúdo | Leitura / dependências | Cópia equivalente / decisão futura |
|---|---|---|---|---|
| `TO_MERGED_NIVEL_I` | Legado registrado e autoridade atual; exceção de leitura/escrita por configuração numerada | Cleaner V2 Nível I: `clean/`, máscaras e JSON/manifests | Nível II, consolidação, Mapear, transparência, Sólidos e tratamentos especiais | Espelhado em `01_AUTO_CLEANER`. **Não** descontinuar antes de migrar leitores e o modo `CENTRAL_V2_LEVEL1_NUMBERED`. |
| `01_AUTO_CLEANER` | Novo alvo do registry; não é a autoridade geral atual | Cópia de espelho do Nível I; também é destino no modo numerado | Pode ser lido pelo modo numerado e por chamadas explícitas ao caminho novo | Cópia A. Descontinuável depois de promover a autoridade e encerrar o modo legado/dual-write. |
| `TO_MERGED_NIVEL_II` | Legado registrado e autoridade atual | Nível II/Glass: relatórios, máscaras e somente saídas alteradas | Consolidação, consultas/comparação e reprocessamento Combo Turbo; usa MERGE, artefatos do Nível I e proteções do Check/catálogo | Espelhado em `05_AUTO_CLEANER_TRANSPARENCIA/BASICA`. **Não** descontinuar enquanto os consumidores resolverem esse estágio pelo registry. |
| `05_AUTO_CLEANER_TRANSPARENCIA/BASICA` | Novo alvo do Nível II | Espelho do Nível II; Combo Turbo também usa o caminho de saída novo ao executar Glass isolado | Comparador em sombra; não é a autoridade geral enquanto `read_authority=legacy` | Cópia A. Capítulo 6 está sem alvo no conjunto medido. |
| `TO_MERGED_NIVEL_III` | Legado registrado e autoridade atual | Mapear: relatórios e manifest de análise estilizada, sem alterar a imagem de entrada | Check, Sommelier (incorporação de resultados), consultas e endpoint de imagem | Espelhado em `02_MAPEAR`. **Não** descontinuar antes de migrar leitores, fontes persistidas e testes. |
| `02_MAPEAR` | Novo alvo; não é a autoridade geral atual | Espelho dos artefatos de Mapear | Leitura observacional/comparações e consumidores com caminho explícito | Cópia A. Comparação dos 65 capítulos observados resultou em `MATCH`. |
| `TO_MERGED_CONSOLIDADO` | Legado registrado e autoridade atual; artefato intermediário | Manifesto por página; páginas vindas do Nível II (ou Combo Turbo) são materializadas em `clean/`; páginas do Nível I são resolvidas por referência | Entrada direta do Mapear, montagem do Consolidado Final, tratamentos, Combo Turbo, comparação e APIs | Espelhado em `02_MAPEAR/INPUT_CONSOLIDADO`. **Não** descontinuar: é nó central de dependência e origem persistida em manifests. |
| `02_MAPEAR/INPUT_CONSOLIDADO` | Novo alvo de entrada intermediária, sob a árvore do Mapear | Cópia espelhada do consolidado intermediário | Mapear/endpoint de imagem e comparação em sombra | Cópia A; não é o relatório de saída do Mapear. 64/65 capítulos deram `MATCH`; cap. 1 divergiu somente por `.DS_Store`. |
| `BUBBLE_SOMMELIER` | Legado registrado, autoridade atual e caminho literal do helper próprio do Sommelier | Runtime grava `report.json` e `crops/`; incorpora dados do Mapear ao relatório | Check, consultas, revisão e resolução de crops | Espelhado em `03_BUBBLE_SOMMELIER`. Há leitor/writer direto fora de `stage_chapter`; precisa de migração explícita. |
| `03_BUBBLE_SOMMELIER` | Novo alvo no registry | Cópia do report e dos crops | Comparação em sombra; leitores próprios ainda montam `BUBBLE_SOMMELIER` diretamente | Cópia A; 65/65 capítulos deram `MATCH`. |
| `02_RECONHECER_TRANSPARENTES` | Estágio novo independente; sem dual-write | Relatório de reconhecimento derivado do diretório Nível I | Adaptador de sugestões para Auto-Cleaner Check | Não tem par legado registrado. Preservar como estágio independente; não confundir com as máscaras/relatório de transparência do Nível I. |
| `04_AUTO_CLEANER_CHECK` | Estágio independente novo | Manifesto de decisões aprovadas, snapshot imutável de imagens revisadas e estado de revisão | Nível II usa proteções aprovadas; Sólidos e tratamentos especiais consomem decisões; frontend acessa via APIs | Sem cópia legado/novo no registry. Preservar identidades, aprovações, descartes e snapshots. |
| `RESIDUE_OCCURRENCES` | Estágio auxiliar independente, `dual_write: false` | Manifesto versionado de ocorrências/caixas, tipos, origens e referências | Check e fallback de proteções manuais do Nível II | Sem cópia. Não é substituto do Check; as relações futuras no registry são declarativas. Preservar manifest histórico. |
| `05_AUTO_CLEANER_SOLIDOS` | Estágio independente | Prévia `clean/`, máscara e `solid-white-manifest.json`; saída `preview_only` | Comparação, visão geral e Combo Turbo; entrada é decisão aprovada do Check e imagem do Nível I/snapshot do Check | Sem par `TO_MERGED_*`. Não descartar a prévia como se fosse duplicata do estágio automático. |
| `COMBO_TURBO` | Estágio independente, fora dos cinco pares de migração | Manifesto de execução e publicações candidatas; pode gerar/atualizar artefatos de Sólidos/Glass isolados | Consolidação e publicação validam o estado, os hashes e as saídas | Sem equivalente `TO_MERGED_*`. Deve permanecer no grafo de migração, embora não esteja no desenho resumido inicial. |
| `SPECIAL_TREATMENTS` | Projeção independente do Check | `special-treatments-manifest.json` com decisões, tratamento, estado e referência/hash do Check | Execução, revisão, reexecução e restauração | Sem par legado. O caminho relativo do Check é validado por consumidores. |
| `06_PINCEL/{DEGRADE,ARTISTICO,SUAVE}` | Estágios independentes e persistentes | Inputs/snapshots, manifests, masks, outputs, relatórios e arquivos arquivados de reexecução | Revisão, composição, recuperação e promoção para o Consolidado Final | Sem cópia `TO_MERGED_*`. Cópias internas são parte da autoria/histórico, não espelhos automáticos. |
| `07_CONSOLIDADO_FINAL` | Autoridade independente para a imagem final consumida/exportada | Uma imagem física por página, `final-manifest.json` e histórico de substituição | Exportador, visualização, tratamentos e restauração | Sem equivalente `TO_MERGED_*`. Não é redundante por definição: é contrato de saída final. |
| `BACKUP_PREVIAS_SOLIDOS` | Presença observada em `Gazing at you`; sem writer identificado na busca de código | Conteúdo e processo de criação não determinados | Nenhum consumidor identificado no código pesquisado | **A investigar.** Não classificar como lixo nem apagar sem atribuir origem/consumidor. |
| `SPECIAL_PAGE_RESTORE_BACKUPS` | Fora de `04_TEXTO_OFF`, criado pelo fluxo explícito de restauração | Backup transacional de restauração | Auditoria/recuperação do estado anterior | Categoria F, não é `BACKUP_PREVIAS_SOLIDOS`. Preservar segundo a política de retenção de restauração. |
| `MERGED_NIVEL_I/II/III` e `MERGED` | Compatibilidade anterior/legada adicional | Não são destinos dos cinco pares atuais | `stages.py` pode resolver aliases `MERGED_NIVEL_*`; `manifests.py` lê diretamente `04_TEXTO_OFF/MERGED` | Investigar presença e capítulos dependentes. São distintos de `TO_MERGED_*` e não podem ser removidos pela migração dos cinco pares sem análise. |
| `reports/experimentos/textoff_especiais_v2/{run_id}` | Staging transitório | Pré-visualizações de tratamentos e execuções isoladas | Comparação/overview | Não pertence aos pares persistentes; política de retenção de runs deve ser auditada separadamente. |

### Outros caminhos de entrada e consumidores externos

- `FLUXO_SECUNDARIO/02_MERGE/<capítulo>` é a fonte de imagens oficiais para Nível I, Nível II, Bubble Sommelier e várias validações; está fora de `04_TEXTO_OFF` e permanece necessário.
- `IMG/<capítulo>` contém identidade/manifestos de capítulo e é consultado para selecionar MERGE válido.
- `processamento/exportacao/exportador.py:7-9` exporta a partir de `07_CONSOLIDADO_FINAL`; não usa os diretórios `TO_MERGED_*`, mas deve continuar como regressão de integração.
- `dev/tools/textoff_prepare_comparison.py:32-53` lê MERGE e grava uma cópia experimental em `MERGED_NIVEL_I/II` fora da obra oficial. É ferramenta de experimento, não consumidor de produção.
- A busca no frontend não encontrou nomes físicos `TO_MERGED_*` nem caminhos de disco dos estágios: a interface chama APIs. Isso não elimina os contratos de API, rotas e testes que alimentam esses endpoints.

## 3. Matriz de dependências no código

Classificações: `[READ]`, `[WRITE]`, `[COPY]`, `[MANIFEST]`, `[RESTORE]`, `[API]`, `[FRONTEND]`, `[TEST]`, `[CONFIG]`.

| Arquivo / função | Operação | Origem → destino | Comportamento relevante |
|---|---|---|---|
| `artifact-migration-registry.json:3-7,28-185` | `[CONFIG]` | 5 pares legado → alvo | Dual-write habilitado, leitura oficial `legacy`, todos os pares persistentes marcados `validated: false`. |
| `stages.py:8-24,66-121` `stage_root`, `_resolve_stage_chapter` | `[CONFIG][READ][RESTORE]` | Identificador → caminho físico | Resolve registry, modo `CENTRAL_V2_LEVEL1_NUMBERED`, aliases `MERGED_NIVEL_*` e paths de `06_PINCEL`/`07_CONSOLIDADO_FINAL`; leitura de Pincel pode mover alias antigo via `os.replace`. |
| `artifact_migration.py:38-69,100-133,147-166` | `[READ][COPY][CONFIG]` | `legacy_path` → `target_path` | Resolver nunca substitui silenciosamente o lado selecionado; espelho substitui a árvore alvo por cópia temporária de `copytree/copy2`. |
| `artifact_validation.py:33-73,76-159,174-204` e `artifact_shadow_read.py:15-84` | `[READ][MANIFEST]` | árvore antiga ↔ nova | Compara inventários, tamanhos e SHA-256; registra observação em log, não fornece dados ao consumidor. `.DS_Store` participa da comparação. |
| `execution.py:17-80` `execute_merged` | `[READ][WRITE][COPY]` | `02_MERGE` → `TO_MERGED_NIVEL_I` → `01_AUTO_CLEANER` | Executa Cleaner V2; grava primeiro na árvore legado/canônica configurada e espelha salvo o modo numerado. |
| `level2.py:41-69,104-153` `execute_merged_level2` | `[READ][WRITE][COPY][MANIFEST]` | MERGE + Nível I + proteções → `TO_MERGED_NIVEL_II` → BASICA | Persiste referência e hash do Nível I, fonte/hash da proteção e artefatos; espelha, reconstrói consolidado e baseline final. |
| `consolidated.py:29-76` `rebuild_consolidated` | `[READ][WRITE][COPY][MANIFEST]` | Nível I + Nível II + Combo → `TO_MERGED_CONSOLIDADO` → `02_MAPEAR/INPUT_CONSOLIDADO` | Copia saídas selecionadas de Nível II (ou Combo quando aplicável), referencia demais imagens e hashes de manifests. |
| `level3_styled.py:83-140` `_analyze_chapter`, `execute_level3` | `[READ][WRITE][COPY][MANIFEST]` | Consolidado + manifests Nível I/MERGE → `TO_MERGED_NIVEL_III` → `02_MAPEAR`; Nível I → reconhecimento transparente | Worker analisa caminhos absolutos do input temporário; relatório registra hashes dos manifests e imagens; publica reconhecimento separado. |
| `bubble_sommelier/artifacts.py:11-28`, `execution.py:31-96`, `mapear_results.py` | `[READ][WRITE][COPY][MANIFEST]` | MERGE + relatório Mapear → `BUBBLE_SOMMELIER` → `03_BUBBLE_SOMMELIER` | Helper próprio monta fisicamente o caminho legado; a execução enriquece report e chama espelho. |
| `auto_cleaner_check_sources.py:20-30,39-105,108-129`; `auto_cleaner_check_manifest.py:22-67` | `[READ][WRITE][MANIFEST]` | Mapear, Sommelier, reconhecimento e resíduos → Check | Snapshot guarda paths relativos e SHA das fontes; Check persiste decisões e snapshots de imagem. No worktree observado há mudança local pendente de associação/deduplicação de candidatos; foi preservada, não alterada por esta auditoria. |
| `level2_manual_protection.py:43-85` | `[READ][MANIFEST]` | Check aprovado, senão `RESIDUE_OCCURRENCES` → Nível II | Check tem precedência quando existe; proveniência registra caminho relativo e SHA. Alteração de path não deve silenciosamente trocar a fonte. |
| `solid_stage.py:18-47,49-97`; `combo_turbo/execution.py:20-55` | `[READ][WRITE][MANIFEST]` | Aprovações Check + Nível I/snapshot → Sólidos; Combo pode escrever/atualizar saída isolada | Manifesto indica `preview_only`; Combo mantém validação e reaproveitamento por hashes. |
| `special_treatments_manifest.py:22-117`, inputs/outputs em `special_*_input.py` e `special_*_output.py` | `[READ][WRITE][MANIFEST][RESTORE]` | Check → `SPECIAL_TREATMENTS` → `06_PINCEL` | Manifesto especial amarra hash e path relativo do Check; alguns outputs de Pincel persistem paths absolutos dos manifests de origem. |
| `final_consolidated.py:62-115,117-180`, `final_consolidated_manifest.py:12-32` | `[READ][COPY][WRITE][MANIFEST][RESTORE]` | Consolidado intermediário + Pincel → `07_CONSOLIDADO_FINAL` | Copia imagem final por página; guarda hashes/origem e histórico. Escrita em caminho `TO_MERGED_*` pode quebrar a montagem baseline ou restauração se não houver resolver de histórico. |
| `special_page_restore.py:15-19,25-61,110-165`, `special_page_restore_source.py` | `[READ][COPY][RESTORE]` | Pincel/histórico + Check + final → backup e restauração | Inspeção é read-only; restauração confirmada cria backup sob raiz da obra. Requer hashes e linhagem de entrada íntegros. |
| `routes/textoff_merged_router.py:32-85`, `routes/textoff_residue_occurrences.py:21-25,160-180` | `[API]` | Interface → rotas → orquestração | Endpoints não devem codificar autoridade física; manter contratos enquanto o resolver muda. |
| `frontend/_app/api/residue_occurrences.js` e `frontend/texto_off/comparison/*` | `[FRONTEND][API]` | UI → `/api/textoff/...` | Nenhum caminho de pasta físico localizado na interface; testes cobrem estado, composição e apresentação do catálogo. |
| `processamento/exportacao/exportador.py:7-9` | `[READ]` | `07_CONSOLIDADO_FINAL` → exportação | Consumidor fora da orquestração principal, não migrar junto com pastas `TO_MERGED_*`. |
| `dev/tools/textoff_prepare_comparison.py:19-75` | `[READ][COPY][TEST]` | MERGE oficial → staging experimental | Cria snapshot experimental e pastas antigas `MERGED_NIVEL_*` fora da obra oficial. |

### Testes e contratos de frontend

Os testes com maior dependência de nomes físicos incluem `test_textoff_artifact_dual_write.py`, `test_textoff_artifact_migration_registry.py`, `test_textoff_artifact_validation.py`, `test_textoff_artifact_authority.py`, `test_textoff_artifact_authority_safety.py`, `test_textoff_artifact_shadow_read.py`, `test_textoff_numbered_level1_output.py`, `test_textoff_consolidated.py`, `test_textoff_level2_*`, `test_bubble_sommelier_mapear_results.py`, `test_auto_cleaner_check*`, `test_combo_turbo_*`, `test_final_consolidated.py` e `test_special_page_restore*`. Frontend: `central_v2_frontend/residue_catalog_*` e `textoff_merged.test.mjs`.

Esses testes não são apenas fixtures neutras: alguns afirmam escrita dupla, autoridade legado, nomes de saída e compatibilidade. A futura migração deverá substituir os contratos intencionalmente e manter casos explícitos de leitura histórica. Nenhum teste foi executado nesta auditoria.

## 4. Manifests e compatibilidade histórica

| Manifesto / prova | Referências encontradas | Impacto de renomeação |
|---|---|---|
| `clean-manifest.json` Nível I | Nomes relativos de `clean/`, máscaras/JSON, `source_stage: MERGE`, páginas e hashes de fonte/relatório. | Hashes de conteúdo podem continuar válidos se bytes não mudarem; consumidores localizam os artefatos pelo diretório do estágio e verificam layout. `source_stage` não é caminho absoluto. |
| `level1-balloon-report.json` | Identidade da página, geometria e classificação/decisões; referenciado a partir do manifest por artefato JSON. | Preservar nome relativo e contrato. Relatório separado de `02_RECONHECER_TRANSPARENTES`. |
| Reconhecimento transparente | Relatório versionado derivado do diretório de Nível I; Check registra path relativo ao estágio e SHA. | Mover o Nível I não deveria alterar o SHA do report, mas o reconhecedor e os snapshots do Check precisam resolver o novo caminho. |
| Nível II `clean-manifest.json` | `source_stage` de Nível I, hashes de manifests, refs relativas de `clean/` e `mask/`, hash e path relativo da fonte de proteção (`CHECK` ou `RESIDUE_OCCURRENCES`). | Mover Nível I/II requer resolver os nomes de estágio persistidos, preservar proteção exata e não substituir Check por catálogo legado em caso de ausência. |
| Consolidado intermediário | `selected_from` como identificador do estágio, artefato relativo `clean/...`, SHA por página e hashes de manifests Nível I/II/Combo. | `selected_from` atualmente inclui identificadores `TO_MERGED_*`; compatibilidade do parser é necessária. A imagem selecionada de Nível II é materializada no próprio consolidado. |
| Mapear manifest/report | `source_stage` consolidado, hash de MERGE, Nível I, Nível II, consolidado e cada imagem; artifact/report refs relativos. | Comparação de atualidade reabre manifests pela seleção de estágio. O report da análise temporária também recebe caminhos absolutos no request do worker, que não é o mesmo que caminho durável do manifest. |
| Auto-Cleaner Check | `source_snapshot` guarda path relativo que aponta hoje a `TO_MERGED_NIVEL_III` e `BUBBLE_SOMMELIER`, status e SHA; decisões guardam IDs, caixas, origens e referências. `images/<page>` é snapshot relativo com SHA. | O snapshot histórico de imagem permanece auto-contido; path de fonte aponta para layout legado e precisa de interpretador de alias ou versão do schema. Hash da fonte não muda ao mover. |
| `residue-occurrences-manifest.json` | Obra/capítulo/página, caixas, tipo, origem e `source_references`; há strings de estágio/origem, sem cópia de imagem. | Não migrar como se fosse espelho: é fonte autoral de ocorrências. Atualizar somente interpretação de referências, sem regravar históricos na migração inicial. |
| `special-treatments-manifest.json` | `source_check.path` relativo à raiz da obra e SHA do Check; projeção de decisões, status e IDs. | Relativo à raiz, mas inclui caminho físico atual do Check; manter compatibilidade com o schema e com status de processamento. |
| Manifests Degradê/Artístico/Suave | Artefatos internos relativos e hashes; alguns registros persistem caminhos absolutos para manifests Check/Special ou entradas/provas retornadas pelo resolver. Arquivos `input/<run_id>/<page>` e `archive/<run_id>/...` sustentam reexecução/recuperação. | Caminhos absolutos são risco concreto ao mover dados entre raízes/provider; caminho relativo e hash não são equivalentes a um snapshot disponível. Precisa compatibilidade/resolução e testes de restauração. |
| `final-manifest.json` | Arquivo final é basename da página; SHA, origem, tratamento, `input_sha256`/origem e hash do consolidado intermediário. Histórico mantém registros supersedidos. | O arquivo final é autônomo por página, mas origem e hash do manifest intermediário precisam ser resolvidos para provar linhagem. Histórico nem sempre conserva bytes anteriores; snapshots do Pincel/arquivo de run têm sua própria lógica. |
| Execuções de restauração | Proposta amarra hashes atual/final/Check/Special/source; backup em `SPECIAL_PAGE_RESTORE_BACKUPS`. | O caminho dessa pasta é fora de `04_TEXTO_OFF`; preservação de backups e resolução da entrada automática são requisitos de rollback. |

**Conclusão sobre manifests históricos:** muitos são relocáveis em tese por conterem referências relativas e hashes, mas isso **não foi provado para todos os schemas/capítulos**. Outras estruturas guardam caminho absoluto ou identificador físico legado. Não reescrever manifests históricos. Antes do corte, inventariar versões antigas reais e testar leitura/restauração em cópia isolada, inclusive formatos planos e `MERGED_NIVEL_*` anteriores.

## 5. Duplicação de imagens e espaço

### Evidência e limite de medição

O texto da solicitação fornece um levantamento anterior de 30.701 PNGs, 16,31 GB lógicos, 14.553 grupos idênticos e 10,90 GB de duplicação lógica. Esses números não foram encontrados como relatório versionado no repositório e são tratados como evidência prévia fornecida, não como resultado desta auditoria.

Na leitura atual de `Gazing at you/FLUXO_SECUNDARIO/04_TEXTO_OFF`, foram contados novamente 30.701 PNGs, totalizando **17.509.159.445 bytes lógicos (17,509 GB decimais)**. `du -sk` reportou 17.213.984 KiB para a árvore completa de `04_TEXTO_OFF`. A diferença em relação aos 16,31 GB indica que a medição anterior pode usar outro snapshot/escopo ou que os arquivos mudaram; não foi atribuída causa.

O volume aparece montado como APFS. `diskutil info` não pôde consultar o framework DiskManagement neste ambiente. O somatório de `st_blocks`/`du` não identifica com segurança extents compartilhados por APFS Clone. Assim, o ganho **físico** recuperável não foi quantificado; números de hashes/tamanho lógico não devem ser apresentados como espaço que será liberado.

### Classificação

| Classe | Exemplos verificados | Avaliação |
|---|---|---|
| **[A] Espelho legado/novo** | Cinco pares do registry; `copytree`/`copy2` replica árvores; comparação real encontrou arquivos funcionais idênticos nos pares do conjunto medido. | Duplicação lógica removível somente após migração dos leitores e validação por capítulo. Alocação física APFS não confirmada. |
| **[B] Snapshot de revisão** | `04_AUTO_CLEANER_CHECK/<capítulo>/images/` criado por `freeze_check_images`; snapshots são imutáveis e associados ao hash da decisão. | Cópia intencional para manter o conteúdo revisado quando a fonte muda; não remover junto com mirrors. |
| **[C] Intermediário necessário hoje** | Nível II copia páginas alteradas para `TO_MERGED_CONSOLIDADO`; Combo pode fornecer imagens selecionadas. Mapear usa imagem consolidada resolvida. | Materialização permite referências e consumo atuais. Uma alternativa por referência só é segura após alterar todos os resolvers/leitores e provar integridade. |
| **[D] Consolidado final** | `rebuild_final_baseline` copia uma imagem por página para `07_CONSOLIDADO_FINAL`; promoções de Pincel copiam nova saída. | Contrato de consumo/exportação e recuperação, não mirror redundante por definição. |
| **[E] Sem consumidor identificado** | `BACKUP_PREVIAS_SOLIDOS` no dado observado; não foi localizado writer/reader de código com esse nome. | Autor e política desconhecidos. Não apagar; investigar proveniência, outros repositórios, scripts externos e frequência de acesso. |
| **[F] Histórico/rollback** | `06_PINCEL/.../input`, `archive/`, `superseded_results`, snapshots de autoria, `SPECIAL_PAGE_RESTORE_BACKUPS` fora de `04_TEXTO_OFF`; também arquivo de decisão do Check. | Preservam evidência necessária a reexecução/restauração. Têm consumidores explícitos e não equivalem a cópias sombra. |
| **[G] Outros** | `.DS_Store`; diretórios temporários `.shadow-*`, `.backup-*`, staging de tratamentos e Combo Turbo; crops de Sommelier. | `.DS_Store` causa falsos `MISMATCH` no comparator e não é artefato funcional. Staging/backup temporário precisa de política de limpeza própria. Crops são artefatos referenciados por identity e SHA, não descartáveis sem validar o report. |

O número prévio de “14.553 grupos idênticos” não foi repartido entre as classes A–G nesta auditoria. A comparação do registry comprova igualdade entre os pares mapeados, mas não atribui cada hash igual em pastas diferentes a um mirror: páginas duplicadas, snapshots e outputs finais também podem ter bytes iguais.

## 6. Riscos de migração

| Risco / componente | Dependência e impacto possível | Severidade | Mitigação / teste necessário |
|---|---|---|---|
| Cutover para novo caminho antes de validar conteúdo | Registry continua `read_authority=legacy`; quatro pares marcados não validados. Nível II cap. 6 sem alvo no conjunto medido. | **Crítica** | Produzir relatório por capítulo; corrigir ausências/divergências antes de alternar autoridade; bloquear leitores quando o alvo declarado faltar. |
| Modo numerado de Nível I | `CENTRAL_V2_LEVEL1_NUMBERED=1` direciona diretamente para `01_AUTO_CLEANER` e pula o espelho, fora da autoridade global configurada. | **Alta** | Localizar uso operacional/env nos deployments; definir se vira configuração canônica ou é removido só após migração validada. Testar cada modo. |
| Helper Sommelier com path literal | `artifacts.py` monta `BUBBLE_SOMMELIER`; report/crops, APIs e Check continuam lendo o legado mesmo com alvo `03_BUBBLE_SOMMELIER`. | **Alta** | Migrar helper, rotas e consumers em conjunto; testar report e crop identity/hash em árvores antigas e novas. |
| Nomes físicos gravados em manifests | `source_stage`, `selected_from` e `source_snapshot.path` podem carregar `TO_MERGED_*`; parsers restringem valores aceitos. | **Alta** | Criar compatibilidade explícita por schema/alias sem alterar manifest histórico; abrir manifests antigos em fixture real e validar hash/reprodução. |
| Caminhos absolutos em proveniência Pincel | Alguns outputs persistem paths de Check/Special/inputs/proofs; restauração os reabre e compara hashes. | **Alta** | Determinar quais campos persistidos são absolutos em cada versão; usar resolver compatível e preservar backup; testar migração de raiz/provider e restore de caso histórico. |
| Snapshots e aprovações do Check | Imagem e decisão estão ligadas por hashes, IDs e source snapshots. Perder o snapshot pode trocar a imagem de referência da revisão. | **Alta** | Não mover/excluir Check; testar abrir revisão histórica, Sólidos e Nível II com Check presente/ausente e catálogo legado. |
| Alteração de interpretação das proteções Nível II | Check tem precedência; sem Check usa `RESIDUE_OCCURRENCES`. Uma falta de path pode alterar regiões protegidas. | **Crítica** | Sem fallback silencioso; comparar `protection_source`, IDs, ROIs, hashes e pixels protegidos antes/depois em cópia isolada. |
| Consolidação e resultados históricos | Conversão de `selected_from`/manifests pode invalidar validade do consolidado, mapas, promoções ou seleção por página. | **Alta** | Recalcular atualidade somente em cópias, provar seleção e SHA de cada página, garantir Combo Turbo e páginas sem mudança. |
| Restauração e reexecução Pincel | Histórico final pode não conter bytes anteriores; restauração depende de snapshots/artifacts arquivados e vários manifests. | **Crítica** | Casos de restauração real com input automático e reexecução; rollback documentado antes de cortar legacy. |
| `MERGED_NIVEL_*` e `MERGED` anterior | São compatibilidades distintas de `TO_MERGED_*`; consumers e `dev/tools` ainda podem usá-las. | **Média/Alta** | Inventariar diretórios e capítulos históricos presentes; decidir política e testar esses formatos separadamente. |
| Consumidor externo de `07_CONSOLIDADO_FINAL` | Exportação fora da orquestração depende do contrato final. | **Alta** | Manter o destino final e validar exportação como regressão; não associar a migração de aliases ao corte. |
| Testes codificam dual-write atual | Desligar cópia sem atualizar testes de contrato pode tanto quebrar CI quanto remover garantias sem substituição. | **Média** | Substituir testes de dual-write por testes de escrita canônica, migração/alias, integridade e ausência de escrita legada. |
| Duplicação/APFS | Liberar dados pela igualdade lógica pode apagar snapshots ou blocos compartilhados, com ganho físico diferente do previsto. | **Alta** | Fazer backup/retention plan; medir uso APFS com ferramenta compatível; só apagar por identidade e dependência verificadas, nunca por hash isolado. |
| Alterações pendentes no worktree | Existem mudanças locais no Check/frontend e backups não commitados no início do levantamento. | **Alta** | Foram preservadas. A implementação futura precisa reaplicar/auditar em worktree limpo sem descartar esse trabalho. |

## 7. Proposta incremental de migração

Ordem baseada nas dependências observadas, ainda sujeita a decisão de produto e implementação:

1. **Congelar o inventário e definir autoridade lógica.** Especificar nome lógico por estágio, caminho novo, aliases legados, política para o modo numerado e contrato para `MERGED_NIVEL_*`/`MERGED` anterior. Não mover dados.
2. **Validar os espelhos completos.** Comparar por capítulo e tipo de artefato com exclusões explícitas de metadados do SO; registrar `MATCH`, diferenças funcionais, ausências, tamanhos e SHA. Resolver o capítulo 6 e qualquer divergência funcional. Atualizar estado validado somente com evidência reproduzível.
3. **Adicionar leitura canônica com compatibilidade explícita.** Adaptar todos os consumidores listados — incluindo helper Sommelier, APIs, Mapear, Nível II, consolidado, Combo Turbo, Check e tratamento/restore. Compatibilidade consulta formato antigo mediante alias/schema declarado, sem fallback silencioso para outra autoridade.
4. **Cobrir manifests antes do corte.** Testar schemas atuais e amostras históricas de cada etapa, incluindo caminho absoluto/relativo, layout plano antigo, crops, fonte de proteção e entradas Pincel. Usar cópias isoladas e confirmar hashes e decisão reproduzida; não reescrever os manifests originais.
5. **Fazer leitura em sombra e comparar resultados.** Nova árvore passa a ser autoridade de leitura apenas em modo controlado; legado continua intacto para rollback. Medir integridade por artefato, imagens selecionadas, origens, fonte de proteção e resultados finais em capítulos de referência.
6. **Desligar dual-write depois de aceitação.** Só então gravar uma vez nos caminhos novos. Manter logger/telemetria de falha de resolução e instrução de rollback para apontar a autoridade anterior, sem apagar dados.
7. **Migrar/validar o acervo histórico.** Catalogar capítulos sem espelho, divergentes, alias antigos e paths absolutos. Migrar cópias em lote controlado com manifest de migração e SHA, mantendo a fonte legada inalterada durante a retenção de rollback. A estratégia para reescrever manifests históricos fica fora do corte inicial e exigiria versão/decisão própria.
8. **Descontinuar pastas legadas por etapas.** Após janela de uso e evidência de zero leitores, arquivar/remover cada par separadamente; não remover `MERGED_NIVEL_*`, `MERGED`, `BACKUP_PREVIAS_SOLIDOS` ou snapshots sem auditoria própria.
9. **Otimizar armazenamento depois da migração funcional.** Estudar APFS Clone/reflinks, cópia sob demanda ou referência física, comparar logical bytes com allocated/shared extents, medir exportação e restore; manter classe B/D/F até que seus contratos tenham substituto validado.

### Estratégia de rollback

- Preservar a árvore legado e manifests originais durante todo o período de cutover.
- Registrar por capítulo qual autoridade foi lida/escrita, hashes comparados e versão do código/registry.
- Reverter autoridade/configuração antes de considerar recópia; nunca sobrescrever a árvore anterior automaticamente durante rollback.
- Retomar o dual-write somente como medida temporária controlada e com comparação habilitada; evitar divergência entre dois lados sem relatório.
- Ensaiar restauração de imagem final, estado do Check, proteção Nível II e resultado Pincel em cópia isolada antes do corte geral.

### Plano de testes para implementação futura

- Integridade de arquivos por estágio, capítulo, tamanho e SHA, ignorando explicitamente `.DS_Store` sem ignorar artefatos funcionais.
- Ausência de escrita em `TO_MERGED_*` depois do cutover e resolução canônica com alvo ausente (falha explícita).
- Leitura de manifests históricos versionados e aliases antigos; caminhos relativos e absolutos; artefatos planos e organizados `clean/mask/json`.
- Igualdade de páginas selecionadas pelo consolidado, proveniência Mapear/Sommelier, Check snapshots/aprovações, fontes de proteção e pixels preservados pelo Nível II.
- Execução isolada de Sólidos/Glass/Combo Turbo, tratamentos Degradê/Artístico/Suave, promoção final, exportação, restauração e rollback.
- Capítulos completos de referência com casos sem alteração, com alteração, com páginas não candidatas, proteção manual, snapshots antigos, manifests faltantes e execuções interrompidas.
- Não executar essas provas em dados oficiais durante implementação; usar workspaces descartáveis e validar hashes das entradas antes/depois.

## 8. Pendências e decisão

- A comparação sobre `Gazing at you` cobre somente os cinco pares mapeados dessa obra e os capítulos existentes em cada origem; não substitui auditoria da árvore de todas as obras/providers.
- Os 14.553 grupos idênticos/10,90 GB são números informados como levantamento anterior; precisam de tabela reproduzível que associe hashes aos caminhos e classes A–G.
- O volume é APFS, mas extent sharing/clones físicos não foi medido; a consulta `diskutil info` falhou por indisponibilidade do framework. Não estimar espaço físico recuperável a partir de bytes lógicos.
- Não foi encontrada referência de código a `BACKUP_PREVIAS_SOLIDOS`; origem e leitores externos continuam em aberto.
- Os dados de teste `dev/tests` cobrem contratos, mas a existência e os schemas exatos de manifests históricos em toda a biblioteca não foram enumerados.
- Alterações locais estavam presentes: `auto_cleaner_check_sources.py`, arquivos do catálogo frontend, CSS, artefatos de backup e o relatório HTML previamente editado. Não foram sobrescritas nem limpas.

**Decisão desta auditoria:** manter os caminhos legados e o espelhamento. A descontinuação definitiva fica bloqueada até resolver a diferença de cobertura, identificar os caminhos absolutos persistidos, migrar os leitores diretos e executar validação/rollback em cópias isoladas. Este relatório não autoriza implementação, movimentação, exclusão ou regravação de artefatos.
