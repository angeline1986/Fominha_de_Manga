# Fominha_de_Manga — Mapa de Proveniência, Manifestos e Autoridade dos Fluxos

**Data da auditoria:** 2026-09-25  
**Branch observada:** `develop`  
**Objetivo:** registrar as evidências levantadas sobre os fluxos que usam manifestos, suas fontes de verdade, validações, hashes, promoção oficial e dependências, para permitir continuidade da auditoria sem depender do histórico completo do chat.

---

## 1. Visão geral descoberta

O projeto possui vários fluxos com manifestos, mas eles **não possuem o mesmo nível de proteção de proveniência**.

A arquitetura observada pode ser resumida assim:

```text
IMG/<capítulo>
    │
    ├── Auto-Merge Nível I
    │      └── auto-merge-manifest.json
    │
    ├── Nível II
    │      └── merge-level2-manifest.json
    │
    ├── Nível III
    │      └── merge-level3-manifest.json
    │
    ├── Nível IV
    │      └── merge-level4-manifest.json
    │
    ├── Nível V
    │      └── merge-level5-manifest.json
    │
    └── Review scoped
           └── merge-review.json
                  │
                  ▼
           MERGE oficial
           merge-manifest.json
                  │
                  ├── PDF_MERGE
                  └── Texto Off — MERGED
                         │
                         └── clean-manifest.json
                                │
                                └── Nível III / Correção Assistida
                                       proposal.json
                                       + SHA-256
```

Há também fluxos paralelos de **Merge Manual** e **Balanceamento**, que também materializam/alteram `merge-manifest.json`.

---

# 2. MERGE oficial

## Arquivo central

```text
FLUXO_SECUNDARIO/02_MERGE/<capítulo>/merge-manifest.json
```

Funções relevantes encontradas em:

```text
processamento/unificacao_imagens/image_stitcher.py
```

### `merge_output_dir()`

Define o diretório oficial:

```text
<obra>/FLUXO_SECUNDARIO/02_MERGE/<capítulo>
```

### `merge_manifest_path()`

Aponta para:

```text
merge-manifest.json
```

### `is_chapter_merged()`

Faz validação física do MERGE oficial.

Valida:

- manifesto existente;
- `outputs`;
- quantidade de outputs;
- existência das páginas fonte em `IMG/<capítulo>`;
- largura uniforme das páginas fonte;
- altura total da fonte;
- `source_total_height` do manifesto;
- cobertura sequencial dos outputs;
- `global_start`;
- `global_end`;
- largura declarada;
- altura declarada;
- existência física dos artefatos;
- dimensões físicas dos artefatos;
- cobertura final igual à altura total da fonte.

A validação termina exigindo:

```text
expected_start == source_total_height
```

### Limitação observada

`is_chapter_merged()` valida **geometria e existência**, mas, pelo código analisado até aqui, não valida hash/fingerprint dos arquivos fonte contra o manifesto.

Portanto:

```text
MERGE oficial
= validado por estrutura + geometria + cobertura

não necessariamente
= validado por identidade criptográfica dos bytes da fonte
```

---

# 3. Composição Auto-Merge + Níveis II–V + Review

Arquivo principal analisado:

```text
processamento/unificacao_imagens/image_stitcher_review.py
```

Função:

```python
_approve_scoped_level2_review(...)
```

Essa função é responsável pela composição final de um Review scoped.

## Cadeia de autoridade

A lógica encontrada estabelece uma cadeia:

```text
Level II pending
      ↓
Level III safe + residual
      ↓
Level IV safe + residual
      ↓
Level V safe + residual
      ↓
Review scoped
```

A fila de Review deve representar o **residual pendente autoritativo atual**.

---

## Level III

Quando existe manifesto Level III:

```text
merge-level3-manifest.json
```

são validados:

- algoritmo:
  `merge_level3_structural_safe_v1`
- `total_height`
- igualdade do `total_height` com Level II;
- `source_level2_sha256`;
- SHA-256 do `merge-level2-manifest.json` atual.

