# Inventário e plano de migração documental — Limpeza de Balões

**Data do inventário:** 2026-10-16\
**Branch observada:** `develop`\
**Commit solicitado como referência para BL-13:** `cef3cd4227012f3ef9410587103eda6a8448e870`\
**Estado:** Lotes 1, 2, 3 e 4 executados conforme autorizacao. Dois HTMLs permanecem nos caminhos originais para revisao; nenhum arquivo foi excluido, convertido ou consolidado.

## Resultado inicial

O baseline reproduzivel no Git e de **124 arquivos rastreados sob `docs/`** na revisao observada. O numero 131 da versao anterior nao pode ser reproduzido: nao existe manifest salvo que identifique os sete itens adicionais daquela contagem, portanto foi erro de contagem e nao uma segunda base de migracao. No working tree atual ha **152 arquivos de documentacao nao ignorados** sob `docs/`: 124 rastreados e 28 nao rastreados, estes ultimos explicitamente inventariados no mapa como preexistentes. Ha ainda seis `.DS_Store` ignorados pelo Git, que nao sao documentos e ficam fora da migracao. O mapa CSV inclui os 152 caminhos atuais; os 124 rastreados formam o inventario versionado original.

A investigação de código confirmou:

- Central V1: `interface_web/`, `orquestracao/` e domínios raiz em `processamento/`.
- Central V2: `central_v2/frontend/`, `central_v2/backend/` e `central_v2/runtime/`.
- Os consumidores comuns foram confirmados por imports estaticos, importlib dinamico e encadeamento de execucao, detalhados na secao "Consumidores compartilhados confirmados". UI, API, jobs e persistencia continuam especificos por versao.
- A busca direta não encontrou V2 consumindo `bubble_cleaner.py`; não o atribuir à V2 sem confirmação adicional.
- Existem documentos que se identificam como parciais, propostas ou datados. São classificados como investigação/histórico, não como contratos atuais.

## Plano de migracao proposto em quatro lotes

1. **LOTE 1 - Central V1:** organizar somente documentacao V1. As paginas em `docs/central_v1/` ja existem no working tree e sao entradas preexistentes, nao movimentos concluidos.
2. **LOTE 2 - Central V2:** mover documentacao especifica V2 para `central_v2/`, com interfaces, etapas e contratos separados por versao.
3. **LOTE 3 - Compartilhada e historica:** arquitetura transversal, modulos realmente compartilhados, legado e registros datados sem autoridade normativa atual.
4. **LOTE 4 - Gestao:** backlog, tickets, planos e evidencias; preservar IDs, datas e conteudo historico.
5. Auto-Merge e Balanceamento ficam fora desta migracao, sem mudanca de caminho nem consolidacao.
6. Nenhum HTML sera convertido para Markdown nem consolidado nesta etapa. Primeiro identificar funcionalidade, navegacao, links externos e consumidores; atualizar mapa/estado somente apos confirmacao.
7. Aplicar movimentos um-a-um por lote, sem sobrescrita; reparar links no mesmo lote e executar `python3 dev/tools/verify_docs_migration.py verify` entre lotes. O verificador compara inventario/hash, origem/destino, cobertura do mapa, links e possiveis perdas.

**Execucao controlada:** Lote 1 validado sem movimentos; Lote 2 executado com sete movimentos; Lote 3 executado com 24 movimentos e dez documentos mantidos; Lote 4 executado com 76 movimentos e dois HTMLs mantidos para revisao. Links afetados foram atualizados sem conversao ou consolidacao dos HTMLs. O mapa completo esta em `dev/tools/docs_migration_map.csv`; cada arquivo tem origem, destino, lote e acao. Nenhum documento foi removido.

Distribuicao do mapa atual (152 caminhos; linhas individuais, sem curingas):

| Grupo | Arquivos | Acao planejada |
|---|---:|---|
| LOTE 1 - Central V1 | 5 | Todos ja estao em `docs/central_v1/`; nenhuma mudanca de caminho planejada neste lote. |
| LOTE 2 - Central V2 | 24 | 7 mover, 15 manter e 2 aguardar revisao HTML. |
| LOTE 3 - compartilhada e historica | 34 | 24 mover e 10 manter. |
| LOTE 4 - gestao | 78 | 76 movidos; 2 HTMLs mantidos para revisao. |
| Fora do escopo | 10 | Manter, incluindo Auto-Merge e Balanceamento. |
| Controle do plano | 1 | Manter `docs/organizacao_limpeza_baloes.md`. |

As quatro linhas com `AGUARDAR_REVISAO_HTML` sao esperas explicitas, nao autorizacoes para mover ou converter. O CSV atual nao tem caminhos de destino duplicados.

Movimentos concluidos no Lote 2:

| Origem | Destino |
|---|---|
| `docs/Refatoracao/00_arquitetura/03_arquitetura_interface_alvo.md` | `docs/central_v2/arquitetura/03_arquitetura_interface_alvo.md` |
| `docs/Refatoracao/02_processamento/text_off/correcao_assistida/analise_correcao_assistida_e_tratamentos_especiais.md` | `docs/central_v2/limpeza_baloes/correcao_assistida/analise_correcao_assistida_e_tratamentos_especiais.md` |
| `docs/Refatoracao/02_processamento/text_off/solidos/01_Solidos_Parametros_Contrato_Tecnico.md` | `docs/central_v2/limpeza_baloes/solidos/01_Solidos_Parametros_Contrato_Tecnico.md` |
| `docs/Refatoracao/02_processamento/text_off/solidos/02_UI_Comparacao_Curadoria_Selecao.md` | `docs/central_v2/limpeza_baloes/solidos/02_UI_Comparacao_Curadoria_Selecao.md` |
| `docs/Refatoracao/02_processamento/text_off/solidos/03_Runbook_Incidentes_Evidencias.md` | `docs/central_v2/limpeza_baloes/solidos/03_Runbook_Incidentes_Evidencias.md` |
| `docs/Refatoracao/02_processamento/text_off/solidos/README.md` | `docs/central_v2/limpeza_baloes/solidos/README.md` |
| `docs/Refatoracao/90_central_v2/responsabilidades_e_ciclo_de_vida.md` | `docs/central_v2/arquitetura/responsabilidades_e_ciclo_de_vida.md` |

