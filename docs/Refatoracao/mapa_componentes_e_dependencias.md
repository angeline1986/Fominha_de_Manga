# Mapa de Componentes e Dependências

**Projeto:** Fominha_de_Manga  
**Escopo:** Central legada → Central V2  
**Fase:** 1 — Mapeamento arquitetural real  
**Status:** Em construção  
**Arquivo legado principal:** `interface_web/processing_web.py`

---

## 1. Objetivo

Documentar as responsabilidades reais atualmente concentradas na Central legada e suas dependências, antes da migração funcional para a Central V2.

Este documento é descritivo.

Não autoriza alteração de algoritmo, heurística, threshold, manifesto, regra de autoridade ou comportamento funcional.

---

## 2. Visão estrutural atual

A Central legada concentra, no mesmo módulo:

- transporte HTTP;
- resolução de Provider/Obra;
- projeção de estado;
- execução e acompanhamento de jobs;
- observabilidade de processamento;
- Auto-Merge Níveis I–V;
- Revisão Merge;
- validação de dimensões;
- Balanceamento;
- Merge Manual;
- geração de PDF;
- Texto Off;
- Tratamentos Especiais;
- Exportação;
- entrega de arquivos estáticos e mídia;
- bootstrap do servidor.

Parte dessas responsabilidades já possui implementação de domínio fora da interface web.

---

## 3. Fronteiras já existentes

| Domínio | Implementação externa identificada | Papel atual de `processing_web.py` |
|---|---|---|
| Exportação | `processamento/exportacao/exportador.py` | HTTP, resolução de contexto e delegação |
| Balanceamento | `processamento/balanceamento/` | HTTP/jobs e delegação |
| Merge Manual | `processamento/merge_manual/` | HTTP/jobs, integração e projeção compartilhada |
| Texto Off | `processamento/limpeza_baloes/` | HTTP/jobs, integração e projeções |
| Validação de imagens | `processamento/validacao_imagens/` | integração, persistência/projeção e execução |
| PDF | `orquestracao/menu.py` e `src/pdf/generator.py` | integração e execução |
| Auto-Merge | `processamento/unificacao_imagens/` + lógica significativa no legado | integração, workflow, materialização, promoção e autoridade |

---

## 4. Transporte HTTP legado

O `Handler` concentra os contratos HTTP da Central atual.

### GET

- `/api/catalog`
- `/api/export/select-directory`
- `/api/textoff-special/select-image`
- `/api/state`
- `/api/textoff-compare`
- `/api/textoff-level3`
- `/api/dimension-analysis`
- `/api/balance-analysis`
- `/api/merge-manual`
- `/api/merge-manual-proposal`
- `/api/pdf-merge-latest`
- `/api/pdf-merge-files`
- `/api/open-folder`
- `/api/shutdown`
- `/api/job/<id>`
- `/media`
- arquivos estáticos

### POST

- `/api/textoff-special/process`
- `/api/textoff-special/promote`
- `/api/export/simulate`
- `/api/export/execute`
- `/api/action`

---

## 5. Dispatcher compartilhado de jobs

O fluxo legado possui um dispatcher central:

`/api/action`
→ `make_job()`
→ `run_job()`
→ executor funcional

O `run_job()` distribui execução entre múltiplos domínios.

Essa dependência deve ser mapeada antes de qualquer tentativa de migração do mecanismo genérico de jobs.

---

## 6. Projeção de estado compartilhada

`row_state()` agrega informações de múltiplas etapas e domínios.

Entre suas dependências estão:

- estado do Merge;
- falhas e partições;
- Revisão Merge;
- Níveis III, IV e V;
- artefatos oficiais;
- diretórios de processamento;
- Texto Off;
- PDF;
- informações derivadas para interface.

Portanto, `row_state()` não deve ser tratado como um DTO simples da Central V2.

---

## 7. Autoridade e promoção

O Auto-Merge possui lógica de autoridade ainda presente no legado, incluindo:

- leitura de manifests;
- materialização de artefatos;
- composição de stages;
- validação por SHA;
- promoção para saída oficial;
- resolução de pendências entre níveis.

Funções como `_promote_stage_composition()` fazem parte dessa fronteira crítica.

Essa área permanece protegida até o mapa de autoridade ser concluído.

---

## 8. Matriz de dependências por fluxo

> Em construção durante a Fase 1.

| Fluxo | HTTP | Job compartilhado | Módulo de domínio próprio | Depende de `row_state()` | Autoridade no legado | Risco de extração |
|---|---|---|---|---|---|---|
| Exportação | Sim | Não | Sim | Não | Não | Baixo |
| Balanceamento | Sim | Sim | Sim | Não identificado no contrato ativo | Sim (`balance_effect`) | Médio/Alto |
| Merge Manual | Sim | Sim | Sim | Sim, via `review_state_loader` | Sim (`apply_final_composition`) | Alto |
| Texto Off | Sim | Sim | Sim | Não identificado como dependência direta | Sim; Nível III pode alcançar `02_MERGE` | Alto |
| PDF | Sim | Sim | Parcial | Não identificado como dependência direta | Sim, sobre artefatos PDF derivados | Médio |
| Validação de imagens | Sim | Sim | Sim | Não identificado como dependência direta | Sim; `dimension_correct` modifica `IMG` | Alto |
| Auto-Merge I–V | Sim | Sim | Parcial | Sim | Sim | Alto |
| Revisão Merge | Via estado/action | Sim | Parcial | Sim | Sim | Alto |