Depois são separados:

```text
safe_artifacts
residual_pending_segments
```

A função verifica que:

```text
safe + residual
```

recompõem exatamente todos os `pending_segments` do Level II.

Isso evita:

- GAP;
- OVERLAP;
- cobertura incompleta;
- intervalo fora do pai.

Depois disso:

```text
authoritative_pending = residual_pending_segments
```

Se não houver residual:

```text
Review scoped não deve ser aprovado.
```

---

## Level IV

Se existe:

```text
merge-level4-manifest.json
```

são aceitos os algoritmos:

```text
merge_level4_directed_structural_safe_v1
merge_level4_global_structural_safe_v1
```

São validados:

- `total_height`;
- correspondência com Level III;
- `source_level3_sha256`;
- SHA-256 do manifesto Level III atual.

Também é exigido que:

```text
safe_artifacts + residual_pending_segments
```

recomponham exatamente o residual do Level III.

A autoridade passa então para:

```text
authoritative_pending = level4_residual_intervals
```

Se houver residual no Level IV dirigido e ainda não existir Level V:

```text
Level IV dirigido possui residual,
mas o Auto-Merge Nível V ainda não foi executado.
```

---

## Level V

Se existe:

```text
merge-level5-manifest.json
```

a implementação aceita somente:

```text
merge_level5_global_structural_safe_v1
```

e exige que o Level IV seja:

```text
merge_level4_directed_structural_safe_v1
```

São validados:

- `total_height`;
- `source_level4_sha256`;
- SHA-256 do manifesto Level IV atual;
- recomposição exata do residual do Level IV.

Depois:

```text
authoritative_pending = level5_residual_intervals
```

Se não houver residual:

```text
Review scoped não deve ser aprovado.
```

---

# 4. Review scoped

O Review deve possuir:

```text
scope.type = "pending_segments"
```

E:

```text
scope.intervals
```

deve ser exatamente igual ao pending autoritativo atual.

Além disso:

```text
regions
```

também precisa representar exatamente os mesmos intervalos.

Portanto existem duas verificações:

```text
scope.intervals == authoritative_pending
regions == authoritative_pending
```

Isso impede aprovar uma proposta de Review criada para um estado anterior do pipeline.

---

# 5. Composição final do Review

A composição final reúne:

```text
Auto-Merge Level I
+
Level II resolved artifacts
+
Level III safe artifacts
+
Level IV safe artifacts
+
Level V safe artifacts
+
Review regions
```

Os artefatos são ordenados por intervalo global.

Antes de qualquer escrita oficial ocorre validação completa:

- intervalo válido;
- GAP;
- OVERLAP;
- arquivo existente;
- imagem legível;
- altura física compatível;
- largura uniforme;
- cobertura total;
- `expected_start == total_height`.

É um fluxo **fail-before-write** para a validação dos artefatos.

Depois cria:

```text
FLUXO_SECUNDARIO/02_MERGE/<capítulo>
```

e grava:

```text
merge-manifest.json
```

O manifesto registra, entre outros:

```text
algorithm
status
approved_at
source_dir
output_dir
source_width
source_total_height
merged_images
outputs
validation
safety
composition
scope
```

A composição também registra quais manifestos participaram:

```text
auto_merge_manifest
level2_manifest
level3_manifest
level4_manifest
level5_manifest
review_manifest
scope
```

---

# 6. Merge Manual

Arquivo:

```text
processamento/merge_manual/finalizer.py
```

Função principal:

```python
apply_final_composition(...)
```

Também usa:

```text
FLUXO_SECUNDARIO/02_MERGE/<capítulo>/merge-manifest.json
```

## Proteções observadas

A proposta manual possui:

```text
proposal_id
chapter
status
```

Existe idempotência:

```text
status == EFETIVADO
+
official merge válido
+
manual_proposal_id correspondente
```

Nesse caso a operação não é reaplicada.

