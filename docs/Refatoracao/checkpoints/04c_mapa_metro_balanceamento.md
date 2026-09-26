# Mapa do Metrô — Checkpoint: Balanceamento

**Projeto:** Fominha_de_Manga  
**Baseline de auditoria:** `develop` / `c6adae7e`  
**Data:** 2026-09-25  
**Status:** evidência consolidada — nenhuma alteração funcional proposta ou aplicada

---

## 1. Objetivo deste checkpoint

Registrar o contrato observado do fluxo de Balanceamento, com foco em:

- relação com o `MERGE` oficial;
- persistência do editor e da proposta;
- detecção de proposta obsoleta;
- validações antes da efetivação;
- promoção transacional;
- atualização do `merge-manifest.json`;
- limites atuais de proveniência.

Este documento descreve o comportamento comprovado na auditoria. Pontos de atenção arquitetural não devem ser interpretados automaticamente como bugs.

---

## 2. Posição no mapa

O Balanceamento não funciona como um novo nível de Auto-Merge. Ele atua **depois que existe um MERGE oficial** e pode substituir parte da composição oficial por uma composição balanceada.

```text
MERGE oficial vN
    │
    ├─ preparar editor manual
    │      └─ balance-editor.json
    │
    ├─ gerar proposta
    │      └─ balance-proposal-manifest.json
    │
    ├─ validar proposta contra MERGE atual
    │
    └─ efetivar
           ├─ staging
           ├─ validação
           ├─ backup
           ├─ promoção
           └─ rollback em falha
                    │
                    ▼
              MERGE oficial vN+1
```

A autoridade compartilhada após a efetivação continua sendo o `merge-manifest.json` do diretório oficial de MERGE.

---

## 3. Editor manual

`prepare_manual_balance()` valida a seleção atual e persiste `balance-editor.json` com schema:

`balance_manual_editor_v1`

O editor registra, entre outros dados:

- `proposal_id`;
- capítulo;
- `selected_files`;
- região `global_start/global_end`;
- `source_slices`;
- preview da região;
- cortes correspondentes às fronteiras atuais do MERGE;
- flags de segurança indicando que o MERGE final e os arquivos-fonte ainda não foram alterados.

### Vínculo com a origem

O vínculo observado com o MERGE é **estrutural**:

- nomes dos arquivos selecionados;
- posição/cobertura global;
- slices utilizados na região.

Não foi identificado no payload do editor:

- SHA-256 dos outputs selecionados;
- fingerprint do conteúdo;
- hash do `merge-manifest.json`;
- identificador criptográfico da versão do MERGE.

---

## 4. Proposta manual

A proposta persistida usa schema:

`balance_manual_result_v1`

Ela registra:

- `proposal_id`;
- capítulo;
- `selected_files`;
- região;
- `source_slices`;
- cortes definidos pelo usuário;
- artefatos produzidos;
- `global_start/global_end/height` dos artefatos;
- informações de segurança.

`_persist_generated_proposal()` grava esse payload diretamente em:

`balance-proposal-manifest.json`

Antes da promoção da proposta para seu diretório definitivo, o código valida:

- conjunto exato de arquivos no staging;
- existência dos artefatos;
- altura física de cada artefato;
- cobertura inicial/final da região;
- ausência de gap/overlap.

A persistência possui mecanismo de backup/recuperação do diretório de proposta.

### Proveniência da proposta

Também não foi identificada, nessa etapa, inclusão posterior de SHA/fingerprint do MERGE de origem. Portanto, a proposta permanece vinculada ao MERGE por identidade nominal e geometria.

---

## 5. Estado operacional

A efetivação exige `balance-status.json` compatível com:

- schema `balance_status_v2`;
- status `PROPOSTA_GERADA`;
- `proposal_id` consistente com a proposta persistida;
- referência válida ao manifesto da proposta.

Esse status é operacional ao fluxo de Balanceamento. A autoridade compartilhada final continua sendo o `merge-manifest.json`.

---

## 6. Detecção de proposta obsoleta

Antes de efetivar, o fluxo revalida a proposta contra os outputs do MERGE oficial atual.

São verificadas as seguintes condições:

1. todos os `selected_files` ainda existem nos outputs atuais;
2. os arquivos selecionados continuam contíguos;
3. o primeiro `global_start` continua igual ao início da região da proposta;
4. o último `global_end` continua igual ao fim da região da proposta;
5. os outputs selecionados não possuem gap ou overlap.

