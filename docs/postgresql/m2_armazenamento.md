# M2 — Armazenamento, imutabilidade e retenção

**Status:** desenho técnico fechado para revisão/aprovação; filesystem operacional atual permanece intacto até autorização de implementação/cutover.
**Escopo:** objetos binários e compatibilidade de paths da Onda 1. Não cria diretórios nem altera dados.

## Estrutura canônica proposta

Manter metadados/índices no PostgreSQL e bytes fora do banco. A decisão de desenho é um único object store em filesystem POSIX dedicado sob a raiz de dados configurada, com layout content-addressed:

```text
${FOMINHA_DATA_ROOT}/artifacts/sha256/<sha[0:2]>/<sha[2:4]>/<sha256>
```

O hash completo do conteúdo é a chave física. A extensão original/media type ficam nos metadados de `artifact_objects`; não compõem identidade. Work/chapter/page/stage/role/version não determinam a chave do blob, pois bytes iguais podem ser referenciados em vários papéis sem colapsar suas identidades lógicas. O prefixo não é usuário-editável; o serviço sempre valida que a key resolve sob a raiz autorizada.

O backend escolhido para o primeiro incremento M3 é filesystem local no volume de `FOMINHA_DATA_ROOT`, alinhado ao backlog vigente e aos executores locais existentes. Um backend remoto (S3/Object Lock ou equivalente) fica como decisão futura de infraestrutura, sem mudar identidade `storage_key`/SHA. Replicação/backup não é authority de escrita e deve preservar a key imutável.

## Contrato de escrita e leitura

1. Worker grava apenas em staging privado e calcula SHA-256, bytes e media type. Workers não têm write permission no object root; nenhuma rota da aplicação recebe path final para escrita.
2. Um único `artifact-store` service/UID valida conteúdo e contrato. O temp object fica no mesmo filesystem/shard da key final, com nome aleatório fora do namespace hash.
3. O service cria a key final por operação atômica `link(temp, final)`/create-if-absent equivalente, que falha se o destino existir. Nunca abre key existente com `O_TRUNC`, nunca usa `replace`/rename destrutivo e não oferece endpoint de overwrite.
4. Após create, faz fsync do objeto e diretório, aplica mode read-only, remove o nome temporário e emite receipt com sha/key/size. O diretório publicado é read-only para app workers e readers; só a identidade do store service tem create permission. O store service não oferece delete/update; limpeza fica em ferramenta separada sob role/credencial de retenção.
5. Se key já existir e bytes + size conferirem, retorna `ALREADY_PRESENT` e reutiliza blob; se a conferência divergir, retorna conflito de integridade (`HASH_KEY_CONFLICT`), põe a key em quarantine e bloqueia publicação. Não tenta reparar a mesma key.
6. A transação registra object, artifact version, run e dependências com idempotency key. A promoção/ponteiro ativo é outra transação, com revisão esperada e approvals revalidados.
7. Readers só recebem `artifact_version_id` ou slot + contexto via resolver; metadata determina a key. O caminho final não é input de confiança do client ou worker.
8. Corrupção ou perda é reparada por cópia que confere exatamente o SHA esperado; restauração cria/recria a key apenas se ausente e usa create-if-absent. Key existente divergente segue quarantine/incidente; não há overwrite silencioso.

**Garantia e limite:** workers da aplicação não conseguem sobrescrever objeto por permissão/mount e o único API de ingestão cria keys exclusivamente. O controle cobre processos não privilegiados da aplicação; host root/storage admin continua capaz de alterar o filesystem e deve ser controlado por RBAC, auditoria e backups/WORM. Se o requisito incluir resistência a administrador do host, será necessário object storage com Object Lock antes de cutover.

O SHA identifica bytes apenas. A versão lógica ainda precisa apontar para página, role, stage run, revisão, fontes e aprovações. Igualdade SHA não torna duas páginas ou revisões intercambiáveis.

## Classes de artefatos

| Classe | Exemplos | Regra proposta |
|---|---|---|
| Fonte | páginas IMG e inputs MERGE | Importar por bytes/hash; preservar identidade de página e origem MERGE, sem tratar como saída TextOff |
| Saída intermediária | clean/mask Nível I/Glass, Mapear, Sommelier | Object imutável vinculado a run/role e dependências. Máscara é objeto separado, com referência de correspondência à imagem/página |
| Decisão/evidência | Check, ocorrências, reports/manifests | Campos usados em consultas viram relações; manifest original fica como objeto evidence quando exigido. Reimportar não cria approval automaticamente |
| Preview/staging | Sólidos, tratamentos antes de promover, workers especiais | Versão `PREVIEW`; nunca ativa/publicada sem ação explícita e validação de fontes |
| Publicado | Consolidado Final/Combo e saídas aprovadas | Write-once; novas versões produzem novos objetos e publicação/ponteiro ativo. Sem overwrite da mesma identidade |
| Backup/restore | imagem anterior, versão superseded, checkpoints selecionados | Backup é referência a versão imutável quando possível; preservar trilha e motivo da restauração |