Tambem foi reparado o link interno para `inventario_e_contrato_v2.md` no documento de Correcao Assistida, agora apontando para seu destino historico em `docs/historico/limpeza_baloes/especiais/`.

Movimentos concluidos no Lote 3 (mapa completo, um arquivo por linha, em `dev/tools/docs_migration_map.csv`):

| Origem | Destino |
|---|---|
| `docs/OLD/00_plano_refatoracao_arquitetural.md` | `docs/historico/documentacao_legada/00_plano_refatoracao_arquitetural.md` |
| `docs/OLD/fluxo_narrativo_milestones.md` | `docs/historico/documentacao_legada/fluxo_narrativo_milestones.md` |
| `docs/OLD/investigacao_cleaner_v1_v2_parcial_2026-10-09.md` | `docs/historico/documentacao_legada/investigacao_cleaner_v1_v2_parcial_2026-10-09.md` |
| `docs/OLD/merge_review_stabilization_v1.md` | `docs/historico/documentacao_legada/merge_review_stabilization_v1.md` |
| `docs/Refatoracao/00_arquitetura/00_plano_refatoracao_arquitetural.md` | `docs/historico/planos/00_plano_refatoracao_arquitetural.md` |
| `docs/Refatoracao/00_arquitetura/01_ambientes_virtuais.md` | `docs/arquitetura/01_ambientes_virtuais.md` |
| `docs/Refatoracao/00_arquitetura/02_baseline_testes_e_contratos.md` | `docs/arquitetura/02_baseline_testes_e_contratos.md` |
| `docs/Refatoracao/00_arquitetura/04a_mapa_metro_fluxos_manifestos.md` | `docs/arquitetura/04a_mapa_metro_fluxos_manifestos.md` |
| `docs/Refatoracao/00_arquitetura/04b_mapa_metro_auditoria_proveniencia.md` | `docs/arquitetura/04b_mapa_metro_auditoria_proveniencia.md` |
| `docs/Refatoracao/00_arquitetura/catalogo_fluxos_criticos.md` | `docs/arquitetura/catalogo_fluxos_criticos.md` |
| `docs/Refatoracao/00_arquitetura/contrato_telas_inspecao_imagem.md` | `docs/arquitetura/contrato_telas_inspecao_imagem.md` |
| `docs/Refatoracao/00_arquitetura/estado_atual_e_inventario_estrutural.md` | `docs/arquitetura/estado_atual_e_inventario_estrutural.md` |
| `docs/Refatoracao/00_arquitetura/investigacao_cleaner_v1_v2_parcial_2026-10-09.md` | `docs/historico/limpeza_baloes/investigacao_cleaner_v1_v2_parcial_2026-10-09.md` |
| `docs/Refatoracao/00_arquitetura/mapa_componentes_e_dependencias.md` | `docs/arquitetura/mapa_componentes_e_dependencias.md` |
| `docs/Refatoracao/02_processamento/text_off/especiais/comparacao_transparencia_candy_ch1_ch3.md` | `docs/historico/limpeza_baloes/especiais/comparacao_transparencia_candy_ch1_ch3.md` |
| `docs/Refatoracao/02_processamento/text_off/especiais/continuidade_2026-09-29.md` | `docs/historico/limpeza_baloes/especiais/continuidade_2026-09-29.md` |
| `docs/Refatoracao/02_processamento/text_off/especiais/correcao_entrada_artistico_082_2026-10-09.md` | `docs/historico/limpeza_baloes/especiais/correcao_entrada_artistico_082_2026-10-09.md` |
| `docs/Refatoracao/02_processamento/text_off/especiais/diagnostico_v1_v2_gazing_2026-10-09.md` | `docs/historico/limpeza_baloes/especiais/diagnostico_v1_v2_gazing_2026-10-09.md` |
| `docs/Refatoracao/02_processamento/text_off/especiais/ensaio_restauracao_082_2026-10-09.md` | `docs/historico/limpeza_baloes/especiais/ensaio_restauracao_082_2026-10-09.md` |
| `docs/Refatoracao/02_processamento/text_off/especiais/executor_e_comparacao_v2.md` | `docs/historico/limpeza_baloes/especiais/executor_e_comparacao_v2.md` |
| `docs/Refatoracao/02_processamento/text_off/especiais/finalizacao_restauracao_082_2026-10-09.md` | `docs/historico/limpeza_baloes/especiais/finalizacao_restauracao_082_2026-10-09.md` |
| `docs/Refatoracao/02_processamento/text_off/especiais/inventario_e_contrato_v2.md` | `docs/historico/limpeza_baloes/especiais/inventario_e_contrato_v2.md` |
| `docs/Refatoracao/02_processamento/text_off/merged/consolidacao_nivel_iii_e_reducao_armazenamento_2026-09-30.md` | `docs/historico/limpeza_baloes/merged/consolidacao_nivel_iii_e_reducao_armazenamento_2026-09-30.md` |
| `docs/Refatoracao/02_processamento/text_off/merged/niveis_iii_a_v.md` | `docs/historico/limpeza_baloes/merged/niveis_iii_a_v.md` |

## Consumidores compartilhados confirmados

