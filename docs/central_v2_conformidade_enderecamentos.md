# Levantamento de conformidade dos endereçamentos da Central v2

**Escopo:** levantamento estático do backend da Central v2 e dos testes relacionados, em 30/09/2026. Este documento registra os pontos encontrados e a direção recomendada; não altera a implementação.

## Conclusão

Os endereçamentos estão **parcialmente centralizados**. O fluxo TextOff Merged já possui constantes para os diretórios dos níveis e uma função comum para resolver o caminho de um estágio. Porém, a raiz `FLUXO_SECUNDARIO/04_TEXTO_OFF`, alguns diretórios legados e várias pastas de outros fluxos continuam escritos diretamente nos módulos consumidores.

Por isso, renomear uma pasta hoje pode exigir alterações em mais de um módulo e precisa considerar resultados já gravados. A Central v2 ainda não tem um único contrato de layout que descreva os diretórios de entrada, processamento e saída de todos os fluxos.

## Inventário dos pontos a alinhar

### 1. TextOff Merged: consolidar a resolução das raízes e estágios

[stages.py](../central_v2/backend/orchestration/textoff_merged/stages.py#L4) define `LEVEL1`, `LEVEL2`, `LEVEL3`, `CONSOLIDATED`, aliases legados e `stage_root()`/`stage_chapter()`. É a melhor base existente, mas a raiz `FLUXO_SECUNDARIO/04_TEXTO_OFF` aparece diretamente dentro dessas funções e não é compartilhada pelos demais consumidores.

Pontos que ainda contêm endereçamento ou nomes de diretório fora desse contrato:

- [manifests.py](../central_v2/backend/orchestration/textoff_merged/manifests.py#L10): `_clean_manifest()` monta diretamente o caminho `04_TEXTO_OFF/MERGED/<capítulo>`; `_manifest_matches_merge()` e outras funções também montam `IMG/<capítulo>`.
- [execution.py](../central_v2/backend/orchestration/textoff_merged/execution.py#L8): seleciona `IMG` diretamente; aceita os destinos `MERGED`, `LEVEL1` e o alias literal `MERGED_NIVEL_I`.
- [consolidated_artifacts.py](../central_v2/backend/orchestration/textoff_merged/consolidated_artifacts.py#L12): usa o nome literal `TO_MERGED_CONSOLIDADO` em vez da constante `CONSOLIDATED`.
- [consolidated.py](../central_v2/backend/orchestration/textoff_merged/consolidated.py#L86): mistura o identificador canônico `LEVEL1` com o nome físico/legado `MERGED_NIVEL_I` ao validar `source_stage` do manifesto.
- [query.py](../central_v2/backend/orchestration/textoff_merged/query.py#L1), [level2.py](../central_v2/backend/orchestration/textoff_merged/level2.py#L1) e [level3_styled.py](../central_v2/backend/orchestration/textoff_merged/level3_styled.py#L1): acessam a raiz de entrada `IMG` diretamente; devem usar a resolução comum para as raízes de dados, embora não precisem conhecer caminhos de saída do TextOff.
- [textoff_special/inputs.py](../central_v2/backend/orchestration/textoff_special/inputs.py#L9): aceita os valores `MERGED_NIVEL_I` e `MERGED_NIVEL_II` como nomes de nível e os passa para `stage_chapter()`. Esses valores funcionam como identificadores de entrada/API e devem ser normalizados em um só lugar, sem confundi-los com diretórios físicos.
- [special_levels.py](../central_v2/backend/orchestration/textoff_merged/special_levels.py#L69) e [manual_specials.py](../central_v2/backend/orchestration/textoff_merged/manual_specials.py#L45): gravam `MERGED_NIVEL_I` nos payloads de tratamento. Esse valor precisa continuar reconhecido como contrato persistido ou ser migrado explicitamente; não deve ser renomeado junto com uma pasta sem avaliar compatibilidade.

### 2. Outros fluxos da Central v2: remover caminhos montados em rotas

Há outras áreas do backend com caminhos de armazenamento escritos diretamente nas rotas:

- [routes/merge_manual.py](../central_v2/backend/routes/merge_manual.py#L18) monta `FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/MERGE_LEVEL5` e `MERGE_LEVEL4`, além de acessar `IMG` em outros pontos do arquivo.
- [routes/balanceamento_media.py](../central_v2/backend/routes/balanceamento_media.py#L32) monta `FLUXO_SECUNDARIO/02_MERGE` e a raiz `FLUXO_SECUNDARIO`; também resolve caminhos relativos de manifests de status dentro dessa raiz.
- [routes/auto_merge/folder.py](../central_v2/backend/routes/auto_merge/folder.py#L29) monta `FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/<estágio>` para abrir uma pasta de resultado.
- [state/manga_state.py](../central_v2/backend/state/manga_state.py#L41), [state/catalog.py](../central_v2/backend/state/catalog.py#L22), [routes/merge_manual.py](../central_v2/backend/routes/merge_manual.py#L60) e a orquestração TextOff acessam `IMG` diretamente. Essa raiz comum deve ter um resolvedor único.

Esses módulos devem receber caminhos resolvidos por uma camada de layout/paths ou por helpers coesos do fluxo. Rotas devem validar a solicitação e chamar o domínio; não devem definir a árvore física de armazenamento.

### 3. Nomes legados e contratos persistidos

Existem três conceitos que hoje usam strings parecidas e precisam ser separados:

1. **Identificador lógico do estágio**, usado pelo código e por `source_stage` em manifestos.
2. **Nome físico da pasta**, como `TO_MERGED_NIVEL_I`.
3. **Alias legado**, como `MERGED_NIVEL_I`, que pode identificar uma pasta antiga ou aparecer em resultados e payloads já persistidos.

[stages.py](../central_v2/backend/orchestration/textoff_merged/stages.py#L9) já faz leitura de diretórios legados dos níveis I–III quando o diretório canônico não existe. Essa compatibilidade não cobre o estágio consolidado e não resolve o diretório `MERGED` usado pelo fluxo anterior em `manifests.py` e `execution.py`.

Antes de renomear qualquer pasta, definir: qual nome passa a ser canônico; por quanto tempo o alias será lido; se haverá migração ou leitura dupla; e como os manifestos antigos continuarão sendo validados. Não gravar novos resultados com aliases legados depois de fixar o nome canônico.

### 4. Testes e fixtures

Os testes montam as mesmas árvores físicas diretamente, em especial:

- [test_textoff_consolidated.py](../dev/tests/test_textoff_consolidated.py#L20) e [test_central_v2_textoff_merged.py](../dev/tests/test_central_v2_textoff_merged.py#L49): diretórios TextOff e manifestos consolidados.
- [test_textoff_special_inputs.py](../dev/tests/test_textoff_special_inputs.py#L15) e [test_textoff_special_execution.py](../dev/tests/test_textoff_special_execution.py#L17): nomes legados de níveis e diretórios especiais.
- [test_central_v2_merge_manual.py](../dev/tests/test_central_v2_merge_manual.py#L20), testes `test_central_v2_auto_merge_*` e `test_central_v2_balanceamento.py`: árvore de processamento e MERGE oficial.

As fixtures devem construir diretórios com as constantes/helpers de layout, para que uma mudança de nome não exija correções repetitivas. Manter testes de contrato específicos que afirmem os caminhos públicos/canônicos e a leitura dos aliases legados; não converter todo teste em validação tautológica do próprio helper.

### 5. Documentação

Os nomes físicos e exemplos de caminhos aparecem em [README.md](../README.md#L305), [runtime/textoff/README.md](../central_v2/runtime/textoff/README.md#L1), [textoff_merged_transparencia.html](textoff_merged_transparencia.html) e [central_v2_menus.html](central_v2_menus.html). A documentação deve distinguir claramente nome de menu, identificador lógico, pasta gravada e compatibilidade legada. Caminhos devem refletir o contrato único e ser atualizados junto com qualquer migração.

## Direção recomendada

Criar um módulo de paths da Central v2 com responsabilidades explícitas, sem dependência da Central v1, que exponha:

- raiz da obra e raízes comuns (`IMG`, `FLUXO_SECUNDARIO`);
- diretórios do fluxo de processamento, MERGE oficial e TextOff;
- enumeração/registro de estágios com identificador lógico, nome canônico e aliases de leitura;
- resolvers de pasta e capítulo, com validação de nomes e opção explícita para leitura legada;
- resolução de referências de artefatos relativas ao capítulo, mantendo as verificações de traversal e hash já existentes.

Os módulos de domínio devem consumir esse contrato. A camada de rotas não deve montar strings de diretório. As constantes de nome lógico devem ficar separadas das constantes de diretório, mesmo quando seus textos coincidirem.

## De/para para retomar a implementação

O estado desta seção é a referência para uma futura sessão. O de/para descreve a direção desejada; não afirma que a refatoração já foi feita.

| Responsabilidade | Antes (estado encontrado) | Depois (alvo) |
|---|---|---|
| Raiz de imagens da obra | Cada consumidor concatena `manga / "IMG"` | `layout.manga_images(manga)` ou propriedade equivalente |
| Raiz dos artefatos secundários | Consumidores repetem `manga / "FLUXO_SECUNDARIO"` | `layout.secondary_root(manga)` |
| MERGE oficial | Consumidores repetem `manga / "FLUXO_SECUNDARIO/02_MERGE" / chapter` | `layout.merge_chapter(manga, chapter)` |
| Processamento Auto Merge | Rotas compõem `FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/<estágio>` | `layout.processing_stage(manga, stage_id)`; capítulo resolvido por helper validado |
| TextOff Merged | `stages.py` centraliza parte dos nomes, mas contém a raiz literal e outros módulos ainda montam caminhos próprios | Registro de estágios canônicos + `layout.textoff_stage(manga, stage_id)` e `layout.stage_chapter(...)` |
| Consolidado TextOff | `consolidated_artifacts.py` repete `"TO_MERGED_CONSOLIDADO"` | Usa `CONSOLIDATED`/identificador registrado; nenhum consumidor sabe o nome físico |
| TextOff anterior (`MERGED`) | `manifests.py` e `execution.py` tratam o nome diretamente | Estágio legado explicitamente registrado, somente leitura onde compatível; novas escritas apontam para destino canônico escolhido |
| Nomes legados de nível | `MERGED_NIVEL_I/II/III` aparecem misturados a nomes de saída e valores de manifesto | Alias de leitura/normalização centralizado e separado do identificador lógico e do diretório canônico |
| Arquivos dentro de capítulo | `clean`, `mask`, `json` já têm constantes em `artifact_paths.py`, mas alguns consumidores podem formar referências manualmente | Todos usam `artifact_ref`, `artifact_file` e `json_file`; manter rejeição de traversal e validação de hash |
| Testes | Fixtures repetem caminhos absolutos relativos da árvore de dados | Fixtures usam o layout compartilhado; testes de contrato mantêm asserções explícitas dos caminhos públicos |

### Antes: composição do caminho em cada consumidor

Exemplos representativos do padrão atual (não copiar como recomendação):

```python
# stages.py: a raiz da Central ainda está embutida no helper de estágio
current = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / canonical

# manifests.py: o leitor do MERGED anterior escolhe a pasta por conta própria
path = manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / "MERGED" / chapter / "clean-manifest.json"

# consolidated_artifacts.py: uma constante existente é ignorada
folder = stage_chapter(manga, "TO_MERGED_CONSOLIDADO", chapter, read_legacy=False)

# routes/balanceamento_media.py: a rota monta o caminho de dados
folder = manga / "FLUXO_SECUNDARIO/02_MERGE" / chapter
```

O risco prático é uma alteração de layout pedir mudanças em vários consumidores. Um consumidor esquecido pode continuar lendo a pasta antiga, não encontrar resultados novos ou gravar dados numa segunda árvore sem erro evidente.

### Depois: consumidores declaram intenção, layout decide o caminho

Formato ilustrativo para a futura refatoração (nomes de API abaixo são propostas, não existem ainda):

```python
# Um módulo de layout conhece a árvore física
layout.manga_images(manga)
layout.merge_chapter(manga, chapter)
layout.textoff_chapter(manga, TEXT_OFF_LEVEL1, chapter, for_write=True)

# Consumidores expressam qual dado precisam, sem repetir nomes físicos
folder = layout.merge_chapter(manga, chapter)
folder = layout.textoff_chapter(manga, CONSOLIDATED, chapter, for_write=False)
```

Se o diretório canônico do Nível I mudar depois, o nome físico deve mudar no registro de layout e, quando necessário, na tabela de aliases/migração. Os consumidores permanecem iguais. O identificador lógico do estágio e o valor gravado nos manifestos só mudam com uma migração de contrato deliberada; renomear uma pasta não deve, por si só, invalidar manifestos nem hashes.

### De/para inicial de nomes

Este mapa separa identificadores lógicos de diretórios atuais. O identificador lógico proposto não precisa coincidir textualmente com o nome da pasta.

| Identificador lógico proposto | Diretório canônico atual | Alias físico legado encontrado | Política desejada |
|---|---|---|---|
| `TEXT_OFF_MERGED_LEGACY` | `MERGED` | — | Ler resultados anteriores; evitar novas gravações neste destino por fluxos novos |
| `TEXT_OFF_LEVEL1` | `TO_MERGED_NIVEL_I` | `MERGED_NIVEL_I` | Gravar no canônico; ler alias enquanto houver dados dependentes |
| `TEXT_OFF_LEVEL2` | `TO_MERGED_NIVEL_II` | `MERGED_NIVEL_II` | Gravar no canônico; ler alias enquanto houver dados dependentes |
| `TEXT_OFF_LEVEL3` | `TO_MERGED_NIVEL_III` | `MERGED_NIVEL_III` | Gravar no canônico; ler alias enquanto houver dados dependentes |
| `TEXT_OFF_CONSOLIDATED` | `TO_MERGED_CONSOLIDADO` | ainda não declarado | Definir política antes de qualquer renomeação |
| `MERGE_OFFICIAL` | `02_MERGE` sob `FLUXO_SECUNDARIO` | — | Compartilhar resolução com os consumidores da V2; manter contrato de domínio |
| `AUTO_MERGE_LEVEL_n` | `01_MERGE_PROCESSAMENTO/<nome do estágio>` | nomes definidos por `STAGES` | A resolução do nome físico fica junto ao registro de estágios Auto Merge |

**Atenção:** `MERGED_NIVEL_I` também aparece em valores de API/payload e no campo `source_stage` de manifestos. A coluna “alias físico legado” não prova que todas essas ocorrências são caminhos. Antes de mudar qualquer string, classificar cada uso como caminho, identificador de API ou dado persistido e manter compatibilidade correspondente.

### Exemplo de impacto de uma renomeação

Supondo que `TO_MERGED_NIVEL_I` fosse renomeado para `TEXT_OFF_LEVEL_1`:

```text
Hoje:
  stages.py: LEVEL1 = "TO_MERGED_NIVEL_I"
  consumidores: stage_chapter(manga, LEVEL1, chapter)
  disco: FLUXO_SECUNDARIO/04_TEXTO_OFF/TO_MERGED_NIVEL_I/<capítulo>/

Depois do contrato centralizado:
  consumidores: layout.textoff_chapter(manga, TEXT_OFF_LEVEL1, chapter)
  layout: TEXT_OFF_LEVEL1 -> TEXT_OFF_LEVEL_1
  compatibilidade de leitura: TO_MERGED_NIVEL_I e MERGED_NIVEL_I, enquanto necessário
```

O segundo formato reduz alterações no código consumidor. Ainda exige planejar a leitura/migração dos diretórios existentes e a validade dos manifestos, mas concentra essa decisão no layout em vez de espalhá-la pela feature.

### Critérios de conclusão da futura tarefa

- Nenhuma rota da Central v2 concatena nomes de diretório de artefatos.
- Os nomes físicos canônicos de entradas/saídas e suas raízes têm uma única fonte de verdade.
- Identificadores lógicos, aliases de API e nomes de diretório são conceitos distintos no código.
- Escritas novas sempre usam o caminho canônico; leitura legada é explícita, testada e pode ser removida por política definida.
- Renomear um diretório canônico exige alterar o registro de layout e os testes de contrato/migração, não todos os consumidores.
- Testes provam resolução canônica, aliases de leitura, ausência de escrita acidental no legado, segurança de caminho e compatibilidade de manifestos existentes.
- Nenhuma alteração acidental à Central v1, aos algoritmos de domínio, aos thresholds ou ao conteúdo dos manifestos sem versão/migração deliberada.

## Ordem sugerida de adequação

1. Definir os identificadores lógicos e os nomes físicos canônicos sem renomear diretórios ainda.
2. Generalizar `stages.py` para resolver também raízes comuns, `MERGED` legado, MERGE oficial e estágios Auto Merge/Balanceamento/Manual.
3. Substituir os caminhos literais nos módulos de produção listados acima, preservando os limites de segurança e hashes existentes.
4. Centralizar aliases de entrada e migração/leitura de manifestos antigos; garantir que novas escritas usem apenas identificadores canônicos.
5. Migrar as fixtures e acrescentar testes de layout canônico, leitura legada, escrita canônica e rejeição de caminhos fora da obra.
6. Atualizar documentação e executar as suítes Python e frontend da Central v2.

## Fora do escopo deste levantamento

- Caminhos usados pela Central v1, bibliotecas de domínio e ferramentas fora de `central_v2/backend` não foram propostos para refatoração automática. A V2 deve continuar chamando os domínios existentes sem copiar seus algoritmos.
- Strings de interface como o rótulo `MERGED` em [navigation.js](../central_v2/frontend/_shell/navigation.js#L88) são nomes de menu, não caminhos de disco; não devem ser renomeadas só por coincidirem com uma pasta.
- Este levantamento não autoriza mover ou renomear dados existentes. Uma futura migração deverá preservar manifestos, hashes e capacidade de localizar resultados anteriores.

## Reavaliação contra o HEAD vigente

**Auditoria estática atualizada em:** 04/10/2026

**HEAD auditado:** `0f8a7a76` (`fix(central-v2): padroniza feedback da curadoria de baloes`)

**Base do levantamento original:** `cd91f214`, commit que adicionou o documento em 02/10/2026; o próprio documento declara que o estado estático descrito é de 30/09/2026.
**Escopo desta atualização:** reconciliar os achados anteriores com o código vigente e registrar achados introduzidos depois do levantamento. Nenhum consumidor operacional foi alterado nesta auditoria.

As classificações abaixo descrevem o código em `0f8a7a76`, não a intenção do levantamento original.

### 1. Reconciliação dos achados originais

| Achado de 30/09/2026 | Estado no HEAD vigente | Evidência e diferença desde o levantamento |
|---|---|---|
| `stages.py` registra os diretórios TextOff e aliases, mas embute `FLUXO_SECUNDARIO/04_TEXTO_OFF` e não resolve outras raízes | **Parcialmente resolvido** | `stages.py` continua centralizando `LEVEL1/2/3`, `CONSOLIDATED` e aliases I–III, mas `stage_root()` ainda monta as duas raízes fisicamente. Não há módulo comum de layout. Ver [`stages.py`](../central_v2/backend/orchestration/textoff_merged/stages.py#L4). |
| `manifests.py` monta `MERGED` e `IMG` diretamente | **Ainda aplicável** | `_clean_manifest()` ainda lê `04_TEXTO_OFF/MERGED` diretamente e `_manifest_matches_merge()` ainda usa `IMG`. Além disso, `execution.py::execute_merged()` continua aceitando e usando `MERGED` como destino de saída do fluxo legado, enquanto o fluxo dedicado Nível I escreve no estágio canônico `LEVEL1`. A coexistência foi mantida por implementação posterior; a política de escrita do fluxo legado precisa ser decidida antes da centralização. Ver [`manifests.py`](../central_v2/backend/orchestration/textoff_merged/manifests.py#L10) e [`execution.py`](../central_v2/backend/orchestration/textoff_merged/execution.py#L12). |
| `execution.py` monta `IMG` e aceita `MERGED_NIVEL_I` como alias de destino | **Alterado por implementação posterior** | A execução dedicada de Nível I agora usa `LEVEL1` e `stage_chapter(..., read_legacy=False)`, e Nível II publica no `LEVEL2` canônico. O fluxo legado ainda aceita `MERGED_NIVEL_I` como alias de destino e resolve os capítulos-fonte em `IMG` diretamente. O alias não foi removido nem deve ser tratado como mera pasta. Ver [`execution.py`](../central_v2/backend/orchestration/textoff_merged/execution.py#L12) e [`level2.py`](../central_v2/backend/orchestration/textoff_merged/level2.py#L60). |
| `consolidated_artifacts.py` usa literal em vez de `CONSOLIDATED` | **Ainda aplicável** | O consumidor ainda passa a string `TO_MERGED_CONSOLIDADO` diretamente a `stage_chapter()` apesar da constante existir em `stages.py`. Ver [`consolidated_artifacts.py`](../central_v2/backend/orchestration/textoff_merged/consolidated_artifacts.py#L13). |
| `consolidated.py` mistura `LEVEL1` com `MERGED_NIVEL_I` ao ler `source_stage` | **Alterado por implementação posterior** | O Nível II atual grava `source_stage` usando `LEVEL1`, e a validação do consolidado ainda aceita `MERGED_NIVEL_I` para compatibilidade com manifestos anteriores. Portanto a leitura do alias é uma fronteira de persistência deliberada; não apagar nem substituir globalmente sem política de compatibilidade. Ver [`consolidated.py`](../central_v2/backend/orchestration/textoff_merged/consolidated.py#L95) e [`level2.py`](../central_v2/backend/orchestration/textoff_merged/level2.py#L138). |
| `query.py`, `level2.py` e `level3_styled.py` resolvem `IMG` diretamente | **Ainda aplicável** | Os três módulos continuam acessando `manga / "IMG"`; em `level2.py`, o código posterior também usa `IMG` para validar entradas, embora escreva resultados em `LEVEL2` pelo resolver TextOff. Ver [`query.py`](../central_v2/backend/orchestration/textoff_merged/query.py#L22), [`level2.py`](../central_v2/backend/orchestration/textoff_merged/level2.py#L63) e [`level3_styled.py`](../central_v2/backend/orchestration/textoff_merged/level3_styled.py#L27). |
| `textoff_special/inputs.py` trata `MERGED_NIVEL_I/II` como nomes de nível e os envia ao resolver | **Ainda aplicável** | `LEVELS` continua declarando esses valores de entrada e `resolve_input()` os passa a `stage_chapter()`. O resolver normaliza o alias físico para o nome canônico de diretório, mas a normalização do identificador de entrada não está reunida num contrato separado. Ver [`inputs.py`](../central_v2/backend/orchestration/textoff_special/inputs.py#L10). |
| `special_levels.py` e `manual_specials.py` gravam `MERGED_NIVEL_I` no payload | **Ainda aplicável** | Ambos ainda emitem esse valor para `preview()`. Ele é dado de integração persistido/consumido pelo fluxo TextOff especial, não apenas um nome de pasta. Ver [`special_levels.py`](../central_v2/backend/orchestration/textoff_merged/special_levels.py#L69) e [`manual_specials.py`](../central_v2/backend/orchestration/textoff_merged/manual_specials.py#L45). |
| `routes/merge_manual.py` monta raízes `IMG`, níveis IV/V e acessa manifests | **Ainda aplicável** | A rota continua compondo os diretórios `IMG`, `MERGE_LEVEL4` e `MERGE_LEVEL5` diretamente. As verificações de containment e de manifesto existentes são proteções que a refatoração deve preservar; elas não centralizam o layout. Ver [`merge_manual.py`](../central_v2/backend/routes/merge_manual.py#L19). |
| `routes/balanceamento_media.py` monta `02_MERGE`, `FLUXO_SECUNDARIO` e `BALANCE_STATUS` | **Ainda aplicável** | Os três caminhos continuam definidos nessa rota; referências relativas do manifesto passam por validação de containment. Ver [`balanceamento_media.py`](../central_v2/backend/routes/balanceamento_media.py#L32). |
| `routes/auto_merge/folder.py` compõe `01_MERGE_PROCESSAMENTO/<estágio>` | **Ainda aplicável** | A tabela `STAGES` e a montagem do caminho físico continuam dentro da rota. A validação do capítulo impede sair da raiz de estágio, mas não transfere a resolução a um contrato de layout. Ver [`folder.py`](../central_v2/backend/routes/auto_merge/folder.py#L9). |
| `state/manga_state.py`, `state/catalog.py` e outros consumidores acessam `IMG` diretamente | **Ainda aplicável** | `resolve_manga()` valida provider, containment e existência da obra; `build_structural_state()` e `build_catalog()` continuam usando o nome literal `IMG`. Os módulos TextOff e rotas também o repetem. Ver [`manga_state.py`](../central_v2/backend/state/manga_state.py#L14) e [`catalog.py`](../central_v2/backend/state/catalog.py#L13). |
| `stages.py` lê aliases físicos I–III, mas não cobre `MERGED` nem consolidado | **Parcialmente resolvido** | O resolver continua com fallback de leitura apenas para I–III. `CONSOLIDATED` existe e novas saídas usam esse nome canônico, mas não há alias declarado para ele; `MERGED` continua como fluxo legado separado fora do registro. Não foi encontrada política de migração ou de leitura para diretório legado do consolidado. |
| Testes repetem as árvores de dados e aliases | **Parcialmente resolvido** | `test_textoff_consolidated.py` já importa `LEVEL1/LEVEL2` em parte das fixtures, mas ainda monta raízes físicas manualmente. Outros testes continuam usando `MERGED_NIVEL_I/II`, `IMG` e diretórios de Merge escritos como strings. Preservar asserts explícitos de contrato ao migrar fixtures. Ver [`test_textoff_consolidated.py`](../dev/tests/test_textoff_consolidated.py#L12), [`test_textoff_special_inputs.py`](../dev/tests/test_textoff_special_inputs.py#L15) e [`test_central_v2_merge_manual.py`](../dev/tests/test_central_v2_merge_manual.py#L20). |
| README e páginas HTML documentam nomes/caminhos sem separar todos os conceitos | **Parcialmente resolvido** | README e documentos HTML existem no HEAD e descrevem os diretórios canônicos TextOff atuais, incluindo Nível II e consolidado. Ainda há caminhos físicos diretamente na documentação e não há uma tabela única que distinga identificadores lógicos, campos persistidos e aliases legados. Os nomes em docs não provam, por si, que sejam paths ativos em runtime. Ver [`README.md`](../README.md#L305), [`runtime/textoff/README.md`](../central_v2/runtime/textoff/README.md#L18), [`textoff_merged_transparencia.html`](textoff_merged_transparencia.html) e [`central_v2_menus.html`](central_v2_menus.html). |

**Itens totalmente resolvidos:** nenhum dos itens de centralização de raízes/estágios foi concluído no HEAD auditado. O módulo `artifact_paths.py` centraliza referências a arquivos `clean/`, `mask/` e `json/`, suporta o layout plano anterior e rejeita traversal, mas isso é uma responsabilidade mais estreita e não substitui o layout da obra. Ver [`artifact_paths.py`](../central_v2/backend/orchestration/textoff_merged/artifact_paths.py#L1).

### 2. Achados posteriores e áreas auditadas

| Achado ou mudança posterior | Evidência no HEAD | Estado |
|---|---|---|
| BubbleSommelier criou uma árvore persistida própria sob `FLUXO_SECUNDARIO/04_TEXTO_OFF/BUBBLE_SOMMELIER` e resolve crops/reports no módulo de artifacts | [`bubble_sommelier/artifacts.py`](../central_v2/backend/orchestration/bubble_sommelier/artifacts.py#L11) define `STAGE`, `merge_dir()`, `execution_dir()`, `report_path()` e `crops_dir()`. `query.py` também compõe `02_MERGE` diretamente. As rotas delegam a esses helpers, mas o estágio Sommelier não integra `stages.py` nem um layout comum. | **Novo achado; ainda não centralizado.** Os hashes, validações de identidade/containment e localizações existentes são contratos a preservar. |
| Implementação posterior do Nível II passou a usar o estágio canônico como destino, com execução por job, temporários e promoção por capítulo | [`level2.py`](../central_v2/backend/orchestration/textoff_merged/level2.py#L60) lê `IMG`, resolve `LEVEL1/LEVEL2`, prepara arquivos temporários junto à raiz do destino e promove resultados; [`level2_process.py`](../central_v2/backend/orchestration/textoff_merged/level2_process.py#L159) grava `source_stage` canônico. | **Alterado por implementação posterior.** O uso do resolver para outputs avançou, mas a raiz comum e os caminhos de entrada continuam espalhados. Manter a semântica transacional e hashes ao migrar. |
| Job manager foi revisto para falhas/progresso, mas não introduziu armazenamento persistido de jobs | [`jobs/manager.py`](../central_v2/backend/jobs/manager.py#L15) mantém `_jobs` em memória; os jobs guardam estado, progresso e resultados, não definem a árvore persistida das obras. | **Sem novo achado de layout no próprio manager.** Caminhos de resultados continuam pertencendo aos módulos de execução/artefatos que o job chama; auditar esses produtores, não substituir strings no manager. |

### 3. Plano de implementação após esta auditoria

Este plano é proposta para a etapa de implementação; **não autoriza alterar dados nem contratos neste documento**.

1. **Fixar o vocabulário antes de migrar consumidores.** Registrar para cada estágio: ID lógico interno, nome físico canônico, aliases físicos somente de leitura, valores aceitos por API/payload, valores persistidos em manifestos e caminho atualmente usado. Cobrir `MERGED` legado, níveis I–III, consolidado, estágios especiais, Auto Merge, Balanceamento, Merge Manual e BubbleSommelier.
2. **Resolver as decisões de compatibilidade antes de definir escritores.** Em particular, decidir o papel futuro do fluxo que ainda grava em `04_TEXTO_OFF/MERGED`, a política de leitura do consolidado legado e por quanto tempo aliases `MERGED_NIVEL_*` serão aceitos em manifests/payloads. Não mover/renomear dados nem converter valores persistidos durante uma simples troca de resolver.
3. **Definir uma API de layout sem misturar conceitos.** Centralizar raiz da obra, `IMG`, `FLUXO_SECUNDARIO`, `02_MERGE`, `01_MERGE_PROCESSAMENTO`, TextOff e BubbleSommelier. O resolver recebe IDs lógicos; uma tabela separada define diretório canônico e aliases de leitura. API/manifestos conservam seus valores atuais até uma migração versionada ser deliberadamente aprovada.
4. **Especificar segurança e política read/write.** Manter as verificações atuais de containment, nomes de capítulo/arquivo, symlinks, hashes e manifesto-bound reads. Leitores devem reconhecer formatos antigos explicitamente; escritores devem usar somente o destino canônico definido no passo 2. A compatibilidade legada não pode escolher escrita por fallback de existência.
5. **Migrar primeiro o resolver e seus testes de contrato; só então os consumidores.** Provar paths atuais, aliases de leitura e destino de escrita com fixtures isoladas. Depois atualizar grupos pequenos: estado/catálogo e raízes comuns; TextOff Merged/consolidado/Nível II; BubbleSommelier; Auto Merge/Balanceamento/Merge Manual e rotas de artefatos. Cada grupo deve manter testes explícitos de compatibilidade.
6. **Atualizar documentos e fechar por busca estática.** Reclassificar ocorrências remanescentes de strings pelo significado — path físico, ID lógico, alias, valor persistido ou texto de UI — e revisar a documentação. Não usar substituição textual global de nomes.

O ponto de decisão 2 é pré-requisito para declarar um contrato canônico de escrita completo. Até essa decisão, o inventário atualizado descreve coexistência observada, não uma aprovação para remover o fluxo legado.
