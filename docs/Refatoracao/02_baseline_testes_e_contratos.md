# Baseline de Testes e Contratos Protegidos --- Fominha_de_Manga

**Data da auditoria:** 2026-09-25\
**Branch auditada:** `develop`\
**HEAD de referência:** `c6adae7efacf289f4ca3894c1abe0dd96364f32a`\
**Fase:** 0.2 --- Inventário, relevância e baseline de testes\
**Natureza:** documentação de baseline; nenhuma alteração de produção
autorizada por este documento.

------------------------------------------------------------------------

## 1. Objetivo

Registrar o estado real da suíte de testes antes da refatoração
arquitetural, distinguindo testes atuais que devem ser preservados,
contratos válidos com fixtures/assertions antigas, testes históricos que
precisam ser migrados ou substituídos, falhas preexistentes que não
representam automaticamente defeitos de produção e lacunas de proteção
em fluxos críticos.

> **Regra da baseline:** teste vermelho não autoriza alteração de
> produção. Primeiro deve ser provado se a falha representa regressão
> funcional, contrato histórico, fixture obsoleta, assertion textual
> antiga ou erro de infraestrutura/import.

------------------------------------------------------------------------

## 2. Resultado consolidado

Execução de referência:

``` bash
python3 -m unittest discover -s dev/tests -p 'test_*.py' -v
```

Baseline observada:

-   **162 testes executados**
-   **139 passaram**
-   **20 failures**
-   **2 errors**
-   **1 skipped**
-   baseline geral: **RED preexistente**

O gate inicial da refatoração não pode ser simplesmente "todos os testes
verdes". A referência é preservar os testes atuais válidos, não
introduzir novos reds e migrar conscientemente os contratos históricos
identificados.

------------------------------------------------------------------------

## 3. Critérios

### KEEP

Compatível com a arquitetura atual e protege comportamento, segurança ou
contrato vigente.

### MIGRATE

O objetivo funcional continua válido, mas o teste contém fixture,
caminho, nomenclatura, mensagem textual, estrutura de UI ou pressuposto
arquitetural antigo.

### REPLACE

Protege diretamente um fluxo arquitetural que deixou de existir. O
conceito útil deve ser coberto por novo teste alinhado ao pipeline
atual.

### RETIRE

Somente quando for demonstrado que implementação e requisito deixaram de
existir e não há contrato equivalente. Nenhum teste deve ser aposentado
apenas porque está vermelho.

------------------------------------------------------------------------

## 4. Baseline saudável já identificada

### Image Stitcher

Permanecem verdes contratos de preservação de MERGE existente, cobertura
do fluxo oficial, rejeição de faixa curta, limites de tamanho e
comportamento seguro do Review.

### Auto-Merge Nível II

Execução isolada de `test_merge_level2_state_authority`,
`test_merge_level2_state_consistency`,
`test_merge_level2_direct_promotion_safety` e
`test_merge_level2_bounded_safe_path`: **19/19 verdes**.

Protegem autoridade de estado, consistência, promoção preservando bytes,
rejeição de GAP/OVERLAP/artefato ausente, safe partial progress,
ausência de forced cut, white/uniform band e limites de chunks.

### Auto-Merge Nível III

Há cobertura verde para SAFE/UNSAFE/INCONCLUSIVE, normalização,
cobertura, overlap, busca determinística, proibição de forced cut, scene
guard, sinais de texto/SFX, integração com Level II, imutabilidade,
offsets globais, promoção direta, stale snapshot, explainability e
estágio separado.

------------------------------------------------------------------------

## 5. Auto-Merge I--V --- área formalmente protegida

Durante a refatoração, teste vermelho não autoriza alteração em
algoritmos, thresholds, classificadores, elegibilidade, autoridade entre
estágios, manifests, SHA-256 de predecessores, composição, promoção,
diretórios oficiais, residual, cobertura ou comportamento fail-closed.

Cadeia conceitual atual:

``` text
Auto-Merge I
    ↓
Auto-Merge II
    ↓
Auto-Merge III
    ↓
Auto-Merge IV — directed
    ↓
Auto-Merge V — global/exhaustive fallback
    ↓
Review / Merge Manual
    ↓
MERGE oficial
```

A autoridade deve avançar somente pelo residual validado do estágio
anterior.

------------------------------------------------------------------------

## 6. Contratos protegidos --- Auto-Merge IV

Implementação:
`processamento/unificacao_imagens/image_stitcher_level4.py`

