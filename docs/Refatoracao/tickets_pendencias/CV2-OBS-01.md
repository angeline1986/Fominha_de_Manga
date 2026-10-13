# CV2-OBS-01 — Padronizar logs do terminal da Central V2

- **Prioridade:** P3 (média)
- **Status:** Concluído
- **Visão:** Saúde Arquitetural · Observabilidade · Central V2
- **Responsável:** A definir

**Objetivo:** Unificar a apresentação dos logs operacionais do backend da Central V2, sem alterar o funcionamento do projeto.

**Abrangência executada:** `central_v2/backend/`. Saídas JSON de subprocessos, diagnósticos técnicos capturados pelo processo pai e registros de auditoria foram preservados. A Central V1 permaneceu intacta.

**Implementação concluída:**
- Reutilizada a infraestrutura de `central_v2/backend/operational_log.py`.
- Padronizados logs de jobs, inicialização do servidor, consulta do Auto-Merge Nível III, resumo do Texto Off Nível II e indisponibilidade da autoridade de artefatos.
- Preservados os protocolos JSON, respostas HTTP, regras de processamento, autoridade de artefatos e exceções.

**Critério de Aceite:**
- [x] Logs operacionais alterados seguem o formato existente de timestamp, nível, categoria, mensagem e atributos.
- [x] Início, progresso, conclusão, falha e duração dos jobs são registrados sem alterar os dados de progresso nem os resultados.
- [x] Testes específicos validam o formato dos jobs e os campos de autoridade de artefatos.
- [x] Testes de logging e testes direcionados aos módulos afetados passaram: 48 testes aprovados.
- [x] Revisão final confirmou que `level3.py` preserva o traceback e o contrato HTTP, e que `artifact_migration.py` preserva as regras de autoridade, validação e exceções.
- [x] Confirmado que a Central V1 permaneceu intacta.
- [x] Nenhuma alteração de código fora de `central_v2/backend/`; testes limitados aos contratos específicos em `dev/tests/`.

**Validação registrada:** revisão do diff e `git diff --check` aprovados. Não foi feito commit ou push; continuam dependendo de autorização explícita.

**Arquivos de backend envolvidos:** `jobs/manager.py`, `server.py`, `routes/auto_merge/level3.py`, `orchestration/textoff_merged/level2_transparent.py` e `orchestration/textoff_merged/artifact_migration.py`.

**Testes específicos:** `test_central_v2_scoped_job_logs.py` e `test_textoff_artifact_authority_safety.py`.

**Restrições preservadas:** nenhuma alteração em regras de negócio, algoritmos, resultados, Central V1 ou contratos de subprocessos. Limite de 200 linhas físicas por arquivo de código respeitado.

**Referência:** `central_v2/backend/operational_log.py`.
