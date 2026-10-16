# Sanitização pendente da Central V2

## Contexto

Durante a validação pré-checkpoint da feature BubbleSommelier + Auto Cleaner
Nível II, a suíte completa da Central V2 revelou falhas de dívida técnica,
testes com contratos antigos e restrições do ambiente. Elas foram triadas e
estão registradas aqui para retomada independente do histórico do chat.

Esta sanitização não faz parte do checkpoint funcional atual. Não alterar os
algoritmos, contratos ou telas da feature para contornar os itens abaixo.

## Resultado da validação pré-checkpoint

- Python Central V2: 103 testes, 34 failures e 6 errors.
- Frontend Central V2: 82 testes, 81 passaram e 1 falhou.
- Testes focados de Nível II, comparison/consolidated e job manager: 29/29
  passaram.
- `python3 -m py_compile` nos Python modificados: aprovado.
- `git diff --check`: aprovado.

O resultado Python agrupado foi: 33 failures do teste arquitetural e 1 teste
com expectativa antiga de status; 5 errors de `socket.bind` bloqueado pelo
ambiente e 1 error em mock incompleto de `http_handler.log_message`.

### Revalidação focada para fechamento do checkpoint

Na retomada da feature, sem repetir as suítes completas, foram executados:

- 37 testes Python focados (29 de job manager, Nível II, comparison e
  consolidated; mais 8 de consulta/execução do endpoint Nível II): todos
  passaram.
- 6 testes frontend focados de progresso compartilhado, progresso por página
  do BubbleSommelier e transição pós-execução do Passo 2: todos passaram.
- `python3 -m py_compile` nos Python modificados: aprovado.
- `node --check` nos arquivos `cli.js`, `pipeline.js` e `runner.js` do runtime:
  aprovado.
- `git diff --check`: aprovado.

Não foi executado ONNX, processamento real de Auto Cleaner nem job de
produção.

## Pendências

### 1. Teste de navegação do Auto-Cleaner desatualizado

Arquivo/teste: `dev/tests/central_v2_frontend/navigation_textoff.test.mjs`,
teste “Limpeza de Balões renders captions and keeps special hover previews in
Pincel”. Ele assume que `groups[0]` é Auto-Cleaner e espera o texto
“Auto-Cleaner”.

Desde o commit `44156a9e` (`feat(central-v2): integra BubbleSommelier com
runtime dedicado`), o menu começa com o grupo `BUBBLE SOMMELIER`, cuja entrada
funcional se chama `Curadoria de balões`; o grupo Auto-Cleaner continua logo
depois. O teste precede essa mudança e não foi atualizado.

Classificação: teste desatualizado, sem alteração acidental de produto nesta
feature. Correção futura: localizar os grupos por identidade/label estável, em
vez de depender do índice.

### 2. Expectativa antiga do Job Manager

Teste: `dev/tests/test_central_v2_auto_merge_execute.py`,
`Level1ExecutionTests.test_occupied_chapter_is_reported_and_later_chapter_continues`.
Ele espera `completed` embora os resultados contenham `failed` para um capítulo
e sucesso para o seguinte.

O contrato atual, implementado em `central_v2/backend/jobs/manager.py`, é:
qualquer resultado de capítulo com `status="failed"` torna o job global
`failed`. A execução continua processando os capítulos posteriores. Um
resultado `no_change` não é falha e mantém o job concluído. Não reverter o
Job Manager para satisfazer a expectativa antiga.

Correção futura: alinhar o teste ao contrato atual, verificando o status global
`failed`, a falha individual e a continuação do capítulo posterior.

### 3. Mock antigo de `http_handler.log_message`

Teste: `dev/tests/test_central_v2_terminal_log.py`,
`CentralV2TerminalLogTests.test_http_log_is_printed_immediately_with_v2_prefix`.
Ele chama `Handler.log_message(None, ...)`. Em `HEAD`, a função apenas
formatava os argumentos e imprimia, então não acessava `self`.

A implementação atual lê `self.path` e `self.command` para suprimir logs de
polling GET bem-sucedido em `/api/jobs/<32hex>`. A chamada com `None` falha
antes de avaliar o filtro. O caminho `/api/jobs/abc` usado no teste não
corresponde ao filtro.

Correção futura: passar um fake/handler mínimo que contenha `path` e `command`
e manter a verificação do log comum. Criar também cobertura específica para a
supressão de polling. Não reverter a supressão e não iniciar uma refatoração
geral dos logs.

