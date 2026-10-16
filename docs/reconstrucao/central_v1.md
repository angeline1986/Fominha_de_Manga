# Manual de reconstrucao - Central V1

## 1. Fronteira e dependencias

Central V1 e o servidor legado implementado em `interface_web/`, com despacho de operacoes em `interface_web/processing_web.py` e rotinas tradicionais em `orquestracao/`. O fluxo Texto Off importa `processamento/limpeza_baloes/cleaner_v2/integration.py`; portanto, "V1" identifica a aplicacao/orquestracao, nao uma versao distinta do motor Panel Cleaner.

Dependencias de runtime confirmadas pelo codigo: Python, OpenCV/NumPy/modelos usados pelos dominios; o Cleaner tem ambiente isolado `processamento/limpeza_baloes/cleaner_v2/.venv`, `requirements.txt`, perfil `outlined-text.ini` e Panel Cleaner 2.11.11. A lista e versoes efetivas devem ser obtidas dos arquivos de requisitos e do ambiente a reconstruir; nao instalar ou baixar pesos durante esta documentacao.

## 2. Fluxo real

### Texto Off Original e Merged

1. O handler `run_job()` despacha a acao do job. `do_clean()` enumera imagens ativas do diretorio do capitulo e chama `clean_chapter(..., source_stage="ORIGINAL")`.
2. `do_clean_merged()` exige um MERGE oficial (`is_chapter_merged`), obtem seus artefatos pela API do `image_stitcher` e chama `clean_chapter(..., source_stage="MERGE")`.
3. `clean_chapter()` valida arquivos e nomes unicos, cria workspace temporario, cria links simbolicos das fontes e executa Panel Cleaner em modo offline, perfil `outlined-text.ini`, limite total 900 s.
4. Requer um `*_clean` e um `*_mask` para cada entrada. Executa autorizacao N1 por balao e depois `cleaner_v2/level2.py`, com timeout 900 s. O Nivel II pode produzir relatorio valido com zero paginas alteradas.
5. Monta `clean-manifest.json`, copia artefatos para staging e promove o diretorio. Se a execucao falha antes da promocao, o codigo declara que a saida oficial anterior e preservada; `_promote_directory()` tambem tenta restaurar o backup se a troca falhar.

O `do_clean_merged()` V1 usa destino `04_TEXTO_OFF/MERGED/<capitulo>/`. A chamada V2 isolada `execute_merged()` usa o destino canonico por estagio `TO_MERGED_NIVEL_I`; nao confundir esses dois consumidores apesar de ambos chamarem a integracao comum.

### Operacoes complementares

Comparacao, Nivel III/residuo, correcao assistida, merge manual e tratamentos especiais estao distribuidos no handler, `orquestracao/textoff/` e adaptadores. Tratamentos especiais seguem a separacao observada entre produzir (`process_special_image`) e promover (`promote_special_result`); cada ramo possui validacao e contrato de persistencia proprio. Nao existe uma ordem unica obrigatoria entre todas essas ferramentas: a interface permite fluxos de revisao distintos.

## 3. HTTP e contratos

Rotas V1 relacionadas identificadas em `Handler` de `processing_web.py`:

| Metodo | Rota | Funcao observada |
|---|---|---|
| GET | `/api/textoff-compare` | projecao/consulta para comparacao |
| GET | `/api/textoff-level3` | consulta do estado de Nivel III |
| GET | `/api/textoff-special/select-image` | seleciona fonte especial por provider/manga |
| POST | `/api/textoff-special/process` | executa processamento especial |
| POST | `/api/textoff-special/promote` | valida e promove resultado especial |
| POST | `/api/action` | cria job; acao/payload e despachados por `run_job()` |
| GET | `/api/job/{id}` | consulta estado de job |

O mesmo handler tem rotas gerais de catalogo, estado, exportacao e merge; elas nao sao contratos exclusivos da limpeza. Nao foi documentado aqui um schema JSON completo de todas as acoes `/api/action`: reconstruir payloads a partir dos consumidores frontend e validadores em `processing_web.py`, sem supor campos opcionais.

## 4. Cleaner: parametros e saidas

`cleaner_v2/integration.py` fixa `ALGORITHM=cleaner_v2_panel_cleaner_2_11_11`, `PROFILE_NAME=outlined-text.ini`, modo offline e timeout 900. O manifesto raiz declara `schema_version: 3`, engine/version, OCR efetivo, `source_stage`, `source_immutable`, paginas/artefatos, integridade, autorizacao, relatorios N1/N2 e falhas. Writer V1 e esta integracao; manifests antigos podem divergir, e a compatibilidade depende dos leitores concretos.

Os limiares de autorizacao e refinamento estao no [manual compartilhado](componentes_compartilhados.md). O fluxo legado combinado executa N1 e N2 dentro da chamada comum; a execucao V2 de N1 pode parar depois da autorizacao, conforme descrito no [manual V2](central_v2.md). Esse e um limite relevante ao comparar resultados.

## 5. Persistencia, hashes e invalidacao

O diretório V1 de limpeza e `FLUXO_SECUNDARIO/04_TEXTO_OFF/MERGED/<capitulo>/` para Merged e `.../ORIGINAL/<capitulo>/` para Original, conforme `processing_web.py` (`tmdir`/`cdir`). O manifesto registra nomes e contagens, mas nao hashes por pagina no escritor integrado V1. A integridade e verificada por completude/valores declarados, nao equivale a proveniencia SHA-256 de cada arquivo.

MERGE possui manifesto proprio e validacao de cobertura em `orquestracao/textoff/merged.py` via `image_stitcher`: outputs em ordem, intervalos contiguos e altura total. Nivel III/IV de outros subfluxos pode vincular manifests por SHA-256 no handler. Para cada ramo de restauracao/promocao, rastrear o escritor e a precondicao local; nao transferir a garantia de hashes de V2 para V1.

## 6. Diferencas e equivalencia

- V1 e V2 podem chamar o mesmo Cleaner, mas diferem em destinos, fronteiras de jobs, consulta, staging, manifests adicionais, elegibilidade e promocao.
- V1 `do_clean_merged()` executa o processamento combinado N1 + N2; o endpoint V2 Nivel I produz estagio separado e reporta Nivel II como `not_run`.
- Equivalencia requer mesma entrada/ordem, commit, perfil/pesos/runtime, saida de cada etapa e invariantes por pagina. Nao e suficiente que ambas telas mostrem "limpo".
- Testes de referencia: `dev/tests/test_textoff_merged_level1_adapter.py`, `test_textoff_merged_level2.py`, `test_cleaner_v2_transparency_classifier.py`, `test_cleaner_v2_ocr_manifest.py`. A suite nao foi executada nesta etapa.

## 7. Lacunas explicitamente abertas

- Inventario completo de payloads HTTP e status de todos os jobs V1.
- Compatibilidade empirica de manifests legados e regras de invalidacao em cada consumidor.
- Versoes efetivas de dependencias e checksums de pesos/modelos no checkout/runtime atual.
- Regras completas e comparacao historica dos fluxos V1 Nivel III, correcao assistida e cada tratamento especial.
- Corpus de equivalencia autorizado e tolerancias de comparacao visual. Nao inferir esses dados a partir de nomes de testes.

## Fontes de codigo

`interface_web/processing_web.py`; `orquestracao/textoff/merged.py`; `processamento/limpeza_baloes/cleaner_v2/integration.py`; `balloon_authorization.py`; `transparency_classifier.py`; `level2.py`; `launcher.py`; `ocr_manifest.py`.