---


## 8.1 Exportação

### Fronteira atual

**HTTP legado**

- `GET /api/export/select-directory`
- `POST /api/export/simulate`
- `POST /api/export/execute`

**Domínio**

- `processamento/exportacao/exportador.py`

**Símbolos principais**

- `select_directory()`
- `simulate_export()`
- `execute_plan()`

### Entradas

`simulate_export()` recebe:

- obra já resolvida;
- pasta-pai de destino;
- conteúdos selecionados.

`execute_plan()` recebe:

- obra já resolvida;
- `plan_id` produzido pela simulação.

### Fontes de dados

Conteúdos atualmente reconhecidos:

- `FLUXO_SECUNDARIO/04_TEXTO_OFF/MERGED`
- `FLUXO_SECUNDARIO/03_PDF_MERGE`

A exportação exclui:

- `*_mask.png`
- `*.json`
- `.DS_Store`

### Estado compartilhado

Os planos de exportação são mantidos em memória:

- `_PLANS`
- `_PLAN_LOCK`

Consequência arquitetural: enquanto esse mecanismo permanecer, simulação e execução dependem do mesmo processo que mantém o plano em memória.

### Integridade

A simulação registra para cada arquivo:

- tamanho;
- `mtime_ns`;
- SHA-256;
- status `new`, `identical` ou `conflict`.

Antes da execução, a descoberta é refeita e comparada com o plano original.

Mudanças na origem ou no destino invalidam a execução.

Conflitos impedem a exportação e arquivos divergentes não são sobrescritos.

A cópia utiliza arquivo temporário seguido de `os.replace()`.

### Efeitos colaterais

No projeto:

- leitura dos artefatos de origem;
- nenhuma promoção;
- nenhuma alteração dos artefatos oficiais identificada.

No destino:

- criação da pasta da obra;
- criação das subpastas necessárias;
- cópia de arquivos novos.

### Dependências arquiteturais

- não depende de `row_state()`;
- não depende de `/api/action`;
- não depende de `make_job()` ou `run_job()`;
- não altera manifests de autoridade;
- não promove artefatos de processamento.

`select_directory()` possui dependência específica de macOS por utilizar `osascript`.

### Risco preliminar de extração

**Baixo**, considerando o acoplamento observado.

Essa classificação não define, isoladamente, a ordem de migração vertical.

---

## 8.2 Balanceamento

### Fronteira ativa

**Leitura**

`GET /api/balance-analysis`
→ `processamento.balanceamento.balanceamento.balance_state()`

**Execução**

`POST /api/action`
→ `make_job()`
→ `run_job()`

Actions observadas:

- `balance_prepare` → `do_balance_prepare()` → `balanceador.prepare_manual_balance()`
- `balance_execute` → `do_balance_execute()` → `balanceador.generate_manual_balance()`
- `balance_effect` → `do_balance_effect()` → `balanceador.effect_manual_balance()`
- `balance_generate` → `do_balance_generate()` → `balanceador.generate_balance_proposal()`

### Módulos

- `processamento/balanceamento/balanceador.py`
- `processamento/balanceamento/balanceamento.py`

`balanceador.py` contém os executores atualmente chamados pelo dispatcher da Central.

`balanceamento.py` fornece `balance_state()` para leitura da interface.

Também existe nesse módulo outro `generate_balance_proposal()`, mas nenhum consumidor operacional foi identificado no levantamento atual. Portanto ele não é classificado neste momento como fluxo ativo nem como código morto.

### Entradas observadas

As operações executadas pela Central trabalham com:

- obra resolvida;
- exatamente um capítulo;
- merges selecionados;
- cortes manuais, quando aplicável;
- callback de progresso.

As validações de quantidade de capítulos e seleção mínima de merges permanecem atualmente nos adaptadores `do_balance_*` do legado.

### Jobs e observabilidade

As quatro operações passam pelo mecanismo compartilhado de jobs.

O `run_job()` registra estado e manifests antes e depois da execução e produz eventos de transição, conclusão ou falha.

Assim, a fronteira operacional atual do Balanceamento inclui não apenas o módulo de domínio, mas também contrato de progresso e observabilidade mantido pelo legado.

### Autoridade e efeitos colaterais

`effect_manual_balance()` possui autoridade funcional sobre o resultado de Merge.

A implementação observada:

- lê manifest de Merge;
- lê proposta/editor/status;
- cria staging;
- cria ou manipula backup;
- copia artefatos;
- substitui/promove diretório de Merge;
- persiste status de Balanceamento.

Portanto `balance_effect` não pode ser tratado como simples transformação ou cálculo.

As demais operações geram estado intermediário, propostas, previews e artefatos próprios do fluxo.

