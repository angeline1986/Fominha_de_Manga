# M2 — Decisões arquiteturais e pendências de cutover

**Status:** desenho consolidado para revisão e autorização de implementação M3. Este registro não representa aprovação formal nem inicia M3.
**Documentos relacionados:** [modelo conceitual](m2_modelo_conceitual.md), [modelo relacional](m2_modelo_relacional.md), [armazenamento](m2_armazenamento.md), [migração por contrato](m2_migracao_contratos.md) e [validação final](m2_validacao_final.md).

## Decisões resolvidas no desenho M2

| ID | Decisão de desenho | Regra definida |
|---|---|---|
| D-01 | Identidade de obra/capítulo/página | IDs internos UUIDv4 estáveis; chaves do provider e paths são aliases. Trees distintas permanecem distintas até decisão explícita de catálogo; colisões não são mescladas automaticamente. |
| D-02 | Página fonte e segmento derivado | `source_pages`, `derived_segments`, `derived_segment_versions` e `segment_source_ranges` são entidades distintas. Recomposição cria nova versão do segmento e preserva páginas e origens. |
| D-03 | IDs e revisões | UUIDv4 identifica entidades; números de versão/revisão são monotônicos dentro do slot/sujeito e atualizados sob lock/CAS. SHA-256 identifica somente bytes. |
| D-04 | Autoridade alvo | Após cutover por contrato aprovado, PostgreSQL controla catálogo, estado, dependências, decisões e publicações; Artifact Store controla bytes. Antes disso, a autoridade operacional atual permanece. Não há autoridade concorrente silenciosa. |
| D-05 | JSONs | Dados usados em resolução são normalizados. JSON legado é evidence imutável ou projeção de compatibilidade identificada, nunca authority concorrente após cutover. |
| D-06 | Backend inicial | Primeiro incremento M3 usa filesystem local content-addressed em `FOMINHA_DATA_ROOT`, com chave derivada do SHA e criação exclusiva. Object Lock remoto é evolução se o threat model exigir proteção contra administrador do host. |
| D-07 | Readers legados | Migração por contrato: mapear consumers, adapter/resolver explícito, leitura-sombra, paridade e só então cutover. Readers externos desconhecidos bloqueiam cutover, não o desenho/implementação isolada. |
| D-08 | Dual-write | Import/sombra é read-only; cutover ocorre por contrato e authority única. O registry existente não autoriza dois writers sem reconciliação. Desativação operacional do dual-write atual é gate de cutover. |
| D-09 | Imutabilidade | Workers escrevem somente staging. Store service dedicado publica por create-if-absent atômico, verifica hash/size, fsync e sela modo de leitura; não há API de update/delete. Conflito de bytes é quarentena, sem overwrite. |
| D-10 | Deduplicação | SHA deduplica blobs físicos apenas. Referências lógicas, papéis, capítulos, revisões e histórico permanecem distintos. Paths `TO_*` não são removidos por igualdade de hash. |
| D-11 | Retenção | Classes e referências são modeladas; GC fica desabilitado até prazos, legal hold, backup/restore e processo de aprovação serem definidos por owner. Os exemplos de prazo não são política. |
| D-12 | Aprovação | Decisão append-only por `(approval_batch_id, occurrence_revision_id)`, com sequência, supersedes e ponteiro corrente por CAS. `REVOKE` deixa o sujeito sem aprovação vigente; aprovações históricas preservam ator, imagem e policy version. |
| D-13 | Invalidação | `artifact_dependencies` e `approval_dependencies` apontam para versões/decisões exatas. Mudança de ponteiro ou decisão corrente grava outbox atomicamente; worker propaga `STALE` transitivamente e idempotentemente. Resolver/publicador valida grafo e falha fechado enquanto houver stale ou outbox pendente. |
| D-14 | Policy de ocorrência | Cada revisão/run fixa `policy_version`; mudanças de taxonomia não reinterpretam decisões anteriores. |
| D-15 | Sólidos → Glass | Preview de Sólidos não é publicado automaticamente nem presumido como input de Glass. Continuidade funcional fica para validação própria, sem mudança de algoritmo em M2. |
| D-16 | Combo job/workspace | Run suporta scope batch e múltiplos capítulos; job/result persistentes são eventos/estado auditável e workspace temporário é transitório. Idempotência exige fingerprint igual. |
| D-17 | Reset | Reset é evento append-only com itens e referências compostas para versões de origem/destino/backup e execuções invalidadas; não reescreve versão nem aprovação histórica. |
| D-18 | `LEGACY_UNVERIFIED` | Importação incerta é read-only, não promovível nem aprovável. Reclassificação exige evidência, owner e evento auditável; sem isso permanece em quarentena lógica. |
| D-19 | Falha/indisponibilidade | Aprovar e publicar falham fechados sem authority atual. Cache só é permitido com política versionada/aprovada; RPO/RTO e cache operacional são cutover gates. |
| D-20 | Concorrência | Unicidade é imposta no banco; mudança de ponteiro/publicação usa lock e revision CAS; edges usam SERIALIZABLE e detecção de caminho reverso. Idempotency key com fingerprint diferente é conflito. |
| D-21 | Base normativa | Este conjunto M2, junto ao backlog e evidências M0/M1, é a proposta de escopo para autorização. Sponsor confirma baseline/versão antes de implementação; mudança posterior exige revisão do desenho. |

