# M3 — Implementação PostgreSQL e persistência

**Status da revisão técnica:** bloqueios de integridade M3 corrigidos e aprovados em testes sintéticos; integração operacional ainda pendente.
**Escopo:** infraestrutura, schema versionado, camada de persistência e Artifact Store para dados sintéticos.  
**Dados reais:** não migrados; diretórios operacionais e executores existentes fora do escopo.

## Baseline antes de alterações de código

Capturado em 2026-10-23 antes de criar ou modificar código:

- Branch `develop`, HEAD `dc4975f775d08ddec207471d2adb1ef3ed7440a7`.
- Diff tracked preexistente: 8 inserções e 18 remoções em 6 caminhos: `central_v2/frontend/_shell/navigation.js`, dois testes frontend, `docs/Refatoracao/pendencias_central_v2.html`, `docs/central_v2/limpeza_baloes/README.md` e gitlink `download/mangago_downloader`.
- Arquivos não rastreados preexistentes: `docs/backlog/central_v2_degrade_performance.md`, `docs/central_v2/limpeza_baloes/funcionalidades_fora_sidebar.md` e o conjunto documental `docs/postgresql/`.
- O submódulo `download/mangago_downloader` está em `f1f2da0c6e1802362026c5cc79f7c0a1a526d7ec`; seu worktree já contém alterações em `.gitignore` e `README.md`, `.venv-test/` e dois patches locais não rastreados. Preservar todo esse estado.
- Itens locais ignorados observados incluem `.venv-test`, caches, backups e `gui_config.json`; nenhum segredo ou conteúdo operacional foi aberto.
- Busca estática não encontrou `DATABASE_URL`, cliente PostgreSQL ou SQLAlchemy no código Python/dependências. Ambiente local disponível nesta sessão: Python 3.12.7, psycopg 3.3.4 e PostgreSQL 16.14 (`initdb`, `psql`, `pg_dump`, `pg_restore`).
- Regras lidas: `central_v2/AGENTS.md`; limite de 200 linhas por arquivo de código e preservação dos algoritmos, V1, manifests e executores. A implementação nova ficará isolada e cada arquivo de código será mantido dentro do limite.

Este baseline é aditivo; não restaura nem normaliza qualquer alteração preexistente. Nenhum comando de fetch, checkout, clean, reset, tratamento ou migration foi executado antes deste registro.

## Arquitetura de implementação

Implementar uma camada opt-in, sem integração com executores nem ativação de authority. Configuração usa variáveis de ambiente; conexão e transações são encapsuladas; migrations SQL versionadas têm rollback explícito; repositórios registram entidades e relações; resolver e invalidação falham fechados. O schema implementa o modelo relacional M2 e evita usar JSONB como substituto de relações centrais.

O Artifact Store local usa raiz configurada separada do repositório, chave content-addressed SHA-256, criação atômica sem overwrite e registro de conflito. Testes usam cluster PostgreSQL descartável e raiz temporária isolada do repositório; não usar `FOMINHA_DATA_ROOT` nem caminhos do acervo operacional.

## Implementação e decisões realizadas

- Adaptador opt-in em `central_v2/backend/persistence/postgresql/`: configuração por ambiente, conexões/transações, CLI de saúde/status e migrations versionadas com checksum, lock consultivo e rollback explícito.
- Dez migrations criam catálogo, escopos e execuções, segmentos, objetos/blobs, versões/dependências, ocorrências/revisões/aprovações, publicações/pointer CAS, Reset/auditoria/importação legada, triggers de integridade e papéis PostgreSQL. As migrations 008/009 corrigem escopo de aprovações, fechamento da importação e privilégios do papel da aplicação; a 010 abre a primeira API de escrita restrita para o catálogo.
- Repositórios cobrem catálogo, runs, artefatos, aprovações, publicação/Reset, auditoria e importação legada. Resolver falha fechada para estados, dependências, aprovação, invalidação pendente e bytes divergentes. Reconciliador apenas reporta blobs ausentes, corrompidos ou órfãos; não remove dados.
- Artifact Store local configurável usa SHA-256 como chave de conteúdo, gravação atômica create-if-absent, modo de arquivo somente leitura, verificação ao resolver/publicar e marcador de conflito. SHA identifica o conteúdo físico, não substitui a identidade lógica da página, execução, slot ou versão.
- Importação aceita `LEGACY_UNVERIFIED` sem associar versão promovida. Tal registro não o torna válido nem autoriza publicação.
- Migrations 005 e 007 fixam `search_path` dentro das funções de trigger. Os testes encontraram a falha quando as funções eram chamadas fora da sessão de migração; ela foi corrigida e revalidada.
- `dual_write`, `read_authority`, executores e autoridade legada permaneceram intocados; nenhum dado operacional foi migrado e nenhum tratamento foi executado.
- A suíte ampliada passou com 20 testes, sem falhas esperadas. `fominha_app` não tem escrita direta em tabelas, inclusive futuras; não consegue validar, aprovar nem publicar por SQL direto. Triggers vinculam lote/snapshot/run e ocorrência à página correta, decisão à página revisada e impedem gravar ou alterar itens de importação após o fechamento.
- A API de escrita do catálogo usa seis funções `SECURITY DEFINER` de propriedade do papel sem login `fominha_migrator`, com `search_path` fixo, `EXECUTE` revogado de `PUBLIC` e concedido apenas a `fominha_app`. O repositório do catálogo chama essas funções; o teste executa o fluxo como papel efetivo da aplicação e confirma que `INSERT` direto segue proibido. Os demais repositórios de escrita ainda exigem conexão privilegiada no ambiente sintético; não configurar essa identidade como runtime operacional.
- Concorrência de publicação manteve um único ponteiro vencedor; o perdedor pode propagar `SerializationFailure`, sem retry/normalização no repositório. A publicação rejeitada não deixou um segundo pointer, mas o chamador precisa tratar o erro.
- Dump/restore de PostgreSQL e cópia/restauração do Artifact Store sintético preservaram as contagens e hashes verificadas. Isso não remove as lacunas de autorização e integridade acima.

Ver resultados reproduzíveis em [testes e evidências](m3_testes_evidencias.md). Pendências de ambiente, segurança e cutover estão separadas em [pendências](m3_pendencias.md).

## Backup e restauração

O [README do adaptador](../../central_v2/backend/persistence/postgresql/README.md) documenta comandos e pré-requisitos para `pg_dump`/`pg_restore`. `backup.py` gera manifesto coordenado com versão do schema, revisões ativas e chaves/SHA/tamanhos de todos os blobs; a criação do manifesto não sobrescreve um existente. Restore sintético verificado, sem blobs reais; consultar evidências.

## Parecer

**PARECER: gate de integridade M3 aprovado no ambiente sintético.** A implementação ainda não está pronta para uso operacional: a API restrita cobre somente o catálogo; faltam as operações de runs, artefatos, aprovação e publicação, além de provisionamento de papéis e decisões de ambiente, backup e migração. Nenhum dado real foi migrado; autoridade, executores e cutover continuam inalterados.
