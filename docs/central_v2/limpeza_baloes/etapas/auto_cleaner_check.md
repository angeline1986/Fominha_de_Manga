# Auto-Cleaner Check — Central V2

**Escopo:** consolida sugestões de fontes automáticas e decisões editáveis, sem executar por si só os detectores originais.

## Fontes e execução

O conjunto de sugestões vem de `mapear`, `sommelier` e `residue_occurrences` (`auto_cleaner_check_sources.py`). A política de extração converte classes conhecidas, por exemplo `soft_gradient` para `residuo_gradiente` (`auto_cleaner_check_extractors.py`). A geometria associa caixas e ocorrências sem usar threshold de distância ou IoU; sobreposições ambíguas continuam separadas (`auto_cleaner_check_geometry.py`).

O usuário edita/revisa ocorrências por página no frontend Check. `auto_cleaner_check.py` entrega decisões persistidas ou sugestões iniciais, valida página contra o conjunto autorizado e persiste as decisões aprovadas.

## Manifesto

- Diretório do estágio: `04_AUTO_CLEANER_CHECK/<capítulo>/` via `stages.py`.
- Arquivo `auto-cleaner-check-manifest.json`, schema `textoff_auto_cleaner_check_manifest_v1`, version `1`.
- Campos-raiz confirmados: `schema`, `version`, `provider`, `manga`, `chapter`, `updated_at`, `source_snapshot`, `approved_occurrences`; após primeira gravação pode incluir `image_snapshot` congelado.
- Escrita ocorre por arquivo temporário, `fsync` e `os.replace`; capítulo e página são validados para impedir traversal/caminho arbitrário.
- Fontes mudadas desde a abertura tornam a edição obsoleta e exigem recarregar.

O Check é a camada de revisão/decisão. A presença de uma sugestão não significa tratamento executado. A etapa Sólidos lê apenas ocorrências aprovadas do tipo `residuo_balao_solido_branco`.

## Lacunas

Documentar dicionário completo de tipos/labels e precedência quando a mesma página tem mais de uma fonte após confirmar cada extractor e estado de saúde de fonte. A V1 não possui contrato equivalente confirmado.
