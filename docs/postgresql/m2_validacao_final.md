# Validação arquitetural M2 — revisão final

**Data:** 2026-10-23  
**Parecer:** **APROVADO para autorização de implementação do M3**  
**Escopo:** revisão documental das correções aos quatro bloqueios arquiteturais. Este parecer não autoriza por si só a implementação, não inicia M3 e não aprova cutover ou expurgo.

## Parecer

Os quatro bloqueios apontados na validação anterior foram resolvidos no desenho e alinhados entre modelo conceitual, modelo relacional, armazenamento, migração dos contratos e registro de decisões. O pacote M2 está arquiteturalmente pronto para o owner decidir se autoriza M3.

O parecer APROVADO significa que a arquitetura tem regras suficientes para orientar a implementação isolada do primeiro incremento. A aprovação formal do owner/sponsor, os parâmetros operacionais e os gates por contrato continuam pendentes. Eles bloqueiam a autorização formal ou o cutover conforme indicado abaixo, mas não deixam os quatro bloqueios arquiteturais sem solução.

## Resultado dos quatro bloqueios

| Bloqueio | Resultado | Evidência no desenho |
|---|---|---|
| Identidade | **Resolvido** | UUIDv4 estável para entidades internas; `source_pages` e `derived_segments` são entidades distintas; composição de cada versão de segmento preserva referências a páginas e versões exatas em `segment_source_ranges`. SHA-256 identifica bytes, nunca página, execução ou revisão. Capítulo e chaves do provider preservam a forma original; aliases não provocam merge automático. Ver [conceitual](m2_modelo_conceitual.md), [relacional](m2_modelo_relacional.md) e [migração](m2_migracao_contratos.md). |
| Integridade relacional | **Resolvido no desenho** | Chaves candidatas/FKs compostas vinculam subject, chapter, slot, versão, run, scope, publication, item, pointer e approval subject. `stage_run_artifacts` referencia seu `stage_run_scope`; outputs devem pertencer à própria run. Unicidade por slot/versão, idempotency key por contrato e CAS sob lock controlam concorrência. Inserção de dependências usa SERIALIZABLE e busca reversa para evitar ciclos concorrentes. Invariantes cross-table devem ser FK composta ou trigger restritiva no banco; checagem somente na aplicação não basta. Ver [relacional](m2_modelo_relacional.md). |
| Imutabilidade | **Resolvido para o threat model definido** | Backend inicial escolhido: filesystem POSIX local content-addressed. Workers só escrevem staging; store service dedicado cria objeto com operação atômica create-if-absent no mesmo volume, verifica SHA/tamanho e sela o objeto. Não há update/delete no serviço. Bytes iguais são reutilizados; chave existente divergente vai para quarentena; falha/retry não substitui objeto; publicação troca ponteiro por nova versão via CAS. Versões antigas permanecem referenciáveis. Limite explícito: proteção contra processos sem privilégio, não contra administrador do host; Object Lock é gate se esse adversário fizer parte do threat model. Ver [armazenamento](m2_armazenamento.md). |
| Aprovação e invalidação | **Resolvido** | A unidade vigente é `(approval_batch_id, occurrence_revision_id)`. Decisões são append-only, sequenciadas e encadeadas por supersedes; um ponteiro corrente é atualizado por lock/CAS. `REVOKE` significa ausência de aprovação utilizável. `artifact_dependencies` e `approval_dependencies` apontam para versões/decisões exatas; mudança de ponteiro ou decisão e outbox são gravadas na mesma transação. Processamento transitivo é idempotente e o resolver/publicador falha fechado se encontrar estado obsoleto ou fila ainda pendente. Histórico anterior não é apagado. Ver [conceitual](m2_modelo_conceitual.md), [relacional](m2_modelo_relacional.md) e [migração](m2_migracao_contratos.md). |

## Coerência e cobertura dos documentos

