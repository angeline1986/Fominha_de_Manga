# M3 — Pendências e gates seguintes

**Parecer técnico da homologação M3:** **REPROVADO para liberação do próximo milestone.** Os bloqueios P0/P1 abaixo precisam ser resolvidos e retestados antes de considerar qualquer autorização posterior. Os demais itens bloqueiam ativação, migração real, troca de autoridade ou cutover.

## Bloqueios da homologação

### P0 — Escrita do papel da aplicação pode contornar validação

Migration 006 concede `INSERT` em todas as tabelas do schema a `fominha_app`. O teste sintético assumiu `SET ROLE fominha_app` e inseriu um evento `VALID` para versão sem passar por `ArtifactRepository.set_state()` nem registrar validação de hash. O banco aceitou a operação. O papel também recebe `INSERT` em pointers/publicações e registros de decisão, então as invariantes implementadas somente nos repositórios não são barreira contra gravações SQL diretas.

**Recomendação:** reduzir grants por tabela/coluna e impedir transições privilegiadas por escrita direta. Escolher uma API SQL restrita (funções com validação/SECURITY DEFINER bem revisada) ou outro mecanismo que faça com que o papel de runtime não consiga validar, publicar ou aprovar por conta própria. Incluir testes de privilégio conectando-se como o papel efetivo da aplicação.

### P1 — Aprovação não está vinculada relacionalmente ao snapshot e à página corretos

O teste confirmou que `approval_batches` aceita `source_snapshot_version_id` cujo slot pertence a outro capítulo. Também aceitou uma decisão de aprovação cujo `reviewed_image_version_id` pertence a outra página que a revisão da ocorrência. As FKs atuais garantem existência de IDs, mas não essas relações de escopo.

**Recomendação:** validar chapter/run/snapshot na criação do lote e relacionar decisão, revisão, ocorrência e imagem por FKs compostas ou triggers de integridade; repetir as provas negativas usando o papel da aplicação.

### P1 — Lote de importação concluído continua mutável

`LegacyImportRepository.record()` insere itens sem verificar o status do lote, e o schema não possui trigger que feche itens quando o lote passa a `COMPLETED`, `PARTIAL` ou `FAILED`. A prova negativa conseguiu anexar item depois de `COMPLETED`.

**Recomendação:** aceitar itens somente enquanto o lote estiver `RUNNING`, impor transições terminais e testar imutabilidade do snapshot de importação depois do fechamento.

## Necessários antes de conectar a dados operacionais

1. Aprovar e provisionar ambientes PostgreSQL, versões suportadas, alta disponibilidade, TLS, autenticação e rotação de credenciais.
2. Rever a matriz de privilégios e associar os papéis sem login (`fominha_app`, `fominha_migrator`, `fominha_retention`) a identidades reais; definir quem pode migrar e auditar.
3. Escolher backend do Artifact Store, durabilidade, replicação, monitoramento de corrupção e proteção técnica além das permissões locais de arquivo. O adaptador M3 implementa filesystem local e não oferece armazenamento imutável/WORM.
4. Aprovar frequência, retenção, local externo, criptografia e exercícios de restauração conjunta de PostgreSQL e blobs; estabelecer RPO/RTO.
5. Validar limites de concorrência, volume, tamanho de imagem, latência e crescimento do outbox com perfil representativo, sem alterar os algoritmos existentes.
6. Fechar mapeamento de cada contrato/artefato legado para o catálogo e o procedimento de classificação de `LEGACY_UNVERIFIED`, incluindo resolução manual de conflitos.

## Pendências de concorrência e recuperação

- **P1 — Retry de serialização:** duas publicações concorrentes no mesmo slot deixaram somente um vencedor e uma revisão ativa. O perdedor propaga `SerializationFailure`; `PublicationRepository` não faz retry nem traduz a exceção para conflito idempotente. Definir retry limitado usando a mesma chave de idempotência, sem duplicar publicação ou responder sucesso ambíguo.
- **P2 — Papéis globais no rollback:** `down` completo passou em cluster descartável com um banco. Em cluster de teste com grants M3 num banco restaurado adicional, migration 006 falhou ao tentar remover `fominha_app`, um papel global ainda referenciado no outro banco. Separar criação/remoção de roles globais das migrations por database ou documentar/automatizar limpeza coordenada do cluster.
- **P2 — `down` é destrutivo:** migrations `down` apagam schema e dados; não são rollback sem perda. Semântica de recuperação exige dump restaurável e cópia coordenada de blobs; a prova sintética passou, mas não há agendador/orquestrador de backup.
- **P2 — Reprodutibilidade:** a suíte agora requer banco novo, vazio e prefixo `fominha_m3_test_`; não reutilizar o banco nem o Artifact Store temporário de uma execução anterior.

## Necessários antes de integração e cutover

- Plano de integração por contrato da Onda 1 e critérios de coexistência/retirada de cada leitor e produtor legado.
- Aprovação explícita para mudança de fonte de autoridade, ativação de `dual_write` ou alteração de `read_authority`; estes pontos não foram modificados em M3.
- Plano de ensaio, reconciliação, rollback, janela de corte e responsáveis pela operação.
- Revisar semântica de Reset para lotes multi-slot. O histórico mantém detalhes por `reset_items`; colunas de origem/destino do evento ficam nulas quando há mais de um slot para evitar representar um item como se fosse o lote inteiro.

## Riscos conhecidos do protótipo

- O Artifact Store usa sistema de arquivos local. Hard-link create-if-absent evita overwrite concorrente pela aplicação e arquivos recebem modo somente leitura, mas administrador do host ainda pode alterar/remover bytes.
- Manifesto e dump precisam compartilhar ponto de consistência com o conjunto de blobs; M3 documenta a coordenação, mas não implementa agendador de backups.
- Não houve teste de carga, falha de host, perda de disco, restauração em outro ambiente, concorrência elevada nem teste de credenciais não privilegiadas.
- Migrations `down` são para bancos descartáveis. Papéis PostgreSQL são globais ao cluster; grants em outros bancos podem impedir sua remoção até que esses bancos sejam tratados pelo operador.
- A validação feita dentro dos repositórios não é suficiente enquanto `fominha_app` puder inserir diretamente estados e relações que contornam essas validações.
- As referências de aprovação podem ser consistentes por existência e ainda apontar para outra página/capítulo; integridade relacional incompleta pode produzir decisão válida para o conteúdo errado.
- Lotes legados fechados não são imutáveis no schema atual e podem receber itens tardios, alterando retrospectivamente seu relatório.

## Fora de escopo e decisão

Não iniciar M4, migrar imagens/JSONs, ativar autoridade PostgreSQL, alterar executores ou remover `TO_*`/legado. Revisar grants e constraints, corrigir os quatro testes esperados e obter execução limpa sem `expected failures`; então atualizar o parecer M3. Depois disso, as decisões de ambiente, segurança, política de dados, contratos da migração e cutover continuam exigindo aprovação separada.
