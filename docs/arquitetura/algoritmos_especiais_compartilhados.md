# Algoritmos especiais compartilhados: contratos confirmados

**Escopo:** adapters e algoritmos em `processamento/limpeza_baloes/`, usados diretamente pela V1 e por imports explícitos do domínio V2. Os resultados não são equivalentes por padrão: UI, fonte escolhida, runtime, manifest e promoção variam por versão.

## Degradê — algoritmo base

O arquivo `patch_degrade_experimento.py` define um pipeline experimental por página: Panel Cleaner → autorização de máscara por balões → surface gate → Local Heal. Este script roda em workspace de experimento e não altera IMG/MERGE oficiais. O adapter `textoff_special_roi.py` define `textoff_special_roi_degrade_v2`; a promoção da Central V1 pertence a `textoff_special_web.py` e não é parte do algoritmo de reconstrução.

### Parâmetros confirmados no patch base

- Cleaner: perfil `preserve-colors.ini`, subprocesso offline? **Não confirmado**: o argumento `--offline` não aparece no comando deste script; timeout `900 s`.
- Patch/search: `PATCH_RADIUS=4`, `SEARCH_RADIUS=70`, `SEARCH_STEP=2`, `MIN_CONTEXT=12`, `SOURCE_VALID=0.92`.
- Em `_surface`: componente menor que `100 px` ignorado; amostras externas vêm do anel entre dilatações elípticas `41×41` e `9×9`, fora da máscara; exige ao menos `50` amostras. Compatibilidade Lab: `|ΔL|<48`, `|Δa|<18`, `|Δb|<18`; recorte local expande cada dimensão pela maior entre `100 px` e o tamanho da caixa; abertura morfológica `3×3`; componentes conectados que tocam dilatação elíptica `17×17` são permitidos.
- O Local Heal usa busca de contexto limitada pelos parâmetros acima e registra superfície/máscara e etapas de blend. As regras completas de seleção e composição devem ser copiadas de `_surface`, `_local_heal`, `_authorize_balloon` e `apply_approved_rois` antes de uma reconstrução pixel a pixel.

**Diferença da V2:** o backend V2 tem worker, snapshot, estado/revisão e persistência próprios. Importar o algoritmo base não compartilha o modo de composição ou permissão de promover.

## Patch Balão Transparente

Algoritmo base: `transparent_balloon_lama_text_mask_v1` em `patch_balao_transparente_experimento.py`. A variante ROI adaptada se identifica como `textoff_special_roi_transparent_v1`.

1. Executa Cleaner e `apply_balloon_authorization()` no workspace temporário.
2. Dilata a máscara autorizada pela dilatação base `3×3` elíptica.
3. Na variante ROI atual, escolhe componentes conectados cuja **caixa delimitadora** cruza uma ROI normalizada. Copia o componente inteiro; não recorta pixels pelo interior da ROI.
4. Aplica dilatação autorizada `9×9` elíptica, executa LaMa sobre fonte original com padding `120 px`, e aplica a saída somente dentro da máscara autorizada.
5. Verifica dimensões e que pixels fora da máscara não mudaram. Máscara vazia ou nenhum componente selecionado resulta em erro.

O adapter gera artefatos intermediários e `roi_report.json`; `proof_phase=true` e `promotion_allowed=false` no próprio adapter V1 ROI. A promoção da V1 pode ter regra mais ampla no wrapper; backend V2 tem revisão e promoção próprias. Não usar o campo de prova local como se fosse autorização V2.

### Transparente — Legado

`textoff_special_roi_transparent_legacy_v1` segue Cleaner → seleção de componentes por caixa/ROI → dilatação `3×3` → `9×9` → LaMa. Não chama Balloon Authorization antes da ROI, ao contrário da variante atual. Mantém outputs e report separados e verifica alterações fora da máscara. A distinção é comportamental, não apenas o nome exibido.

## Gradiente Suave

`textoff_gradiente_suave_v1` (`gradiente_suave.py`) não usa Cleaner/LaMa: reconstrói retângulos através de interpolação de cores Lab. Requer caixas válidas em pixels e expansão escrita sem sobreposição.

- Expansão vertical/horizontal usa `max(12, round(0.35 × altura da ROI))`.
- Deixa faixa de contexto de `12 px` nas bordas da imagem; estima topo/base pela mediana da faixa Lab antes/depois da área expandida.
- Suaviza perfil de cada linha com Gaussian blur 1D; kernel ímpar de até `41`, limitado pela largura da região.
- Interpola linearmente do perfil mediano superior ao inferior e escreve todo o retângulo expandido.
- Rejeita expansão sobreposta e verifica zero alterações fora das regiões de escrita.

O preview/report chama a área escrita de retângulo expandido. Isso significa que a região alterada ultrapassa a caixa que o usuário desenhou. Capturar essa regra ao reproduzir; não reduzir a escrita à ROI.

## Artístico / Estilizado

`patch_balao_estilizado_experimento.py` e `textoff_special_styled_roi.py` implementam classificador/proteção de detalhes gráficos, superfície e reparo local, com seleção por ROI em etapa posterior.

Constantes confirmadas no classificador: área mínima `100 px`; proteção de detalhe gráfico ligada; saturação mínima `70`; diferenças locais de saturação/valor `24`/`18`; área máxima do componente gráfico `1800 px`; dilatação `1`; anel local exige `80 px`, raio `12`, fatores relativos de borda/MAD `3.0`, floors `0.025` e `3.5`. O auto-classificador styled está habilitado.

A geometria e exata combinação dessas métricas precisam ser transcritas junto de `_components`, `_select_components`, `_authorized_mask`, `_surface` e `_local_heal`; a tabela acima lista valores configurados, não substitui a ordem dos operadores. A V1 e V2 podem chamar o mesmo módulo com entradas, worker e caminho de saída distintos.

## Fontes de verificação

- `processamento/limpeza_baloes/patch_degrade_experimento.py`
- `patch_balao_transparente_experimento.py`, `textoff_special_transparent_roi.py`, `textoff_special_transparent_legacy_roi.py`
- `patch_balao_estilizado_experimento.py`, `textoff_special_styled_roi.py`
- `gradiente_suave/gradiente_suave.py`
- Chamadores V1: `textoff_special_web.py`; chamados V2: `central_v2/backend/orchestration/textoff_special/domain.py`.
