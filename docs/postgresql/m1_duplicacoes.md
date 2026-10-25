# M1 — Duplicações físicas por hash

**Escopo:** arquivos regulares nas árvores `IMG/`, `FLUXO_SECUNDARIO/02_MERGE/` e `FLUXO_SECUNDARIO/04_TEXTO_OFF/` das cinco obras com árvore TextOff, mais PNGs em `reports/experimentos/textoff_especiais_v2/`. Extensões PNG, JPG, JPEG, WebP, BMP, TIF e TIFF. Cada arquivo foi lido em blocos para SHA-256; nenhum conteúdo foi regravado.

## Resultado

| Métrica | Valor |
|---|---:|
| Imagens hashadas | 83.164 |
| SHA-256 distintos | 25.785 |
| Grupos com conteúdo idêntico em mais de um caminho | 24.411 |
| Ocorrências excedentes sobre uma por grupo | 57.379 |
| Bytes excedentes pela regra “guardar uma por hash” | 39.070.074.956 (~36,38 GiB) |

O número é volume byte a byte repetido no recorte, não espaço que possa ser removido. A regra de manter somente uma ocorrência ignora semântica e foi usada apenas para estimar o teto. Não foi feita deduplicação, hardlink, movimentação ou exclusão.

O arquivo `m1_duplicate_image_groups.csv` contém todos os grupos repetidos: SHA-256, bytes por arquivo, número de ocorrências e caminhos com prefixo `output/` ou `repository/` conforme a origem.

## Exemplos de duplicação confirmada

1. Páginas idênticas entre `TO_MERGED_NIVEL_I/<cap>/clean/` e `01_AUTO_CLEANER/<cap>/clean/`: efeito compatível com espelhamento do registry.
2. Saídas iguais em `07_CONSOLIDADO_FINAL/<cap>/` e em Nível I: seleção/publicação pode preservar byte idêntico com papéis distintos.
3. Cópias idênticas entre `comix/Gazing at you/` e `comix/Gazing at you_v2/`: são árvores/identidades de obra distintas até prova em contrário.
4. Alguns snapshots `04_AUTO_CLEANER_CHECK/<cap>/images/` também coincidem com arquivos publicados; ainda assim podem sustentar uma decisão vinculada à revisão analisada.
5. A comparação de `IMG`, `02_MERGE` e PNGs de preview inclui fontes upstream e staging; igualdade de hash entre esses papéis não prova permissão de substituição.

## Classificação e decisão

| Classe | Evidência necessária | Status nesta auditoria |
|---|---|---|
| Cópia exata por `dual_write` | SHA igual, mapeamento do registry e papel igual | provável em pares legacy/target; não autoriza remoção |
| Histórico legítimo | run, revisão, publicação anterior ou consumidor de restore | preservar até validar dependências |
| Imagem transformada | SHA diferente; relação de proveniência no manifest | não é duplicata byte a byte |
| Intermediário necessário | leitor identificado ou dependência de máscara/relatório | preservar |
| Temporário | run encerrado e política de retenção definida | não verificado |
| Órfão | ausência de leitores atuais e histórico/proveniência examinados | nenhum declarado órfão por SHA isolado |

**Candidatos de auditoria futura:** pares legacy/target que tenham SHA igual e correspondência de contrato; snapshots idênticos a outputs somente depois de confirmar papel, revisão e consumidores; cópias entre obras distintas apenas após comprovar identidade lógica comum. Nenhum item é classificado como `REMOVER` autorizado.

## Limites do cálculo

- Hash igual prova identidade de bytes, não identidade de página/revisão, legitimidade da fonte ou dispensabilidade.
- Hash diferente não prova imagem visualmente distinta (metadados/encoding podem variar).
- Imagens fora das árvores enumeradas, PDFs, máscaras em outros estágios, arquivos compactados e armazenamento externo não foram incluídos.
- O inventário foi feito numa única fotografia; jobs simultâneos poderiam alterar árvores. Não houve processo do app em execução por este diagnóstico.