Características auditadas:

-   estratégia `directed_coarse_refine_v1`;
-   shortlist/coarse scan, bins, seeds e refinamento local;
-   classificação final reutiliza o classificador estrutural do Nível
    III;
-   somente `Level3Decision.SAFE` é elegível;
-   composição respeita limites mínimo/máximo;
-   ausência de caminho seguro mantém residual;
-   nenhum caminho de forced UNSAFE/INCONCLUSIVE foi identificado.

Thresholds atuais:

``` text
TARGET = 7000
MIN = 3000
MAX = 12000
COARSE_STEP = 256
BIN_HEIGHT = 3000
SEEDS_PER_BIN = 3
REFINE_RADIUS = 128
REFINE_STEP = 8
```

Devem permanecer congelados durante a refatoração salvo mudança
funcional explicitamente aprovada.

------------------------------------------------------------------------

## 7. Contratos protegidos --- Auto-Merge V

Implementação:
`processamento/unificacao_imagens/image_stitcher_level5.py`

Características auditadas:

-   estratégia global/exaustiva;
-   reutiliza classificador estrutural do Nível III;
-   somente candidatos SAFE;
-   tenta composição completa;
-   sem composição completa, pode preservar prefixo SAFE parcial;
-   restante permanece residual;
-   não aceita UNSAFE/INCONCLUSIVE;
-   não realiza forced cut.

Thresholds atuais:

``` text
TARGET = 7000
MIN = 3000
MAX = 12000
SCAN_STEP = 2
CLASSIFIER_WORKERS = 8
```

O comportamento de **partial SAFE progress** é contrato protegido.

------------------------------------------------------------------------

## 8. GAP-TEST-AM45 --- lacuna crítica

Auto-Merge IV e V participam diretamente da cadeia de autoridade,
segurança, residual e promoção, mas não possuem testes dedicados
proporcionais à criticidade.

Para IV não foi encontrada caracterização especializada equivalente à
existente para II/III. Para V existem referências incidentais em Merge
Manual, mas elas não caracterizam algoritmo, manifest, autoridade,
residual, segurança ou promoção.

**Risco:** uma refatoração poderia alterar thresholds, estratégia
directed/global, autoridade, SHA predecessor, SAFE-only, partial
progress, composição ou promoção sem detecção adequada.

**Ação obrigatória antes de refatorar IV/V:** criar testes de
caracterização específicos capturando o comportamento atual, sem
redesenhá-lo.

------------------------------------------------------------------------

## 9. DOC-AM5-01 --- documentação interna desatualizada

A docstring de `image_stitcher_level5.py` não representa integralmente o
contrato atual. Ainda descreve residual proveniente diretamente do Nível
III e sugere que, sem composição completa, todo o intervalo permanece
residual.

O código atual observado recebe autoridade após Nível IV dirigido e
suporta composição SAFE parcial.

**Classificação:** débito de documentação. Não autoriza alteração do
algoritmo.

------------------------------------------------------------------------

## 10. Auto-Merge Nível I

`test_merge_level1_auto_merge_persistence_contract.py`

-   `test_level1_failure_materializes_resolved_segments` → **KEEP**
-   `test_level1_has_dedicated_storage` → **MIGRATE**; espera
    `FLUXO_SECUNDARIO/AUTO_MERGE`, atual é
    `FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/AUTO_MERGE`
-   `test_open_folder_supports_auto_merge` → **MIGRATE**
-   `test_ui_explains_saved_level1_work` → **MIGRATE**

Nenhuma falha justifica alteração do Nível I.

------------------------------------------------------------------------

## 11. Auto-Merge Nível II --- testes históricos

`test_merge_level2.py`

-   `test_materialization_preserves_mid_page_spans_exactly`
-   `test_validation_preserves_pending_between_passed_segments`

Os objetivos são críticos: preservar pixels/offsets e impedir
desaparecimento de pending entre segmentos aprovados. Porém as fixtures
usam ausência do manifest atual obrigatório,
diretórios/nomenclatura/schema antigos.

**Classificação:** **MIGRATE --- contrato funcional crítico válido /
fixture arquitetural obsoleta.**

------------------------------------------------------------------------

## 12. Level II Review Guard / State Machine

`test_validated_level2_without_pending_never_generates_whole_chapter_review`
→ **MIGRATE**. O comportamento continua protegido; a falha é textual. A
mensagem atual fala em "residual autoritativo".

