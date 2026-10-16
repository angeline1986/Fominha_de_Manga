# Manual de reconstrucao - Central V2

## 1. Fronteira e dependencias

V2 e a aplicacao em `central_v2/`: frontend proprio, dispatch HTTP em `backend/routes/`, jobs em `backend/jobs/`, orquestracao em `backend/orchestration/` e runtimes isolados em `central_v2/runtime/`. Importa dominios compartilhados em `processamento/limpeza_baloes/`. A V2 recusa execucao Merged enquanto o servidor V1 estiver ativo (`legacy_server_active` e `_ensure_v2_session`). A arquitetura completa de componentes e dependencias esta em `../arquitetura/mapa_componentes_e_dependencias.md`.

## 2. Ordem real dos fluxos

### Merged: entrada, Niveis I e II e consolidacao

1. `GET /api/textoff/merged` consulta estado por obra; os endpoints de nivel consultam worklists. `query.py`, `overview.py`, `manifests.py` e `stages.py` resolvem autoridade e validade.
2. Execucao Merged comum e Nivel I sao jobs separados (`/execute` e `/level1/execute`). Validam obra/capitulos/MERGE e a sessao V2 antes de enfileirar.
3. Nivel I (`level1_cleaner.py`) valida imagens, executa Panel Cleaner e autorizacao por balao, gera relatorios/manifest em staging e promove o estagio. O contrato V2 explicito de Nivel I nao executa o pos-processamento legado N2.
4. Nivel II explicito (`level2.py`, `level2_process.py`, `cleaner_v2/level2.py`) valida o Nivel I vigente, processa somente candidatos autorizados, registra resultado por pagina e vincula manifesto ao Nivel I. `reprocess` e validado como booleano no endpoint.
5. `consolidated.py` reconstrui uma selecao por pagina: Level II para paginas alteradas validas, senao Level I. Verifica manifests, fontes e artefatos, escreve `json/clean-manifest.json`, promove staging e espelha o consolidado para a area de leitura.
6. Nivel III e job explicito, elegivel somente quando Nivel I esta integro e a analise esta pendente. Niveis IV/V sao execucoes de tratamentos especiais com worklist/propostas especificas.
7. Sommelier, Auto-Cleaner Check, Solidos, especiais de Laboratorio e consolidado final sao ferramentas/etapas distintas. Nao ha uma sequencia global obrigatoria que execute todas automaticamente.

### Rotas TextOff confirmadas

| Metodo | Rota | Uso |
|---|---|---|
| GET | `/api/textoff/merged` | consulta geral |
| GET | `/api/textoff/merged/level1`, `/level2`, `/level3`, `/levelIV`, `/levelV` | worklists por nivel |
| GET | `/api/textoff/merged/level3/image` | imagem somente se declarada em relatorio valido |
| POST | `/api/textoff/merged/execute` | job Merged comum |
| POST | `/api/textoff/merged/level1/execute`, `/level2/execute`, `/level3/execute`, `/levelIV/execute`, `/levelV/execute` | jobs por etapa |
| GET | `/api/textoff/comparison[/image]` | comparacao e imagem |
| GET | `/api/textoff/check/reset-merge/preflight` | preflight da restauracao de override do Check |
| POST | `/api/textoff/check/reset-merge` | restaura override a partir do MERGE |
| GET | `/api/textoff/special/restore-page[/image]` | consulta/imagem de proposta de restauracao de pagina |
| POST | `/api/textoff/special/restore-page` | enfileira restauracao explicita da pagina |
| GET/POST | `/api/textoff/solidos[/image]`, `/api/textoff/solidos/execute` | curadoria/execucao de Solidos (constantes de rota no modulo) |
| GET/POST | `/api/textoff/laboratorio/...` | paginas, imagens e execucoes de tratamentos especializados |
| GET/POST | `/api/textoff/sommelier`, `/review`, `/crop`, `/execute` | analise, revisao, recorte e execucao |

Os payloads sao especificos por handler; use validadores e clientes em `routes/`, `frontend/_app/api/` e `frontend/texto_off/`. Uma rota `job` normalmente responde 202 com identificador; isso nao significa que a operacao terminou ou foi promovida.

## 3. Algoritmos e parametros rastreados

### Cleaner e autorizacao

Panel Cleaner 2.11.11, perfil `outlined-text.ini`, offline e timeout de 900 s. Cleaner valida entrada unica, exige clean+mask por pagina. Autorizacao N1 segmenta baloes com modelo Manga109 (`huyvux3005/manga109-segmentation-bubble`, `best.pt`, revisao `f9a4108c4955136a810e5e92207972f3fb3a65fd`), confidence 0.25, IoU 0.45. Componentes menores que 20 pixels sao preservados; para autorizar, pelo menos 90% do componente deve estar dentro de um balao. Interior erosao: 2.5% do menor lado, limites 2..8 px. Falha fechada.

Detector de transparencia: amostra interior claro (`gray >= 200`), no minimo 500 pixels; marca por desvio-padrao de cinza `>= 9.0` ou razao de saturacao HSV `> 5` de pelo menos `0.05`. Gate secundario quando habilitado: erosao de borda 3 px, dilatacao de mascara de texto 5 px, distancia Lab do branco `>= 8.0`, razao nao-branca `>= 0.01`. Qualquer interseccao de componente com balao transparente adia o componente inteiro.

### Nivel II