### Dependências relevantes

O Balanceamento utiliza componentes de:

- `processamento.unificacao_imagens.image_stitcher_level3`;
- `processamento.limpeza_baloes.bubble_cleaner`;
- Pillow;
- NumPy.

Não foi identificada dependência direta de `row_state()` dentro do contrato ativo específico do Balanceamento.

Entretanto, o job compartilhado executa projeções/eventos transversais antes e depois da operação.

### Implementações paralelas identificadas

Os dois módulos possuem símbolos internos semelhantes e ambos definem `generate_balance_proposal()`.

A análise atual comprova que a Central chama o gerador de `balanceador.py`.

O gerador existente em `balanceamento.py` permanece registrado como implementação sem consumidor operacional identificado até análise específica posterior.

### Risco preliminar de extração

**Médio/Alto.**

O processamento está majoritariamente modularizado, porém:

- depende do dispatcher compartilhado de jobs;
- depende do contrato de progresso;
- participa da observabilidade transversal;
- possui promoção efetiva para `02_MERGE`;
- mantém estado e artefatos próprios;
- apresenta duas superfícies internas relacionadas ao Balanceamento.

A classificação não define a ordem de migração.

---

## 8.3 Merge Manual

### Fronteira atual

O domínio está dividido em:

- `api.py` — fachada consumida pela Central;
- `service.py` — projeção somente leitura;
- `review_state.py` — interpretação do estado autoritativo de Review;
- `proposal.py` — geração e persistência de propostas;
- `finalizer.py` — composição e promoção para o MERGE oficial.

### Contratos consumidos pela Central

Leitura:

- `GET /api/merge-manual`
  → `get_merge_manual_state()`
- `GET /api/merge-manual-proposal`
  → `get_latest_merge_manual_proposal()`

Execução via `/api/action`:

- `merge_manual_generate`
  → `generate_merge_manual_proposal_job()`
- `merge_manual_apply`
  → `apply_merge_manual_proposal_job()`

### Dependência do estado de Review

O Merge Manual não importa diretamente `row_state()`.

A Central injeta:

`review_state_loader=lambda ch: row_state(manga, ch)`

Esse loader é utilizado na:

- construção do estado de leitura;
- geração da proposta;
- efetivação da proposta.

O próprio domínio declara `review_row_state` como sua fonte de verdade e evita reexecutar ou reinterpretar a cadeia Auto-Merge I–V.

Consequência arquitetural: a Central V2 precisa disponibilizar uma projeção autoritativa equivalente antes de substituir o loader legado.

### Autoridade

`apply_final_composition()` modifica o MERGE oficial.

O fluxo observado:

1. bloqueia a operação por capítulo;
2. valida manifesto e identidade da proposta;
3. suporta reaplicação idempotente;
4. valida o estado atual da Review;
5. valida as fontes;
6. reconstrói a composição automática + manual;
7. escreve candidato em staging;
8. preserva o MERGE anterior em backup;
9. promove o staging para o diretório oficial;
10. valida o resultado com `is_chapter_merged()`;
11. remove o status anterior de Review;
12. marca a proposta como `EFETIVADO`.

Após validação, o próprio código estabelece o MERGE oficial como autoridade do capítulo.

### Rollback

Antes da promoção são preservados:

- MERGE oficial anterior;
- status de Review;
- manifesto original da proposta.

Em caso de exceção, o fluxo tenta restaurar integralmente esses três estados e remove o staging.

### Efeitos colaterais

O fluxo pode:

- criar staging;
- criar/remover backup;
- substituir o diretório de MERGE oficial;
- remover estado anterior de Review;
- atualizar o manifesto da proposta.

Portanto a efetivação não é uma operação somente de apresentação ou cálculo.

### Jobs e observabilidade

Geração e aplicação passam pelo dispatcher compartilhado `/api/action` → `make_job()` → `run_job()`.

Assim como no Balanceamento, a migração precisa preservar o contrato transversal de job, progresso/resultado e eventos antes/depois.

### Risco preliminar de extração

**Alto.**

Embora o domínio esteja bem modularizado, a migração envolve:

- fonte de verdade derivada da Review;
- contrato atualmente fornecido por `row_state()`;
- dispatcher compartilhado de jobs;
- promoção do MERGE oficial;
- validações de integridade;
- idempotência;
- rollback integral.

A classificação não define a ordem de migração.

---

## 8.4 Texto Off

### Fronteira operacional

A Central atual consome seis subfronteiras de Texto Off:

1. limpeza principal;
2. comparação;
3. fila e sinalização do Nível III;
4. análise residual;
5. correção assistida Nível III;
6. Tratamentos Especiais.

O diretório contém outros módulos experimentais e auxiliares, mas eles não são classificados como contratos operacionais da Central apenas por existirem no código.

### Limpeza principal

As actions:

- `clean`
- `clean_merged`

utilizam o mesmo executor:

`processamento.limpeza_baloes.cleaner_v2.integration.clean_chapter()`

`clean` trabalha sobre as imagens originais do capítulo com:

`source_stage="ORIGINAL"`

