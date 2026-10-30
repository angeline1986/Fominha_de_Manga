# M3 — Pendências e gates seguintes

**Parecer técnico da homologação M3:** os quatro bloqueios de integridade foram corrigidos e passaram em 20 testes sintéticos. A ativação operacional permanece pendente; `fominha_app` não tem escrita direta em tabelas, mas pode registrar metadados do catálogo por funções restritas.

## Bloqueios de integridade corrigidos

### P0 — Escrita do papel da aplicação pode contornar validação

Migration 009 revoga os grants de escrita de 006, inclusive os grants de `UPDATE` por coluna e o `INSERT` padrão em tabelas futuras. O teste usa `SET LOCAL ROLE fominha_app`, confirma `current_user`, percorre as tabelas e verifica que o papel não pode inserir, atualizar ou excluir. Também tenta inserir diretamente estado `VALID` e publicação; ambos são recusados.

**Próximo passo para uso operacional:** estender a API de escrita restrita além do catálogo, com identidades distintas para validação de bytes, aprovação e publicação, sem devolver grants diretos ao papel de runtime. O adaptador M3 permanece opt-in e não está ligado aos executores.

### P1 — Aprovação não está vinculada relacionalmente ao snapshot e à página corretos

Migration 008 exige que o snapshot e o run do lote cubram o capítulo e, quando aplicável, a página/segmento. A ocorrência do assunto e a imagem da decisão também precisam pertencer à página do snapshot, quando ele é uma página. Os testes cobrem capítulo diferente e outra página do mesmo capítulo, inclusive por SQL direto.

O papel da aplicação não tem escrita direta em tabelas e as funções atuais cobrem apenas catálogo; não consegue criar lote ou decisão. Os triggers protegem também gravações feitas pela conexão privilegiada dos testes.

### P1 — Lote de importação concluído continua mutável

`LegacyImportRepository.record()` verifica o lote com lock antes de inserir. Migration 008 só aceita novos itens enquanto o lote estiver `RUNNING`; o lock serializa inserção e fechamento. Itens são append-only e a transição do lote é irreversível para `COMPLETED`, `PARTIAL` ou `FAILED`. Testes de repositório e SQL direto passaram.

O relatório da importação fechada não recebe itens tardios nem mutações dos itens já registrados.

## Necessários antes de conectar a dados operacionais

1. Aprovar e provisionar ambientes PostgreSQL, versões suportadas, alta disponibilidade, TLS, autenticação e rotação de credenciais; definir a API de escrita confiável antes de conectar executores.
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
- O papel de runtime só escreve metadados do catálogo por funções restritas. Os demais repositórios ainda precisam de API própria antes de funcionar com credenciais operacionais de menor privilégio.

## Fora de escopo e decisão

Os quatro testes esperados agora passam normalmente. As migrations 008/009 e a nova 010 fizeram `down`/`up` em bancos descartáveis. Antes de integrar dados reais, ativar autoridade PostgreSQL, alterar executores ou remover `TO_*`/legado, ainda faltam decisões de ambiente, segurança, política de dados, contratos da migração, API de escrita para as demais operações e cutover.
