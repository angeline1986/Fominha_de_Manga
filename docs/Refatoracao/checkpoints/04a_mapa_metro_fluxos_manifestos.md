# Mapa do Metrô — Fluxos, Manifestos e Autoridade
## Fominha_de_Manga — checkpoint de auditoria

**Data do checkpoint:** 2026-09-25  
**Branch auditada:** `develop`  
**Baseline:** `c6adae7efacf2894f4ca3894c1abe0dd96364f32a`  
**Status:** documento intermediário de continuidade; nenhuma alteração funcional autorizada.

> Objetivo deste documento: preservar o que já foi comprovado durante a auditoria dos fluxos que usam manifestos, checkpoints e artefatos autoritativos. Ele não substitui o plano de refatoração e ainda será ampliado com Texto Off, PDF, Exportação e demais interligações.

---

## 1. Modelo mental identificado

A arquitetura atual não possui uma única cadeia linear de manifestos. Há três conceitos distintos que precisam permanecer separados durante a refatoração:

1. **Autoridade/contrato persistido** — manifestos, SHA, residual, status e artefatos que autorizam ou bloqueiam uma etapa.
2. **Estado derivado** — projeções como `novo`, `parcial`, `pendente_level3`, `pendente_level4`, `pendente_level5`, `pendente_review` e `concluido`.
3. **Observabilidade** — eventos de execução, transições, manifests antes/depois, duração e diagnóstico.

`row_state()` em `interface_web/processing_web.py` já funciona como um embrião de **State Resolver**, porém mistura descoberta física, validação de autoridade, elegibilidade da próxima etapa e DTO da UI.

---

## 2. Linha principal — Auto-Merge até MERGE oficial

```text
IMG
 │
 ▼
MERGE INICIAL
 │
 ├── sucesso ───────────────────────────────────────────────► MERGE OFICIAL
 │
 └── falha
      ▼
 merge-attempt.json
      │
      ▼
 NÍVEL I
 auto-merge-manifest.json
      │
      ├── completo ─────────────────────────────────────────► MERGE OFICIAL
      │
      └── residual
           ▼
 NÍVEL II
 merge-level2-manifest.json
      │
      ├── sem residual ─────────────────────────────────────► MERGE OFICIAL
      │
      └── residual
           ▼
 NÍVEL III
 merge-level3-manifest.json
      │ SHA(Level II)
      │
      ├── sem residual ─────────────────────────────────────► MERGE OFICIAL
      │
      └── residual
           ▼
 NÍVEL IV — directed
 merge-level4-manifest.json
      │ SHA(Level III)
      │
      ├── sem residual ─────────────────────────────────────► MERGE OFICIAL
      │
      └── residual
           ▼
 NÍVEL V — exhaustive
 merge-level5-manifest.json
      │ SHA(Level IV)
      │
      ├── SAFE completo ────────────────────────────────────► MERGE OFICIAL
      ├── SAFE parcial + residual ──────────────────────────► REVIEW
      └── nenhum SAFE ──────────────────────────────────────► REVIEW

Rota histórica:
NÍVEL IV legacy exhaustive + residual ──────────────────────► REVIEW
```

### 2.1 `merge-attempt.json`

Classificação atual:

**checkpoint operacional + estado histórico da falha + bootstrap da cadeia de autoridade.**

Não é equivalente aos manifestos de estágio.

Contém/participa de:
- falha do merge;
- partição I/II;
- `resolved_segments`;
- `pending_segments`;
- `level2_validated`;
- atualização do residual após Nível II.

Ponto arquitetural importante: `read_merge_failure()` pode recalcular a partição e persistir novamente `merge-attempt.json`; portanto, apesar do nome `read_*`, a leitura pode alterar estado persistido.

Quando uma composição oficial é concluída com sucesso, esse estado transitório pode ser removido.

---

## 3. Nível I → Nível II

### Nível I

Manifesto:
`auto-merge-manifest.json`

Contrato observado:
- materializa segmentos resolvidos pelo Nível I;
- registra artefatos;
- registra `pending_segments`;
- registra cobertura;
- torna-se contrato de entrada do Nível II.

### Nível II

Manifesto:
`merge-level2-manifest.json`

Algoritmo:
`merge_level2_bounded_safe_path_v1`

O Nível II possui duas fontes com papéis diferentes:

- `merge-attempt.json.partition` → contexto operacional mutável;
- `auto-merge-manifest.json` → contrato de estágio e fonte efetiva do residual a processar.

