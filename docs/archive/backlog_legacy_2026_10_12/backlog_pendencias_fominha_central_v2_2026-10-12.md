# Backlog consolidado — Fominha_de_Manga / Central V2

**Data de consolidação:** 12/10/2026  
**Origem:** backlog `backlog_pendencias_fominha_central_v2_2026-10-12.md`, proposta `proposta_validacao_automatica_limite_200_linhas.md` e evidências da conversa.
**Objetivo:** reunir as pendências em um backlog priorizado, incorporando a proposta do limite de 200 linhas, sem alterar a implementação atual.
**Referência funcional:** branch `develop`, commit `280b30bf` (checkpoint publicado da comparação ORIGINAL / DEGRADÊ / ARTÍSTICO / SUAVE).  
**Importante:** prioridades são sugestões para triagem; nenhuma atividade está automaticamente autorizada para implementação.

## Índice de pendências por prioridade

A ordem abaixo agrupa as prioridades sugeridas no backlog. Dentro de cada faixa, os itens aparecem pelo ID; prioridades condicionais e estados suspensos estão identificados.

1. **Alta** — [BL-01](#bl-01--padronizar-o-layout-do-07_consolidado_final-em-clean), [BL-04](#bl-04--verificar-fonte-utilizada-na-exportação-das-imagens-finais) *(condicional à exportação da obra)*, [BL-05](#bl-05--compatibilidade-de-obras-processadas-na-central-v1-com-auto-cleaner-passo-1-da-central-v2), [BL-08](#bl-08--verificação-automática-do-limite-de-200-linhas-por-arquivo).
2. **Média-alta** — [BL-06](#bl-06--integrar-indicador-de-progresso-oficial-aos-tratamentos-longos-do-laboratório-l3).
3. **Média** — [BL-02](#bl-02--decidir-se-mask-e-outras-pastas-vazias-devem-existir-no-consolidado-final), [BL-03](#bl-03--formalizar-o-contrato-arquitetural-do-consolidado-final), [BL-07](#bl-07--tratamento-seguro-do-shutdown-durante-execuções-longas), [BL-09](#bl-09--cobertura-de-regressão-visual-por-contrato-no-laboratório), [BL-12](#bl-12--cobertura-adicional-da-autorização-experimental-por-múltiplos-componentes).
4. **Média-baixa** — [BL-10](#bl-10--analisar-falhas-preexistentes-das-suítes-amplas).
5. **Baixa-média** — [BL-13](#bl-13--monitoramento-do-estado-independente-dos-três-filtros-e-da-qualidade-visual).
6. **Baixa / suspensa** — [BL-11](#bl-11--definir-ux-da-autorização-assistida-do-degradê-proposta-suspensa) *(suspenso até nova decisão; não autorizado para implementação)*.

As prioridades são sugestões para triagem, não autorização de implementação. BL-01/BL-03 e BL-06/BL-07 têm dependências ou coordenação descritas nos próprios itens.

## Critérios de classificação

- **Pendente confirmado:** comportamento ou lacuna demonstrada por execução, inspeção ou diagnóstico apresentado.
- **Melhoria proposta:** decisão de produto/arquitetura ainda não implementada.
- **Investigação:** evidência insuficiente para afirmar a causa ou necessidade de correção.
- **Concluído / referência:** não reabrir como pendência salvo nova regressão.

## Backlog a incorporar

### BL-01 — Padronizar o layout do `07_CONSOLIDADO_FINAL` em `clean/`

- **Categoria:** arquitetura de artefatos / compatibilidade. **Estado:** melhoria proposta. **Prioridade sugerida:** alta para organização futura, sem migração imediata.
- **Problema:** hoje os PNGs limpos são gravados diretamente em `07_CONSOLIDADO_FINAL/<capítulo>/`, enquanto o sistema também cria `clean/` e `mask/` vazias. A estrutura é incoerente com a organização esperada para artefatos limpos.
- **Evidência:** capítulos 18 e 19 de `comix/Emergency_Youth Record Book`; capítulo 18 com 25 PNGs na raiz, `clean/` e `mask/` vazias, manifesto `json/final-manifest.json` com `artifact: "page-*.png"`.
- **Causa no código (confirmada):** `rebuild_final_baseline()` e `promote_treatment_pages()` gravam em `staged / page`; `read_final_page()` e `final_consolidated_manifest.read_manifest()` resolvem `folder / page`. Outros produtores também utilizam a raiz (Artístico e restauração).
- **Proposta:** definir como contrato de destino para novas versões `07_CONSOLIDADO_FINAL/<capítulo>/clean/page-*.png`; **manter leitura retrocompatível** do layout plano antigo. Atualizar produtores, leitores, validadores, manifesto e testes de forma coordenada. Não mover arquivos manualmente.
- **Compatibilidade:** preservar imagens históricas, hashes de conteúdo, histórico, versões de manifesto, promoções, backups/restaurações e tratamentos. Alterações de manifesto mudam seu hash e podem invalidar propostas vinculadas à versão anterior.
- **Arquivos identificados:** `central_v2/backend/orchestration/textoff_merged/final_consolidated.py`, `final_consolidated_manifest.py`, `special_styled_final.py`, `special_page_restore.py`, `special_page_restore_prepare.py`, `special_styled_recovery.py`, testes de Consolidado Final e tratamentos especiais.
- **Aceite:** novos capítulos ficam organizados em `clean/`; antigos continuam utilizáveis na raiz; leitores, pincéis, comparações, restaurações e hashes continuam íntegros; testes demonstram os dois layouts; nenhum artefato é perdido.
- **Dependência:** aprovar formalmente o novo contrato antes de codificar; tratar eventual migração física dos capítulos antigos em item separado.

### BL-02 — Decidir se `mask/` e outras pastas vazias devem existir no Consolidado Final

- **Categoria:** organização do armazenamento. **Estado:** melhoria proposta. **Prioridade sugerida:** média.
- **Problema:** `prepare_artifact_dirs()` cria `clean/`, `mask/` e `json/` genericamente; a etapa Final não produz máscara própria, deixando `mask/` vazia (e `clean/` vazia no layout atual).
- **Proposta:** depois de definir BL-01, criar somente diretórios efetivamente previstos para o Final, sem romper consumidores que dependam da existência das pastas.
- **Aceite:** estrutura de diretórios documentada; ausência de pastas vazias desnecessárias; compatibilidade preservada.

### BL-03 — Formalizar o contrato arquitetural do Consolidado Final

- **Categoria:** documentação / contratos. **Estado:** pendente confirmado. **Prioridade sugerida:** média.
- **Problema:** diagnóstico não localizou documento que justifique formalmente o layout plano do Final ou que prescreva organização universal em `clean/`.
- **Proposta:** documentar árvore de diretórios, papéis de `clean/`, `mask/`, `json/`, semântica de `artifact`, hashes, histórico, leitura legada e regras de migração; integrar a documentação de refatoração.
- **Aceite:** contrato versionado e refletido em testes.

### BL-04 — Verificar fonte utilizada na exportação das imagens finais

- **Categoria:** integração de pipeline / exportação. **Estado:** investigação. **Prioridade sugerida:** alta se a obra será exportada.
- **Achado:** diagnóstico do código indicou que `processamento/exportacao/exportador.py` utiliza `FLUXO_SECUNDARIO/04_TEXTO_OFF/MERGED`, e não consome diretamente `07_CONSOLIDADO_FINAL` e seu manifesto.
- **Risco:** exportar versão desatualizada, deixando de incluir resultados mais recentes de Auto-Cleaner e Pincéis.
- **Próximo passo:** mapear qual ação de exportação o usuário realmente utiliza, a fonte selecionada, e o fluxo esperado; não presumir que esse exportador seja o único consumidor.
- **Aceite:** exportação pretendida usa explicitamente a versão vigente correta ou oferece seleção controlada; verifica manifesto e hash; evita promoção tácita.

### BL-05 — Compatibilidade de obras processadas na Central V1 com Auto-Cleaner Passo 1 da Central V2

- **Categoria:** compatibilidade legada / catálogo. **Estado:** investigação aberta. **Prioridade sugerida:** alta.
- **Caso:** `comix/Emergency_Youth Record Book`, com 52 capítulos em `IMG` e pastas `FLUXO_SECUNDARIO/02_MERGE/<capítulo>` contendo arquivos de merge antigos.
- **Sintoma:** Auto-Cleaner — Passo 1 reconhecia `ALL (52)`, mas `MERGES = —` em todos os capítulos; seleções e `Executar Passo 1` desabilitados.
- **O que falta comprovar:** endpoint que compõe a tabela, regra exata de elegibilidade, verificação de manifesto/merge, diferença entre capítulo antigo e capítulo elegível atual. Não está provado que a localização dos arquivos seja a causa.
- **Proposta:** compatibilidade de leitura, se necessária, sem reprocessamento compulsório dos 52 capítulos e sem migrar dados às cegas.
- **Aceite:** merges legados válidos são reconhecidos ou recusados com motivo técnico explícito; capítulos elegíveis ficam selecionáveis; preservação dos dados antigos.
- **Observação temporal:** foram mostrados artefatos do Texto Off para o capítulo 18 posteriormente; isso não comprova, por si só, que o problema específico de elegibilidade do Passo 1 foi corrigido. Revalidar status antes de abrir trabalho.

### BL-06 — Integrar indicador de progresso oficial aos tratamentos longos do Laboratório L3

- **Categoria:** experiência de execução / jobs. **Estado:** melhoria proposta, adiada deliberadamente. **Prioridade sugerida:** média-alta.
- **Contexto:** execução Artístico real durou aproximadamente 124 s, e Degradê pode executar classificação e assistência em passagens sequenciais; barra provisória não comprova percentual real.
- **Componentes existentes:** frontend `_shared/progress/progress.js` (`createJobProgress()`); sistema de jobs `central_v2/backend/jobs/manager.py` e GET `/api/jobs/<id>`; mecanismo de progresso do worker existe em `textoff_special/process.py`.
- **Proposta:** analisar integração não bloqueante com estados e progresso real, sem percentuais inventados; definir tratamento de navegação, troca de página, resultado obsoleto, execução concorrente e encerramento.
- **Aceite:** usuário distingue fila, execução, conclusão e falha; progresso fiel ao backend quando disponível; resultado nunca é confundido entre páginas/ROIs; o processamento não é cancelado falsamente por um simples `AbortController`.

### BL-07 — Tratamento seguro do shutdown durante execuções longas

- **Categoria:** confiabilidade operacional. **Estado:** investigação / melhoria proposta. **Prioridade sugerida:** média.
- **Achado:** em teste de Degradê um `worker-result.json` foi gravado, mas o manifesto permaneceu `running` e a resposta HTTP não chegou; havia registro de `POST /api/shutdown` naquela investigação. Não ficou provado travamento no `process.wait()` nem que o shutdown foi a causa única.
- **Proposta:** proteger finalização de operações em andamento, política explícita de shutdown (aguardar, recusar temporariamente ou finalizar job de forma segura) e recuperação de estados órfãos, preferencialmente articulada ao BL-06.
- **Aceite:** não deixa execução concluída permanentemente como `running`; evita perda de manifesto/resultado e não altera fluxos oficiais inesperadamente.
- **Não fazer:** alterar worker, lock ou shutdown apenas por hipótese, sem reprodução/contrato.

### BL-08 — Verificação automática do limite de 200 linhas por arquivo

- **Categoria:** qualidade / governança arquitetural. **Estado:** proposta documentada, não implementada. **Prioridade sugerida:** alta.
- **Regra:** arquivos de código elegíveis podem ter até 200 linhas físicas; 201 linhas é violação. Arquivos `.md` são isentos. Linhas em branco e comentários contam. A política deve fixar o tratamento de CRLF e de arquivos sem newline final.
- **Objetivo:** executar a mesma verificação localmente e na CI, informar caminho, quantidade, limite e excedente, e impedir novas violações sem bloquear a base por dívida histórica.
- **Escopo a decidir antes da implementação:** inventariar extensões consideradas código (incluindo Python, JavaScript e demais fontes efetivamente versionadas). Não assumir que todo arquivo não Markdown é código: imagens, JSON de dados, binários e locks precisam de política explícita. Exclusões documentadas devem cobrir dependências, `.venv`, `node_modules`, caches, artefatos gerados e submódulos quando aplicável. O submódulo `download/mangago_downloader` precisa de política própria; seu conteúdo não deve ser alterado automaticamente.
- **Verificador proposto:** `dev/scripts/check_file_size.py`, descobrindo arquivos elegíveis versionados via Git, aplicando exclusões e, durante a transição, comparando com um baseline de dívida legada. Deve retornar código diferente de zero para violações bloqueantes e produzir diagnóstico legível.
- **Hook local:** validar o conteúdo staged do índice Git, inclusive staging parcial, e não apenas o estado do workspace. Documentar a instalação; o hook melhora o feedback local, mas pode ser contornado e não substitui a CI.
- **CI:** executar o mesmo verificador em Pull Requests e pushes relevantes. Tornar o status check obrigatório na proteção da branch para bloquear merges com violações. Um workflow, sozinho, não impede push direto; isso depende das regras e permissões do repositório.
- **Adoção gradual:**
  1. **Inventário somente leitura:** listar extensões, violações atuais, dívida legada, exceções e políticas para gerados/submódulos; não alterar código de produção.
  2. **Bloquear novas violações:** arquivos novos e arquivos existentes até 200 linhas não podem exceder o limite. Arquivos legados acima de 200 podem diminuir, mas não crescer em relação a baseline controlado. O baseline deve ser monotônico para impedir que uma redução parcial volte a aumentar.
  3. **Regularizar legado:** modularizar por responsabilidades coesas, preservar interfaces e comportamento, atualizar/remover gradualmente a dívida do baseline e, ao final, aplicar a regra rígida sem exceções de legado.
- **Critérios de aceite:** 200 linhas passa e 201 falha; Markdown longo passa; legado pode diminuir e não pode crescer; staging parcial é medido corretamente; renomeações, remoções, CRLF e newline final têm resultado consistente; gerados/dependências não geram falsos positivos; execução local e CI concordam; falha informa arquivo e excesso sem editar arquivos; status obrigatório realmente impede merge.
- **Decisões pendentes:** extensões; tratamento e atualização do baseline; definição de gerados; política de submódulos; implementação do hook; eventos e proteções da CI/branch; testes do validador para evitar bloqueios indevidos.
- **Sequência futura, cada etapa sujeita a autorização:** inventário e relatório; aprovação de extensões/exclusões/baseline; script e testes isolados; hook; CI e proteção de branch quando autorizadas; validação de falsos positivos e redução gradual da dívida.
- **Limites:** não alterar algoritmos Degradê, Artístico ou Suave; não refatorar imediatamente todos os arquivos grandes; não alterar venvs, imagens, manifestos ou resultados experimentais; não modificar `laboratorio_one/` nem `download/mangago_downloader/`; não criar hooks, workflows ou mudanças de código com base apenas na proposta; não fazer commit ou push sem autorização específica.
- **Documento incorporado:** `proposta_validacao_automatica_limite_200_linhas.md` (11/10/2026). A proposta permanece não implementada e não autoriza mudanças.

### BL-09 — Cobertura de regressão visual por contrato no Laboratório

- **Categoria:** testes / qualidade visual. **Estado:** melhoria contínua. **Prioridade sugerida:** média.
- **Histórico:** a primeira matriz de 80 combinações verificava principalmente geometria, sem provar escala natural, estado sem imagem ou `gap` no Foco. Correções posteriores foram validadas e publicadas.
- **Proposta pendente:** institucionalizar testes por requisito e não só por número de combinações: imagem natural × zoom, quatro cartões acessíveis, ROIs normalizadas e renderizadas, 12 px entre visualizador e sidebar nos dois modos, troca de páginas, respostas atrasadas, estados sem imagem, screenshot/manual quando apropriado.
- **Aceite:** matriz requisito→asserção→evidência; resultados explicam o que ficou fora da cobertura. Não reabrir correções de zoom já concluídas sem nova evidência.

### BL-10 — Analisar falhas preexistentes das suítes amplas

- **Categoria:** testes / manutenção. **Estado:** investigação. **Prioridade sugerida:** média-baixa, fora do caminho crítico.
- **Histórico:** testes focados do L3 passaram, mas suítes amplas registraram falhas de sandbox/porta, checks arquiteturais e `button_contract` em `roi_selection.js` e `exportar_arquivos/browser.js`; teste de isolamento `DomainIsolationTests.test_both_nested_executors_use_worker_python_and_restore_binding` falhou por divergência entre mock e assinatura do executor.
- **Proposta:** criar baseline reproduzível em ambiente suportado, separar falhas legadas de regressões, corrigir mocks/contratos e comandos de execução sem alterar algoritmos protegidos.
- **Aceite:** cada falha classificada por causa, status e escopo, sem atribuir todas ao Laboratório.

### BL-11 — Definir UX da autorização assistida do Degradê (proposta suspensa)

- **Categoria:** UX / autorização experimental. **Estado:** proposta revertida, **não aprovada para nova implementação**. **Prioridade sugerida:** baixa até nova decisão.
- **Situação funcional de referência:** Degradê assistido com seleção individual e confirmação extra funciona na versão publicada `280b30bf`.
- **Tentativa:** retirar segunda confirmação e autorizar automaticamente componentes adiados cobertos integralmente pela ROI. O cenário manual retornou `ROI insuficiente`, embora o fluxo anterior tivesse funcionado; mudança foi revertida com `git restore` em quatro arquivos e remoção do módulo experimental. `develop` voltou a ficar limpo.
- **Pendência de produto:** decidir se a segunda confirmação deve ser mantida ou simplificada, **sem mudar inadvertidamente o contrato de elegibilidade**.
- **Regra:** qualquer futura proposta exige comparação explícita entre contrato anterior e novo, demonstração em caso real e aprovação separada antes de mudar semântica de autorização. Não reimplementar automaticamente a tentativa fracassada.

### BL-12 — Cobertura adicional da autorização experimental por múltiplos componentes

- **Categoria:** testes de segurança funcional. **Estado:** investigação / cobertura parcial. **Prioridade sugerida:** média.
- **Histórico:** houve testes de seleção múltipla, expiração, uso único, invalidação por ROI e hash; o caso real validado tinha um componente adiado. Não houve demonstração completa com uma imagem real contendo vários componentes.
- **Proposta:** selecionar caso real elegível para validar autorização individual, outros componentes preservados, consumo único e concordância de manifesto/máscara; sem alterar o algoritmo do Cleaner.
- **Aceite:** nenhum componente não autorizado ou fora da ROI é alterado; flow Check permanece intacto.

### BL-13 — Monitoramento do estado independente dos três filtros e da qualidade visual

- **Categoria:** qualidade do produto / comparação. **Estado:** melhoria futura. **Prioridade sugerida:** baixa-média.
- **Marco validado:** em uma mesma sessão, ORIGINAL, DEGRADÊ, ARTÍSTICO e SUAVE exibiram imagens com mesmo zoom e ROI; resultados funcionaram independentemente.
- **Observação visual:** para o balão testado em `page-013.png`, Degradê e Artístico deixaram faixa rosada visível; Suave apresentou reconstrução aparentemente mais uniforme. Não generalizar qualidade para todos os balões.
- **Proposta:** quando houver demanda, padronizar registro de comparações e classificação de resultados por estilo de balão, mantendo os algoritmos intocados até avaliação específica.
- **Aceite:** critério visual e exemplos reproduzíveis; não modificar tratamento apenas com base em uma captura.

## Itens concluídos — não adicionar como pendência

| Marco | Evidência nesta conversa | Observação |
|---|---|---|
| Zoom natural, ROI e layout do Laboratório | Commit `319e2a63` publicado | Quatro cartões horizontais e `gap` de 12 px no Foco validados |
| Artístico e Suave integrados ao L3 | Commit `f0f99add` publicado | Executados em imagem real |
| Degradê assistido com confirmação individual | Commit `280b30bf` publicado | Fluxo manual e três visões lado a lado validados |
| Modularização de `router.py` e `index.js` | Commit `280b30bf` publicado | Arquivos tocados respeitaram 200 linhas na validação |
| Reversão da tentativa de Degradê em um clique | `gita` limpo em `develop...origin/develop` | Preservadas `.playwright-cli/` e `laboratorio_one/` |
| Localização das imagens do Consolidado Final | Diagnóstico concluído | Layout plano **atualmente esperado pelo código**, ainda que alvo de mudança futura em BL-01 |

## Recomendações para incorporação no backlog existente

1. **Não duplicar automaticamente** itens já existentes: conciliar por tema e acrescentar estas evidências e critérios de aceite ao registro original.
2. Iniciar por **BL-01/BL-03** se a prioridade for padronizar armazenamento, mas implementar leitura retrocompatível antes de qualquer migração.
3. Tratar **BL-04/BL-05** como perguntas funcionais independentes: exportação da versão final e elegibilidade de obras antigas; evitar atribuir ambas à localização dos PNGs sem prova.
4. Planejar **BL-06/BL-07** em conjunto, sem confundir progresso da UI com encerramento seguro do worker.
5. Manter **BL-11 suspenso**; não reintroduzir a regressão já revertida.
6. Antes de qualquer implementação: diagnóstico restrito, plano com arquivos e limite de 200 linhas, aprovação expressa, teste focado e validação funcional do usuário; commit e push apenas com autorizações específicas.

## Limitações deste documento

Esta consolidação foi feita **somente com o histórico desta conversa** e relatórios compartilhados. **Não houve acesso nem comparação com o backlog já existente**; portanto, IDs BL-xx são provisórios e não representam IDs do backlog original. Tampouco foi feita auditoria do estado local atual dos diretórios no Mac. Todas as propostas permanecem pendentes de triagem e aprovação.
