# Bubble Sommelier — Central V2

**Escopo:** detector e análise visual exclusivos da V2. A V1 equivalente não foi encontrada nesta revisão.

## Implementação e contrato

- UI: `central_v2/frontend/texto_off/sommelier/`.
- API/orquestração: `central_v2/backend/routes/bubble_sommelier.py` e `backend/orchestration/bubble_sommelier/{query,execution,artifacts,mapear_results,runtime}.py`.
- Runtime: `central_v2/runtime/bubble_sommelier/`, Node com lock próprio.
- Persistência: `FLUXO_SECUNDARIO/04_TEXTO_OFF/BUBBLE_SOMMELIER/<capítulo>/` conforme `artifacts.py`.

O backend valida o profile id, recebe páginas/fonte autorizadas, executa o runtime, grava relatório, estados/checkpoints e expõe revisão/crops. A integração pode incorporar resultados Mapear e espelhar artefatos para compatibilidade, conforme `execution.py` e `mapear_results.py`.

## Detector e parâmetros confirmados

O runtime prepara tiles verticais, executa RT-DETR e aplica estratégias de seleção de labels, NMS e seleção final. `detector/infer.js` filtra confiança `< 0.30`; NMS remove sobreposição `IoU > 0.50`. Tiling para quando tiles ficariam abaixo de `200 px` de altura; a geometria e stride vêm de `tiling.js`.

O worker principal identifica candidatos `bubble`, calcula medidas em grid `12×12` e roteia como `SPECIAL` quando cobertura `>= 0.75` e MAD de luminância `> 1.0`. A cobertura é do recorte/máscara válida segundo `analysis/grid.js`; o perfil pode alterar escolhas de detector. Profile IDs aceitos pelo backend: `poc_a_v1` e `poc_b_v1`.

Essas medidas apontam regiões candidatas e não limpam pixels. A análise opcional por visão pode falhar e é reportada como falha de análise; isso não equivale a falha de detecção.

## Artefatos, revisão e limites

O relatório identifica modelo/profile, hash de imagem/crop, geometria, confidence, métricas e decisão. A etapa alimenta fluxo de revisão/catálogo; classificação `SPECIAL` não autoriza automaticamente aplicação de tratamento.

Não verificado: versões exatas dos pesos RT-DETR efetivamente baixados por profile, política de retenção e cada threshold de perfil. Ler manifest runtime e `analysis/` antes de reproduzir; não usar as constantes globais como substituto dos parâmetros de cada profile.