`cleaner_v2/level2.py`: area minima 20,000 px; retangularidade minima 0.85; tipo A se desvio-padrao interno `>= 2.5`; tipo B se desvio-padrao `<= 1.5`, range de contexto `>= 25.0`, media interna `<= 245.0` e ao menos tres lados de contexto. Padding da caixa local do classificador: 160 px. A orquestracao `level2_vision.py` tambem declara dilatacoes base/autorizada 3x3 e 9x9, padding LaMa 120 e limite MPS de 3 paginas por modelo. Sao parametros de componentes/etapas diferentes; nao combinar como se fossem um unico classificador.

## 4. Contratos, manifests e persistencia

Raiz usual: `FLUXO_SECUNDARIO/04_TEXTO_OFF/`. `stages.py` define `TO_MERGED_NIVEL_I`, `TO_MERGED_NIVEL_II`, `TO_MERGED_NIVEL_III`, `TO_MERGED_CONSOLIDADO`, nomes legados e leitura via registry; `CENTRAL_V2_LEVEL1_NUMBERED=1` altera raiz Nivel I. Estagios modernos organizam `clean/`, `mask/`, `json/`; `artifact_paths.py` valida referencias relativas e mantem leitura do layout plano antigo. `artifact_migration.py` implementa autoridade/dual-write para entradas registradas. Nao assumir que o layout canonico seja usado por manifests antigos.

Nivel I gera `json/clean-manifest.json` schema_version 3, algoritmo, engine/perfil/OCR, source stage/artifacts, completude/integridade, artefatos clean/mask, autorizacao, sumario N1/N2 e relatorios. Manifest diagnostico opcional registra source/official manifest SHA-256 e copias byte-identicas de raw masks.

Nivel II grava seu manifesto de pagina/etapa com algoritmo, predecessor Nivel I, hashes e lista de paginas/artefatos analisados, alterados e inalterados. `consolidated.py` escreve `TO_MERGED_CONSOLIDADO/<chapter>/json/clean-manifest.json`, liga `source_level1_manifest_sha256` e `source_level2_manifest_sha256`, lista `selections` por pagina com estagio de origem e SHA-256, valida os arquivos antes de publicar.

Consolidado Final usa `07_CONSOLIDADO_FINAL/<chapter>/json/final-manifest.json`, schema `textoff_consolidado_final_manifest_v1`. Cada pagina referencia seu artifact e SHA-256; payload inclui provider/manga/chapter, hash do manifesto intermediario, `updated_at`, `page_count`, `pages` e `history`. Promocao de tratamento confirma que imagem/manifest fonte continuam iguais, copia e confere hash, preserva entrada substituida no historico e publica staging sob lock transacional.

## 5. Restauracao, invalidacao e falhas

Resolucao de estagio usa registry e aliases legados; consultas podem congelar snapshot e rejeitar mudanca de identidade/hash durante a leitura (`stage_path_snapshot`, `test_textoff_query_snapshots.py`). Consolidado torna-se obsoleto se mudar manifesto/fonte Nivel I, Nivel II, selecao ou hash de artefato. Restauracao de pagina e explicita: preflight vincula pagina e manifests atuais por SHA-256; promocao revalida antes de publicar e marca tratamentos afetados como pendentes. Staging temporario e `promote_stage`/locks protegem os writers que os usam; garantias sao especificas por writer, nao globais.

Tratamento de falha deve seguir estado e manifesto da etapa. Erro de job nao autoriza inferir que houve rollback em todos os artefatos secundarios; os testes de cada writer definem seu contrato transacional.

## 6. Equivalencia e cobertura

Comparar por etapa: mesmas fontes e ordem; manifests de predecessores validos; mesma decisao/candidato; relatorios e status; contagens/hash dos artefatos; integridade fora da mascara permitida; promocao/restauracao e invalidacao; contrato HTTP e estado de job. Nao tratar hashes de manifest como iguais quando timestamp/run id pode variar; comparar campos semanticos definidos pelo writer. A avaliacao visual requer fixture autorizada e nao deve ser substituida por metricas de contagem.

Testes localizados incluem `test_central_v2_textoff_merged.py`, `test_textoff_merged_level1_adapter.py`, `test_textoff_merged_level2.py`, `test_textoff_consolidated.py`, `test_final_consolidated.py`, `test_special_page_restore.py`, `test_textoff_query_snapshots.py`, `test_textoff_artifact_*` e suites de Solidos/Especial/Sommelier. Nao executados nesta etapa.

## 7. Lacunas

- Inventario linha a linha de payload/resposta de todas as rotas e estados de job.
- Inventario fechado de parametros de Sommelier, Check, Solidos e de cada adapter especial; nao inferir a partir do nome.
- Politica completa de retry para todos os jobs, runtimes e arquivos secundarios.
- Versoes efetivas do runtime atual, disponibilidade e hashes dos modelos necessarios.
- Compatibilidade de cada schema legado fora dos casos cobertos por teste.

## Fontes de codigo

`central_v2/backend/routes/textoff_merged_router.py`; `routes/textoff_merged.py`; `orchestration/textoff_merged/{level1_cleaner.py,level2.py,level2_process.py,level2_vision.py,consolidated.py,stages.py,artifact_paths.py,final_consolidated.py,final_consolidated_manifest.py,special_page_restore*.py}`; `processamento/limpeza_baloes/cleaner_v2/`.
