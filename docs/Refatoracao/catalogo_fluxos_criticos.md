# Catálogo de Fluxos Críticos

**Projeto:** Fominha_de_Manga  
**Fase:** 0 — Proteção antes da refatoração  
**Natureza:** catálogo operacional de fluxos críticos  
**Regra:** este documento descreve contratos observados. Não autoriza alteração funcional ou estrutural.

---

## 1. Objetivo

Registrar, para cada fluxo crítico protegido durante a refatoração:

- entrada;
- endpoint/evento;
- orquestração;
- módulo responsável;
- artefatos/manifests;
- estado final esperado;
- teste automatizado existente;
- smoke/caso real disponível.

Este catálogo complementa o Mapa do Metrô. O Mapa documenta principalmente autoridade, proveniência e transições; este documento registra a superfície operacional que deverá permanecer protegida durante a refatoração.

---

## 2. Central Web

**Entrada:** abertura da Central de Processamento Web.

**Endpoint/evento:** frontend estático; `/api/catalog`; `/api/state`.

**Orquestração:** `interface_web/processing_web.py`, incluindo `Handler`, `catalog()` e `state()`.

**Módulo responsável:** `interface_web/processing_web.py`.

**Artefatos/manifests:** não produz autoridade própria; agrega estado derivado e expõe os artefatos/manifests dos fluxos especializados.

**Estado final esperado:** Central disponível, catálogo carregado e estado da obra projetado sem alterar autoridade persistida.

**Teste automatizado existente:** não foi identificado teste HTTP direto de `Handler`, `do_GET`, `do_POST` ou `ThreadingHTTPServer`.

**Smoke/caso real disponível:** não formalizado na baseline atual.

---

## 3. Seleção de obra e capítulo

**Entrada:** provider, obra e capítulos selecionados na Central.

**Endpoint/evento:** `/api/catalog`, `/api/state` e payload de `/api/action`.

**Orquestração:** `catalog()`, `state()`, `manga_path()` e `selected()`.

**Módulo responsável:** `interface_web/processing_web.py`.

**Artefatos/manifests:** não cria manifesto próprio; resolve a obra e os diretórios de capítulo que alimentarão o fluxo solicitado.

**Estado final esperado:** obra resolvida e conjunto válido de capítulos entregue ao fluxo; seleção vazia é rejeitada.

**Teste automatizado existente:** existem testes de descoberta/listagem de capítulos no fluxo CLI, mas não foi identificado teste específico do contrato de seleção da Central Web.

**Smoke/caso real disponível:** não formalizado na baseline atual.

---

## 4. Jobs

**Entrada:** `POST /api/action` com `action`, provider, obra, capítulos e parâmetros específicos.

**Endpoint/evento:** `POST /api/action`; consulta por `GET /api/job/<id>`.

**Orquestração:** `make_job()` → `run_job()` → dispatch por `job.action`.

**Módulo responsável:** `interface_web/processing_web.py`.

**Artefatos/manifests:** não possui manifesto de domínio próprio; registra eventos `job_requested`, `job_finished` e `job_failed`, incluindo estado e inventário de manifests antes/depois.

**Estado final esperado:** `done` com resultado do fluxo ou `error` com erro registrado.

**Teste automatizado existente:** não foi identificado teste dedicado ao lifecycle genérico de jobs.

**Smoke/caso real disponível:** não formalizado na baseline atual.

---

## 5. Auto-Merge I–V

**Entrada:** capítulos selecionados e imagens fonte em `IMG/<capítulo>`.

**Endpoint/evento:** `/api/action` com ações `merge`, `merge_level2`, `merge_level3`, `merge_level4` e `merge_level5`.

**Orquestração:** `run_job()` → `do_merge()` / `do_merge_level2()` / `do_merge_level3()` / `do_merge_level4()` / `do_merge_level5()`.

**Módulo responsável:** algoritmos especializados em `processamento/unificacao_imagens/`; autoridade, promoção e integração atualmente coordenadas por `interface_web/processing_web.py`.