Antes da promoção são validados:

- proposta atual;
- fontes;
- geometria;
- largura;
- altura;
- peças automáticas;
- peças manuais;
- pending;
- cobertura.

A composição é escrita em staging.

Depois:

```text
official → backup
staging → official
```

E ocorre validação por:

```python
v3.is_chapter_merged(chapter_dir)
```

Há rollback integral em caso de erro.

## Observação importante

O `merge-manifest.json` oficial recebe informação da proposta manual, mas a proteção observada é principalmente:

```text
proposal_id
+
estado atual
+
validação estrutural
+
rollback
```

Não foi encontrada, nessa parte analisada, uma cadeia SHA-256 equivalente à existente no Texto Off Nível III.

---

# 7. Balanceamento

Arquivos:

```text
processamento/balanceamento/balanceador.py
processamento/balanceamento/balanceamento.py
```

O Balanceamento trabalha sobre:

```text
FLUXO_SECUNDARIO/02_MERGE/<capítulo>/merge-manifest.json
```

e mantém estado separado:

```text
FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/BALANCE_STATUS/<capítulo>/balance-status.json
```

Propostas:

```text
FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/BALANCE_PROPOSALS/
```

Editor:

```text
FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/BALANCE_EDITOR/
```

## `balance-status_v2`

O fluxo atual utiliza:

```text
schema = balance_status_v2
```

com:

```text
status
proposal_id
editor_manifest
proposal_manifest
updated_at
```

## Efetivação

Função:

```python
effect_manual_balance(...)
```

Foi observado que existem verificações de obsolescência:

```text
Proposta obsoleta:
o MERGE oficial mudou desde a geração da proposta.
```

Também:

```text
os merges originais não são mais contíguos
```

e:

```text
a cobertura oficial da região foi alterada
```

Isso demonstra que o Balanceamento possui proteção explícita contra alteração do MERGE entre geração e efetivação.

### Ponto ainda não fechado

O grep mostrou referências a:

```text
fingerprint
sha256
hash
source_manifest
```

mas não foi encontrada, nos trechos fornecidos, a implementação completa da identidade usada para determinar que o MERGE mudou.

Esse ponto precisa ser auditado antes de concluir que a proteção é criptográfica.

---

# 8. PDF_MERGE

`PDF_MERGE` não apareceu como consumidor de manifesto próprio dentro de:

```text
processamento/balanceamento
processamento/merge_manual
processamento/unificacao_imagens
```

O fluxo web está em:

```text
interface_web/processing_web.py
```

Função:

```python
do_pdf_merge(...)
```

Fluxo:

```text
is_chapter_merged(chapter)
        ↓
merge_artifact_files(merge_output_dir(chapter))
        ↓
gerador de PDF
        ↓
FLUXO_SECUNDARIO/03_PDF_MERGE/<capítulo>/<capítulo>.pdf
```

A validação de entrada é o MERGE oficial.

Não foi identificada, nos trechos analisados, uma validação do PDF contra uma versão/hash específica do `merge-manifest.json`.

Também não foi encontrado manifesto próprio de PDF nesse levantamento.

---

# 9. Texto Off — Cleaner V2

Arquivo:

```text
processamento/limpeza_baloes/cleaner_v2/integration.py
```

Manifesto:

```text
clean-manifest.json
```

O manifesto contém:

```text
schema_version = 3
algorithm = cleaner_v2_panel_cleaner_2_11_11
engine
engine_version
profile
offline
source_stage
source_immutable
pages_total
outputs_total
masks_total
mask_complete
integrity_ok
source_artifacts
clean_artifacts
mask_artifacts
level1
level2
failures
```

## Proveniência

O manifesto registra:

```text
source_artifacts
clean_artifacts
mask_artifacts
```

e afirma:

```text
source_immutable = True
```

Porém, nos trechos analisados, **não há SHA-256 das imagens fonte no `clean-manifest.json`**.

Portanto:

```text
source_immutable = True
```

