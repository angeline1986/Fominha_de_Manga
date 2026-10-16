# Auto-Cleaner Sólidos — Central V2

## Objetivo e fontes

Executar sobre regiões aprovadas no Check do tipo `residuo_balao_solido_branco`. Não recalcula decisões do Check nem faz uma nova detecção geral: lê o manifesto aprovado e usa a fonte resultante do Auto-Cleaner I / imagem de Check efetiva (`solid_stage.py`).

## Processamento

`routes/laboratorio_solidos.py::_filter` aplica uma operação de remoção/filtragem às caixas em pixels; `textoff_merged/solid_stage.py::execute_chapter` valida ROIs inteiras, limite operacional da imagem (`100,000,000` pixels), hashes de cada imagem e do manifesto Check antes e depois do trabalho. Os arquivos são preparados em staging, com `clean/`, `mask/` e manifesto, e publicados como nova pasta sem sobrescrever estágio existente.

Manifesto `solid-white-manifest.json`, schema `textoff_solid_stage_v1`, guarda provider/obra/chapter, motor `laboratorio_solidos._filter`, hash do Check, `preview_only: true`, páginas com hashes de fonte/clean/mask e auditoria por região. Assim, conclusão dessa etapa não implica promoção ao Consolidado Final.

## Parâmetros e limites

O código valida a caixa (`x`, `y`, `width`, `height`) em pixels inteiros e aceita somente PNG para a página selecionada. O algoritmo de pixels é centralizado em `_filter`; os parâmetros geométricos e regra de alteração de pixels precisam ser especificados por leitura desse método antes de reproduzir. Esta página não afirma equivalência visual com filtros manuais da V1.