**Artefatos/manifests:** `auto-merge-manifest.json`, `merge-level2-manifest.json`, `merge-level3-manifest.json`, `merge-level4-manifest.json`, `merge-level5-manifest.json` e, quando resolvido integralmente, `merge-manifest.json`.

**Estado final esperado:** MERGE oficial válido quando todo o capítulo é resolvido; caso contrário, residual autoritativo encaminhado ao próximo estágio aplicável ou Review/Merge Manual conforme contrato vigente.

**Teste automatizado existente:** cobertura de caracterização dos níveis I–V, promoção, autoridade e integração IV → V → MERGE/Review. GAP-TEST-AM45 fechado.

**Smoke/caso real disponível:** existe teste capaz de consumir o capítulo 6 real de `Emergency_Youth Record Book` quando disponível no ambiente; não constitui ainda smoke baseline formalizado.

---

## 6. Review

**Entrada:** residual autoritativo ainda não resolvido automaticamente.

**Endpoint/evento:** `/api/action` com `review_generate`, `review_approve` ou `review_reject`.

**Orquestração:** `run_job()` → `do_review_generate()` / `do_review_approve()` / `do_review_reject()`.

**Módulo responsável:** `processamento/unificacao_imagens/image_stitcher_review.py`, com integração atual em `processing_web.py`.

**Artefatos/manifests:** `merge-review.json`, artefatos de `MERGE_REVIEW` e, após aprovação válida, `merge-manifest.json`.

**Estado final esperado:** proposta pendente, rejeição preservando IMG/MERGE, ou promoção para MERGE oficial válido.

**Teste automatizado existente:** caracterização de escopo, autoridade, composição final, segurança e integração com residual dos níveis automáticos.

**Smoke/caso real disponível:** capítulo 6 real pode ser utilizado por teste especializado quando disponível; smoke baseline ainda não formalizado.

---

## 7. Merge Manual

**Entrada:** residual autoritativo proveniente do Review.

**Endpoint/evento:** `/api/action` com `merge_manual_generate` e `merge_manual_apply`; leitura por `/api/merge-manual` e `/api/merge-manual-proposal`.

**Orquestração:** `run_job()` → serviços de proposta e aplicação do Merge Manual.

**Módulo responsável:** `processamento/merge_manual/`.

**Artefatos/manifests:** proposta manual, estado do Review e `merge-manifest.json` oficial após finalização válida.

**Estado final esperado:** composição manual validada promovida ao MERGE oficial, preservando artefatos automáticos fora do escopo manual e rejeitando estado obsoleto.

**Teste automatizado existente:** `dev/tests/test_merge_manual_proposal.py`, `dev/tests/test_merge_manual_apply_final.py` e `dev/tests/test_merge_manual_readonly.py`.

**Smoke/caso real disponível:** não formalizado na baseline atual.

---

## 8. Texto Off

**Entrada:** imagens originais ou MERGE oficial válido.

**Endpoint/evento:** `/api/action` com `clean`, `clean_merged` e ações de Nível III; consultas específicas de comparação/Nível III.

**Orquestração:** `run_job()` → `do_clean()` / `do_clean_merged()` e jobs especializados do Nível III.

**Módulo responsável:** `processamento/limpeza_baloes/`, principalmente Cleaner V2 e módulos especializados do Nível III.

**Artefatos/manifests:** resultados de Texto Off, `clean-manifest.json`, propostas/previews e manifests especializados do Nível III.

**Estado final esperado:** resultado limpo materializado e associado ao mapeamento registrado pelo fluxo; correções assistidas permanecem sujeitas à validação de proposta e estado vigente.

**Teste automatizado existente:** não foi identificado teste automatizado específico de Texto Off na suíte atual.