`clean_merged` exige MERGE oficial válido, obtém seus artefatos oficiais e executa com:

`source_stage="MERGE"`

Portanto são dois contextos de entrada do mesmo pipeline oficial, e não duas implementações independentes do Cleaner.

### Migração inicial para Central V2

A página **Texto Off — Merged** está sendo iniciada em `central_v2/frontend/texto_off/merged.js`. Sua consulta e job usam `/api/textoff/merged` e `/api/textoff/merged/execute`; a orquestração fica em `orquestracao/textoff/merged.py` e delega a limpeza para o `clean_chapter()` existente. A V2 valida MERGE oficial, expõe a lista de capítulos/artefatos e não copia o Cleaner nem seus gates.

O estado “resultado registrado” compara `source_stage`, nomes dos arquivos e contagem do `clean-manifest.json`. Isso **não prova identidade dos bytes do MERGE**, pois o manifesto Cleaner atual não guarda fingerprint da entrada. A interface informa esse limite; rastreabilidade por hash permanece lacuna separada para decisão e migração futura.

### Contrato oficial do Cleaner V2

`clean_chapter()`:

- valida existência e unicidade das entradas;
- mantém timeout oficial de 900 segundos;
- processa em diretório temporário;
- executa o Cleaner V2;
- exige `*_clean` para todas as entradas;
- exige `*_mask` para todas as entradas;
- executa autorização de balões do Nível I;
- exige análise de todas as páginas no Nível I;
- executa o refinamento Nível II;
- exige relatório e análise de todas as páginas no Nível II;
- gera `level1-balloon-report.json`;
- gera `level2-report.json`;
- gera `clean-manifest.json`;
- promove o diretório somente após as validações.

Nível I e Nível II fazem parte do contrato oficial de uma única execução de `clean_chapter()`.

### Integridade e promoção da limpeza

A promoção utiliza staging e preserva a saída anterior durante o processamento.

O `clean-manifest.json` registra, entre outros dados:

- algoritmo;
- engine e versão;
- profile;
- `source_stage`;
- imutabilidade da fonte;
- quantidade de páginas;
- artefatos fonte;
- artefatos limpos;
- máscaras;
- dados do Nível I;
- dados do Nível II;
- indicador de integridade.

Falhas anteriores à promoção preservam a saída oficial existente.

### Nível III

Actions identificadas:

- `textoff_level3_flag`
  → `flag_correction_job()`
- `textoff_level3_analyze`
  → `analyze_residual_job()`
- `textoff_level3_preview`
  → `generate_preview_job()`
- `textoff_level3_approve`
  → `approve_proposal_job()`

A aprovação é uma operação de autoridade.

Antes da promoção, `approve_proposal()` valida:

- identidade e schema da proposta;
- capítulo;
- `source_stage`;
- arquivos fonte e limpo;
- existência da pendência;
- SHA-256 da base oficial;
- SHA-256 da imagem fonte;
- dimensões do preview.

Propostas cuja base ou fonte mudou são rejeitadas como obsoletas.

### Autoridade da aprovação Nível III

Para `source_stage="ORIGINAL"`:

- substitui o resultado oficial do Texto Off;
- preserva a imagem original em `IMG`.

Para `source_stage="MERGE"`:

- substitui o resultado oficial do Texto Off;
- substitui também a imagem correspondente em `02_MERGE`.

Assim, o Nível III pode atravessar a fronteira do Texto Off e modificar um artefato oficial upstream de Merge.

### Rollback do Nível III

A aprovação preserva e pode restaurar:

- resultado oficial anterior do Texto Off;
- imagem anterior de `02_MERGE`, quando aplicável;
- estado `pending.json`;
- manifesto `proposal.json`.

As promoções utilizam arquivos temporários, `os.replace` e verificações SHA-256 posteriores.

Falhas de rollback são reportadas explicitamente.

### Comparação e estado

A Central utiliza:

- `textoff_compare.comparison_state()`;
- `textoff_compare.media_base()`;
- `textoff_level3.queue_state()`.

Esses contratos atendem leitura, comparação e fila de revisão e não devem ser confundidos com as operações de promoção.

### Tratamentos Especiais

A Central utiliza:

- `select_special_image()`;
- `process_special_image()`;
- `promote_special_result()`.

A promoção especial:

- valida a execução e seus metadados;
- rejeita tratamentos ainda bloqueados para promoção;
- valida SHA-256 do resultado;
- valida snapshot da base oficial;
- rejeita propostas obsoletas;
- cria backup quando substitui saída existente;
- promove via arquivo temporário + `os.replace`;
- registra manifesto da promoção.

Pela evidência atual, essa promoção altera a saída oficial de Texto Off correspondente ao stage resolvido.

Não foi identificada nesse contrato a promoção direta da imagem fonte para `02_MERGE`, comportamento que existe explicitamente na aprovação Nível III.

### Jobs e observabilidade

As operações de limpeza e Nível III executadas por `/api/action` passam pelo dispatcher compartilhado:

`make_job()` → `run_job()`

Assim, além dos contratos de domínio, a migração precisa preservar o envelope transversal de execução, progresso, resultado e eventos antes/depois.