| Modulo / adaptador | Central V1: import / chamada / fluxo | Central V2: import / chamada / fluxo | Conclusao |
|---|---|---|---|
| `cleaner_v2.integration.clean_chapter` | `interface_web/processing_web.py:2430-2473` chama em `do_clean` e `do_clean_merged`; `orquestracao/textoff/merged.py:105-134` chama em `execute_merged`. | `central_v2/backend/orchestration/textoff_merged/cleaner.py` importa `integration` e `run_cleaner_v2` chama `integration.clean_chapter`; rotas Merged encaminham a execucao. | Funcao de dominio compartilhada; interfaces e jobs separados. |
| `cleaner_v2.launcher` e metadados OCR | `cleaner_v2/integration.py` importa launcher e `ocr_manifest_metadata`, usados no caminho V1 de `clean_chapter`. | `textoff_merged/cleaner_process.py` e `level1_cleaner.py` importam `MODULE_DIR`; `level1_cleaner.py` usa `ocr_manifest_metadata`. | Configuracao e leitura de perfil compartilhadas; execucao V2 pode isolar etapas. |
| `cleaner_v2.balloon_authorization.apply_balloon_authorization` | Importado e chamado por `cleaner_v2/integration.py` em `clean_chapter`. | Importado por `textoff_merged/level1_worker.py` e chamado durante o worker de Nivel I. | Regra de autorizacao compartilhada; escritores e manifestos seguem por versao. |
| Adaptadores especiais em `processamento/limpeza_baloes/` | `interface_web/processing_web.py:2690,2761,2765` chama `textoff_special_web`; esse modulo importa adaptadores ROI e executa/promove resultados. | `textoff_special/catalog.py` declara modulo/funcao; `textoff_special/domain.py` resolve com `importlib.import_module`; `execution.py` chama o processo/worker isolado. | Algoritmos/adaptadores compartilhados por chamada dinamica; catalogo, rotas, runtime e artefatos V2 sao proprios. |
| `textoff_compare.py`, `textoff_level3*.py`, `textoff_special_web.py` | Chamados diretamente por `interface_web/processing_web.py` para comparacao, correcao assistida e especiais. | Nenhum import/chamada V2 encontrado na busca de imports/callers; a V2 tem rotas e orquestracao proprias. | Documentar como V1, nao como modulo compartilhado. |

No fluxo V2 de casos especiais, `catalog.py` seleciona `treatment.module`/`treatment.function`, `domain.py` resolve os nomes via `importlib`, e o worker executa na venv do tratamento. Essa chamada dinamica confirma o consumidor mesmo sem import estatico.

## Cobertura investigada e lacunas

| Área | Evidência de código | Resultado inicial | Lacuna |
|---|---|---|---|
| V1 interface/HTTP | `interface_web/processing_web.py`, `textoff_special.js`, `textoff_compare.js` | Handler e ações V1 identificados | Inventário completo endpoint → job → writer ainda pendente. |
| V1 domínio | `orquestracao/textoff/merged.py`, `processamento/limpeza_baloes/` | Cleaner, comparação, residual, correção assistida e especiais localizados | Schema e regra de cada tratamento precisam ser verificados writer a writer. |
| V2 interface/API | `central_v2/frontend/texto_off/`, `backend/routes/` | Módulos de Laboratório, Merged, especiais, Check, Sólidos e Sommelier localizados | Matriz de payloads e estados por rota está parcial. |
| V2 pipeline/persistência | `backend/orchestration/textoff_merged/`, `textoff_special/` | Cleaner I/II, consolidado, final e restore localizados | Catalogar todos os campos/schema dos manifests e invalidação por etapa. |
| Algoritmos | `cleaner_v2/*.py`, adaptadores e runtimes | Alguns parâmetros de Cleaner e Nível II confirmados | Thresholds restantes e métricas de Sommelier/Solids pendentes. |
| Atalhos | listeners V2 no commit de referência | Esc/F/setas com escopo documentados | Cobertura equivalente V1 não confirmada. |
| Dependências | requirements/locks e diretórios runtime | fontes de ambiente identificadas | baseline é histórico; capturar versões atuais sem instalar ou executar pipeline. |

## Mapa arquivo a arquivo

O mapa completo, um registro por arquivo e sem curingas, esta em `dev/tools/docs_migration_map.csv` (152 caminhos do working tree: origem, destino, lote e acao). A tabela abaixo detalha os 124 caminhos versionados do inventario inicial; os 28 arquivos nao rastreados atuais tambem aparecem como linhas individuais no CSV. Destino igual a origem significa manter no local. HTMLs com destino diferente ficam em espera, sem mudanca ate confirmar funcao, navegacao e consumidores.