As regras D-01 a D-20 fecham os quatro bloqueios arquiteturais e as invariantes necessárias para desenhar o primeiro incremento. D-21 e a aprovação formal do owner são gates de autorização do M3, não lacunas técnicas dos quatro bloqueios.

## Pendências necessárias antes do cutover ou expurgo

Estas decisões não bloqueiam autorização para implementar o desenho isoladamente, mas precisam estar resolvidas antes de mudar autoridade operacional, liberar tráfego produtivo ou remover cópias:

- Aprovação formal do owner/sponsor para o baseline M2, escopo M3, owners e exceções. A implementação só começa com autorização explícita.
- Inventário de todos os readers/writers externos e manuais, owners de compatibilidade e evidência de paridade por contrato.
- Prazos finais por classe, legal hold, retenção de backups e autorização/critério de GC; manter GC desabilitado até lá.
- RPO/RTO, restore coordenado PostgreSQL + blobs, frequência de verificação de checksum, política de cache/outage e janela de rollback.
- Credenciais/roles operacionais, segregação do store service, observabilidade e resposta a conflito/corrupção.
- Plano de cortar `dual_write`, JSONs e paths por contrato, incluindo materialização temporária e evidência de ausência de readers ativos.
- Aprovação separada para remover aliases, árvores `TO_*` ou qualquer arquivo legado; hash idêntico sozinho nunca é critério suficiente.
- Gate de ameaça: filesystem POSIX e isolamento do writer protegem contra processos workers sem privilégio; se for requisito resistir a administrador do host/volume, escolher e validar backend com Object Lock antes do cutover.

## Gates propostos

1. **Autorização M3:** owner aprova baseline documental, escopo do primeiro incremento, responsáveis e critérios de aceite. Sem autorização, não iniciar implementação.
2. **Gate por contrato antes de cutover:** readers e writers conhecidos, paridade/restore comprovados, rollback praticável, autoridade única e owner aprova mudança.
3. **Gate de expurgo:** alcance histórico/backup verificado, prazo e legal hold atendidos, relatório antes/depois e autorização específica do owner.

| Campo de aprovação | Registro |
|---|---|
| Decisão formal do desenho | PENDENTE do owner/sponsor |
| Aprovadores e responsáveis | A definir |
| Data e escopo aprovado | A definir |
| Exceções | Nenhuma registrada neste documento |

Este registro consolida propostas de desenho; não autoriza implementação, alteração de authority, importação operacional, cutover ou expurgo.