Tratamentos Especiais possuem endpoints HTTP próprios e não devem ser artificialmente convertidos para o mesmo contrato de job sem decisão arquitetural específica.

### Dependência de `row_state()`

Não foi identificada dependência direta de `row_state()` nos contratos operacionais de Texto Off analisados.

Isso não elimina dependências transversais do dispatcher legado para captura de estado e observabilidade.

### Risco preliminar de extração

**Alto.**

O risco decorre da combinação de:

- múltiplos subfluxos operacionais;
- pipeline oficial Nível I + Nível II;
- manifests e relatórios próprios;
- processamento externo;
- integridade por SHA-256;
- promoção transacional;
- propostas e controle de obsolescência;
- rollback;
- jobs compartilhados;
- promoção da correção Nível III para `02_MERGE` quando a fonte é MERGE.

A classificação não define a ordem de migração.

---

## 8.5 Validação de imagens

### Fronteira atual

O domínio existente está em:

`processamento/validacao_imagens/analisador_dimensoes.py`

A regra de análise por capítulo está concentrada em:

`analyze_chapter()`

Entretanto, a fronteira funcional completa ainda não está encapsulada nesse módulo.

A Central legada mantém:

- `dimension_root()`;
- `_dimension_payload()`;
- `dimension_state()`;
- `do_dimension_analyze()`;
- `do_dimension_correct()`.

Assim, existe separação parcial entre regra de domínio e camada de aplicação, mas a aplicação ainda está significativamente acoplada a `interface_web/processing_web.py`.

### Contratos HTTP e jobs

Leitura:

`GET /api/dimension-analysis`
→ `dimension_state()`

Execução:

`dimension_analyze`
→ `do_dimension_analyze()`

`dimension_correct`
→ `do_dimension_correct()`

As duas operações executáveis passam pelo dispatcher compartilhado de jobs.

### Análise dimensional

`_dimension_payload()`:

- resolve os capítulos selecionados;
- delega a análise para `analisador_dimensoes.analyze_chapter()`;
- monta o payload de aplicação;
- calcula o resumo agregado;
- opcionalmente persiste os resultados.

A persistência utiliza:

`FLUXO_SECUNDARIO/ANALISE_DIMENSOES/analise_dimensoes_atual.json`

e:

`FLUXO_SECUNDARIO/ANALISE_DIMENSOES/analise_dimensoes_atual.txt`

Quando apenas parte dos capítulos é analisada, o JSON preserva resultados anteriores dos demais capítulos e atualiza os capítulos processados na execução atual.

O TXT registra somente o escopo efetivamente analisado naquela execução.

### Projeção de estado

`dimension_state()` lê o JSON persistido e produz a projeção consumida pela interface.

Quando não existe análise persistida, retorna estado indisponível com resumo zerado e tolerância padrão.

Essa responsabilidade permanece na Central legada e ainda não possui fachada própria no domínio.

### Correção dimensional

`do_dimension_correct()` é uma operação mutável sobre as imagens ativas de `IMG`.

Para cada capítulo:

- utiliza a largura dominante calculada pela análise;
- seleciona imagens classificadas como `EXCECAO_DIMENSAO`;
- exige que todas as imagens candidatas continuem ativas;
- bloqueia a correção do capítulo se algum backup `_old` já existir;
- bloqueia a correção antes de iniciar se qualquer candidato falhar nas validações de segurança;
- redimensiona a largura para a largura dominante;
- recalcula proporcionalmente a altura;
- utiliza `Image.Resampling.LANCZOS`;
- grava primeiro em arquivo temporário;
- renomeia o original para `*_old`;
- promove o temporário para o nome original.

Em falha durante a substituição, tenta restaurar o original a partir do backup.

### Autoridade

A correção possui autoridade direta sobre as imagens fonte oficiais em `IMG`.

Após pelo menos uma correção bem-sucedida:

1. a análise dimensional do capítulo é recalculada e persistida;
2. `clear_merge_failure(ch)` é executado.

`clear_merge_failure()` remove especificamente o arquivo de status de falha do Merge e remove seu diretório apenas quando ele fica vazio.

Pela evidência analisada, essa chamada não recalcula Merge nem remove os artefatos oficiais de Merge.

### Estado, persistência e efeitos

A fronteira possui:

- leitura de imagens em `IMG`;
- alteração direta de imagens em `IMG`;
- backups `_old`;
- persistência JSON;
- persistência TXT;
- atualização da análise após correção;
- remoção de estado de falha do Merge;
- progresso via job compartilhado.

### Dependência de `row_state()`

Não foi identificada dependência direta de `row_state()` nos contratos de Validação de imagens analisados.

Permanece a dependência transversal do dispatcher compartilhado para execução e observabilidade.

### Situação arquitetural

`analisador_dimensoes.py` já oferece uma fronteira de domínio para análise, mas não representa sozinho o fluxo funcional completo.

Persistência, projeção de estado, correção e integração com o status de Merge continuam implementadas no legado.

Na migração para a Central V2, essas responsabilidades não devem ser copiadas para a nova camada HTTP nem consumidas diretamente de `processing_web.py`.

