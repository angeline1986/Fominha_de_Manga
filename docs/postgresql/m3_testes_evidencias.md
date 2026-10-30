# M3 — Testes e evidências

**Resultado da revisão de integridade e primeira API de escrita:** 20 testes sintéticos passaram, sem falhas esperadas. A ativação operacional ainda depende de API restrita para as demais operações e decisões de infraestrutura. Ver [implementação M3](m3_implementacao.md) e [pendências](m3_pendencias.md).

## Ambiente

- PostgreSQL 16.14 em cluster descartável e isolado, porta 55434; banco vazio de teste `fominha_m3_test_20261027_e`.
- Python 3.12.7 e psycopg 3.3.4.
- Bytes e metadados exclusivamente sintéticos. O Artifact Store dos testes ficou em diretório temporário; nenhum caminho do acervo nem `FOMINHA_DATA_ROOT` foi usado.
- Dez scripts `up` foram aplicados. Após a suíte, a migration 010 fez `down` e `up` novamente com sucesso no banco descartável; 008/009 passaram pelo mesmo ciclo no banco anterior. A prova anterior cobriu o ciclo integral 007 a 001; não foi repetida neste ciclo.
- A suíte exige um banco novo, vazio e com prefixo `fominha_m3_test_`; recusa nomes fora do prefixo e bancos com ledger de migrations existente. Essa proteção foi adicionada após uma execução de repetição revelar referências de blobs temporários de uma execução anterior.
- O Artifact Store dos testes foi removido ao final. O cluster e os bancos descartáveis não contêm arquivos do acervo operacional.

## Suíte de integração

Comando executado da raiz do repositório:

```sh
FOMINHA_PG_TEST_DSN='postgresql://alinesouza@127.0.0.1:55434/fominha_m3_test_20261027_e' \
PYTHONPATH=central_v2/backend \
python3 -m unittest discover -s dev/tests/postgresql -v
```

Resultado final: **20 testes descobertos e aprovados; nenhuma falha esperada**. A execução anterior passou com 19 testes antes da inclusão da API restrita do catálogo.

- Fluxo sintético de catálogo, página, execuções, versões de artefato, validação do blob, publicação e avanço de revisão ativa.
- Reset reverte a revisão ativa sem sobrescrever versões antigas e grava evento/itens de Reset.
- Ocorrência, revisão, aprovação, dependência de aprovação, revogação, invalidação transitiva e recusa do resolver para artefato obsoleto.
- Tabelas e dez migrations presentes; triggers impedem mutação de objetos registrados; repetição idempotente de bytes não cria conteúdo divergente.
- Como papel efetivo `fominha_app`, o repositório criou provedor, obra, capítulo, página, segmento e etapa via funções restritas, repetiu operações idempotentes e recebeu erro de permissão ao tentar `INSERT` direto em tabela. O teste confirmou `fominha_migrator` como proprietário das funções; `fominha_retention` não conseguiu executá-las.
- Manifesto verifica SHA/tamanho dos objetos e versões ativas. Registro sintético `LEGACY_UNVERIFIED` permanece sem versão promovida.
- Idempotência de runs/publicações, conflito de fingerprint e publicação concorrente: um único resultado venceu o CAS e só um ponteiro ativo foi gravado. O perdedor da serialização pode propagar `SerializationFailure`; não há retry interno.
- Escopo de artefato de saída para outro capítulo e outra página do mesmo capítulo é recusado por FK/trigger.
- Falha após avanço do pointer durante Reset reverte pointer, publicação e evento Reset na transação; o chamador recebe `ValueError`.
- `pg_dump`/`pg_restore` foi exercitado dentro do teste. Uma cópia sintética do Artifact Store foi verificada pelo manifesto; contagens antes/depois do restore coincidiram.
- Falha de inserção após gravar blob produz `ORPHAN_CANDIDATE`; blob registrado e ausente produz `MISSING_OR_CORRUPT` sem apagar metadados.
- Auditoria e idempotência de chave/fingerprint de run foram exercitadas.

### Falhas anteriores corrigidas

1. `test_application_role_cannot_mark_unvalidated_blob_valid`: `fominha_app` não tem `INSERT` em eventos de estado. Teste adicional confirma leitura e ausência de escrita em todas as tabelas atuais e em uma tabela futura.
2. `test_approval_snapshot_must_match_chapter`: o lote rejeita snapshot de outro capítulo; SQL direto rejeita snapshot de outra página não coberta pelo run e ocorrência de outra página no mesmo lote.
3. `test_decision_image_must_match_approved_page`: a decisão rejeita imagem de outra página, inclusive por SQL direto.
4. `test_finished_legacy_batch_rejects_late_items`: repositório e SQL direto rejeitam item após fechamento; `UPDATE` e `DELETE` de itens também são recusados.

Os quatro testes perderam `expectedFailure` e passaram normalmente. A verificação de permissões usou `SET LOCAL ROLE fominha_app` e confirmou `current_user=fominha_app`; não foi usada credencial operacional.

O primeiro ciclo identificou falha de `search_path` em funções de trigger; migrations 005 e 007 foram corrigidas para fixá-lo e a suíte final passou após reaplicação integral do schema.

## Backup e restore sintéticos

Foi criado dump custom-format do banco de teste, restaurado em novo banco descartável com `pg_restore --exit-on-error --no-owner`; uma cópia dos blobs foi verificada em um novo Artifact Store usando o manifesto. Contagens antes e depois do restore coincidiram. A tabela abaixo mostra a consulta ao banco de teste ao final de toda a suíte:

| Evidência | Contagem |
|---|---:|
| Migrations registradas | 10 |
| Artefatos ativos | 4 |
| Eventos de Reset | 1 |
| Decisões de aprovação | 2 |
| Itens de importação legada | 2 |

As contagens referem-se ao banco descartável após a suíte de 20 testes. As tentativas negativas não acrescentaram decisão de outra página nem item tardio.

O backup de blobs foi verificado pelo manifesto durante a suíte contra uma cópia do Artifact Store sintético. O restore PostgreSQL não representa backup/restauração do acervo real e não substitui validar uma janela coordenada de backup em infraestrutura de produção. As migrations `down` removem o schema e seus dados; rollback de schema não é uma recuperação sem perda, que depende do restore testado.

## Limites da evidência

- Não foram executados tratamentos de imagem, testes de algoritmos, migração/importação de dados reais, carga elevada ou benchmarks. A concorrência foi exercitada com dois publishers sintéticos e threads locais; a corrida entre fechamento do lote e inclusão de item não teve teste concorrente próprio.
- Não foram alterados executores, contratos legados, `dual_write` ou `read_authority`.
- O restore é local e sintético; armazenamento redundante, recuperação em outra máquina, RPO/RTO e retenção continuam para decisão e operação pré-cutover.
- Em homologação anterior num cluster descartável com outro banco restaurado usando os papéis M3, o rollback da migration 006 falhou ao tentar `DROP ROLE fominha_app` por grants ainda existentes no outro banco. O rollback completo passou em cluster de um banco. Papéis PostgreSQL são globais ao cluster; a limpeza dos papéis precisa ser separada do rollback por banco ou coordenada para todos os bancos.