`test_level2_all_passed_finishes_without_review` → **REPLACE/MIGRATE**.
A fixture representa promoção histórica baseada em `partition`. Conceito
a preservar: **sem residual, não criar Review desnecessário**.

------------------------------------------------------------------------

## 13. Level III → Review --- composição histórica

`test_merge_level3_review_composition.py`

-   `test_composes_level2_level3_and_review_in_global_order`
-   `test_rejects_review_that_targets_original_level2_pending`
-   `test_rejects_stale_level3_snapshot`

As invariantes continuam importantes: ordem global, Review não operar
sobre autoridade antiga e stale snapshot falhar fechado. A fixture
representa `Level II → Level III → Review`, anterior à cadeia IV/V.

**Classificação:** **MIGRATE/REPLACE**. Não adicionar manifests
artificiais apenas para satisfazer a fixture histórica.

------------------------------------------------------------------------

## 14. Level III --- contratos antigos de UI

`test_merge_level3_ui_alignment_contract.py` e
`test_merge_level3_ui_page_contract.py`

-   `test_level3_uses_level2_operational_structure` → **MIGRATE**;
    assertion exata de `class="toolbar"` ficou antiga após
    `toolbar standard-filterbar`.
-   `test_review_v2_route_preserved` → **REPLACE/MIGRATE**; pressupõe
    III → Review, enquanto residual atual segue para IV.
-   `test_level3_page_is_operational_and_can_route_to_review_v2` →
    **REPLACE/MIGRATE** pelo mesmo motivo.

Demais testes do conjunto permaneceram verdes.

------------------------------------------------------------------------

## 15. Review Final Composition

`test_merge_review_final_composition.py` e
`test_merge_review_final_composition_scope.py`

Failures de composição global e múltiplas regiões usam fixtures
essencialmente `Level II + Review`, com algoritmo/schema anteriores.

**Classificação:** **MIGRATE/REPLACE**.

Preservar: ordem global, cobertura exata, integridade dos artefatos,
múltiplas regiões residuais e stale scope fail-closed.

`test_approve_rejects_stale_review_scope` → **KEEP**.

------------------------------------------------------------------------

## 16. Review Pending Scope

`test_merge_review_pending_scope.py`: 8 testes, 4 verdes, 3 failures, 1
error.

### KEEP

-   `test_processing_web_does_not_scope_review_before_level2_validation`
-   `test_source_limit_uses_supplied_uniform_candidates_without_pages`
-   `test_uniform_detector_accepts_full_width_uniform_strip`
-   `test_uniform_detector_rejects_center_only_uniform_strip`

### MIGRATE

-   `test_review_candidate_is_restricted_to_pending_interval` ---
    objetivo válido; assertion procura `merged-*`.
-   `test_disjoint_pending_intervals_remain_independent` --- mesmo
    problema de nomenclatura histórica.

### REPLACE/MIGRATE

-   `test_processing_web_passes_level2_pending_segments_to_review` ---
    protege ligação histórica direta Level II → Review. O novo teste
    deve proteger que Review recebe somente o residual autoritativo
    atual.

### MIGRATE fixture

-   `test_scoped_review_accepts_terminal_remainder_within_review_max`
    --- requisito válido, mas fixture divide uma única página-fonte em
    dois artefatos que recebem `page-001.png`; o collision guard atual
    falha fechado corretamente.

Não enfraquecer `ensure_unique_output_path()`.

------------------------------------------------------------------------

## 17. Nomenclatura de artefatos

Contrato atual usa nomes baseados no intervalo de páginas-fonte, por
exemplo:

``` text
page-068.png
page-068-073.png
```

Há leitura transitória de `merged-*`, mas novas fixtures não devem
depender da nomenclatura antiga.

Testes atuais de single/multi page, extensão, interseção de spans,
colisão fail-closed e leitura atual+legado → **KEEP**.

------------------------------------------------------------------------

## 18. PDF Batch Validation

`test_pdf_batch_validation.py` falha na coleta por:

``` text
ModuleNotFoundError: No module named 'menu'
```

O teste usa `import menu`; a implementação atual está em
`orquestracao/menu.py`.

Foi confirmado que `_import_convert_to_pdf` e `run_pdf_batch` continuam
existentes.

**Classificação:** **MIGRATE --- import arquitetural obsoleto.**

Não há evidência de defeito no processamento de PDF.

------------------------------------------------------------------------

## 19. Exportação

`test_exportacao.py`