A fronteira de aplicação deverá ser extraída para módulo próprio antes ou durante a migração vertical desse fluxo, preservando o comportamento existente.

### Risco preliminar de extração

**Alto.**

O risco decorre de:

- lógica de aplicação ainda residente no legado;
- modificação direta de `IMG`;
- backups `_old`;
- persistência incremental da análise;
- integração com estado de falha do Merge;
- execução por jobs compartilhados;
- necessidade de preservar exatamente as regras atuais de correção.

A classificação não define a ordem de migração.

---

## 8.6 PDF

### Fronteira operacional

A capacidade PDF possui dois contratos distintos na Central atual:

1. PDF normal, gerado a partir das imagens do capítulo;
2. PDF do MERGE, gerado a partir dos artefatos do MERGE oficial.

Os dois contratos compartilham a finalidade de geração de PDF, mas possuem fontes, validações, destinos e fronteiras de aplicação diferentes.

### PDF normal

A action:

`pdf`

é adaptada por:

`do_pdf()`

e delegada para:

`orquestracao.menu.run_pdf_batch()`

Assim, a Central não contém a regra principal desse fluxo; ela adapta progresso e resultado para o contrato compartilhado de job.

### Fonte e destino do PDF normal

Para capítulos localizados em `IMG`, `_pdf_path()` resolve o destino como:

`<obra>/PDF/<capítulo>/<capítulo>.pdf`

A geração utiliza:

`src.converter.convert_to_pdf`

carregado pelo adaptador `_import_convert_to_pdf()` de `orquestracao/menu.py`.

### Validações do PDF normal

Antes da geração, `run_pdf_batch()`:

- preserva PDF existente quando `regenerate_existing=False`;
- bloqueia capítulo com marcador de download em andamento;
- valida o marcador persistente de conclusão quando existente;
- valida as imagens do capítulo;
- registra falhas de validação sem interromper o restante do lote.

Depois da geração:

- exige retorno válido do conversor;
- valida o PDF produzido;
- compara a quantidade de páginas com a quantidade de imagens quando aplicável;
- registra falhas de validação do PDF.

Portanto, geração e validação pós-geração fazem parte do contrato atual do PDF normal.

### PDF do MERGE

A action:

`pdf_merge`

é implementada por:

`do_pdf_merge()`

em `interface_web/processing_web.py`.

Diferentemente do PDF normal, sua fronteira de aplicação ainda está na Central legada.

### Fonte e destino do PDF do MERGE

Antes da geração:

- exige `is_chapter_merged(ch)` válido;
- obtém os artefatos por `merge_artifact_files(merge_output_dir(ch))`.

A fonte, portanto, é exclusivamente o MERGE oficial.

O destino é:

`FLUXO_SECUNDARIO/03_PDF_MERGE/<capítulo>/<capítulo>.pdf`

Se o PDF já existir, a execução atual o preserva e retorna `skipped`.

A geração utiliza:

`src.pdf.generator.generate_pdf_from_images`

carregado pelo helper `pdf_generator()` da Central legada.

### Diferença entre os pipelines

Não foi identificada no contrato atual de `do_pdf_merge()` uma validação pós-geração equivalente à executada por `run_pdf_batch()`.

Essa diferença deve ser preservada durante a refatoração até que exista decisão funcional explícita para alterar o comportamento.

O PDF do MERGE não deve ser redirecionado automaticamente para `run_pdf_batch()` apenas para uniformizar a arquitetura.

### Autoridade

Os dois fluxos possuem autoridade sobre seus respectivos artefatos PDF derivados.

O PDF normal não modifica as imagens fonte.

O PDF do MERGE depende da validade do MERGE oficial como fonte, mas não modifica os artefatos oficiais de MERGE.

Assim, a autoridade desta fronteira é de geração de artefato derivado, e não de promoção sobre `IMG` ou MERGE.

### Projeções auxiliares

A Central legada também mantém helpers de leitura/localização do PDF do MERGE, incluindo:

- `pdf_merge_files()`;
- `latest_pdf_merge_batch()`.

Essas responsabilidades fazem parte da projeção HTTP/UI atual e não da geração propriamente dita.

### Jobs e observabilidade

As actions `pdf` e `pdf_merge` passam pelo dispatcher compartilhado:

`make_job()` → `run_job()`

Portanto, a migração deve preservar o envelope de execução, progresso, resultado e observabilidade associado aos jobs.

### Dependência de `row_state()`

Não foi identificada dependência direta de `row_state()` nos contratos de geração de PDF analisados.

O estado agregado da Central pode projetar a existência de PDF, mas isso é distinto de uma dependência funcional da geração.

### Situação arquitetural

O PDF normal já possui uma fronteira de aplicação reutilizável fora da Central:

`orquestracao.menu.run_pdf_batch()`

O PDF do MERGE ainda concentra sua regra de aplicação em `processing_web.py`.

Na Central V2:

- o PDF normal pode consumir a fronteira existente;
- o PDF do MERGE não deve ser copiado para a nova camada HTTP;
- sua regra de aplicação deverá ser extraída para uma fronteira própria antes ou durante sua migração vertical.

