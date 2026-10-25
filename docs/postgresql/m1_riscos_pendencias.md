# M1 — Riscos, lacunas e pendências para M2

## Riscos confirmados

1. **Legado ainda autoritativo:** registry ativa dual-write e leituras legacy; os mappings não estão validados.
2. **Leitura que pode mover arquivos:** `stages.py::_resolve_stage_chapter` faz `os.replace` para migração de caminhos de Pincel em uma resolução. Scanners futuros devem operar por path físico sem chamar esse resolver.
3. **Shadow pode substituir target:** `artifact_migration.py::_mirror_tree` substitui o destino e remove seu backup temporário após o sucesso. Há proteção contra falha durante a troca, mas isso não equivale a histórico de artefatos publicados.
4. **Atomicidade disco/estado é local por writer:** staging, backup e rollback não têm semântica única. A documentação local também aponta essa lacuna.
5. **Identidades próximas não provam mesma obra:** existem árvores separadas `Gazing at you` e `Gazing at you_v2` com imagens iguais por hash; identidade lógica precisa de regra explícita.
6. **Integridade depende de cadeia e papel:** Check, Sólidos, Glass, tratamentos, consolidado final e Reset consomem snapshots, máscaras e hashes vinculados à etapa/revisão.
7. **Cópias exatas em alto volume:** teto de redundância matemática ~36,38 GiB no recorte de `IMG`, `02_MERGE`, `04_TEXTO_OFF` e previews; papéis distintos e histórico impedem converter esse número diretamente em economia.
8. **Consumidores fora da Onda 1:** exportação/PDF, Central V1, Auto-Merge, Review/Manual, Balanceamento e submódulo de download precisam continuar encontrando seus contratos.
9. **Backup global não comprovado:** foram vistos diretórios/arquivos locais ignorados e rotinas de restore específicas; não há evidência de backup/restauração completa do acervo.
10. **Dados operacionais misturam estados:** manifests compartilham nomes (`clean-manifest.json`) em etapas distintas. Classificar por basename cria colisões conceituais.

## Não verificado

- Plano-base v3 e limites de escopo autoritativos; arquivo não localizado no caminho esperado.
- Conteúdo e restaurabilidade dos backups ignorados locais.
- Frequência de alteração por página/run e retenção efetiva dos diretórios staging.
- Cobertura exaustiva de todos os readers externos de cada caminho (incluindo scripts manuais e instalações V1).
- Compatibilidade entre `Gazing at you` e `_v2` como mesma obra ou cópias independentes.
- Existência de arquivos sem consumidor: nenhum foi declarado órfão apenas por estar duplicado ou não aparecer num grep.
- Proveniência completa de cada JSON físico: a contagem foi por arquivos, a matriz por famílias de formato e código.
- Readers/authority de `ORIGINAL/` e parte dos manifests legados não estão confirmados; 147 manifests MERGE e 70 JSONs de preview foram catalogados, mas o grafo de leitores segue incompleto.
- `reports/experimentos/textoff_especiais_v2/` é ignorado pelo Git e tem 11 runs; não foi inferido que todos seus arquivos sejam descartáveis ou duráveis.

## Bloqueios/decisões exigidas antes de M2

- Congelar catálogo de identidades provider/obra/capítulo/página e a política para reprocessamento/revisões.
- Definir contrato por papel e consumidor (`base`, `mask`, `preview`, `published`, etc.), substituindo path global.
- Fechar rastreio de writers/readers de `ORIGINAL`, manifests MERGE, NIVEL3 legado, scripts manuais e instalações V1.
- Definir autoridade e retenção para JSONs transitórios, backups de Sólidos e staging de preview especial; decidir se job state do Combo é efêmero ou persistente.
- Confirmar contrato de reconhecimento transparente que alimenta Check e os papéis das imagens (origem, máscara, snapshot, preview, publicado).
- Fixar compatibilidade do consolidado final e dos leitores externos antes de retirar qualquer caminho.
- Mapear manifests de Check/ocorrências e seus dados de aprovação, snapshots e stale detection a estruturas relacionais.
- Projetar publication e filesystem write-once/content-addressed; acomodar falha antes/depois do commit e reconciliação.
- Definir o que fica como evidência JSON imutável, por quanto tempo e como validar/reimportar.
- Estabelecer backup/restore verificável para banco e binários, retenção, recuperação e autoridade em indisponibilidade.
- Definir casos isolados e dados de referência para equivalência de Glass/Sólidos, Reset, tratamentos e exportação.
- Obter exceções e owners para cada divergência, `LEGACY_UNVERIFIED` ou consumidor não migrável.

## Próxima etapa

M0 e M1 estão documentados. M2 não foi iniciado. Qualquer implementação PostgreSQL, alteração de registry/autoridade, mudança de paths ou migração dos executores exige nova autorização explícita.