### 4. Testes HTTP bloqueados pelo ambiente

Os cinco testes abaixo falharam ao criar `ThreadingHTTPServer`, antes de
exercitar as rotas. O erro foi
`PermissionError: [Errno 1] Operation not permitted` em `socket.bind`.

- `dev/tests/test_central_v2_auto_merge_http.py` —
  `Level1HTTPTests.test_query_over_http_is_read_only_and_post_does_not_execute`.
- `dev/tests/test_central_v2_shutdown.py` —
  `ShutdownTests.test_only_shutdown_post_stops_server_after_acknowledgement`.
- `dev/tests/test_central_v2_smoke.py` —
  `CentralV2SmokeTests.test_catalog_over_real_http_handler`.
- `dev/tests/test_central_v2_smoke.py` —
  `CentralV2SmokeTests.test_health_over_real_http_handler`.
- `dev/tests/test_central_v2_smoke.py` —
  `CentralV2SmokeTests.test_state_query_over_real_http_handler`.

Classificação: ambiente. Executar esses testes em ambiente que permita
loopback/bind local. Não alterar produção para contornar essa restrição.

### 5. Scanner arquitetural inclui `node_modules`

Teste: `dev/tests/test_central_v2_architecture.py`,
`ArchitectureTests.test_source_files_have_at_most_200_lines`.

A varredura usa `ROOT.rglob("*")`, filtra extensões de código e exclui
`.venv`, mas não exclui `node_modules`. Foram 26 subfalhas de dependências
instaladas em `central_v2/runtime/bubble_sommelier/node_modules`, incluindo
`tslib`, `adm-zip`, `@emnapi/runtime`, `semver` e `onnxruntime-common`.

Correção futura: excluir diretórios `node_modules` da varredura de código
próprio. Não modificar os arquivos das dependências.

### 6. Limite arquitetural de 200 linhas

O mesmo teste exige no máximo 200 linhas por arquivo. Fotografia na triagem
(HEAD → working tree; delta Git em linhas adicionadas/removidas):

| Arquivo | HEAD | Atual | Delta | Situação |
| --- | ---: | ---: | ---: | --- |
| `central_v2/frontend/_shell/limpeza_baloes.css` | 275 | 334 | +98/-39 | Já excedia no HEAD |
| `central_v2/frontend/texto_off/sommelier/review.js` | 185 | 265 | +173/-93 | Cruzou no working tree |
| `central_v2/frontend/texto_off/sommelier/index.js` | 259 | 299 | +48/-8 | Já excedia no HEAD |
| `central_v2/runtime/bubble_sommelier/pipeline.js` | 182 | 203 | +61/-40 | Cruzou no working tree |
| `central_v2/backend/orchestration/bubble_sommelier/artifacts.py` | 226 | 226 | — | Já excedia no HEAD |
| `central_v2/backend/orchestration/textoff_merged/consolidated.py` | 194 | 370 | +180/-4 | Cruzou no working tree |
| `central_v2/backend/orchestration/textoff_merged/level2.py` | 198 | 264 | +81/-15 | Cruzou no working tree |

Arquivos que cruzaram o limite durante o trabalho atual: `sommelier/review.js`,
`bubble_sommelier/pipeline.js`, `textoff_merged/consolidated.py` e
`textoff_merged/level2.py`.

Arquivos que já excediam no HEAD: `limpeza_baloes.css`, `sommelier/index.js` e
`bubble_sommelier/artifacts.py`.

Correção futura: decompor responsabilidades em módulos coesos. Não aumentar o
limite, desabilitar o teste, compactar código artificialmente nem excluir
código próprio do scanner.

### 7. Regra para validações temporárias

`/tmp` e `/private/tmp` podem conter dados, screenshots, relatórios e harnesses.
Validações oficiais devem executar o código funcional do working tree; não
devem validar uma cópia modificada do código operacional.

Histórico: a comparação experimental A/B do BubbleSommelier utilizou uma
variante temporária de `worker.js`. Seus resultados são experimento e não
validação do runtime atual.

## Retomada

Tratar estas pendências em uma tarefa própria de sanitização. Preservar o
checkpoint funcional; não misturar esta dívida técnica com correções de
streaming, métricas, regras de limpeza ou UX do BubbleSommelier/Auto Cleaner.