Ao concluir:
- persiste artefatos;
- persiste residual;
- atualiza `merge-attempt.json`;
- se não houver residual, promove composição oficial e remove o checkpoint transitório.

---

## 4. Nível II → Nível III

Manifesto:
`merge-level3-manifest.json`

Algoritmo:
`merge_level3_structural_safe_v1`

Contrato comprovado:
- execução depende de `level2_validated`;
- residual operacional ainda é obtido da partição;
- ao finalizar, exige `merge-level2-manifest.json`;
- grava `source_level2_manifest`;
- grava `source_level2_sha256`;
- persiste `safe_artifacts`;
- persiste `residual_pending_segments`;
- registra diagnósticos e regras de segurança.

A integridade III→II é, portanto, explicitamente encadeada por SHA no manifesto do Nível III.

---

## 5. Nível III → Nível IV

Manifesto:
`merge-level4-manifest.json`

Algoritmo atual:
`merge_level4_directed_structural_safe_v1`

Contrato comprovado:
- entrada autoritativa passa por `_level3_review_pending()`;
- exige Nível III válido;
- exige manifesto do Nível III;
- processa apenas residual autorizado;
- grava SHA do manifesto III;
- persiste artefatos SAFE e residual;
- não aceita corte forçado, UNSAFE ou INCONCLUSIVE;
- publicação do estágio usa diretório temporário e substituição do destino.

Se não houver residual, pode promover MERGE oficial.

Se houver residual no algoritmo directed atual, o próximo estágio é Nível V.

Rota histórica:
`merge_level4_global_structural_safe_v1` com residual segue diretamente para Review.

---

## 6. Nível IV → Nível V

Manifesto:
`merge-level5-manifest.json`

Algoritmo:
`merge_level5_global_structural_safe_v1`

Contrato comprovado:
- somente residual de Nível IV **directed** atual entra no V;
- manifesto IV precisa existir;
- algoritmo IV precisa ser o esperado;
- grava `source_level4_sha256`;
- valida recomposição exata do residual;
- suporta SAFE completo;
- suporta **prefixo SAFE parcial + residual**;
- se não encontrar composição SAFE, mantém residual;
- residual final segue para Review.

Isso confirma que documentação antiga que descrevia o V como apenas “tudo ou nada” está desatualizada.

---

## 7. Promoções automáticas para MERGE oficial

Função central atual:
`_promote_stage_composition()`

Ela funciona como **barreira de integridade + transição de autoridade**, não apenas como cópia de arquivos.

Antes de criar o MERGE oficial:
- ordena peças;
- exige cobertura contínua;
- rejeita gap/overlap;
- valida existência dos artefatos;
- abre imagens;
- valida largura;
- valida altura física = intervalo global;
- exige cobertura integral;
- evita sobrescrever autoridade oficial já reconhecida.

O `merge-manifest.json` oficial registra:
- algoritmo de composição;
- `status=approved`;
- dimensões;
- cobertura;
- outputs;
- `source_stage`;
- `source_file`;
- composição;
- regras de segurança.

Depois da escrita, `is_chapter_merged()` precisa reconhecer a composição; em falha, o diretório oficial criado é removido.

### Algoritmos de composição observados

- Nível I: `merge_auto_level1_composition_v1`
- Nível II: `merge_auto_level2_composition_v2`
- Nível III: `merge_auto_level2_level3_composition_v2`
- Nível IV: `merge_auto_level2_level3_level4_composition_v1`
- Nível V: `merge_auto_level2_level3_level4_level5_composition_v1`

---

## 8. Review

O Review possui duas rotas:

### Rota atual — residual autoritativo

A geração recebe `pending_segments` já autorizados pelo runtime.

O gate atual em `do_review_generate()` usa `_level5_review_pending()` e bloqueia:
- residual de III se IV ainda não executou;
- residual de IV directed se V ainda não executou.

São aceitos:
- residual do V;
- residual do IV legacy exhaustive.

A proposta `merge-review.json` registra escopo, intervalos, regiões, cortes, outputs e política de segurança.

### Rota histórica

Quando não existe Level II validado, `pending_segments=None` mantém o caminho histórico de proposta para capítulo completo.

### Aprovação

`_approve_scoped_level2_review()` — apesar do nome legado — atualmente valida a cadeia I–V + Review.

Na aprovação:
- valida algoritmos esperados;
- valida SHA II→III;
- valida SHA III→IV;
- valida SHA IV→V;
- recompõe exatamente o residual em cada transição;
- exige que o escopo do Review corresponda exatamente ao residual autoritativo atual;
- bloqueia proposta obsoleta;
- valida cobertura completa antes da escrita;
- reutiliza artefatos sem rerender.

