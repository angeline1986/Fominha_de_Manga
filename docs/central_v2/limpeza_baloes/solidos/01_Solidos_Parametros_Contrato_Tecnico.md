# Central V2 — Sólidos: contrato técnico, parâmetros e preservação

**Referência de código:** `angeline1986/Fominha_de_Manga`, branch `develop`, commit de referência `1af79b5c` (2026-10-15). **Status:** documentação de implementação; os parâmetros abaixo foram lidos do código desse commit. Não constitui homologação completa do processamento em produção.

## 1. Escopo e sequência real

1. **Auto-Cleaner I** (`01_AUTO_CLEANER`) produz `clean/<nome>_clean.png`; o tratamento Sólidos não refaz o AC1 nem altera seus thresholds.
2. **Auto-Cleaner Check** (`04_AUTO_CLEANER_CHECK`) persiste somente as regiões aprovadas explicitamente, com identificador, página, tipo e `box_pixels`.
3. **Etapa visual 05 — Auto-Cleaner: Sólidos**, diretório `05_AUTO_CLEANER_SOLIDOS/<capítulo>`: filtra exclusivamente `tipo == "residuo_balao_solido_branco"`; imagem de entrada = **clean do AC1**, não a imagem IMG/MERGE original. Importa e executa `laboratorio_solidos._filter` — **um motor**, dois pontos de uso.
4. **Glass aparece como 06 somente na navegação**. O estágio Sólidos não alimenta automaticamente o Glass, o consolidado nem substitui o AC1. `preview_only: true` é uma garantia explícita.
5. **Laboratório > Sólidos permanece independente** e permite ROI manual e origem IMG/MERGE, produzindo prévias isoladas próprias. Não o remover nem substituir pela etapa 05.

## 2. Motor exato: `central_v2/backend/routes/laboratorio_solidos.py`

Função ` _filter(image: PIL.Image, selections: list[dict]) -> (PIL.Image, PIL.Image, audit)`. Conversão de entrada `image.convert("RGB")`, `numpy.asarray(...).copy()`. Máscara composta global `uint8`, dimensões integrais da imagem. Cada ROI validada por `_box`.

| Parâmetro / decisão | Valor no código | Contrato operacional |
|---|---:|---|
| Arredondamento dos pixels | `round(x), round(y), round(width), round(height)` | Lab aceita coordenadas que o validador admite; etapa 05 exige previamente inteiros no manifesto Check. |
| Dimensão mínima de ROI | `width >= 12`, `height >= 12` | Menor: rejeitar com `Área fora da imagem ou muito pequena.` |
| Limites da ROI | `x>=0`, `y>=0`, `x+w <= W`, `y+h <= H` | Nunca operar fora da imagem. |
| Faixa de branco para avaliação de fundo | `min(R,G,B) >= 245` | Mede fração de pixels suficientemente brancos na ROI. |
| Fração branca mínima | `white_fraction >= 0.70` | Menor: não modifica ROI; auditoria `preserved_requires_review`, motivo `Fundo não suficientemente branco`. |
| Canal para detecção | `cv2.COLOR_RGB2GRAY` | Tons de cinza do recorte. |
| Margem interna de análise | `gray[3:-3,3:-3]` | Protege 3 pixels nas bordas. |
| Limiar de pixel escuro | `gray < 205` | Produz máscara binária dos componentes. |
| Conectividade | `cv2.connectedComponentsWithStats(dark, 8)` | 8 vizinhos. |
| Área de componente | `2 <= area < width*height*0.20` | Componentes muito grandes são descartados. |
| Largura de componente | `bbox_width < width*0.80` | Proteção contra áreas extensas. |
| Altura de componente | `bbox_height < height*0.70` | Proteção contra áreas extensas. |
| Dilatação da máscara | kernel de uns `(3,3)`, `iterations=1` | Expande máscara localmente após selecionar componentes. |
| Proteção de brancos puros | `region_mask[gray >= 253] = 0` | Remove esses pixels da máscara, não os pinta. |
| Proteção adicional de bordas | 3 pixels por lado com máscara zerada | Evita invadir o contorno da região. |
| Máximo de pixels selecionados | `changed <= ROI_area*0.30` | Acima: ROI preservada e `Máscara insegura`. |
| Candidato selecionado | ao menos uma CC aceita; máscara > 0 | `status: candidate`; se nenhum pixel mudado: `unchanged`. |
| Cor escrita na máscara | pixels da RGB de saída recebem `[255,255,255]` | Não é inpainting nem reconstrução por contexto: branqueamento de pixels da máscara. |
| Composição de máscaras | `np.maximum(mask_all[roi], region_mask)` | Máscara global preserva união das regiões. |