**Migração V2 iniciada:** página Texto Off — Merged consulta `/api/textoff/merged`, executa `/api/textoff/merged/execute` como job e delega ao `clean_chapter(source_stage="MERGE")`. Testes novos cobrem a consulta/projeção, validação da seleção, contrato HTTP e execução frontend. Isso não altera ainda os contratos de Texto Off — Original, Correção Assistida ou Tratamentos Especiais.

**Smoke/caso real disponível:** não formalizado na baseline atual.

**Lacuna conhecida:** a proveniência MERGE oficial → Texto Off — Merged não possui, no levantamento atual, fingerprint inequívoco dos bytes do MERGE de origem no `clean-manifest.json`.

O rótulo “Resultado registrado” na nova tela V2 significa correspondência de stage, nomes e contagem de artefatos no manifesto; não deve ser interpretado como confirmação de que os bytes da origem permanecem idênticos.

---

## 9. Tratamentos especiais

**Entrada:** imagem selecionada dentro do fluxo de Texto Off.

**Endpoint/evento:** `/api/textoff-special/select-image`, `/api/textoff-special/process` e `/api/textoff-special/promote`.

**Orquestração:** handlers específicos da Central → serviços especializados de Texto Off.

**Módulo responsável:** módulos especializados sob `processamento/limpeza_baloes/` e integração Web correspondente.

**Artefatos/manifests:** previews/resultados especializados e integração com o mapeamento vigente do Texto Off, conforme o tratamento aplicado.

**Estado final esperado:** prévia especializada gerada e, somente após promoção válida, resultado incorporado ao fluxo correspondente.

**Teste automatizado existente:** não foi identificado teste automatizado específico de Tratamentos Especiais nem teste HTTP direto dessas rotas na suíte atual.

**Smoke/caso real disponível:** não formalizado na baseline atual.

---

## 10. Balanceamento

**Entrada:** MERGE oficial válido e seleção de merges/região.

**Endpoint/evento:** `/api/action` com `balance_prepare`, `balance_execute`, `balance_effect` e `balance_generate`; consulta por `/api/balance-analysis`.

**Orquestração:** `run_job()` → funções Web de Balanceamento → módulos especializados.

**Módulo responsável:** `processamento/balanceamento/balanceador.py` e `processamento/balanceamento/balanceamento.py`.

**Artefatos/manifests:** `balance-editor.json`, `balance-proposal-manifest.json`, status operacional de Balanceamento e `merge-manifest.json` atualizado após efetivação.

**Estado final esperado:** proposta sem alterar MERGE durante preparação; após efetivação válida, composição balanceada substitui somente a região autorizada e o MERGE oficial continua sendo a autoridade compartilhada.

**Teste automatizado existente:** não foi identificado teste automatizado específico de Balanceamento na suíte atual; o contrato/proveniência está documentado no checkpoint específico.

**Smoke/caso real disponível:** não formalizado na baseline atual.

---

## 11. PDF

**Entrada:** capítulos originais para PDF comum ou MERGE oficial válido para PDF_MERGE.

**Endpoint/evento:** `/api/action` com `pdf` ou `pdf_merge`; consultas auxiliares `/api/pdf-merge-latest` e `/api/pdf-merge-files`.

**Orquestração:** `run_job()` → `do_pdf()` / `do_pdf_merge()`.

**Módulo responsável:** integração Web e `processamento/pdf_original/`; geração delegada ao conversor correspondente.

**Artefatos/manifests:** PDF original e `03_PDF_MERGE/<capítulo>/<capítulo>.pdf`; não foi identificado manifesto próprio do PDF_MERGE.

**Estado final esperado:** PDF válido gerado; no PDF_MERGE, MERGE inválido bloqueia geração e PDF já existente atualmente resulta em `skipped`.

**Teste automatizado existente:** cobertura extensa de validação de entrada, geração, pós-validação, falhas, preservação e capítulos incompletos.

**Smoke/caso real disponível:** não formalizado na baseline atual.

**Lacuna conhecida:** não foi identificada identidade/hash da versão do MERGE que originou um PDF_MERGE existente.

