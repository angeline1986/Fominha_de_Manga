# CV2-OBS-01 — Inventariar e padronizar logs de terminal do projeto

- **Prioridade:** P3 (média, sugerida)
- **Status:** A Fazer — não implementar nesta etapa
- **Visão:** Saúde Arquitetural · Observabilidade · Fominha_de_Manga
- **Responsável:** A definir

**Objetivo:** Inventariar os logs divergentes, validar um contrato comum e padronizar a saída do terminal gradualmente, sem alterar o comportamento dos processamentos.

**Abrangência:** Central V1 e V2, Auto-Merge, Balanceamento, PDF, TextoOff, Cleaner, workers e orquestradores.

**Referência inicial de formato:** `HH:MM:SS.mmm NÍVEL [CATEGORIA] mensagem · atributo=valor`. O contrato final de apresentação precisa ser validado antes da implementação.

**Estratégia:**
1. Inventariar `print()`, logging e mensagens verbosas, classificando saídas operacionais e diagnósticas.
2. Propor o contrato final e listar os arquivos afetados para aprovação.
3. Implementar em módulos incrementais, reutilizando a infraestrutura existente.
4. Validar formato, rastreabilidade, regressões e ausência de mudanças funcionais.

**Critério de Aceite:**
- [ ] Apresentar inventário dos fluxos, formatos divergentes e arquivos afetados antes de implementar.
- [ ] Validar exemplos e contrato para timestamp, severidade, categoria, mensagem e metadados.
- [ ] Garantir consistência para eventos equivalentes e legibilidade em execuções simples e em lote.
- [ ] Tornar identificáveis início, evolução, conclusão, falha e duração; correlacionar por `run_id` quando disponível.
- [ ] Diferenciar logs operacionais dos detalhes diagnósticos e preservar registros úteis para auditoria.
- [ ] Reutilizar a infraestrutura de logging existente e evitar duplicações ou mensagens irrelevantes.
- [ ] Testar regressões dos fluxos afetados sem alterar regras, algoritmos ou resultados de processamento.
- [ ] Não registrar dados sensíveis, tokens ou credenciais.

**Restrições (o que NÃO fazer):**
- Não substituir indiscriminadamente `print()` sem avaliar sua finalidade.
- Não alterar processamento para melhorar apenas a apresentação dos logs.
- Não iniciar implementação antes do inventário e da aprovação do contrato.
- Respeitar o limite de 200 linhas físicas por arquivo de código.
- Não fazer commit ou push sem autorização explícita.

**Links de Referência:** Item legado P6 “Expandir padronização dos logs” em `docs/archive/backlog_legacy_2026_10_12/pendencias_central_v2_legacy.md` (frente anterior limitada à Central V2).