**Não reajustar** `245`, `.70`, `205`, `3px`, `2`, `.20`, `.80`, `.70`, dilatação `(3,3)`, `253` ou `.30` para “melhorar” um caso sem criar experimento versionado e evidências comparativas. Um resultado `preserved_requires_review` é uma decisão de segurança, não necessariamente bug.

### 2.1 Auditoria por ROI

Registro por ROI inclui `box: [x,y,w,h]`, `status`, `changed_pixels` e, no caso elegível, `components`, `white_fraction` (4 casas). Estados possíveis observados no código: `candidate`, `unchanged`, `preserved_requires_review`. Motivos explícitos: `Fundo não suficientemente branco`, `Máscara insegura`. Cuidado: `candidate` informa alteração proposta; não é homologação visual do resultado.

### 2.2 Limites próprios do Laboratório

- Endpoint `POST /api/textoff/laboratorio/solidos/execute`; payload contém `provider`, `manga`, `chapter`, `page`, `source` (`img` ou `merge`) e `selections` (ROIs validadas por `validate_selections`).
- `len(selections) <= 30` por prévia, imagem de até `100_000_000` pixels.
- `run_id = uuid.uuid4().hex`; saída em `<OUTPUT_ROOT>/_laboratorio_solidos_previews/<run_id>/{preview.png,mask.png,manifest.json}`.
- Manifest `schema: laboratorio_solidos_preview_v1`, `source_sha256`, `preview_sha256`, `regions`, `preview_only:true`, identificação de provider/obra/capítulo/página.
- `GET /api/textoff/laboratorio/solidos/image?run_id=<32 hexadecimal>` exige ID válido, `preview_only` e hash do preview igual ao manifesto. Respostas de erro 400 ou 404.
- A prévia do Laboratório não é saída canônica da etapa 05 e não deve substituí-la por cópia manual.

## 3. Check: contrato da decisão humana

Arquivo: `<obra>/FLUXO_SECUNDARIO/04_TEXTO_OFF/04_AUTO_CLEANER_CHECK/<capítulo>/auto-cleaner-check-manifest.json`.

- `schema = textoff_auto_cleaner_check_manifest_v1`; `version = 1`.
- Valida `provider`, `manga`, `chapter`, `source_snapshot` (objeto) e `approved_occurrences` (lista de objetos).
- Sólidos seleciona apenas elementos `approved_occurrences` com `tipo: residuo_balao_solido_branco`.
- Exige `id` único e não vazio, `page` PNG com nome simples, `box_pixels` objeto com `x`, `y`, `width`, `height` **inteiros exatos** (bool não é aceito).
- A política declarativa em `occurrence_policy.py` mapeia `residuo_balao_solido_branco` para rótulo `Resíduo em balão sólido branco` e `protect_from_transparency_basic=True`. Atenção: o próprio módulo informa que a política isoladamente não muda o worker legado; não declarar a proteção efetiva em todos os caminhos sem validar sua integração.
- O tipo também existe em `residue_occurrences.py` e na classificação da UI `comparison/residue_model.js`. A cadeia inteira deve manter o mesmo ID estável.
- A persistência do Check utiliza `tempfile.mkstemp`, `fsync`, `os.replace` para atualização atômica; capítulo validado contra travessia de diretórios.

## 4. Etapa 05: fluxo interno e invariantes

Código: `central_v2/backend/orchestration/textoff_merged/solid_stage.py`.