---

## 12. Exportação

**Entrada:** obra, diretório de destino e conteúdos selecionados para exportação.

**Endpoint/evento:** `/api/export/select-directory`, `/api/export/simulate` e `/api/export/execute`.

**Orquestração:** handlers específicos → serviço de Exportação.

**Módulo responsável:** `processamento/exportacao/`.

**Artefatos/manifests:** plano de exportação transitório; copia artefatos selecionados, incluindo Texto Off — Merged e PDF_MERGE, aplicando exclusões do fluxo.

**Estado final esperado:** simulação determina exatamente os arquivos elegíveis; execução copia o plano válido sem remover conteúdo alheio do destino e rejeita alteração da origem detectada entre simulação e execução.

**Teste automatizado existente:** `dev/tests/test_exportacao.py` cobre simulação, execução, preservação de conteúdo existente e rejeição quando a origem muda.

**Smoke/caso real disponível:** não formalizado na baseline atual.

---

## 13. Cobertura e lacunas da Fase 0

O catálogo diferencia três situações:

1. **contrato automatizado existente** — há caracterização/regressão específica;
2. **cobertura parcial** — componentes são testados, mas a superfície completa da Central não é;
3. **não identificado** — nenhuma proteção automatizada específica foi encontrada no levantamento.

Lacunas de cobertura observadas:

- ausência de teste dedicado ao lifecycle genérico de jobs;
- seleção obra/capítulo da Central sem contrato automatizado específico identificado além do smoke HTTP mínimo;
- ausência de teste automatizado específico de Texto Off;
- ausência de teste automatizado específico de Tratamentos Especiais;
- ausência de teste automatizado específico de Balanceamento.

Essas lacunas não são classificadas automaticamente como defeitos e não autorizam mudança funcional.

---

## 14. Relação com o smoke baseline

### 14.1 Smoke HTTP mínimo da Central

Foi formalizado em `dev/tests/test_processing_web_smoke.py` um smoke operacional mínimo da Central.

Cobertura:

- `ThreadingHTTPServer` real;
- `Handler` real da Central;
- porta efêmera;
- filesystem temporário e isolado;
- `GET /api/catalog`;
- `GET /api/state`;
- resolução de provider/obra;
- serialização e resposta HTTP;
- encerramento controlado do servidor.

O smoke não acessa a biblioteca real, não executa algoritmos de processamento e não dispara `/api/action`.

Comando de baseline:

`python3 -m unittest -v dev.tests.test_processing_web_smoke`

Resultado registrado na Fase 0:

`Ran 1 test in 0.648s — OK`

### 14.2 Caso real algorítmico complementar

`dev/tests/test_image_stitcher_review.py` contém caracterização com o dataset real do capítulo 6 de `Emergency_Youth Record Book`, quando disponível no ambiente.

O caso valida, entre outros contratos, 143 PNGs de origem, geração de 30 saídas, altura total de 119971 pixels, limite máximo de 8 imagens-fonte por segmento e determinismo entre duas execuções.

Esse caso é evidência algorítmica complementar e não substitui o smoke HTTP da Central. O teste pode ser marcado como `skip` quando o dataset real esperado não estiver disponível.

### 14.3 Limites do baseline

O smoke mínimo não caracteriza o lifecycle genérico de `/api/action`/jobs nem constitui smoke individual de todos os fluxos críticos.

Essas coberturas permanecem registradas separadamente como lacunas ou contratos específicos e não impedem, por si só, o registro do smoke baseline mínimo da Fase 0.

---

## 15. Estado do catálogo

Os fluxos críticos exigidos pela Fase 0 foram catalogados quanto a entrada, endpoint/evento, orquestração, responsabilidade, artefatos/manifestos, estado esperado, cobertura automatizada e disponibilidade de smoke.

**Status deste documento:** FORMALIZADO — FASE 0.

Nenhuma alteração de produção foi realizada durante a elaboração deste catálogo.