| Caminho atual | Classificação / ação | Destino proposto | Justificativa |
|---|---|---|---|
| `docs/03_arquitetura_interface_alvo_visual_v2.html` | Referência visual/arquitetural V2; manter, revisar link e vigência | `docs/03_arquitetura_interface_alvo_visual_v2.html` | Não mudar arquivo HTML antes de confirmar uso; manter fora do escopo de limpeza algorítmica. |
| `docs/OLD/00_plano_refatoracao_arquitetural.md` | Histórico; preservar sem reescrever | `docs/historico/documentacao_legada/00_plano_refatoracao_arquitetural.md` | Material legado/plano datado; manter para contexto, sem tratá-lo como contrato vigente. |
| `docs/OLD/fluxo_narrativo_milestones.md` | Histórico; preservar sem reescrever | `docs/historico/documentacao_legada/fluxo_narrativo_milestones.md` | Material legado/plano datado; manter para contexto, sem tratá-lo como contrato vigente. |
| `docs/OLD/investigacao_cleaner_v1_v2_parcial_2026-10-09.md` | Histórico; preservar sem reescrever | `docs/historico/documentacao_legada/investigacao_cleaner_v1_v2_parcial_2026-10-09.md` | Material legado/plano datado; manter para contexto, sem tratá-lo como contrato vigente. |
| `docs/OLD/merge_review_stabilization_v1.md` | Histórico; preservar sem reescrever | `docs/historico/documentacao_legada/merge_review_stabilization_v1.md` | Material legado/plano datado; manter para contexto, sem tratá-lo como contrato vigente. |
| `docs/OLD/plano_milestones_img_old.md` | Histórico; preservar sem reescrever | `docs/historico/documentacao_legada/plano_milestones_img_old.md` | Material legado/plano datado; manter para contexto, sem tratá-lo como contrato vigente. |
| `docs/Refatoracao/00_arquitetura/00_plano_refatoracao_arquitetural.md` | Plano/histórico de implementação | `docs/historico/planos/00_plano_refatoracao_arquitetural.md` | Plano não é contrato funcional; preservar para rastreabilidade. |
| `docs/Refatoracao/00_arquitetura/01_ambientes_virtuais.md` | Arquitetura/contrato transversal; revisar vigência | `docs/arquitetura/01_ambientes_virtuais.md` | Preservar limites e fontes, atualizar status/links sem apagar conteúdo útil. |
| `docs/Refatoracao/00_arquitetura/02_baseline_testes_e_contratos.md` | Arquitetura/contrato transversal; revisar vigência | `docs/arquitetura/02_baseline_testes_e_contratos.md` | Preservar limites e fontes, atualizar status/links sem apagar conteúdo útil. |
| `docs/Refatoracao/00_arquitetura/03_arquitetura_interface_alvo.html` | HTML estatico V2; aguardar revisao do par e consumidores | `docs/central_v2/arquitetura/03_arquitetura_interface_alvo.html` | Nao ha scripts, anchors ou consumidor local encontrado; manter o formato e aguardar revisao. |
| `docs/Refatoracao/00_arquitetura/03_arquitetura_interface_alvo.md` | Documento V2; manter separado do HTML ate revisao | `docs/central_v2/arquitetura/03_arquitetura_interface_alvo.md` | Nenhuma consolidacao autorizada; preservar ambas as representacoes. |
| `docs/Refatoracao/00_arquitetura/04a_mapa_metro_fluxos_manifestos.md` | Arquitetura/contrato transversal; revisar vigência | `docs/arquitetura/04a_mapa_metro_fluxos_manifestos.md` | Preservar limites e fontes, atualizar status/links sem apagar conteúdo útil. |
| `docs/Refatoracao/00_arquitetura/04b_mapa_metro_auditoria_proveniencia.md` | Arquitetura/contrato transversal; revisar vigência | `docs/arquitetura/04b_mapa_metro_auditoria_proveniencia.md` | Preservar limites e fontes, atualizar status/links sem apagar conteúdo útil. |
| `docs/Refatoracao/00_arquitetura/catalogo_fluxos_criticos.md` | Arquitetura/contrato transversal; revisar vigência | `docs/arquitetura/catalogo_fluxos_criticos.md` | Preservar limites e fontes, atualizar status/links sem apagar conteúdo útil. |
| `docs/Refatoracao/00_arquitetura/contrato_telas_inspecao_imagem.md` | Arquitetura/contrato transversal; revisar vigência | `docs/arquitetura/contrato_telas_inspecao_imagem.md` | Preservar limites e fontes, atualizar status/links sem apagar conteúdo útil. |
| `docs/Refatoracao/00_arquitetura/estado_atual_e_inventario_estrutural.md` | Arquitetura/contrato transversal; revisar vigência | `docs/arquitetura/estado_atual_e_inventario_estrutural.md` | Preservar limites e fontes, atualizar status/links sem apagar conteúdo útil. |
| `docs/Refatoracao/00_arquitetura/investigacao_cleaner_v1_v2_parcial_2026-10-09.md` | Investigação histórica parcial | `docs/historico/limpeza_baloes/investigacao_cleaner_v1_v2_parcial_2026-10-09.md` | A própria identificação parcial/datada impede uso como fonte definitiva. |
| `docs/Refatoracao/00_arquitetura/mapa_componentes_e_dependencias.md` | Arquitetura/contrato transversal; revisar vigência | `docs/arquitetura/mapa_componentes_e_dependencias.md` | Preservar limites e fontes, atualizar status/links sem apagar conteúdo útil. |
| `docs/Refatoracao/02_processamento/auto_merge/evidencias/nivel_1/cenarios_sinteticos.jsonl` | Fora do escopo Limpeza de Balões; manter | `docs/Refatoracao/02_processamento/auto_merge/evidencias/nivel_1/cenarios_sinteticos.jsonl` | Auto-Merge não integra esta reorganização; links permanecem no local. |
| `docs/Refatoracao/02_processamento/auto_merge/nivel_1/consulta_v2.md` | Fora do escopo Limpeza de Balões; manter | `docs/Refatoracao/02_processamento/auto_merge/nivel_1/consulta_v2.md` | Auto-Merge não integra esta reorganização; links permanecem no local. |
| `docs/Refatoracao/02_processamento/auto_merge/nivel_1/contrato.md` | Fora do escopo Limpeza de Balões; manter | `docs/Refatoracao/02_processamento/auto_merge/nivel_1/contrato.md` | Auto-Merge não integra esta reorganização; links permanecem no local. |
| `docs/Refatoracao/02_processamento/auto_merge/nivel_1/estrategia_v2.md` | Fora do escopo Limpeza de Balões; manter | `docs/Refatoracao/02_processamento/auto_merge/nivel_1/estrategia_v2.md` | Auto-Merge não integra esta reorganização; links permanecem no local. |
| `docs/Refatoracao/02_processamento/auto_merge/nivel_1/plano_e_evidencias.md` | Fora do escopo Limpeza de Balões; manter | `docs/Refatoracao/02_processamento/auto_merge/nivel_1/plano_e_evidencias.md` | Auto-Merge não integra esta reorganização; links permanecem no local. |
| `docs/Refatoracao/02_processamento/auto_merge/nivel_2/analise_v2.md` | Fora do escopo Limpeza de Balões; manter | `docs/Refatoracao/02_processamento/auto_merge/nivel_2/analise_v2.md` | Auto-Merge não integra esta reorganização; links permanecem no local. |
| `docs/Refatoracao/02_processamento/auto_merge/nivel_3/implementacao_v2.md` | Fora do escopo Limpeza de Balões; manter | `docs/Refatoracao/02_processamento/auto_merge/nivel_3/implementacao_v2.md` | Auto-Merge não integra esta reorganização; links permanecem no local. |
| `docs/Refatoracao/02_processamento/auto_merge/nivel_4/implementacao_v2.md` | Fora do escopo Limpeza de Balões; manter | `docs/Refatoracao/02_processamento/auto_merge/nivel_4/implementacao_v2.md` | Auto-Merge não integra esta reorganização; links permanecem no local. |
| `docs/Refatoracao/02_processamento/auto_merge/nivel_5/implementacao_v2.md` | Fora do escopo Limpeza de Balões; manter | `docs/Refatoracao/02_processamento/auto_merge/nivel_5/implementacao_v2.md` | Auto-Merge não integra esta reorganização; links permanecem no local. |
| `docs/Refatoracao/02_processamento/text_off/correcao_assistida/analise_correcao_assistida_e_tratamentos_especiais.md` | Documentação específica de Texto Off; revisar versão e manter separado | `docs/central_v2/limpeza_baloes/correcao_assistida/analise_correcao_assistida_e_tratamentos_especiais.md` | A origem precisa ser confirmada por implementação; não misturar V1/V2. |
| `docs/Refatoracao/02_processamento/text_off/especiais/comparacao_transparencia_candy_ch1_ch3.md` | Investigação/relato de execução; preservar como histórico após extração de fatos atuais | `docs/historico/limpeza_baloes/especiais/comparacao_transparencia_candy_ch1_ch3.md` | Há hipóteses, contratos propostos ou observações datadas; confrontar com código antes de reutilizar. |
| `docs/Refatoracao/02_processamento/text_off/especiais/continuidade_2026-09-29.md` | Investigação/relato de execução; preservar como histórico após extração de fatos atuais | `docs/historico/limpeza_baloes/especiais/continuidade_2026-09-29.md` | Há hipóteses, contratos propostos ou observações datadas; confrontar com código antes de reutilizar. |
| `docs/Refatoracao/02_processamento/text_off/especiais/correcao_entrada_artistico_082_2026-10-09.md` | Investigação/relato de execução; preservar como histórico após extração de fatos atuais | `docs/historico/limpeza_baloes/especiais/correcao_entrada_artistico_082_2026-10-09.md` | Há hipóteses, contratos propostos ou observações datadas; confrontar com código antes de reutilizar. |
| `docs/Refatoracao/02_processamento/text_off/especiais/diagnostico_v1_v2_gazing_2026-10-09.md` | Investigação/relato de execução; preservar como histórico após extração de fatos atuais | `docs/historico/limpeza_baloes/especiais/diagnostico_v1_v2_gazing_2026-10-09.md` | Há hipóteses, contratos propostos ou observações datadas; confrontar com código antes de reutilizar. |
| `docs/Refatoracao/02_processamento/text_off/especiais/ensaio_restauracao_082_2026-10-09.md` | Investigação/relato de execução; preservar como histórico após extração de fatos atuais | `docs/historico/limpeza_baloes/especiais/ensaio_restauracao_082_2026-10-09.md` | Há hipóteses, contratos propostos ou observações datadas; confrontar com código antes de reutilizar. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-29/balao_transparente_legado_runtime.json` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-29/balao_transparente_legado_runtime.json` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-29/balao_transparente_runtime.json` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-29/balao_transparente_runtime.json` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-29/candy_comparison.json` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-29/candy_comparison.json` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-29/entradas_autorizadas.json` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-29/entradas_autorizadas.json` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-29/execucoes_v1.json` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-29/execucoes_v1.json` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-29/matriz_resultados.json` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-29/matriz_resultados.json` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/SHA256SUMS.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/SHA256SUMS.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/degrade_suave_direct_packages.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/degrade_suave_direct_packages.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/degrade_suave_pip_check.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/degrade_suave_pip_check.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/degrade_suave_pip_freeze.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/degrade_suave_pip_freeze.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/degrade_suave_python.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/degrade_suave_python.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/patch_degrade_direct_packages.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/patch_degrade_direct_packages.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/patch_degrade_pip_check.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/patch_degrade_pip_check.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/patch_degrade_pip_freeze.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/patch_degrade_pip_freeze.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/patch_degrade_python.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/patch_degrade_python.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/patch_estilizado_direct_packages.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/patch_estilizado_direct_packages.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/patch_estilizado_pip_check.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/patch_estilizado_pip_check.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/patch_estilizado_pip_freeze.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/patch_estilizado_pip_freeze.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-09-30/patch_estilizado_python.txt` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-09-30/patch_estilizado_python.txt` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-10-09/078_degrade_estagios.png` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-10-09/078_degrade_estagios.png` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/evidencias/2026-10-09/082_suave_antes_depois.png` | Evidência histórica V1/V2; preservar | `docs/gestao/evidencias/textoff/especiais/evidencias/2026-10-09/082_suave_antes_depois.png` | Dados e imagens vinculados a experimentos específicos; não consolidar como especificação. |
| `docs/Refatoracao/02_processamento/text_off/especiais/executor_e_comparacao_v2.md` | Investigação/relato de execução; preservar como histórico após extração de fatos atuais | `docs/historico/limpeza_baloes/especiais/executor_e_comparacao_v2.md` | Há hipóteses, contratos propostos ou observações datadas; confrontar com código antes de reutilizar. |
| `docs/Refatoracao/02_processamento/text_off/especiais/finalizacao_restauracao_082_2026-10-09.md` | Investigação/relato de execução; preservar como histórico após extração de fatos atuais | `docs/historico/limpeza_baloes/especiais/finalizacao_restauracao_082_2026-10-09.md` | Há hipóteses, contratos propostos ou observações datadas; confrontar com código antes de reutilizar. |
| `docs/Refatoracao/02_processamento/text_off/especiais/inventario_e_contrato_v2.md` | Investigação/relato de execução; preservar como histórico após extração de fatos atuais | `docs/historico/limpeza_baloes/especiais/inventario_e_contrato_v2.md` | Há hipóteses, contratos propostos ou observações datadas; confrontar com código antes de reutilizar. |
| `docs/Refatoracao/02_processamento/text_off/merged/consolidacao_nivel_iii_e_reducao_armazenamento_2026-09-30.md` | Investigação/relato de execução; preservar como histórico após extração de fatos atuais | `docs/historico/limpeza_baloes/merged/consolidacao_nivel_iii_e_reducao_armazenamento_2026-09-30.md` | Há hipóteses, contratos propostos ou observações datadas; confrontar com código antes de reutilizar. |
| `docs/Refatoracao/02_processamento/text_off/merged/niveis_iii_a_v.md` | Investigação/relato de execução; preservar como histórico após extração de fatos atuais | `docs/historico/limpeza_baloes/merged/niveis_iii_a_v.md` | Há hipóteses, contratos propostos ou observações datadas; confrontar com código antes de reutilizar. |
| `docs/Refatoracao/02_processamento/text_off/solidos/01_Solidos_Parametros_Contrato_Tecnico.md` | Documentação específica V2; mover como arquivo independente | `docs/central_v2/limpeza_baloes/solidos/01_Solidos_Parametros_Contrato_Tecnico.md` | Confrontar com rotas e domínio ativos sem consolidar outros documentos. |
| `docs/Refatoracao/02_processamento/text_off/solidos/02_UI_Comparacao_Curadoria_Selecao.md` | Documentação específica V2; mover como arquivo independente | `docs/central_v2/limpeza_baloes/solidos/02_UI_Comparacao_Curadoria_Selecao.md` | Confrontar com rotas e domínio ativos sem consolidar outros documentos. |
| `docs/Refatoracao/02_processamento/text_off/solidos/03_Runbook_Incidentes_Evidencias.md` | Documentação específica V2; mover como arquivo independente | `docs/central_v2/limpeza_baloes/solidos/03_Runbook_Incidentes_Evidencias.md` | Confrontar com rotas e domínio ativos sem consolidar outros documentos. |
| `docs/Refatoracao/02_processamento/text_off/solidos/README.md` | Documentação específica V2; mover como arquivo independente | `docs/central_v2/limpeza_baloes/solidos/README.md` | Preservar este arquivo separado dos demais documentos Solidos. |
| `docs/Refatoracao/03_balanceamento/mapa_metro_balanceamento.md` | Fora do escopo Limpeza de Balões; manter | `docs/Refatoracao/03_balanceamento/mapa_metro_balanceamento.md` | Balanceamento é domínio relacionado ao MERGE, mas fora do escopo documental desta tarefa. |
| `docs/Refatoracao/90_central_v2/responsabilidades_e_ciclo_de_vida.md` | Arquitetura V2; preservar e revisar | `docs/central_v2/arquitetura/responsabilidades_e_ciclo_de_vida.md` | Documento de ciclo de vida V2; confrontar estado e imports atuais. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/cleaner_v2_baseline_SHA256SUMS.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/cleaner_v2_baseline_SHA256SUMS.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/cleaner_v2_models_SHA256SUMS.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/cleaner_v2_models_SHA256SUMS.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/cleaner_v2_outlined-text.ini` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/cleaner_v2_outlined-text.ini` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/cleaner_v2_packages.json` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/cleaner_v2_packages.json` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/cleaner_v2_pip_freeze.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/cleaner_v2_pip_freeze.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/cleaner_v2_python.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/cleaner_v2_python.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/gradiente_suave_SHA256SUMS.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/gradiente_suave_SHA256SUMS.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/gradiente_suave_direct_packages.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/gradiente_suave_direct_packages.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/gradiente_suave_pip_freeze.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/gradiente_suave_pip_freeze.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/gradiente_suave_python.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/gradiente_suave_python.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/level3_regional_SHA256SUMS.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/level3_regional_SHA256SUMS.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/level3_regional_direct_packages.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/level3_regional_direct_packages.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/level3_regional_pip_freeze.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/level3_regional_pip_freeze.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/level3_regional_python.txt` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/environment_baseline/2026-09-25/level3_regional_python.txt` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/99_evidencias_transversais/plano_refatoracao_original.md` | Evidência histórica; preservar com data | `docs/gestao/evidencias/ambientes/plano_refatoracao_original.md` | Captura de baseline datada; não apresentar como ambiente atual. |
| `docs/Refatoracao/pendencias_central_v2.html` | Backlog atual; preservar duas representações até decidir fonte geradora | `docs/gestao/backlog/central_v2/pendencias_central_v2.html` | Roadmap e visualizador devem permanecer sincronizados; revisar se HTML é gerado ou mantido manualmente. |
| `docs/Refatoracao/pendencias_central_v2.md` | Backlog atual; preservar duas representações até decidir fonte geradora | `docs/gestao/backlog/central_v2/pendencias_central_v2.md` | Roadmap e visualizador devem permanecer sincronizados; revisar se HTML é gerado ou mantido manualmente. |
| `docs/Refatoracao/plano_milestones_protecao_historico_central_v2.md` | Plano/política de trabalho; manter em gestão/histórico após revisar vigência | `docs/gestao/planos/plano_milestones_protecao_historico_central_v2.md` | Não é especificação de algoritmo; preservar decisão e responsável pelo plano. |
| `docs/Refatoracao/politica_investigacao_regressoes.md` | Plano/política de trabalho; manter em gestão/histórico após revisar vigência | `docs/gestao/planos/politica_investigacao_regressoes.md` | Não é especificação de algoritmo; preservar decisão e responsável pelo plano. |
| `docs/Refatoracao/sanitizacao_pendente_central_v2.md` | Plano/política de trabalho; manter em gestão/histórico após revisar vigência | `docs/gestao/planos/sanitizacao_pendente_central_v2.md` | Não é especificação de algoritmo; preservar decisão e responsável pelo plano. |
| `docs/Refatoracao/tickets_pendencias/BL-01.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-01.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/BL-02.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-02.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/BL-03.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-03.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/BL-04.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-04.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/BL-05.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-05.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/BL-06.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-06.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/BL-07.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-07.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/BL-08.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-08.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/BL-09.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-09.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/BL-12.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-12.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/BL-13.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/BL-13.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-AC-01.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-AC-01.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-AC-03.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-AC-03.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-AC-04.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-AC-04.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-AC-05.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-AC-05.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-AC-06.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-AC-06.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-AM-01.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-AM-01.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-AUD-01.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-AUD-01.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-CAT-01.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-CAT-01.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-CAT-02.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-CAT-02.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-CAT-03.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-CAT-03.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-OBS-01.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-OBS-01.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-OBS-02.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-OBS-02.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-OBS-03.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-OBS-03.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-OBS-04.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-OBS-04.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-UX-01.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-UX-01.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-UX-02.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-UX-02.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-UX-03.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-UX-03.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-UX-04.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-UX-04.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/Refatoracao/tickets_pendencias/CV2-UX-05.md` | Ticket; preservar histórico/ID | `docs/gestao/tickets/central_v2/CV2-UX-05.md` | Ticket rastreável; manter conteúdo e corrigir links no índice. |
| `docs/archive/backlog_legacy_2026_10_12/backlog_pendencias_fominha_central_v2_2026-10-12.md` | Snapshot de gestão; preservar | `docs/gestao/backlog/arquivo_legado_2026-10-12/backlog_pendencias_fominha_central_v2_2026-10-12.md` | Snapshot datado do backlog; não mesclar com estado atual. |
| `docs/archive/backlog_legacy_2026_10_12/backlog_pendencias_fominha_central_v2_2026-10-12_consolidado.md` | Snapshot de gestão; preservar | `docs/gestao/backlog/arquivo_legado_2026-10-12/backlog_pendencias_fominha_central_v2_2026-10-12_consolidado.md` | Snapshot datado do backlog; não mesclar com estado atual. |
| `docs/archive/backlog_legacy_2026_10_12/pendencias_central_v2_legacy.html` | Snapshot de gestão; preservar | `docs/gestao/backlog/arquivo_legado_2026-10-12/pendencias_central_v2_legacy.html` | Snapshot datado do backlog; não mesclar com estado atual. |
| `docs/archive/backlog_legacy_2026_10_12/pendencias_central_v2_legacy.md` | Snapshot de gestão; preservar | `docs/gestao/backlog/arquivo_legado_2026-10-12/pendencias_central_v2_legacy.md` | Snapshot datado do backlog; não mesclar com estado atual. |
| `docs/archive/backlog_legacy_2026_10_12/proposta_validacao_automatica_limite_200_linhas.md` | Snapshot de gestão; preservar | `docs/gestao/backlog/arquivo_legado_2026-10-12/proposta_validacao_automatica_limite_200_linhas.md` | Snapshot datado do backlog; não mesclar com estado atual. |
| `docs/central_v2_conformidade_enderecamentos.md` | Referência visual/arquitetural V2; manter, revisar link e vigência | `docs/central_v2_conformidade_enderecamentos.md` | Não mudar arquivo HTML antes de confirmar uso; manter fora do escopo de limpeza algorítmica. |
| `docs/central_v2_menus.html` | Referência visual/arquitetural V2; manter, revisar link e vigência | `docs/central_v2_menus.html` | Não mudar arquivo HTML antes de confirmar uso; manter fora do escopo de limpeza algorítmica. |
| `docs/fluxo_auto_merge_merge_manual.html` | Fluxo relacionado, fora do escopo principal; manter | `docs/fluxo_auto_merge_merge_manual.html` | Merge Manual/Balanceamento não é etapa de limpeza documentada nesta tarefa. |
| `docs/textoff_merged_transparencia.html` | HTML V2 com consumidores locais; manter formato e aguardar revisao | `docs/central_v2/limpeza_baloes/etapas/textoff_merged_transparencia.md` | Nao converter. O README da raiz e `docs/central_v2_conformidade_enderecamentos.md` apontam para o HTML; reparar consumidores somente apos decisao futura. |