### Contrato de imagem e máscara

- Cada imagem é artefato com `role` explícito, por exemplo `source`, `clean`, `mask`, `preview`, `published`, `crop` ou `report`; roles finais precisam ser aprovados em catálogo versionado.
- Mask referencia o subject (source page ou derived segment), a versão exata da imagem-base, a run que a produziu, dimensões, encoding e algoritmo. Máscara não pode ser aplicada a imagem com dimensões ou `source_version_id` diferentes.
- Para outputs por página, persistir width/height, media type, bytes, SHA-256 e digest das dependências. Normalizar cor/orientação só se o contrato algorítmico atual já o fizer; M2 não altera pixels.
- Aplicação/preview de máscara deve falhar fechado quando artefato ou versão base não confere. Mesma imagem por SHA em outro page/role não satisfaz uma dependência sem referência lógica válida.

## Transição dos diretórios `TO_*` e duplicações

`TO_MERGED_NIVEL_I`, `TO_MERGED_NIVEL_II`, `TO_MERGED_NIVEL_III` e `TO_MERGED_CONSOLIDADO` não serão removidos nesta etapa. Proposta de transição:

1. Catalogar paths presentes e importar arquivos/metadados de forma somente leitura, registrando estado de origem, hash, contrato e classificação. Onde falta proveniência, marcar `LEGACY_UNVERIFIED`.
2. Comparar manifest, arquivo, role, página e revisão. Hash igual sem igualdade de contexto não é equivalência contratual.
3. Executores novos escrevem objeto canônico e registram versões novas; o resolvedor lê a autoridade explicitamente configurada. Não manter dois writers autoritativos.
4. Durante compatibilidade, readers antigos podem receber caminho resolvido para o mesmo blob; se precisarem de arquivo materializado, classificar como projeção temporária, somente leitura e rastreada. Essa projeção não conta como objeto canônico nem como autorização de eliminação do legado.
5. Migrar readers e writers por contrato, com métrica de acessos legacy, parity checks e rollback documentado. `TO_MERGED_CONSOLIDADO` continua distinto do output final até todos os consumidores estarem no contrato novo.
6. Após paridade, owners e backup/restore verificados e janela de rollback encerrada, proposta de retirar aliases/projeções antigos por lote aprovado. Remoção real exige autorização operacional separada.

### Deduplicação segura

- **Permitida como proposta no object store:** dois objetos com SHA idêntico podem compartilhar a mesma key física, enquanto suas versões lógicas, dependências, ocorrências e publicações seguem separadas.
- **Não inferir:** apagar caminho legado, snapshot, máscara ou publicação somente porque o hash se repete. Papel, revisão, owner, reader e restore são pré-condições.
- **Processo futuro:** inventário → comparação por contrato/contexto → seleção do blob canônico → atualização controlada de referências → leitura de paridade → janela de rollback → aprovação de expurgo → relatório antes/depois. Toda etapa deve ser idempotente e reversível até aprovação final.
- O excedente de 36,38 GiB levantado em M1 é limite matemático agregado; não constitui alvo de limpeza nem previsão de espaço recuperado.

## Imutabilidade e histórico

Blobs write-once por key. `artifact_versions`, dependencies, approval decisions, publications e audit history são append-only no nível lógico, protegidos por roles DB e constraints. O ponteiro ativo pode mudar transacionalmente, com expected revision e `previous_version_id`. Views/symlinks de compatibilidade são derivadas, read-only e não aceitam gravação de volta ao blob. Uma reexecução sempre tem `stage_run_id` distinto; idempotent retry com o mesmo request key só reutiliza a versão se input fingerprint/outputs forem iguais, caso contrário retorna conflito de idempotency e exige novo run.

O storage precisa verificar checksum em ingestão, publicação, restore e auditoria periódica. Se verificação periódica for amostrada, frequência e risco residual devem ser aprovados. Falha de checksum marca objeto `CORRUPT/QUARANTINED`, bloqueia promoção e inicia recuperação por cópia comprovada/backup; nunca troca silenciosamente o hash registrado.

## Retenção proposta

