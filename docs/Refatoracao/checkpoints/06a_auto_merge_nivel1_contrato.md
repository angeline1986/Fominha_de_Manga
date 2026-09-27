# Auto-Merge Nível I — contrato observado na V1

Data: 2026-09-27. Auditoria da árvore de trabalho, HEAD de referência
`235b25d2f96284fbe047c9dabe6972639c6eb64b`.

## Escopo

V1 somente como referência: nenhum código movido, copiado para a V2 ou alterado.
O domínio existente também permanece intacto. Testes e sondas executam somente
sobre imagens sintéticas em diretórios temporários, sem iniciar a Central V1.

Este documento descreve o comportamento atual; não transforma limitações
observadas em decisões automaticamente aprovadas para a V2.

## Entrada e fluxo

```text
seleção de provider / obra / capítulos
→ POST /api/action {action: "merge", provider, manga, chapters}
→ make_job → run_job → do_merge
→ image_stitcher.merge_chapter(output_dir_override=AUTO_MERGE)
→ conclusão: manifesto de estágio → validação / promoção → MERGE oficial
→ falha: classificação de segmentos → salvamento parcial → residual
→ resultado por capítulo e consulta GET /api/job/{id}
```

Referências em `interface_web/processing_web.py`:

| Símbolo / linha | Responsabilidade observada |
| --- | --- |
| `manga_path`, 34; `chapters`, 109; `selected`, 1855 | Resolver seleção |
| `make_job`, 1846; `run_job`, 1861 | Fila, exclusão, dispatcher e eventos |
| `do_merge`, 2063 | Execução por capítulo e agregação dos resultados |
| `_analyze_merge_partition`, 203 | Classificação e retomada após região extensa |
| `_materialize_level1_resolved`, 276 | Renderizar trechos resolvidos e persistir estágio |
| `set_merge_failure`, 361 | Tentativa e residual persistidos |
| `_promote_level1_complete`, 450 | Compor promoção a partir do manifesto Nível I |
| `_promote_stage_composition`, 404 | Validar cobertura, copiar e reconhecer MERGE |
| `_auto_merge_summary_payload`, 2015 | Projetar metadados persistidos no resultado |
| `_merge_manifest_state`, 1311; `row_state`, 1713 | Projeção da tela, incluindo outros níveis |

O POST retorna 202 com `job_id` e `request_id`. A validação da seleção ocorre
no job; um pedido aceito pode depois terminar com erro de provider/capítulo.
Providers atuais: `comix`, `mangago`, `ridi`. Seleção vazia é rejeitada.
Os nomes são resolvidos entre capítulos existentes de `IMG`, sem aceitar um
caminho arbitrário informado como capítulo.

## Algoritmo reutilizável

`processamento/unificacao_imagens/image_stitcher.py` já fornece:

- `list_pages` (162): somente `page-NNN` nas extensões png/jpg/jpeg/webp;
- `analyze_chapter` (355): dimensões, faixas brancas e coordenadas globais;
- `choose_cuts` (434): seleção V3 dos cortes seguros;
- `render_chunks` (527) e `validate_merge_outputs` (588);
- `merge_chapter` (638): execução completa, destino alternativo e progresso;
- `merge_output_dir` (178), nomenclatura e rejeição de colisões;
- `is_chapter_merged` (191): reconhecimento físico do MERGE oficial.

Defaults protegidos: alvo 7000; busca antes/depois 1800/2500; altura mínima
3000; máxima 12000; faixa branca mínima 150; white ratio 0.985; limiar claro
245; amostragem 256. A V2 deve consumir esses defaults, não manter cópias.

Altura acima do máximo sem corte elegível interrompe `merge_chapter` antes
da renderização. O domínio não retorna nesse caso um resultado parcial pronto.

## Autoridade e caminhos

Todos os caminhos abaixo são relativos à obra:

| Artefato | Caminho |
| --- | --- |
| Fonte | `IMG/<capítulo>/page-NNN.ext` |
| Estágio Nível I | `FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/AUTO_MERGE/<capítulo>/` |
| Manifesto do estágio | `auto-merge-manifest.json`, dentro do estágio |
| Tentativa / partição | `FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/MERGE_STATUS/<capítulo>/merge-attempt.json` |
| MERGE oficial | `FLUXO_SECUNDARIO/02_MERGE/<capítulo>/merge-manifest.json` |
| Eventos | `FLUXO_SECUNDARIO/PROCESSING_LOG/processing-events.jsonl` |

