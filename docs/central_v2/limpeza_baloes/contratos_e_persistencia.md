# Contratos, artefatos e persistência — Central V2

## Contrato entre camadas

```text
frontend/texto_off/<tela>
   → frontend/_app/api ou cliente específico
   → backend/routes/<domínio>.py
   → backend/orchestration/<domínio>
   → processamento/limpeza_baloes ou runtime dedicado
   → diretório de estágio + manifesto
   → consulta valida fonte/manifesto antes de servir o artefato
```

Arquivos de referência: `central_v2/frontend/_app/api/textoff.js`, `laboratorio.js`, `comparison.js`; rotas `textoff_merged.py`, `textoff_special.py`, `special_treatments.py`, `textoff_comparison.py` e `laboratorio_*.py`; orquestrações correspondentes.

## Referências de persistência verificadas

| Artefato | Diretório / arquivo | Writer/leitor relevante |
|---|---|---|
| Cleaner Nível I | `FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/<capítulo>/{clean,mask,json}/` | `level1_cleaner.py`, `level1_worker.py`, `cleaner_v2/integration.py` |
| Nível II | `TO_MERGED_NIVEL_II/<capítulo>/{clean,mask,json}/` | `level2_process.py`, `cleaner_v2/level2.py`, validação V2 |
| Consolidado I/II | `TO_MERGED_CONSOLIDADO/<capítulo>/json/clean-manifest.json` | `consolidated.py`; reconstrói referência lógica das fontes atuais |
| Final consolidado | pasta final Text Off por capítulo, `json/final-manifest.json` | `final_consolidated.py`, `final_consolidated_manifest.py` |
| Restauração especial | diretório de staging/backup escolhido por módulo de restore | `special_page_restore.py`, `_backup.py`, `_check.py`, `_source.py` |

Os nomes exibidos são os defaults/caminhos dos módulos atuais, e devem ser revalidados em alterações de schema. A leitura de final manifest exige schema `textoff_consolidado_final_manifest_v1` e hash esperado do arquivo.

## Integridade e autoridade

- `artifact_paths.py` restringe referências a artefatos seguros de uma categoria dentro do diretório do capítulo.
- A consolidação valida manifests-fonte, estágio/algoritmo, hashes dos manifests precursores, conjuntos de fontes, contagens e hashes dos artefatos.
- Manifestos são escritos no formato JSON e vários escritores promovem um diretório preparado após validação. A estratégia exata (substituição, backup e rollback) é local ao escritor; não há uma única semântica para todo Text Off.
- A restauração de página gera proposta sobre os hashes atuais, compara o manifesto final e o especial e valida novamente antes de publicar. Evidência de backup registra hashes para permitir conferir a fonte/estado restaurados.
- O registry `artifact-migration-registry.json` e `artifact_migration.py` documentam compatibilidade/migração de paths de artefatos. Migração de arquivo em disco é comportamento operacional distinto de reorganização da documentação.

## Snapshots, histórico e invalidação

O fluxo V2 possui `cleaner_revision.py` no frontend e módulos para snapshots/backup/invalidação específicos de etapa/restauração. A cobertura de snapshots por todos os writers não foi verificada. Antes da reconstrução, rastrear cada mutação do manifest precursor até seus consumidores e o que é invalidado.

## Não verificado

- Schema completo e versionamento de todos os manifests (cada etapa tem writer próprio).
- Política única de retenção/limpeza de staging.
- Garantia de rollback em todo writer além dos que montam staging e fazem promoção explícita.
- Compatibilidade de hashes ou nomes entre manifests da V1 e V2.