é uma declaração de propriedade do fluxo, não uma prova criptográfica de identidade dos bytes.

---

# 10. Texto Off — Comparar resultados

Arquivo:

```text
processamento/limpeza_baloes/textoff_compare.py
```

O módulo é explicitamente somente leitura.

Ele aceita um `clean-manifest.json` quando:

```text
algorithm == cleaner_v2_panel_cleaner_2_11_11
integrity_ok == True
source_stage compatível
source_artifacts e clean_artifacts existem
```

Depois monta pares:

```text
source_file ↔ clean_file
```

e verifica a existência física do clean.

Também associa o estado do Nível III por:

```text
STAGE:source_file
```

## Limitação

O Comparar Resultados **não calcula SHA-256**.

Também não verifica se a fonte atual possui exatamente os mesmos bytes que existiam quando o Cleaner V2 produziu o resultado.

Logo:

```text
Comparar Resultados
= leitura/validação do manifesto + existência dos arquivos

não
= validação criptográfica de proveniência
```

---

# 11. Texto Off — Nível III / Correção Assistida

Arquivos:

```text
processamento/limpeza_baloes/textoff_level3.py
processamento/limpeza_baloes/textoff_level3_correction.py
```

## Validação do par

`textoff_level3.py` e `textoff_level3_correction.py` verificam:

```text
clean-manifest.json
source_artifacts
clean_artifacts
```

e exigem que:

```text
(source_file, clean_file)
```

pertença ao mapeamento registrado no manifesto.

Isso impede selecionar arbitrariamente um arquivo fora do resultado atual do Cleaner.

---

# 12. Nível III — proteção criptográfica

`textoff_level3_correction.py` possui:

```python
_sha256(path)
```

Na geração da proposta são calculados:

```text
base_sha256 = SHA(clean atual)
source_sha256 = SHA(source atual)
```

O `proposal.json` registra esses valores.

Na aprovação:

1. o par atual é novamente validado;
2. o `clean_path` atual é comparado com `base_sha256`;
3. o `source_path` atual é comparado com `source_sha256`;
4. a imagem de preview recebe SHA;
5. antes da promoção os arquivos são revalidados;
6. após a promoção o resultado é novamente conferido;
7. há rollback por backup se ocorrer falha.

Essa é a primeira fronteira claramente observada em que existe:

```text
geração
   ↓
SHA do estado
   ↓
aprovação
   ↓
SHA do estado atual
   ↓
promoção
```

---

# 13. Texto Off — Gradient Patch

Arquivo:

```text
processamento/limpeza_baloes/textoff_gradient_patch.py
```

A função analisada:

```python
generate_gradient_preview(...)
```

usa:

```text
pending_for_chapter()
_validate_current_pair()
_mask_for()
```

`_mask_for()` consulta:

```text
clean-manifest.json
```

e exige o mapeamento completo:

```text
source_artifacts
clean_artifacts
mask_artifacts
```

O par:

```text
source_file + clean_file
```

precisa existir no manifesto.

A máscara correspondente também precisa existir dentro do diretório permitido.

## Observação

Nos trechos analisados, o Gradient Patch **herda a validação do par do Cleaner V2**, mas não foi identificada uma camada SHA própria nessa rota.

Portanto, sua proteção de proveniência é:

```text
manifesto + mapeamento source/clean/mask
+
validação atual do par
```

e não, pelo que foi observado até aqui:

```text
SHA da fonte/clean/mask
```

---

# 14. Estado atual das fronteiras de proveniência

