# CV2-OBS-02 — Reduzir logs rotineiros do SHADOW_READ

- **Prioridade:** P2
- **Status:** DONE
- **Visão:** Saúde Arquitetural · Observabilidade · Central V2
- **Responsável:** A definir

**Objetivo:** Reduzir o volume de mensagens SHADOW_READ no terminal sem perder diagnósticos úteis para investigação.

**Diagnóstico inicial:** Ao acessar Limpeza de Balões, `observe_shadow_read()` registra individualmente resultados de comparação em `central_v2/backend/orchestration/textoff_merged/artifact_shadow_read.py`. Mensagens `MISSING_LEGACY` e `MISMATCH` podem gerar centenas de linhas durante navegação simples e dificultar a leitura de eventos operacionais.

**Solução implementada:** Resultados de comparação, inclusive `MATCH`, `MISMATCH` e estados de artefatos ausentes, são emitidos em nível `DEBUG`. Os detalhes continuam disponíveis ao habilitar diagnóstico DEBUG. Exceções inesperadas permanecem em nível `ERROR` com traceback.

**Critério de Aceite:**
- [x] Resultados de comparação rotineiros e divergências ficam no nível de diagnóstico `DEBUG`.
- [x] Reduzir mensagens repetitivas no terminal durante consultas comuns.
- [x] Manter diagnósticos detalhados acessíveis ao habilitar `DEBUG`.
- [x] Validar que comparações, autoridade, migração e validação de artefatos permanecem inalteradas.
- [x] Exceções inesperadas continuam identificáveis em `ERROR` com traceback.

**Validação:** `test_textoff_artifact_shadow_read.py` (7 testes), `test_textoff_artifact_authority.py` (6 testes) e `test_textoff_artifact_validation.py` (14 testes) aprovados.

**Relação com CV2-OBS-01:** CV2-OBS-01 está concluído e não será reaberto. Este item trata especificamente do volume de mensagens produzido pelo SHADOW_READ e deve ser priorizado como pendência separada.

**Restrições (o que NÃO fazer):**
- Não alterar comparações, autoridade, migração ou validação de artefatos.
- Não modificar a Central V1 nem regras de processamento.
- Não suprimir diagnósticos necessários sem definir uma forma de consultá-los.
- Não alterar algoritmos, regras de autoridade, migração ou validação ao ajustar os logs.
- Respeitar o limite de 200 linhas físicas por arquivo de código.

**Links de Referência:** `central_v2/backend/orchestration/textoff_merged/artifact_shadow_read.py`, função `observe_shadow_read()`; `docs/Refatoracao/tickets_pendencias/CV2-OBS-01.md`.