O manifesto oficial produzido registra a composição conforme a profundidade atingida.

Após `rv.approve()` criar autoridade oficial válida, o wrapper web confirma `is_chapter_merged()` e então remove Review transitório e `merge-attempt.json`.

---

## 9. Merge Manual

O Merge Manual **não é Auto-Merge VI**.

Ele é uma rota de resolução/finalização sobre o residual autoritativo do Review.

Fluxo:

```text
REVIEW / RESIDUAL AUTORITATIVO
          │
          ▼
     MERGE MANUAL
          │
     proposta + fingerprint
          │
     revalidação do estado
          │
     composição completa
          │
     STAGING validado
          │
          ▼
     MERGE OFICIAL
```

Regras comprovadas:
- revalida o estado atual do Review;
- revalida fontes/fingerprint;
- a proposta final precisa resolver todo o residual autoritativo;
- artefatos automáticos fora da faixa manual são preservados;
- peças manuais só podem ocupar a faixa selecionada;
- composição final precisa cobrir `0..total_height`;
- valida arquivos e geometria antes da promoção;
- usa staging;
- preserva pixels via cópia, sem rerender.

### Rollback

A efetivação possui rollback explícito:
- restaura manifesto original da proposta;
- restaura `merge-attempt.json`;
- remove novo MERGE se já promovido;
- restaura MERGE anterior a partir do backup;
- remove staging;
- propaga a exceção.

Portanto, a indicação `transactional_promotion=true` possui suporte concreto no comportamento observado.

---

## 10. Balanceamento

O Balanceamento está **depois do MERGE oficial**.

Ele não faz parte da cadeia Auto-Merge I–V.

```text
MERGE OFICIAL vN
      │
      ▼
BALANCEAMENTO
      │
      ├─ seleciona outputs contíguos
      ├─ gera/edita proposta
      ├─ revalida estado atual
      └─ substitui somente a região selecionada
      │
      ▼
MERGE OFICIAL vN+1
```

Entrada:
`02_MERGE/<capítulo>/merge-manifest.json`

A seleção:
- precisa conter pelo menos dois merges;
- precisa existir nos `outputs`;
- precisa ser contínua;
- determina faixa global exata.

### Stale detection

A efetivação revalida:
- se os arquivos selecionados ainda existem;
- se continuam contíguos;
- se os limites globais continuam iguais;
- se a região continua sem gap/overlap.

Até o ponto auditado, essa stale detection é **estrutural**, e não por SHA integral do manifesto oficial.

### Promoção

O Balanceamento:
- preserva outputs fora da região;
- substitui a região pelos artefatos balanceados;
- valida composição integral;
- monta staging;
- valida dimensões físicas;
- parte do manifesto oficial atual (`new_manifest = dict(manifest)`);
- atualiza `outputs` e `merged_images`;
- acrescenta uma entrada `source_stage=balance` em `composition`;
- move MERGE anterior para backup;
- promove staging;
- reabre o novo manifesto;
- atualiza `BALANCE_STATUS` para `EFETIVADO`;
- remove backup em sucesso;
- restaura backup em falha.

### Estado operacional

Fluxo atual:
`balance_status_v2`

Existe compatibilidade de leitura com:
`balance_status_v1`

O próprio código marca o produtor V1 como `LEGACY_CANDIDATE`, mantido temporariamente para remoção controlada durante o refactor.

### Parâmetros protegidos já observados no Balanceamento

- detector de balões: `conf=0.55`
- margem de proteção: `margin_px=16`

Esses valores entram no inventário de parâmetros calibrados/protegidos.

---

## 11. Gate oficial — `is_chapter_merged()`

Consumidores posteriores não precisam confiar apenas na existência de `02_MERGE`.

`is_chapter_merged()` valida:
- presença e leitura do `merge-manifest.json`;
- coerência entre `merged_images` e `outputs`;
- existência das páginas-fonte atuais;
- legibilidade das páginas-fonte;
- largura uniforme;
- altura total atual das fontes;
- igualdade com `source_total_height`;
- cobertura contínua dos outputs;
- ausência de gaps;
- intervalos positivos;
- largura declarada;
- altura declarada;
- existência e legibilidade de cada artefato;
- dimensões físicas de cada artefato;
- cobertura final integral.

Assim:

```text
merge-manifest.json
       +
IMG atual
       +
artefatos 02_MERGE
       │
       ▼
is_chapter_merged()
       │
       ▼
MERGE operacionalmente válido
```

Esse gate já foi identificado como pré-condição de:
- PDF_MERGE;
- Texto Off — Merged.

---

## 12. PDF_MERGE

Produtor atual:
`do_pdf_merge()` em `interface_web/processing_web.py`

Fluxo comprovado:

```text
MERGE OFICIAL
      │
      ├─ is_chapter_merged() == True
      └─ merge_artifact_files()
              │
              ▼
        gerador de PDF
              │
              ▼
03_PDF_MERGE/<capítulo>/<capítulo>.pdf
```

Se o PDF já existir, o fluxo retorna `skipped`.

### Lacuna de rastreabilidade identificada

Até este checkpoint:
- não foi identificado manifesto específico do PDF_MERGE;
- não foi identificado fingerprint/hash da versão do MERGE que originou o PDF;
- Balanceamento/Merge Manual/Review não apresentaram referência a `03_PDF_MERGE`;
- portanto, quando o MERGE oficial muda, um PDF já existente pode permanecer fisicamente presente;
- `do_pdf_merge()` não regenera automaticamente um PDF existente.

**Classificação atual:** lacuna de rastreabilidade/versionamento comprovada.  
**Ainda não classificada como defeito funcional**, pois falta verificar possíveis rotas explícitas de reset/regeneração na interface.

---

## 13. Texto Off — Merged

Mapeamento iniciado, ainda incompleto.

Entrada já comprovada:

```text
MERGE OFICIAL
      │
      ├─ is_chapter_merged()
      └─ merge_artifact_files()
              │
              ▼
          Cleaner V2
       source_stage="MERGE"
              │
              ▼
       diretório Texto Off
```

Próxima investigação pendente:
- estrutura do `clean-manifest.json`;
- identidade/proveniência dos arquivos de entrada;
- SHA/fingerprint;
- comportamento quando o MERGE oficial muda depois da limpeza;
- relação com tratamentos especiais/Níveis posteriores do Texto Off.

---

## 14. Parâmetros calibrados/protegidos

**Regra de refatoração:**
parâmetros de detecção, classificação, segurança, busca e geometria são comportamento funcional calibrado.

Não alterar, consolidar, “otimizar”, substituir defaults ou mudar relações entre parâmetros durante a refatoração arquitetural sem:
1. iniciativa funcional específica;
2. caracterização dedicada;
3. evidência comparativa;
4. validação funcional;
5. aprovação explícita.

### Nível I — `image_stitcher.py`

- `DEFAULT_TARGET_HEIGHT = 7000`
- `DEFAULT_SEARCH_BEFORE = 1800`
- `DEFAULT_SEARCH_AFTER = 2500`
- `DEFAULT_MIN_CHUNK_HEIGHT = 3000`
- `DEFAULT_MIN_WHITE_BAND = 150`
- `DEFAULT_MAX_CHUNK_HEIGHT = 12000`
- `DEFAULT_WHITE_RATIO = 0.985`
- `DEFAULT_LIGHT_THRESHOLD = 245`
- `DEFAULT_SAMPLE_WIDTH = 256`

### Nível II — `Level2Config`

- target/min/max herdados do Nível I
- `min_uniform_band = DEFAULT_MIN_WHITE_BAND`
- `uniform_max_channel_std = 4.0`
- `uniform_max_row_delta = 3.0`
- `preferred_source_files = 4`

### Nível III — `Level3Config`

- `analysis_half_window = 120`
- `cut_band_half_height = 8`
- `gaussian_kernel = 5`
- `canny_low = 50`
- `canny_high = 150`
- `morphology_kernel = 3`
- `uniform_std_max = 10.0`
- `safe_edge_density_max = 0.015`
- `min_component_area = 24`
- `min_component_height = 10`
- `hough_threshold = 18`
- `hough_min_line_length = 24`
- `hough_max_line_gap = 6`
- `diagonal_min_angle_deg = 18.0`
- `diagonal_max_angle_deg = 72.0`
- `local_search_radius = 200`
- `local_search_step = 2`
- `text_fx_max_cluster_area = 900`
- `text_fx_max_cluster_width = 90`
- `text_fx_max_cluster_height = 60`
- `text_fx_min_cluster_area = 8`
- `text_fx_min_clusters = 3`
- `text_fx_uniform_background_std_max = 18.0`
- `continuous_scene_max_height = 3000`

### Nível IV

