# M1 — Inventário de persistência da Onda 1

**Data:** 2026-10-23
**Método:** leitura estática de código/documentação e enumeração/hash somente leitura em `output/`. Nenhum tratamento de imagem foi executado.

## Resumo quantitativo

| Medida | Resultado | Escopo/limite |
|---|---:|---|
| Raízes `04_TEXTO_OFF` | 5 | quatro obras e uma árvore de teste em `output/` |
| Arquivos `.json` nessas raízes | 2.285 | arquivos físicos; 25 nomes-base distintos, não 2.285 schemas ou autoridades |
| Arquivos `.json` em todo `output/` | 2.876 | fora do recorte há também manifests de outros fluxos |
| Diretórios `TO_*` | 16 | quatro nomes conhecidos em quatro obras; nenhum em `Teste Candy YumYum` |
| Imagens hashadas | 83.164 | formatos de imagem em `IMG`, `02_MERGE`, `04_TEXTO_OFF` nas cinco obras, mais 74 PNGs de preview |
| Grupos com SHA-256 igual | 24.411 | ao menos dois caminhos físicos por grupo |
| Ocorrências excedentes nos grupos | 57.379 | contagem mantendo uma ocorrência por hash |
| Bytes excedentes teóricos | 39.070.074.956 (~36,38 GiB) | teto matemático, não espaço aprovado para remoção |

O tamanho de `output/` é aproximadamente 60 GB. O valor de bytes excedentes soma, em cada grupo SHA, os tamanhos de todas as ocorrências exceto uma. A varredura inclui inputs, outputs, snapshots e previews, cujos papéis diferem; não mede economia segura nem autoriza deduplicação.

## Árvores de dados observadas

Raízes relativas a `output/`:

- `mangago/Candy YumYum (Yaoi)/FLUXO_SECUNDARIO/04_TEXTO_OFF/`
- `mangago/Benevolent Violence (Yaoi)/FLUXO_SECUNDARIO/04_TEXTO_OFF/`
- `comix/Gazing at you/FLUXO_SECUNDARIO/04_TEXTO_OFF/`
- `comix/Gazing at you_v2/FLUXO_SECUNDARIO/04_TEXTO_OFF/`
- `mangago/Teste Candy YumYum/FLUXO_SECUNDARIO/04_TEXTO_OFF/` (árvore com indicação de teste)

Cada árvore combina nomes legados e destinos novos; também há diretórios de originais, reconhecimento de transparência, previews, backups e tratamentos especiais. A listagem de diretórios/caminhos e contagens por stage está em `m1_matriz_diretorios.md`.

## Fluxo de persistência consolidado

```text
obra/capítulo e IMG
  → Nível I / Mapear / Sommelier
  → Check e ocorrências revisáveis
  → Sólidos e Glass
  → tratamentos especiais e Reset/restauração
  → COMBO_TURBO (quando usado)
  → consolidado lógico → consolidado final
  → comparadores / exportação / PDF e outros consumidores
```

Não é uma transação única. Cada etapa tem writers, manifests, snapshots e regras de promoção próprias. O grafo rastreável por contrato está em `m1_matriz_dependencias.md`.

## Contagem e classes de JSON

Os 2.285 arquivos em TextOff incluem muitas ocorrências por página (por exemplo, `clean-manifest.json`, `level1-balloon-report.json`, `level2-report.json`, `report.json`, `styled-balloon-report.json`, `final-manifest.json`), decisões, relatórios, snapshots e arquivos auxiliares. Foram catalogados também 147 manifests `02_MERGE` e 70 JSONs de preview/staging (2.502 JSONs no total desses três inventários). Ver `m1_matriz_json.md` para produtores, leitores e destino candidato. Os JSONs não foram carregados para bancos nem copiados.

## Conclusões de inventário

1. Há cinco pares de caminhos de estágio que convivem em disco: quatro pastas `TO_MERGED_*` e seus destinos paralelos; o `TO_MERGED_CONSOLIDADO` é input/intermediário do Mapear e também referência lógica, não equivalente ao consolidado final.
2. Os hashes comprovam duplicação byte a byte em escala, mas não determinam equivalência semântica: imagens iguais aparecem como saída de etapa, cópia de consolidação, snapshot de Check e resultado entre `Gazing at you` e `Gazing at you_v2`.
3. Registry ainda declara legacy como autoridade e dual-write. `validated=false` impede tratar o mapeamento como equivalência comprovada.
4. Check, ocorrências, Sólidos, Glass, tratamento, Reset e Combo Turbo têm estado operacional adicional em manifests. Um catálogo só de caminhos/imagens seria insuficiente.
5. Consumidores de exportação, PDF, Central V1 e Auto-Merge devem permanecer compatíveis nesta etapa; não foram migrados.

## Limitações e não verificado

- O plano v3 referenciado pelo pedido não estava disponível no caminho esperado.
- Os schemas, versões e campos de todos os 2.285 JSONs não foram validados registro a registro. A matriz agrupa por função/formato indicado pelo código.
- Hashes cobrem os formatos listados nas fontes `IMG`, `02_MERGE`, `04_TEXTO_OFF` e PNGs do staging de preview; não cobrem PDFs, ZIPs, outros estágios ou armazenamento externo.
- Não foi medida frequência histórica de atualização: o filesystem não fornece essa série e não foram executados tratamentos.
- Não foi feita restauração de backup, execução de pipeline, teste, migration ou alteração de arquivo operacional.
- A lista de JSONs do repositório (20 arquivos visíveis no inventário estático, incluindo configs/evidências/submódulo) não é somada aos 2.285 JSONs operacionais do acervo.

## Pendências para M2

- Aprovar identidade lógica e chaves únicas de provider/obra/capítulo/página, inclusive tratamento de `Gazing at you` versus `_v2`.
- Decidir como manifests ficam como evidência histórica e qual subset migra como estado relacional; definir versão/schema e critérios de `LEGACY_UNVERIFIED`.
- Definir papéis e contexto consumidor das imagens, especialmente Mapear, Sommelier, Check, Glass, especiais e consolidadores.
- Desenhar dependências, invalidação, aprovações, concorrência, Reset, recuperação, retenção e publicação imutável.
- Validar qual cópia do Mapear input é seleção lógica e qual é binário efetivamente consumido; preservar `07_CONSOLIDADO_FINAL` até migrar leitores.
- Definir base representativa e cópias isoladas para equivalência funcional; não presumir que o SHA idêntico prove intercambiabilidade.
- Resolver gaps de proveniência, leitores externos e comportamento em ausência/indisponibilidade do PostgreSQL.

## Relatórios detalhados

- `m0_baseline.md`
- `m1_matriz_json.md`
- `m1_json_inventory.csv` (cada arquivo físico JSON, caminho relativo, bytes e SHA-256)
- `m1_input_json_inventory.csv` (147 manifests de origem `02_MERGE`)
- `m1_preview_json_inventory.csv` (70 JSONs de staging de preview especial)
- `m1_matriz_diretorios.md`
- `m1_matriz_dependencias.md`
- `m1_duplicacoes.md`
- `m1_duplicate_image_groups.csv` (todos os grupos de imagens com SHA-256 repetido)
- `m1_riscos_pendencias.md`