-   `test_exclusions` → **KEEP**
-   `test_preserves_extra_and_structure` → **MIGRATE**
-   `test_source_change_invalidates` → **MIGRATE**

O primeiro failure estrutural espera:

``` text
dest/MERGED/...
dest/PDF_MERGE/...
```

O contrato atual cria:

``` text
dest/<obra>/raws_semi-clean/...
dest/<obra>/Traducoes/...
```

O segundo failure é apenas assertion textual: espera "mudaram", enquanto
a implementação atual informa "A origem ou o destino mudou desde a
simulação. Simule novamente."

Nenhuma alteração de produção justificada.

------------------------------------------------------------------------

## 20. Contrato atual de Review

O Review atual não é consumidor direto do pending original do Level II.
A autoridade deriva do estágio mais recente aplicável.

Proteções observadas:

-   manifest de Auto-Merge obrigatório;
-   algoritmo esperado por estágio;
-   `total_height` consistente;
-   SHA-256 do predecessor;
-   recomposição exata entre safe + residual;
-   rejeição de GAP/OVERLAP;
-   Review limitado ao residual autoritativo;
-   fail-closed quando estágio obrigatório ainda não foi executado;
-   Review não opera sem residual.

Esses contratos não podem ser relaxados para satisfazer fixtures
históricas.

------------------------------------------------------------------------

## 21. Merge Manual

Cobertura atual verde inclui cobertura exata, stale source, GAP,
OVERLAP, residual externo ao escopo, mapeamento de eixo global,
seleção/range e leitura do estado.

→ **KEEP**

Referências incidentais ao Nível V não substituem testes especializados
do Nível V.

------------------------------------------------------------------------

## 22. UI/estado atuais

Permanecem verdes contratos de Review V2, namespace isolado,
navegação/render separado, residual válido, regras de estado, Level II
não reaparecer após validação, Review não aceitar parcial indevido,
Visão Geral respeitar validação e erro de merge não marcar Review
automaticamente.

→ **KEEP**

------------------------------------------------------------------------

## 23. Root Menu / Orquestração

`test_root_menu_hub.py` permaneceu verde, cobrindo retorno de fluxo
manual, resolução dinâmica do projeto, ausência de caminho absoluto de
usuário, tratamento de output ausente, parsing, lote de PDF, continuação
após falha, skip de PDF existente, facade pública do conversor e
resolução do output compartilhado.

→ **KEEP**

------------------------------------------------------------------------

## 24. Regras para a próxima fase

1.  Não alterar algoritmos para tornar testes históricos verdes.
2.  Migrar testes cujo objetivo continua válido.
3.  Criar caracterização dedicada de Auto-Merge IV e V.
4.  Registrar contratos atuais antes de extrair/delegar código.
5.  Não criar novas funções em `interface_web/processing_web.py`.
6.  Novas lógicas devem residir em módulos próprios.
7.  Cada mudança deve seguir `extrair → delegar → validar → commit`.
8.  Preservar manifests e cadeia SHA.
9.  Preservar fail-closed.
10. Validar com casos reais quando a mudança atingir comportamento
    funcional.

------------------------------------------------------------------------

## 25. Decisão da Fase 0.2

A baseline vermelha foi explicada sem necessidade de modificar produção.

Os reds auditados concentram-se em:

-   fixtures de arquitetura anterior;
-   assertions textuais/estruturais;
-   rotas históricas;
-   nomenclatura anterior;
-   imports movidos;
-   contratos anteriores à cadeia completa de autoridade.

Não foi encontrada evidência suficiente para usar esses reds como
justificativa para alterar algoritmos protegidos.

A principal descoberta estrutural é:

> **Auto-Merge IV e V são críticos para a cadeia atual, mas não possuem
> caracterização dedicada equivalente à proteção existente para
> II/III.**

A Fase 0.2 pode ser considerada documentalmente encerrada com uma
pendência obrigatória antes da refatoração de IV/V:

**resolver GAP-TEST-AM45 por meio de testes de caracterização do
comportamento atual.**

------------------------------------------------------------------------

## 26. Próximo checkpoint recomendado

Antes de extrações/refatorações de produção:

-   criar testes de caracterização de Auto-Merge IV;
-   criar testes de caracterização de Auto-Merge V;
-   migrar testes de infraestrutura simples que não exigem mudança
    funcional;
-   reexecutar a baseline;
-   registrar nova fotografia da suíte.

Essas ações devem ocorrer separadamente e com validação incremental.
