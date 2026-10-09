# Relatório de validação da reexecução Artístico por ocorrência

Data: 08/10/2026. Referência: `develop` com alterações locais preservadas.
Nenhum tratamento foi executado na obra operacional; não houve commit nem push.

## Contrato verificado

| Verificação | Evidência | Resultado |
| --- | --- | --- |
| Seleção individual na interface | `special_styled_table.test.mjs`: A, B e C na mesma página; requisição contém apenas B. Seletor mostra ID/página e, abaixo, ROI e filtro. | Aprovado |
| SHA antes da execução | `validate_styled_reexecution` compara o SHA enviado com a página final; `_execute_chapter` compara novamente antes de `preview`. | Aprovado |
| SHA antes da publicação | `_validate_inputs` confere SHA esperado, página, manifestos, entrada histórica, máscaras e composição sob a transação. Teste altera a página imediatamente antes da publicação; o fluxo falha sem publicar manifestos. | Aprovado |
| Restauração antiga | `test_replacement_removes_old_pixels_even_when_new_delta_is_smaller`: pixel alterado apenas pelo filtro antigo volta à entrada pré-filtro. | Aprovado |
| Isolamento e repetição | `test_three_balloons_reexecute_only_b_and_repeat_from_original`: A e C mantêm pixels e registros; B→D→E usa a mesma entrada histórica. | Aprovado |
| Histórico incompleto | Ausência de saída, hash divergente ou autoria por ocorrência ausente bloqueia antes da publicação. | Aprovado |
| Dependência posterior | Máscara Degradê sobreposta, inclusive com pixel coincidentemente igual, bloqueia; máscara independente é preservada. Histórico posterior sem máscara verificável bloqueia. | Aprovado |
| Falha transacional | Testes de journal e rollback Artístico. | Aprovado |

## Testes

- `python3 -m unittest discover -s dev/tests -p 'test_special_*.py'`: **62/62 passaram**.
- `node --experimental-vm-modules --test dev/tests/central_v2_frontend/special_styled_table.test.mjs dev/tests/central_v2_frontend/special_treatments_table.test.mjs`: **11/11 passaram**.
- Cinco testes HTTP (`test_central_v2_auto_merge_http`, `test_central_v2_shutdown`, `test_central_v2_smoke`) passaram fora do sandbox, onde puderam abrir portas locais.
- `git diff --check` e `compileall`: passaram. Arquivos Artístico alterados respeitam o limite de 200 linhas.

## Falhas da regressão ampla

Regressão Python: 134 testes, 35 falhas e 5 erros na primeira execução. Regressão
frontend: 113 testes, 112 passaram e 1 falhou. Classificação individual:

| Falhas | Classificação | Evidência |
| --- | --- | --- |
| 8 violações de 200 linhas em arquivos versionados | Preexistentes em `develop` | O mesmo teste falhou para os mesmos oito arquivos em extração limpa de `HEAD`. |
| 26 violações de 200 linhas em `runtime/bubble_sommelier/node_modules` | Preexistentes no ambiente local | Dependências instaladas fora do versionamento; nenhum arquivo foi alterado pela correção Artístico. A regra de arquitetura também percorre `node_modules`. |
| `test_occupied_chapter_is_reported_and_later_chapter_continues` | Preexistente em `develop` | Falha idêntica reproduzida na extração limpa de `HEAD`: job fica `failed` apesar de o segundo capítulo ser promovido. |
| 5 erros de bind HTTP | Ambiente de teste, resolvidos | Sandbox negou `127.0.0.1`; os mesmos cinco testes passaram com acesso local. |
| `textoff_merged.test.mjs`, menu Limpeza de Balões | Preexistente em `develop` | Falha idêntica em extração limpa de `HEAD`: menu contém `auto-cleaner-check`, expectativa omite essa entrada. |

Os oito arquivos versionados acima de 200 linhas são:

1. `central_v2/backend/orchestration/bubble_sommelier/artifacts.py`
2. `central_v2/backend/orchestration/textoff_merged/artifact_validation.py`
3. `central_v2/backend/orchestration/textoff_merged/consolidated.py`
4. `central_v2/backend/orchestration/textoff_merged/level1_cleaner.py`
5. `central_v2/frontend/_shell/limpeza_baloes.css`
6. `central_v2/frontend/_shell/limpeza_baloes_flow.css`
7. `central_v2/frontend/texto_off/sommelier/index.js`
8. `central_v2/frontend/texto_off/sommelier/review.js`

Os 26 arquivos de dependências locais acima de 200 linhas são:

1. `@emnapi/runtime/dist/emnapi.cjs.js`
2. `@emnapi/runtime/dist/emnapi.esm-bundler.js`
3. `@emnapi/runtime/dist/emnapi.iife.js`
4. `@emnapi/runtime/dist/emnapi.js`
5. `adm-zip/adm-zip.js`
6. `adm-zip/headers/entryHeader.js`
7. `adm-zip/util/utils.js`
8. `adm-zip/zipEntry.js`
9. `adm-zip/zipFile.js`
10. `define-data-property/test/index.js`
11. `detect-libc/lib/detect-libc.js`
12. `global-agent/dist/classes/Agent.js`
13. `global-agent/dist/factories/createGlobalProxyAgent.test.js`
14. `onnxruntime-common/dist/cjs/inference-session-impl.js`
15. `onnxruntime-common/dist/cjs/tensor-factory-impl.js`
16. `onnxruntime-common/dist/cjs/tensor-impl.js`
17. `onnxruntime-common/dist/esm/inference-session-impl.js`
18. `onnxruntime-common/dist/esm/tensor-factory-impl.js`
19. `onnxruntime-common/dist/esm/tensor-impl.js`
20. `onnxruntime-node/script/install-utils.js`
21. `semver/classes/range.js`
22. `semver/classes/semver.js`
23. `semver/internal/re.js`
24. `semver/ranges/subset.js`
25. `tslib/tslib.es6.js`
26. `tslib/tslib.js`

Todos os caminhos desta lista têm prefixo
`central_v2/runtime/bubble_sommelier/node_modules/`. Nenhuma falha remanescente foi
atribuída à correção Artístico. Nenhuma falha de teste ficou inconclusiva após os
reruns, mas a validação visual operacional continua pendente.

## Página operacional solicitada

`mangago/Candy YumYum (Yaoi)`, `Ch. 4`, `page-049-054.png` **continua bloqueada para
reexecução individual**.
O Manifesto Especial registra quatro ocorrências Artísticas com status `failed`.
O Consolidado Final registra resultado Artístico anterior
`6bb36a8f1fb4f82058307181e98d6a40847ef41fecd5720bb4688f30726b4441`
seguido de Degradê, mas não existe manifesto Artístico por ocorrência nem manifesto
Degradê com máscara posterior. Uma busca pelos arquivos da página na obra não
encontrou a saída Artística antiga com esse hash. A entrada pré-Artístico existe e
confere com o hash histórico, mas não comprova autoria individual.

Hashes do Manifesto Especial, Manifesto Final e página final foram conferidos no
início e no fim da inspeção e permaneceram iguais. O procedimento para validação
visual em cópia está em `artistico_ch4_page_049_054.md`. A página real não pode ser
liberada para reexecução individual com as evidências atuais. A restauração completa
da página é um fluxo separado, validado em cópia isolada no relatório
`restauracao_pagina_candy_ch4.md`; a obra operacional permanece inalterada.