Não executar expurgo automático durante migração ou janela de rollback. Definir tabela de política por classe antes de operar:

| Classe | Retenção inicial proposta | Condição de encerramento |
|---|---|---|
| Fonte/import e artefato publicado | indefinida até política aprovada; manter ativo e histórico referenciado | somente expurgo autorizado após não haver dependência/referência e restore auditado |
| Runs e evidências de decisão/publicação | manter durante migração; retenção definitiva depende owner/legal/produto | preservar trilha mínima mesmo que blob associado expire |
| Preview concluído e não promovido | candidato a prazo curto após conclusão e sem dependência, por exemplo 30 dias | prazo é sugestão, requer aprovação; remover apenas com manifest/metadata conforme política |
| Worker/job falho ou interrompido | candidato a retenção maior, por exemplo 90 dias, para diagnóstico/retry | prazo é sugestão, requer aprovação; não apagar se referenciado por run ou incident |
| Cópia de compatibilidade/alias legacy | até reader removido e janela de rollback encerrada | owner valida migração e volume de acessos legacy chega ao limiar acordado |
| Backup físico | conforme RPO/RTO e legislação/negócio | backup só expira depois de backup posterior e restore verificado |

Valores 30/90 dias são opções iniciais para discussão, não política decidida. Necessário owner, custo, classificação de dado e retenção por jurisdição antes de configurar tarefa de limpeza.

## Falhas, recuperação e rollback

PostgreSQL e filesystem/object store não compartilham transação atômica. Proposta de protocolo recuperável:

- **Falha antes da gravação do blob:** run fica `FAILED`; não existe artifact version nem active pointer.
- **Blob escrito; transação de metadata falha:** blob fica `ORPHAN_CANDIDATE`; reconciler busca referência, mas não apaga automaticamente. Após grace period, backup/ledger check e aprovação de GC, pode ser removido por ferramenta de retenção.
- **Metadata de versão criada; publicação não confirmada:** versão fica `STAGED/UNPUBLISHED`; publication row e outbox são idempotentes. Reconciler finaliza apenas se dependências, approvals, object checksum e expected active revision continuam válidos. Se a revisão mudou, publication vira `CONFLICT`, sem alterar o ponteiro.
- **Transação de publicação concluída, resposta perdida:** `idempotency_key` retorna o resultado existente. Mesmo request key com fingerprint diferente resulta `409 IDEMPOTENCY_CONFLICT`; nunca cria overwrite.
- **Duas publicações concorrentes no mesmo slot:** uma vence compare-and-swap do `active_artifacts.revision`; a outra fica `CONFLICT` e precisa novo preflight/publication ID. A versão anterior permanece íntegra e recuperável.
- **Objeto ausente/corrompido:** pointer não altera; bloquear leitura/publicação, localizar outra cópia pelo hash, registrar recuperação e validar antes de atualizar localização.
- **DB indisponível:** não aprovar nem publicar com estado potencialmente stale. Cache de resolução só pode ser usado por política aprovada com revision/expiry; sem cache elegível, fail closed.
- **Rollback funcional:** nova publication/restoration aponta para artifact version anterior; não sobrescreve blobs. Rollback de schema é procedimento de migration futura, separado de rollback de artefato.

Backups devem cobrir banco e blobs de modo coordenado (snapshot/manifesto de backup contendo revision/IDs e checksums); critérios RPO/RTO e exercício de restore são decisões pendentes. Restaurar banco sem objetos correspondentes ou objetos sem seu catálogo não é restore completo.

## `LEGACY_UNVERIFIED`

Classificar com estado e motivo, sem inferir ausência de uso:

- path/schema sem origem comprovada, readers desconhecidos ou JSON inválido mantém referência de origem, SHA, bytes, timestamps disponíveis e `issue_code`;
- nunca criar aprovação, versão ativa ou publicação automática a partir desse estado;
- preservar em quarantine/read-only no modelo relacional e no storage enquanto houver bloqueio;
- resolver por owner e evidência de consumer, ou arquivar como não migrado com justificativa e prazo de reavaliação;
- conflitos de mesmo nome com hashes/papéis diferentes são registros distintos; não “corrigir” pelo basename.

## Decisões necessárias

Materialização compatível durante transição; catálogo final de roles; prazos/owners de retenção; frequência de checksum; RPO/RTO, outage/cache policy; condições e autoridade para expurgo; adoção futura de Object Lock remoto se o threat model incluir host administrator. O desenho do primeiro backend POSIX e create-if-absent está escolhido, sujeito à aprovação formal e sem implementação neste documento.