### Risco preliminar de extração

**Médio.**

O risco decorre principalmente de:

- existência de dois contratos distintos;
- dependência do PDF normal de validações e estado persistente de download;
- dependência do PDF Merge da autoridade do MERGE oficial;
- implementação do PDF Merge ainda residente no legado;
- jobs compartilhados;
- necessidade de preservar as diferenças funcionais atuais.

A classificação não define a ordem de migração.

---

## 8.7 Auto-Merge I–V

### Fronteira operacional

O Auto-Merge é uma cadeia incremental de cinco níveis:

`Nível I → Nível II → Nível III → Nível IV → Nível V`

Cada nível pode:

- resolver integralmente o capítulo e permitir promoção para o MERGE oficial;
- produzir artefatos SAFE intermediários;
- manter segmentos residuais para o nível seguinte;
- encaminhar residual não resolvido para revisão/manual conforme o estágio.

A Central atual expõe actions independentes:

- `merge`;
- `merge_level2`;
- `merge_level3`;
- `merge_level4`;
- `merge_level5`.

Todas passam pelo dispatcher compartilhado de jobs.

### Implementação atual

Os adapters principais permanecem em:

`interface_web/processing_web.py`

por meio de:

- `do_merge()`;
- `do_merge_level2()`;
- `do_merge_level3()`;
- `do_merge_level4()`;
- `do_merge_level5()`.

As regras e utilitários de Merge também dependem fortemente de:

`processamento/unificacao_imagens/image_stitcher.py`

e dos módulos especializados dos níveis seguintes.

A fronteira, portanto, é apenas parcialmente extraída do legado.

### Nível I

O Nível I pode produzir dois estados principais de manifesto:

`auto_merge_level1_complete`

ou:

`auto_merge_level1_resolved_segments`

Quando o capítulo é integralmente resolvido no Nível I, `_promote_level1_complete()` pode consolidar diretamente a composição oficial.

Quando existem segmentos não resolvidos, os artefatos resolvidos do Nível I tornam-se parte da composição acumulada utilizada pelos níveis posteriores.

### Nível II

O Nível II utiliza:

`merge-level2-manifest.json`

com algoritmo esperado:

`merge_level2_bounded_safe_path_v1`

A promoção direta pelo Nível II somente ocorre quando não existem `pending_segments`.

Sua composição oficial acumula:

`Nível I + Nível II`

sem rerenderizar os artefatos intermediários.

### Nível III

O Nível III utiliza:

`merge-level3-manifest.json`

com algoritmo:

`merge_level3_structural_safe_v1`

Antes de uma promoção integral:

- o manifesto do Nível II precisa ser válido;
- `source_level2_sha256` precisa corresponder ao SHA-256 atual do manifesto do Nível II;
- não podem existir `residual_pending_segments`.

Sua composição acumula:

`Nível I + Nível II + Nível III`

### Nível IV

O fluxo atual reconhece explicitamente o Nível IV dirigido:

`merge_level4_directed_structural_safe_v1`

e também identifica o modo exaustivo legado:

`merge_level4_global_structural_safe_v1`

Para promoção pelo fluxo dirigido:

- o manifesto do Nível III precisa ser válido;
- `source_level3_sha256` do Nível IV precisa corresponder ao manifesto atual do Nível III;
- não podem existir segmentos residuais.

Sua composição acumula:

`Nível I + Nível II + Nível III + Nível IV`

A distinção entre Nível IV dirigido e legado participa também da decisão de continuidade para Nível V ou Review.

### Nível V

O Nível V utiliza:

`merge-level5-manifest.json`

com algoritmo:

`merge_level5_global_structural_safe_v1`

A promoção exige especificamente o novo Nível IV dirigido.

A cadeia de integridade verificada inclui:

`Nível III → SHA-256 → Nível IV → SHA-256 → Nível V`

Antes da promoção:

- o manifesto do Nível IV deve existir;
- o algoritmo do Nível IV deve ser o dirigido;
- o SHA-256 registrado pelo Nível IV deve corresponder ao manifesto atual do Nível III;
- o SHA-256 registrado pelo Nível V deve corresponder ao manifesto atual do Nível IV;
- não podem existir `residual_pending_segments`.

Quando ainda existe residual no Nível V, o contrato atual o encaminha para Merge Manual.

### Barreira de promoção para MERGE oficial

A consolidação automática dos níveis converge para:

`_promote_stage_composition()`

Essa função constitui uma barreira crítica de autoridade.

Antes da promoção, ela valida:

- existência de peças;
- `total_height` válido;
- ordenação da composição;
- cobertura contínua iniciando em zero;
- ausência de lacunas;
- ausência de sobreposições;
- existência dos artefatos;
- legibilidade das imagens;
- altura física compatível com o intervalo global;
- largura uniforme;
- cobertura final exatamente igual a `total_height`.

### Proteção do MERGE oficial

O destino oficial é resolvido por:

`image_stitcher.merge_output_dir(ch)`

A promoção é recusada quando:

- já existe MERGE oficial válido;
- existe diretório oficial não reconhecido.

Assim, a rotina não sobrescreve silenciosamente uma autoridade anterior.

### Materialização oficial

Somente após todas as validações a função cria o diretório oficial e copia os artefatos da composição.

Em seguida grava:

`merge-manifest.json`

com:

- status `approved`;
- algoritmo da composição;
- dimensões e cobertura;
- lista de outputs;
- estágio de origem de cada artefato;
- informações de segurança;
- cadeia de manifests que compôs o resultado.

A promoção só é considerada válida se:

`image_stitcher.is_chapter_merged(ch)`

reconhecer o resultado produzido.

Se qualquer etapa da consolidação falhar, o diretório oficial recém-criado é removido.

### Autoridade

Os diretórios e manifests intermediários dos níveis representam estados da cadeia de resolução.

A autoridade final do capítulo passa a ser o MERGE oficial somente após a promoção bem-sucedida e sua validação por `is_chapter_merged()`.

Portanto:

`manifests intermediários → composição validada → merge-manifest.json oficial`

é a cadeia de autoridade observada.

A existência isolada de diretórios ou artefatos intermediários não equivale a MERGE oficial válido.

### Projeção por `row_state()`

`row_state()` participa diretamente da interpretação operacional dessa cadeia.

Ele combina, entre outros:

- validade do MERGE oficial;
- estado de falha do Merge;
- partição do Nível II;
- validação do Nível II;
- validade e residual do Nível III;
- validade e residual do Nível IV;
- algoritmo do Nível IV;
- validade e residual do Nível V.

A partir dessa combinação projeta estados como:

- `novo`;
- `parcial`;
- `pendente_level3`;
- `pendente_level4`;
- `pendente_level5`;
- `pendente_review`;
- `concluido`.

Também deriva `needs_review` conforme a cadeia efetivamente alcançada.

### Autoridade versus projeção

`row_state()` não deve ser tratado como a autoridade persistente do Auto-Merge.

Sua função atual é interpretar autoridades persistidas e produzir uma projeção operacional para a Central.

Essa distinção é obrigatória para a Central V2:

`manifests/artefatos oficiais = autoridade`

`resolver de estado = projeção derivada`

A V2 não deve inferir o estágio apenas pela existência de pastas nem transformar estado visual em nova fonte de verdade.

### Jobs e observabilidade

As cinco actions utilizam o dispatcher compartilhado:

`make_job()` → `run_job()`

O contrato de migração precisa preservar:

- progresso;
- mensagens;
- resultado por capítulo;
- erros;
- observabilidade antes/depois;
- relação entre execução e estado persistido.

### Integração com falha de Merge

Após promoções automáticas reconhecidas, fluxos dos níveis podem executar:

`clear_merge_failure(ch)`

Essa operação remove o marcador persistido de falha do Merge quando o capítulo deixa de depender daquele estado.

Isso não deve ser reinterpretado como remoção dos artefatos oficiais de Merge.

### Situação arquitetural

O Auto-Merge possui regras de domínio e algoritmos especializados fora da Central, porém a camada de aplicação ainda está fortemente concentrada em `processing_web.py`.

Estão no legado responsabilidades como:

- adapters dos cinco níveis;
- interpretação da cadeia;
- composição entre estágios;
- barreira de promoção;
- parte relevante da validação de manifests;
- projeção operacional.

Na Central V2 essas responsabilidades não devem ser copiadas para routes, jobs ou frontend.

A migração exige uma fronteira de aplicação própria que preserve a cadeia de autoridade existente e reutilize os módulos de domínio atuais.

### Restrições de refatoração

Esta análise não autoriza alteração de:

- algoritmos dos níveis I–V;
- heurísticas;
- thresholds;
- `image_stitcher.py`;
- formatos ou semântica dos manifests;
- regras de cobertura;
- regras de promoção;
- encadeamento SHA-256;
- critérios de encaminhamento entre níveis;
- compatibilidade histórica do Nível IV.

Esses comportamentos permanecem protegidos.

### Risco preliminar de extração

**Alto.**

O risco decorre de:

- autoridade sobre o MERGE oficial;
- cinco estágios dependentes;
- manifests encadeados;
- validações de integridade;
- vínculos SHA-256;
- compatibilidade com Nível IV legado;
- projeção transversal em `row_state()`;
- dispatcher compartilhado;
- transição para Review e Merge Manual;
- grande quantidade de lógica de aplicação ainda residente no legado.

A classificação não define a ordem de migração.

---
## 9. Contrato de análise por componente

Para cada fluxo deverão ser registrados antes da decisão de migração:

- símbolos envolvidos;
- responsabilidade;
- chamadores;
- dependências chamadas;
- entradas;
- saídas;
- efeitos colaterais;
- paths manipulados;
- manifests e artefatos;
- estado compartilhado;
- exceções relevantes;
- testes de proteção existentes;
- risco de extração.

---

## 10. Próxima análise

Completar a matriz por fluxo e o mapa de autoridade antes de definir formalmente a ordem de migração vertical para a Central V2.