## Documentação localizada fora de `docs/`

| Caminho | Classificação / ação | Destino/decisão | Justificativa |
|---|---|---|---|
| `README.md` | Índice de projeto; manter e apontar para índice técnico | `README.md` | Atualizado para linkar o novo índice sem duplicar a especificação. |
| `processamento/limpeza_baloes/cleaner_v2/README.md` | Instruções do motor ativo; manter junto ao código e consolidar links | Mesmo caminho | É o README de instalação local do motor; não mover para manter descoberta no pacote. |
| `central_v2/runtime/textoff/README.md` | Documentação de runtime V2; manter junto ao runtime | Mesmo caminho | Contexto de execução e seleção de ambiente fica próximo do código que consome o runtime. |
| `central_v2/runtime/textoff/especiais/README.md` | Documentação de runtimes de tratamentos V2; manter junto ao runtime | Mesmo caminho | Dependências e isolamento são específicos do runtime. |
| `dev/docs/git_workflow.md` | Instrução de desenvolvimento geral; fora do escopo | Mesmo caminho | Não descreve processamento de Limpeza de Balões. |
| `dev/experiments/bubble_cleaner/README_EXPERIMENTO.md` | Experimento; preservar como histórico, sem promoção automática | Mesmo caminho / referenciar no histórico | Código experimental só é vigente se houver caller ativo confirmado. |
| `dev/experiments/bubble_cleaner_v2/README_V2.md` | Experimento; preservar como histórico | Mesmo caminho / referenciar no histórico | Não misturar experimento com `cleaner_v2` oficial. |
| `dev/experiments/bubble_cleaner_v3/README_V3.md` | Experimento; preservar como histórico | Mesmo caminho / referenciar no histórico | Versão do experimento não estabelece algoritmo ativo da Central. |
| `dev/validation/artistico_ch4_page_049_054.md` | Evidência de validação datada; preservar | Mesmo caminho ou espelhar índice em `docs/gestao/evidencias/` | Relata caso específico, não especificação do algoritmo. |
| `dev/validation/reexecucao_artistico_relatorio.md` | Relatório/evidência datada; preservar | Mesmo caminho ou espelhar índice em `docs/gestao/evidencias/` | Distinguir resultados observados de critérios gerais. |
| `dev/validation/restauracao_operacional_candy_ch4.md` | Evidência de restauração específica; preservar | Mesmo caminho ou espelhar índice em `docs/gestao/evidencias/` | Dados e conclusão pertencem a uma obra/capítulo, não generalizar. |
| `dev/validation/restauracao_pagina_candy_ch4.md` | Evidência de restauração específica; preservar | Mesmo caminho ou espelhar índice em `docs/gestao/evidencias/` | Preservar vínculo com execução e hashes registrados. |
| `interface_web/index.html` | Interface executavel, nao documentacao | Manter em `interface_web/index.html` | Fora da migracao documental. |
| `central_v2/frontend/index.html` | Interface executavel, nao documentacao | Manter em `central_v2/frontend/index.html` | Fora da migracao documental. |
| `central_v2/AGENTS.md` | Instruções de desenvolvimento V2 | Manter junto ao código; não reproduzir como especificação pública | Instruções do agente não são fonte de algoritmo nem devem ser movidas como documentação de produto. |
| Submodulo `download/mangago_downloader` completo | Projeto independente; fora do escopo | Nenhum arquivo do submodulo entra no mapa de migracao | Nenhuma alteracao permitida no submodulo. |