| Fluxo | Manifesto | Valida estrutura | Valida estado atual | SHA explícito |
|---|---|---:|---:|---:|
| Auto-Merge I | `auto-merge-manifest.json` | Sim | Parcial | Não identificado |
| Level II | `merge-level2-manifest.json` | Sim | Sim, por cadeia | SHA consumido pelos níveis seguintes |
| Level III | `merge-level3-manifest.json` | Sim | Sim | **Sim: SHA do Level II** |
| Level IV | `merge-level4-manifest.json` | Sim | Sim | **Sim: SHA do Level III** |
| Level V | `merge-level5-manifest.json` | Sim | Sim | **Sim: SHA do Level IV** |
| Review scoped | `merge-review.json` | Sim | Sim | Via cadeia de manifestos |
| MERGE oficial | `merge-manifest.json` | **Sim** | **Sim, estruturalmente** | Não identificado |
| Merge Manual | `merge-manifest.json` + proposta | Sim | Sim | Não identificado como SHA |
| Balanceamento | `balance-status_v2` + proposta | Sim | **Sim / obsolescência** | mecanismo exato ainda não fechado |
| PDF_MERGE | PDF | entrada exige MERGE válido | Parcial | Não identificado |
| Cleaner V2 | `clean-manifest.json` | Sim | Parcial | Não |
| Comparar Resultados | `clean-manifest.json` | Sim | Parcial | Não |
| Correção Assistida Nível III | `proposal.json` | Sim | **Sim** | **Sim** |
| Gradient Patch | `clean-manifest.json` | Sim | Sim, via par | Não identificado |

---

# 15. Pontos de atenção para a próxima etapa

## A. MERGE → Texto Off

Esta é a principal lacuna de proveniência observada.

Hoje o Cleaner recebe os arquivos do MERGE e registra seus nomes:

```text
source_artifacts
```

mas não foi observado fingerprint do conteúdo do MERGE no `clean-manifest.json`.

Isso significa que precisamos distinguir:

```text
"este é o mesmo nome de arquivo"
```

de:

```text
"este é exatamente o mesmo artefato que foi processado"
```

---

## B. PDF_MERGE

Ainda precisa ser definido se o PDF deve possuir:

```text
source_merge_manifest_sha256
```

ou outra forma de vinculação ao MERGE oficial.

---

## C. Balanceamento

Ainda precisa ser identificado exatamente como `effect_manual_balance()` determina:

```text
"O MERGE oficial mudou"
```

e se isso é baseado em:

- hash;
- fingerprint;
- manifesto;
- geometria;
- combinação desses mecanismos.

---

## D. `clean-manifest.json`

Possível evolução futura:

```text
source_artifacts
+
source_artifacts_sha256
+
source_manifest_sha256
+
source_total_height
+
source_width
```

Mas isso é **apenas ponto de investigação/proposta**, não decisão de implementação.

---

## E. Regra arquitetural que emerge

Os fluxos já possuem uma noção forte de:

```text
manifesto
→ dependência
→ validação
→ promoção
```

mas a profundidade varia.

O padrão mais robusto encontrado até agora é o da Correção Assistida Nível III:

```text
manifesto
+
estado atual
+
SHA
+
staging
+
promoção
+
validação pós-promoção
+
rollback
```

Esse padrão pode servir como referência arquitetural para avaliar os demais fluxos, **sem assumir que todos devam ser alterados para ficar iguais**.

---

# 16. Próxima auditoria recomendada

Antes de qualquer alteração de código, fechar três pontos:

1. **Balanceamento:** localizar a implementação exata da detecção de MERGE obsoleto.
2. **PDF_MERGE:** verificar se existe algum mecanismo de identificação/versionamento do MERGE usado para gerar o PDF.
3. **MERGE → Cleaner V2:** verificar onde seria possível estabelecer identidade do MERGE processado sem acoplar indevidamente o Cleaner à implementação interna do Merge.

Depois disso será possível montar o mapa definitivo:

```text
FONTE
  ↓
MANIFESTO
  ↓
ARTEFATO
  ↓
CONSUMIDOR
  ↓
VALIDAÇÃO
  ↓
PROMOÇÃO
  ↓
PRÓXIMO MANIFESTO
```

**Importante:** este documento registra somente o que foi evidenciado nos trechos fornecidos durante a auditoria. Itens marcados como "não identificado" ainda não significam que não existam no restante do repositório.