1. `rows_for` obtém manifesto Check, valida o documento e retorna ROIs tipadas mais SHA-256 **do arquivo Check inteiro**.
2. `source_for` valida `page` simples terminado em `.png`; lê `stage_chapter(manga, LEVEL1, chapter)/clean/<stem>_clean.png`. A origem deve existir e estar contida no diretório do nível I.
3. `execute_chapter`: exige ao menos uma ROI, rejeita `target` já existente, agrupa por página, rejeita IDs repetidos, lê cada imagem em RGB e aplica limite de `100_000_000` pixels.
4. Calcula SHA-256 inicial de **cada imagem de origem**; antes de salvar cada página checa hash da fonte e do Check; após todo o lote revalida todos os hashes.
5. Aplica `_filter` **sem modificar parâmetros**, salvando `clean/<stem>_clean.png`, `mask/<stem>_mask.png` e `solid-white-manifest.json` em diretório temporário `.solid-stage-*`.
6. Publicação via `os.rename(scratch, target)` somente se o destino ainda não existir; no encerramento limpa scratch remanescente. **Não reprocessa por cima de saída existente**.
7. Retorna `{chapter, pages, regions, candidates}`; `candidates` neste retorno soma `changed_pixels` (o nome pode induzir confusão: não representa número de ROIs candidatas).

**Manifest da etapa 05:** `schema:textoff_solid_stage_v1`, `provider`, `manga`, `chapter`, `motor:laboratorio_solidos._filter`, `check_sha256`, `preview_only:true`, `pages:[{page,source_sha256,result_sha256,mask_sha256}]`, `regions:[{id,page,box,status,changed_pixels,...}]`. Não contém promoção automática nem integração de downstream.

## 5. Rotas da etapa 05

| Rota | Método | Uso e proteção |
|---|---|---|
| `/api/textoff/solidos` | GET | Lista capítulos que possuem áreas Sólidos aprovadas no Check; estado `processed` significa existência do manifest de prévia. |
| `/api/textoff/solidos/execute` | POST | Enfileira um único capítulo por requisição, devolve `202 {job}`. Rejeita capítulo sem ROIs e resultado já existente. |
| `/api/jobs/<id>` | GET | Consultado pelo frontend a cada aproximadamente 600 ms até `completed` ou `failed`. |
| `/api/textoff/solidos/image` | GET | `provider,manga,chapter,page,kind` (`before`, `after`, `mask`); valida identidade, `preview_only` e SHA-256 de cada imagem antes de servir. |
| `/api/textoff/comparison` | GET | Para Sólidos exige `comparisonMode=solid`, `scope=solid`, `step=solid`; retorna páginas com `id,name,version`. |
| `/api/textoff/comparison/image` | GET | Identidade e parâmetros acima + `page` ordinal, `version` e `side=before|after`; versão por SHA-256 do conjunto nome + hash origem + hash resultado. Chama o endpoint interno autenticado de imagem isolada. |

Roteador: `central_v2/backend/routes/textoff_merged_router.py` direciona `solidos`/`execute`/`image`. `textoff_comparison.py` despacha trio exato de `step/scope/comparisonMode` para `solid_comparison.py`; não alterar esse trio isoladamente.

## 6. Segurança: regras de não regressão

- Não tocar em `image_stitcher.py`, thresholds AC1, auto-merge Níveis I/II/III ou heurísticas Glass para corrigir Sólidos.
- Não alterar Sólidos do Laboratório ao corrigir somente uma tela.
- Não persistir sobre imagens de origem nem consolidado; `preview_only:true` permanece.
- Não remover SHA-256 e verificação de origem, Check, preview e máscara.
- Não trocar `source_for` por IMG original: entrada é o AC1 clean.
- Não renomear diretórios existentes porque Glass mudou para “06” na sidebar; o número 06 é visual.
- Não permitir reexecução silenciosa quando `05_AUTO_CLEANER_SOLIDOS/<capítulo>` já existe. Desenhar procedimento explícito versionado de invalidação/restauração antes de adicionar reprocessamento.

## 7. Evidência operacional conhecida versus não comprovada

**Conhecido do histórico da implementação:** houve aprovação visual do filtro Sólidos no Laboratório, com remoção de texto em balões brancos sem eliminação aparente das bordas. Capítulos 1 e 2 da obra de referência contavam com 6 ocorrências aprovadas em cada capítulo. Instalações de estágio, layout, comparação e commits `a0749ef7`, `934a3f4e` sucederam-se, e o commit `1af79b5c` adicionou seleção em lote na Curadoria.

**Não comprovado por essas evidências:** regressão completa em todos os capítulos/obras, comportamento downstream com Glass, recuperação de execução interrompida, throughput em lote, imutabilidade sob corrida concorrente e homologação completa da UI após cada commit. Não preencher resultados inexistentes em futuras revisões.