## Duplicidades, contradições e links

- Auditoria dos sete HTMLs: `docs/Refatoracao/pendencias_central_v2.html` e `docs/archive/backlog_legacy_2026_10_12/pendencias_central_v2_legacy.html` tem scripts, busca, tabs/detalhes por teclado e links para tickets; permaneceram em seus caminhos e tiveram somente links internos afetados atualizados. `docs/central_v2_menus.html` e `docs/fluxo_auto_merge_merge_manual.html` tem navegacao por anchors; README, tickets e documentos locais os referenciam. `docs/textoff_merged_transparencia.html` e estatico, mas recebe links do README e de `docs/central_v2_conformidade_enderecamentos.md`. Os dois HTMLs de arquitetura de interface sao estaticos, sem consumidor local encontrado, mas tem pares Markdown. Nenhum foi convertido ou consolidado.
- Ha pares Markdown/HTML de arquitetura V2 e backlog. Comparar conteudo, comportamento, navegacao e consumidores antes de decidir qualquer mudanca de local; nao apagar copias.
- O HTML `docs/textoff_merged_transparencia.html` nao sera convertido para Markdown nesta migracao. A conversao proposta fica suspensa ate confirmar scripts, navegacao, consumidores e se o HTML e fonte de dados independente.
- O backlog arquivado de 2026-10-12 usa alguns IDs BL em sentido diferente do roadmap/ticket atual. Por exemplo, o texto antigo atribui BL-13 a filtros/curadoria; o ticket atual BL-13 é Esc no Laboratório. IDs antigos são contexto histórico, não autoridade para o estado presente.
- Duas referências relativas quebradas no snapshot de backlog foram corrigidas para apontar aos documentos ainda existentes em `docs/Refatoracao/` e `docs/`.
- Notas de restauração/diagnóstico ligam a arquivos locais temporários (`/private/tmp`, caminhos de dados da obra) ou a relatórios de execuções passadas. Esses links não são portáveis e alguns alvos não existem nesta cópia; preservar como evidência datada e registrar como indisponíveis, sem substituir por caminhos inventados.
- Os movimentos dos quatro lotes foram aplicados sem sobrescrita; as referencias locais para os arquivos movidos foram verificadas. Os dois HTMLs do Lote 4 permanecem nos caminhos originais, com seus recursos e navegacao preservados.

