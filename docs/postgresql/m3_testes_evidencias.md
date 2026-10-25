# M3 — Testes e evidências

**Resultado da homologação:** **REPROVADO para liberação do próximo milestone**. A suíte completou, mas quatro testes negativos foram marcados como falhas esperadas porque o desenho atual aceita estados/referências inválidos. Ver [implementação M3](m3_implementacao.md) e [pendências](m3_pendencias.md).

## Ambiente

- PostgreSQL 16.14 em cluster descartável e isolado, porta 55433; banco vazio de teste `fominha_m3_test_review_20261023`.
- Python 3.12.7 e psycopg 3.3.4.
- Bytes e metadados exclusivamente sintéticos. O Artifact Store dos testes ficou em diretório temporário; nenhum caminho do acervo nem `FOMINHA_DATA_ROOT` foi usado.
- Os sete scripts `up` foram aplicados. Em banco isolado sem grants em outros bancos, os sete `down` foram executados em ordem inversa (`007` a `001`) e reaplicados (`001` a `007`) com sucesso.
- A suíte exige um banco novo, vazio e com prefixo `fominha_m3_test_`; recusa nomes fora do prefixo e bancos com ledger de migrations existente. Essa proteção foi adicionada após uma execução de repetição revelar referências de blobs temporários de uma execução anterior.
- Cluster foi parado após os testes; diretório e bancos temporários descartáveis foram preservados. Os Artifact Stores de teste, criados em diretórios temporários, foram removidos ao final. Nenhum arquivo do acervo operacional foi envolvido.

## Suíte de integração

Comando executado da raiz do repositório:

```sh
FOMINHA_PG_TEST_DSN='postgresql://alinesouza@127.0.0.1:55433/fominha_m3_test_review_20261023' \
PYTHONPATH=central_v2/backend \
python3 -m unittest discover -s dev/tests/postgresql -v
```

Resultado final: **15 testes descobertos: 11 passaram e 4 falharam como esperado (`expected failures=4`)**. O exit code do `unittest` foi zero por causa do marcador `expectedFailure`; a homologação geral continua reprovada pelas falhas abaixo.

- Fluxo sintético de catálogo, página, execuções, versões de artefato, validação do blob, publicação e avanço de revisão ativa.
- Reset reverte a revisão ativa sem sobrescrever versões antigas e grava evento/itens de Reset.
- Ocorrência, revisão, aprovação, dependência de aprovação, revogação, invalidação transitiva e recusa do resolver para artefato obsoleto.
- Tabelas e sete migrations presentes; triggers impedem mutação de objetos registrados; repetição idempotente de bytes não cria conteúdo divergente.
- Manifesto verifica SHA/tamanho dos objetos e versões ativas. Registro sintético `LEGACY_UNVERIFIED` permanece sem versão promovida.
- Idempotência de runs/publicações, conflito de fingerprint e publicação concorrente: um único resultado venceu o CAS e só um ponteiro ativo foi gravado. O perdedor da serialização pode propagar `SerializationFailure`; não há retry interno.
- Escopo de artefato de saída para outro capítulo e outra página do mesmo capítulo é recusado por FK/trigger.
- Falha após avanço do pointer durante Reset reverte pointer, publicação e evento Reset na transação; o chamador recebe `ValueError`.
- `pg_dump`/`pg_restore` foi exercitado dentro do teste. Uma cópia sintética do Artifact Store foi verificada pelo manifesto; contagens antes/depois do restore coincidiram.
- Falha de inserção após gravar blob produz `ORPHAN_CANDIDATE`; blob registrado e ausente produz `MISSING_OR_CORRUPT` sem apagar metadados.
- Auditoria e idempotência de chave/fingerprint de run foram exercitadas.

### Falhas esperadas que bloqueiam a homologação

1. `test_application_role_cannot_mark_unvalidated_blob_valid`: o papel `fominha_app` consegue inserir evento `VALID` diretamente sem validação da existência/hash do blob.
2. `test_approval_snapshot_must_match_chapter`: o repositório/schema aceita um snapshot de artefato de capítulo diferente do lote de aprovação.
3. `test_decision_image_must_match_approved_page`: uma decisão de aprovação aceita imagem revisada de outra página.
4. `test_finished_legacy_batch_rejects_late_items`: um lote de importação `COMPLETED` aceita novo item depois de finalizado.

Esses casos estão marcados `expectedFailure` para que a suíte documente as lacunas sem mascará-las como aprovações. São defeitos funcionais de integridade, não limitações do ambiente de teste.

O primeiro ciclo identificou falha de `search_path` em funções de trigger; migrations 005 e 007 foram corrigidas para fixá-lo e a suíte final passou após reaplicação integral do schema.

## Backup e restore sintéticos

Foi criado dump custom-format do banco de teste, restaurado em novo banco descartável com `pg_restore --exit-on-error --no-owner`; uma cópia dos blobs foi verificada em um novo Artifact Store usando o manifesto. Contagens antes e depois do restore coincidiram. A tabela abaixo mostra a consulta ao banco de teste ao final de toda a suíte:

| Evidência | Contagem |
|---|---:|
| Migrations registradas | 7 |
| Artefatos ativos | 4 |
| Eventos de Reset | 1 |
| Decisões de aprovação | 3 |
| Itens de importação legada | 2 |

As contagens incluem os registros das provas negativas que o sistema aceitou: uma decisão com imagem de outra página e um item tardio após fechar um lote. Esses registros sintéticos evidenciam as lacunas; não são dados operacionais.

O backup de blobs foi verificado pelo manifesto durante a suíte contra uma cópia do Artifact Store sintético. O restore PostgreSQL não representa backup/restauração do acervo real e não substitui validar uma janela coordenada de backup em infraestrutura de produção. As migrations `down` removem o schema e seus dados; rollback de schema não é uma recuperação sem perda, que depende do restore testado.

## Limites da evidência

- Não foram executados tratamentos de imagem, testes de algoritmos, migração/importação de dados reais, carga elevada ou benchmarks. A concorrência foi exercitada com dois publishers sintéticos e threads locais.
- Não foram alterados executores, contratos legados, `dual_write` ou `read_authority`.
- O restore é local e sintético; armazenamento redundante, recuperação em outra máquina, RPO/RTO e retenção continuam para decisão e operação pré-cutover.
- Em homologação anterior num cluster descartável com outro banco restaurado usando os papéis M3, o rollback da migration 006 falhou ao tentar `DROP ROLE fominha_app` por grants ainda existentes no outro banco. O rollback completo passou em cluster de um banco. Papéis PostgreSQL são globais ao cluster; a limpeza dos papéis precisa ser separada do rollback por banco ou coordenada para todos os bancos.
