# M1 — Matriz de dependências da Onda 1

| Contrato | Produtor/gravador principal | Artefatos/estado | Consumidores conhecidos | Próximo destino conceitual |
|---|---|---|---|---|
| Auto-Cleaner Nível I | `textoff_merged/level1_worker.py`, `cleaner.py`, domínio Cleaner V2 | clean PNGs, masks, `clean-manifest.json`, `level1-balloon-report.json` | query/comparison, Mapear, Level II, especiais, consolidado | stage run, inputs/outputs, artifacts e hashes |
| Mapear | `level3_styled.py`, `level3_styled_worker.py` | `styled-balloon-report.json`, manifest/diagnósticos | query, Bubble Sommelier, Check, imagens API | relatório/artifacts; ocorrências ligadas à revisão |
| Bubble Sommelier | `bubble_sommelier/execution.py`, runtime `report.js` | `report.json`, crops, incorporações Mapear | consulta/review/crops, Check, Sólidos | stage run, artefatos e revisões/ocorrências |
| Auto-Cleaner Check | `auto_cleaner_check.py`, manifest module e rotas | `auto-cleaner-check-manifest.json`, snapshots de fontes/imagens, decisões | Sólidos, Glass/Nível II, Reset, especiais, Combo | decisões, approvals, revisão e dependências |
| Ocorrências de resíduos | `residue_occurrences.py`, `textoff_residue_occurrences.py` | `residue-occurrences-manifest.json` | Check, proteção manual de Glass, especiais | occurrences e decisions com revisão/hash |
| Sólidos | `solid_stage.py`, `solid_reexecution.py` | `solid-white-manifest.json`, outputs/previews, histórico | Combo Turbo, comparação, overview | stage run, outputs e dependência de Check |
| Nível II / Glass | `level2.py`, `level2_process.py`, Cleaner V2 | clean/mask, manifests e relatórios | Check, consolidadores, especiais, Combo | stage run, outputs, fonte + máscara/auxiliares |
| Tratamentos especiais | `special_*_execution.py`, `special_*_output.py`, `special_treatments_manifest.py` | manifests por tratamento, agregado, snapshots/ROI, imagens | revisão/reexecução, composição final, restore, comparação | approvals/decisions, stage run e artefatos imutáveis |
| Consolidado lógico | `consolidated.py::rebuild_consolidated` | clean-manifest de seleção por página, ocasionalmente cópias | Mapear, tratamentos, Combo e query | active artifact por papel/contexto; sem diretório só para seleção |
| Consolidado final | `final_consolidated.py` e publicadores de especiais/Combo | imagens físicas e `final-manifest.json` com histórico | tratamentos, Reset/restore, comparadores, exportação/PDF | publicação/ativo; manter compatibilidade até leitores migrarem |
| Reset/restauração | `reset_check_override.py`, `reset_merge_preflight.py`, `special_page_restore_*` | override/proposta, backup e evidências de hash | Check, Glass, restauração e consumidores de final | evento auditável + versões preservadas; nunca reescrever histórico |
| Combo Turbo | `combo_turbo/*` | jobs, resultados, manifesto, workspace, publicação | Solid/Glass, consolidado lógico/final, UI/API | Combo é parte do diagnóstico Onda 1; decidir se estado/job efêmero migra ao banco ou permanece transitório, mantendo publicação/artefatos no contrato |
| Reconhecimento transparente | `level3_styled.py`, `transparent_publication.publish` | `transparent-recognition.json` e imagens publicadas | `transparent_check_adapter.py`, `auto_cleaner_check_sources.py`, Check | vincular publicação, entrada e hashes à revisão consumida |
| Origem MERGE | pipeline `02_MERGE` | 147 `merge-manifest.json` nas cinco obras inspecionadas | leitores downstream TextOff parcialmente rastreados; `manifests.py::_clean_manifest` lê MERGED legado | resolver contrato de origem e cadeia de hashes antes de alterar caminhos/autoridade |
| Preview especial/staging | `textoff_special/execution.py`, workers e autorização | 70 JSONs/74 PNGs em `reports/experimentos/textoff_especiais_v2` | polling, worker, preview, review e publicador; runtime/retenção precisam rastreio | classificar estado efêmero vs evidência durável e decidir recuperação/retenção |

## Consumidores externos a preservar

| Consumidor | Evidência local | Dependência/risco para corte |
|---|---|---|
| Comparação e preview | `backend/routes/textoff_comparison.py`, `orchestration/textoff_merged/comparison.py` | resolve artefatos por stage; verificar papel e histórico |
| Exportação/PDF | rotas `export_*`, `pdf_*`, referências de arquitetura TextOff | pedido de auditoria exige inventariar consumidores, sem migrá-los em M0/M1 |
| Central V1 | regras em `central_v2/AGENTS.md`, módulos compartilhados e contratos do pipeline | preservar paths/artefatos consumidos; leitores concretos precisam de rastreio por fluxo |
| Auto-Merge, Review/Manual, Balanceamento | `backend/routes/auto_merge/`, `orchestration/`, módulos raiz | identificar dependências, não migrar autoridade nesta fase |
| Submódulo `download/mangago_downloader` | submódulo modificado localmente; dados saved works JSON no submódulo | intocável no diagnóstico e excluído do corte de persistência TextOff |

## Bloqueios de dependência

- A camada de autoridade continua em JSON/paths e `read_authority=legacy`; database resolver ainda não existe.
- O registry registra cinco mappings em dual-write e nenhum está validado; não há prova de igualdade total entre árvores.
- Check e consumidores de Glass/Sólidos dependem de revisões, fontes e máscaras, não apenas da imagem ativa.
- Final e restauração ligam hashes de imagem/manifests e preservam histórico superseded; migração parcial pode quebrar recuperação.
- Combo Turbo está incluído no diagnóstico; decidir persistência do job/workspace efêmero e reconciliação com artefatos publicados.
- Readers/writers de `ORIGINAL`, scripts manuais/V1 e parte dos consumidores downstream de `02_MERGE` ainda não estão confirmados.
- Definir autoridade e retenção de JSONs transitórios, backups de Sólidos e staging de preview especial.
- O resolver de paths de Pincel pode mover diretório legado como efeito colateral; não usar em ferramentas de inventário somente leitura.