| Documento | Resultado desta revisão |
|---|---|
| [Modelo conceitual](m2_modelo_conceitual.md) | Define identidades distintas, autoridade alvo, estados de aprovação, dependências e fail-closed. |
| [Modelo relacional](m2_modelo_relacional.md) | Define entidades, unicidades, ownership, FKs compostas, escopos multi-capítulo, transações concorrentes, eventos append-only e ponteiros. Não é DDL nem migration. |
| [Armazenamento](m2_armazenamento.md) | Define layout CAS, escritor isolado, create-if-absent, conflitos, falhas, reconciliação, preservação de versões e limite do threat model. |
| [Migração por contrato](m2_migracao_contratos.md) | Aplica identidade, authority, imutabilidade, freshness e recuperação comuns a catálogo/MERGE, Nível I, Mapear, Sommelier, reconhecimento transparente, Check, Ocorrências, Sólidos, Glass, especiais, Reset, Combo Turbo e Consolidado Final. |
| [Decisões arquiteturais](m2_decisoes_pendentes.md) | Marca D-01 a D-20 resolvidas no desenho e separa baseline/aprovação M3 de pendências operacionais de cutover/expurgo. |

### Consistência verificada

- IDs lógicos não são derivados de SHA, filename ou caminho. Página fonte, segmento, versão do segmento, execução, slot, versão de artefato e publicação têm identidade própria.
- Cada run pode cobrir capítulo, página, segmento ou lote, incluindo Combo multi-capítulo. Cada artefato da run declara scope coerente.
- Versões factuais e decisões não são editadas após commit. Estados de validade são eventos/projeções, e publicação/approval usam ponteiros concorrentes com CAS. Consumers registram dependência de aprovação exata, para que revogação ou nova decisão invalide também artefatos derivados sem troca de blob.
- Persistência de bytes e transação relacional não são tratadas como atômicas entre sistemas: estados de staging, órfão, conflito e publicação parcial têm reconciliação idempotente e não sobrescrevem versões existentes.
- `TO_*`, JSONs e cópias permanecem até cutover por contrato. Deduplicação física não remove identidade/referência lógica; igualdade de hash não basta para apagar paths.
- `LEGACY_UNVERIFIED` permanece não promovível e sem aprovação inferida. Ausência de ator, proveniência ou backup produz exceção explícita.

## Pendências que bloqueiam M3

**Bloqueios técnicos de desenho: nenhum identificado nesta revisão.**

Para passar de “pronto para autorização” a “M3 autorizado”, o owner/sponsor precisa registrar aprovação formal do baseline M2, escopo do primeiro incremento, responsáveis e critérios de aceite. Essa autorização é uma decisão de governança, ainda pendente, e não é substituída por este parecer.

## Decisões e evidências necessárias somente antes do cutover ou expurgo

- Inventário e owner dos readers/writers externos e manuais; adapter e compatibilidade por contrato.
- Evidência de paridade, recuperação e rollback em ambiente isolado para cada contrato.
- RPO/RTO, restore coordenado de PostgreSQL + blobs, política de cache/outage e frequência de checksum operacional.
- Prazo de retenção por classe, legal hold, processo de GC e owner que autoriza remoção; GC deve permanecer desabilitado até a definição.
- Plano de desligamento de `dual_write`, JSONs e paths antigos após readers migrarem; monitoramento de acessos durante a janela acordada.
- Decisão de threat model sobre resistência a administrador do host; se exigida, backend com Object Lock ou controle equivalente precisa ser validado antes de cutover.
- Aprovação separada para remover aliases, cópias, árvores `TO_*` ou qualquer dado operacional.

Estas pendências são gates de produção/cutover ou expurgo; não reabrem os quatro bloqueios do desenho. A especificação de política de aprovação por contrato deve acompanhar a implementação de cada adapter, preservando a regra comum de revisão exata, decisão vigente e dependência fresca.

## Recomendação

Solicitar ao owner/sponsor a decisão formal sobre o baseline M2 e, se aprovado, autorização explícita do escopo de implementação M3. Depois, implementar somente em ambiente isolado, seguindo primeiro as invariantes relacionais, o store CAS e a máquina de aprovação/invalidação; manter qualquer cutover condicionado aos gates listados acima.

## Limites da revisão

Esta validação foi documental. Não houve implementação, criação/inicialização de PostgreSQL, migrations, execução de tratamentos ou testes, alteração de código/JSON/imagens, operação de cutover ou modificação de dados operacionais. A aprovação avalia suficiência do desenho escrito; a implementação futura ainda deverá demonstrar que as constraints, permissões, operações atômicas, transições e recuperação correspondem ao especificado.