Se essas condições falharem, a proposta é considerada obsoleta ou incompatível.

### Classificação

**Stale detection estrutural.**

A proteção observada detecta alterações em nomes, ordem, contiguidade e cobertura da região.

Não foi identificada comparação por SHA/fingerprint dos bytes dos outputs nem da versão do `merge-manifest.json`.

Consequentemente, duas versões diferentes do MERGE que mantenham os mesmos nomes e intervalos podem ser indistinguíveis para essa checagem estrutural.

Isso deve ser registrado como **ponto de atenção de proveniência**, e não como bug comprovado.

---

## 7. Efetivação

A efetivação constrói uma composição candidata combinando:

- outputs oficiais preservados fora da região;
- artefatos da proposta dentro da região balanceada.

Antes da promoção, o staging é validado fisicamente.

Para cada output candidato:

- o arquivo deve existir;
- a largura deve coincidir com a largura esperada da origem;
- a altura física deve coincidir com `global_end - global_start`;
- a cobertura deve ser contínua;
- a cobertura final deve alcançar `total_height`.

A promoção só ocorre depois dessas validações.

---

## 8. Promoção transacional e rollback

A promoção utiliza staging e backup:

```text
MERGE atual
   │
   ├─ candidato montado em staging
   ├─ candidato validado
   │
   ├─ MERGE atual → backup
   ├─ staging → MERGE oficial
   │
   ├─ validação pós-promoção
   │
   ├─ sucesso → remove backup
   │
   └─ falha → remove candidato e restaura backup
```

Após a promoção, o manifesto promovido é relido e a quantidade de outputs é comparada com a composição candidata.

Falhas durante essa etapa restauram o MERGE anterior.

---

## 9. Atualização do `merge-manifest.json`

O Balanceamento não cria uma autoridade final paralela.

Ele parte do manifesto oficial vigente:

`new_manifest = dict(manifest)`

e atualiza:

- `outputs`;
- `merged_images`;
- `validation`.

A validação final registra novamente cobertura completa e `ok: true`.

O histórico de composição recebe uma nova entrada com:

- `source_stage: "balance"`;
- `proposal_id`;
- `global_start`;
- `global_end`;
- `replaced_files`;
- artefatos produzidos;
- `effected_at`.

Portanto, o novo MERGE registra explicitamente que sua composição passou pelo Balanceamento.

---

## 10. Proveniência — conclusão comprovada

A cadeia observada é:

```text
MERGE oficial
    │
    │ vínculo nominal + geométrico
    ▼
balance-editor.json
    │
    │ selected_files + região + source_slices
    ▼
balance-proposal-manifest.json
    │
    │ selected_files + região + novos cortes + artefatos
    ▼
revalidação estrutural
    │
    ▼
promoção transacional
    │
    ▼
MERGE oficial atualizado
    └─ composition += source_stage: balance
```

### Proteções existentes

- validação da seleção;
- contiguidade;
- cobertura global;
- validação física dos artefatos;
- validação de dimensões;
- staging;
- backup;
- rollback;
- rastreabilidade da intervenção na `composition`.

### Limite identificado

Não foi identificada uma identidade criptográfica que conecte:

`MERGE de origem → editor → proposta → efetivação`.

Assim, a rastreabilidade operacional é forte, mas a versão exata do MERGE de origem não fica criptograficamente congelada na proposta.

---

## 11. Ponto de atenção arquitetural

**Classificação:** proveniência/versionamento.

Uma possível evolução futura seria persistir na criação do editor/proposta uma identidade inequívoca do MERGE de origem, por exemplo um fingerprint derivado do manifesto e/ou dos outputs relevantes, e revalidá-la antes da efetivação.

Essa é apenas uma recomendação arquitetural para avaliação posterior.

**Não alterar durante a refatoração arquitetural sem iniciativa funcional específica, evidência comparativa e aprovação.**

---

## 12. Status para o Mapa do Metrô

**Balanceamento: mapeado para esta etapa.**

Contrato atual documentado:

`MERGE → Editor → Proposta → stale estrutural → staging/validação → promoção/rollback → novo MERGE`

O resultado deste checkpoint deve ser incorporado posteriormente ao documento canônico:

`docs/Refatoracao/mapa_metro_fluxos_manifestos.md`
