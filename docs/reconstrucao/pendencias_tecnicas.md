# Pendencias tecnicas da reconstrucao

Registro unico das lacunas tecnicas remanescentes apos a auditoria do checkout `cef3cd42`. Prioridade indica impacto na reproducao e na verificacao de equivalencia, nao urgencia de alteracao operacional.

| ID | Prioridade | Pendencia | Codigo / evidencias relacionadas | Criterio para encerrar |
|---|---|---|---|---|
| PT-01 | P1 | Completar o catalogo de payloads/respostas HTTP e estados dos jobs em todos os subfluxos V1/V2. Os manuais cobrem rotas principais, mas nao cada campo e transicao. | V1: `interface_web/processing_web.py`, `interface_web/*.js`; V2: `central_v2/backend/routes/`, `central_v2/backend/jobs/`, `central_v2/frontend/_app/api/`, `central_v2/frontend/texto_off/`. | Matriz rota -> validador -> funcao -> job/estado -> artefatos, com testes/consumidores como evidencia. |
| PT-02 | P1 | Registrar ambiente efetivo para reproducao, incluindo versoes instaladas, hashes dos perfis e checksums dos modelos/pesos realmente usados. Baselines existentes sao snapshots historicos. | `processamento/limpeza_baloes/cleaner_v2/requirements.txt`, `outlined-text.ini`, `launcher.py`; `central_v2/runtime/`; evidencias antigas em `docs/gestao/evidencias/ambientes/environment_baseline/`. | Captura gerada do checkout/runtime alvo, ligada a commit e modelos, sem assumir que cache local corresponde ao modelo declarado. |
| PT-03 | P2 | Fechar o inventario de parametros e regras para Sommelier, Auto-Cleaner Check, Solidos e adapters especiais que nao foram especificados integralmente nos manuais. | `central_v2/backend/orchestration/bubble_sommelier/`; `central_v2/backend/orchestration/textoff_merged/auto_cleaner_check*.py`, `solid_stage.py`; `central_v2/backend/orchestration/textoff_special/`; `processamento/limpeza_baloes/` adapters; testes correspondentes em `dev/tests/`. | Cada regra documentada com simbolo/valor e consumidor ativo; limites sem cobertura marcados como desconhecidos. |
| PT-04 | P2 | Estabelecer corpus autorizado e criterio visual para equivalencia, incluindo casos-limite de transparencia; hashes/invariantes tecnicos nao medem qualidade visual por si. | `processamento/limpeza_baloes/cleaner_v2/transparency_classifier.py`, `balloon_authorization.py`, `level2.py`; testes `dev/tests/test_cleaner_v2_transparency_classifier.py`, `test_textoff_merged_level2.py`; fixtures/evidencias de `docs/gestao/evidencias/textoff/`. | Fixtures com autorizacao de uso, fonte e checksums registrados, resultados esperados por etapa e criterio de revisao visual aprovado. |

## Prioridade

- **P1:** necessario para tornar a reconstrucao operacional e repetivel sem adivinhar contratos ou ambiente.
- **P2:** necessario para declarar equivalencia abrangente de todas as ferramentas e sua qualidade visual; nao bloqueia a descricao dos fluxos ja rastreados.

Este documento registra trabalho pendente; nao autoriza executar tratamentos, alterar parametros, baixar modelos ou processar obras.