### Conclusão completa

1. Se já há MERGE fisicamente reconhecido, remover marcador de falha e pular.
2. Caso contrário, a V1 remove o diretório AUTO_MERGE anterior e executa V3 nele.
3. Envolve o manifesto V3 em `auto_merge_level1_complete`, schema 1:
   `chapter`, `source_dir`, `output_dir`, `total_height`, `artifacts`,
   `pending_segments: []`, `coverage.auto_segments` e `v3_manifest`.
4. Remove o `merge-manifest.json` intermediário do estágio.
5. Valida cobertura contínua, arquivos, alturas e larguras antes de promover.
6. Copia os artefatos, sem renderizá-los novamente, ao destino oficial.
7. Grava `merge_auto_level1_composition_v1`, `status: approved`, outputs,
   validation, safety e composition com `scope: level1_complete`.
8. Exige reconhecimento físico final. Falha remove o destino recém-criado.

A promoção recusa qualquer destino oficial já existente, inclusive inválido.
Não sobrescreve esse destino. Conclusão exige cobertura de 0 até a altura total,
sem lacuna ou sobreposição e com dimensões físicas compatíveis.

### Resultado parcial / falha

`set_merge_failure` persiste tentativa schema 2 e, quando disponível, partição
`whitespace_v3_level2_partition`, schema 2, inicialmente não validada no Nível II.
Ela contém segmentos resolvidos/pendentes, intervalos, páginas e `source_spans`.

A classificação usa análise e cortes V3, mas a busca de uma faixa posterior
à região extensa e a retomada estão implementadas na V1. Trechos resolvidos
são materializados; o estágio recebe `auto_merge_level1_resolved_segments`,
schema 1, com artifacts, pending_segments e coverage.auto_segments.

Mesmo sem artefatos resolvidos pode existir manifesto com residual. As páginas
que intersectam uma região pendente não são contadas como totalmente resolvidas.
Nomes de PNG seguem os intervalos de páginas; colisões falham explicitamente.

## Jobs e resultados

O job transita `queued → running → done/error`. `done` significa que o lote
terminou: capítulos individuais ainda podem ter `partial` ou `error`.
`OPLOCK` serializa jobs no processo V1; até três capítulos executam em paralelo.
Resultados retornam na ordem da seleção, não na ordem de término.

Progresso por capítulo: prepare 1%; análise 5–75%; cortes 78%; render 82%;
validação 97%; done 100%. Progresso global agrega capítulos de forma monotônica.
Finalização de capítulo com erro também encerra seu progresso.

| Resultado | Significado |
| --- | --- |
| `ok` | Estágio completo promovido e reconhecido |
| `skipped` | MERGE oficial já reconhecido |
| `partial` | Falha com ao menos um artefato parcial salvo |
| `error` | Falha sem artefato parcial salvo, inclusive impedimento de promoção |

Campos de resultado: `chapter`, `status`, `message`, `auto_merge_saved`,
`auto_merge_folder`, `auto_merge_files`, `pending_files`,
`pending_segments_count`, `residuals`, `reason_codes`, `next_stage`.
Conclusão também informa `merged_images`. Residual existente aponta para
Nível II; erro sem residual aponta para verificação da ocorrência.

Eventos incluem request/job/action, seleção, timestamps, estado e manifests
antes/depois, hashes disponíveis, duração e resultado. A observabilidade não
substitui o manifesto como autoridade.

## Projeção da interface

A V1 oferece seleção, busca, paginação, filtros, progresso, resultado e pasta
de saída. O resumo distingue completo, parcial, já concluído e requer atenção.

`row_state` combina níveis I–V, Review e outros fluxos. Não é um DTO específico
do Nível I. `_merge_manifest_state` lê metadados sem abrir pixels;
`is_chapter_merged` faz reconhecimento físico. Essas operações não são
intercambiáveis e precisam de nomes e contratos distintos na V2.

Ver [decisões e evidências](06b_auto_merge_nivel1_plano_e_evidencias.md).