- target `7000`
- min `3000`
- max `12000`
- coarse step `256`
- bin height `3000`
- seeds/bin `3`
- refine radius `128`
- refine step `8`

### Nível V

- target `7000`
- min `3000`
- max `12000`
- scan step `2`
- classifier workers `8`
- reutiliza `Level3Config` para classificação estrutural.

### Review

Também reutiliza parâmetros protegidos do V3 e possui política própria observada, incluindo:
- `DEFAULT_MIN_WHITE_BAND`;
- `DEFAULT_MAX_CHUNK_HEIGHT`;
- `REVIEW_MAX`;
- `EXTRA_LIMIT`;
- `max_source_images`;
- zona segura estendida;
- fallback uniforme restrito ao `MERGE_REVIEW`.

Os valores ainda não inventariados devem ser coletados antes de qualquer refatoração do Review.

---

## 15. Caracterização de testes já comprovada

### Nível II
Baseline dedicado existente e verde: **19/19** nos contratos auditados.

### Nível IV
Novo teste de caracterização:
`dev/tests/test_merge_level4_contract.py`

Resultado:
**8/8 OK**

Cobertura: caracterização algorítmica do Nível IV.  
Não deve ser descrita como proteção integral de toda a autoridade/integração do estágio.

### Nível V
Ainda falta caracterização dedicada.

---

## 16. Pontos arquiteturais para o refactor

### Não perder
- manifests intermediários;
- hashes de predecessor;
- residual autoritativo;
- validação de recomposição;
- fail-closed;
- fail-before-write;
- staging;
- rollback;
- preservação de pixels;
- parâmetros calibrados;
- rotas históricas ainda suportadas;
- compatibilidade de leitura enquanto houver artefatos legados.

### Direção arquitetural sugerida — ainda não implementada

Separar conceitualmente:

```text
MANIFESTOS / CONTRATOS
"Posso executar? Minha origem ainda é válida?"
        │
        ▼
STATE RESOLVER
"Em qual estação o capítulo está? Qual a próxima rota elegível?"
        │
        ▼
OBSERVABILITY JOURNAL
"O que aconteceu? Quando? Quanto durou? Por que mudou?"
```

Já existe embrião de observabilidade no runtime, com eventos de job/transição e inventário de manifests/SHA. A solução futura deve evoluir esse mecanismo, não criar uma segunda infraestrutura paralela sem necessidade.

---

## 17. Pendências do mapa

Ainda precisam ser mapeados antes da versão final:

- [ ] `clean-manifest.json` do Cleaner V2;
- [ ] Texto Off — Original;
- [ ] Texto Off — Merged;
- [ ] tratamentos especiais/Níveis posteriores do Texto Off;
- [ ] relação entre mudança do MERGE e Texto Off já existente;
- [ ] reset/regeneração do PDF_MERGE;
- [ ] Exportação e quais artefatos/autoridades ela consome;
- [ ] relação PDF/Texto Off/Balanceamento;
- [ ] manifests/status adicionais de Balanceamento que ainda sejam relevantes;
- [ ] catálogo final de produtores e consumidores;
- [ ] tabela final de autoridade, predecessor, SHA/fingerprint e stale detection;
- [ ] mapa visual consolidado;
- [ ] caracterização dedicada do Nível V.

---

## 18. Débitos/documentação observados — não corrigir durante o mapeamento

- mensagens antigas de Nível III/IV ainda podem mencionar Review diretamente apesar da rota atual incluir IV/V;
- docstring do Nível V está desatualizado em relação ao suporte atual a SAFE parcial;
- `_approve_scoped_level2_review()` possui nome histórico, embora hoje valide I–V + Review;
- `balance_status_v1` é explicitamente `LEGACY_CANDIDATE`;
- PDF_MERGE ainda não apresentou proveniência/versionamento em relação à versão do MERGE.

Esses itens devem ser classificados e tratados na fase adequada do refactor, não corrigidos incidentalmente durante a auditoria.

---

## 19. Próximo ponto de retomada

A auditoria parou exatamente antes de executar:

```bash
grep -Rni \
  --include='*.py' \
  -E 'clean-manifest\.json|source_stage|sha256|fingerprint|source_files|source.*hash|manifest' \
  processamento/limpeza_baloes/cleaner_v2 \
  | head -160
```

Objetivo da próxima etapa:
**mapear a proveniência `MERGE OFICIAL → Texto Off — Merged → clean-manifest.json` e verificar se uma mudança posterior do MERGE torna o resultado de Texto Off detectavelmente obsoleto.**