## Verificação desta etapa documental

- A contagem 131 foi retirada por nao ser reproduzivel. Baseline versionado: 124 arquivos; working tree documentado: 152 arquivos nao ignorados (124 rastreados e 28 nao rastreados), mais seis `.DS_Store` ignorados e excluidos do mapa.
- Foi preparado `dev/tools/verify_docs_migration.py`. `build-map` gera um CSV explicito por arquivo; `snapshot` salva hashes e links antes da migracao; `verify` compara antes/depois, destinos, arquivos sem destino, links locais e arquivos potencialmente perdidos.
- O baseline congelado em `dev/tools/docs_migration_before.json` representa os 152 documentos antes dos lotes. O verificador compara fontes e destinos de links apos aplicar o mapa, alem de hashes, cobertura, duplicidade e perda de arquivos.
- A contagem chegou a 209 apos o Lote 3 porque 20 links Markdown do diagnostico movido passaram a subir um nivel a mais que a raiz do repositorio; o scanner os excluiu por resolverem fora da raiz. Os destinos de codigo existiam. Os caminhos foram corrigidos para quatro niveis, restaurando a contagem local para 229. No Lote 4, links para tickets e evidencias movidos tambem foram atualizados.
- Lote 1: cinco documentos lidos; classificacao V1/shared coerente com as chamadas descritas; todas as referencias locais resolvem; nenhuma mudanca de caminho. Lote 2: sete arquivos movidos, quinze preservados nos destinos existentes e dois HTMLs mantidos em seus caminhos originais.
- O Lote 3 moveu 24 documentos e manteve dez nos caminhos previstos. O Lote 4 moveu 76 documentos e manteve dois HTMLs para revisao. Nenhum arquivo foi excluido, convertido ou consolidado. O verificador padrao avalia os quatro lotes.
- Validacao consolidada: 152 documentos previstos e 152 presentes; zero documentos perdidos; zero destinos duplicados; 229 links locais no baseline e 229 apos normalizar origem e destino pelo mapa; zero links sem correspondencia e zero links quebrados. Sete hashes divergentes estao justificados por reparos documentais precisos; os outros conteudos correspondem ao baseline.
- Caminhos absolutos e resultados de runs inexistentes permanecem como referencias historicas, sem serem apresentados como links portaveis.
- Nao foram executados testes nem processamento. `git diff --check`, `git status --short` e a verificacao documental dos quatro lotes foram executados; os resultados finais constam no relatorio desta etapa.
- O working tree continha alterações e backups antes desta tarefa. Eles foram preservados; esta etapa só editou/adicionou documentos. O resultado de `git status --short` deve ser lido junto com o estado preexistente, especialmente `docs/Refatoracao/tickets_pendencias/BL-13.md` e roadmaps que já estavam alterados no início.
