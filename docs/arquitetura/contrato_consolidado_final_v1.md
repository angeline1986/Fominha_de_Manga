# Contrato v1 do Consolidado Final

**Escopo:** Central V2, uma obra e um capítulo por vez. **Formato publicado:** `textoff_consolidado_final_manifest_v1`, `version: 1`. Este documento descreve o formato vigente; mudanças de layout pertencem a [BL-01](../gestao/tickets/central_v2/BL-01.md) e [BL-02](../gestao/tickets/central_v2/BL-02.md). A origem de exportação foi aprovada no [ADR-001](adr/ADR-001-origem-exportacao-texto-off.md).

## Árvore e autoridade

```text
<obra>/FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL/
└── <capítulo>/
    ├── <página>.png                 imagem final vigente
    ├── json/final-manifest.json     manifesto v1 do capítulo
    ├── history/<sha256>/<página>.png  versão anterior arquivada, quando disponível
    ├── laboratorio/<run_id>/<página>.png  cópia da aplicação do Laboratório, quando disponível
    ├── clean/                       pasta auxiliar que pode existir
    └── mask/                        pasta auxiliar que pode existir
```

O PNG na **raiz do capítulo** é o resultado final publicado. `clean/` e `mask/` podem ser criadas pelo preparador genérico de artefatos; não são fonte de imagens finais nem requisito de leitura ou exportação. `json/` contém o manifesto obrigatório para leitores que validam o Final. `history/` e `laboratorio/` são criadas conforme as operações de aplicação e restauração do Laboratório. Nenhum consumidor deve inferir que essas pastas opcionais existam ou que todo evento antigo possua PNG arquivado.

O exportador usa apenas PNGs diretamente em pastas de capítulo **numéricas** de `07_CONSOLIDADO_FINAL/` e copia para `raws_semi-clean/<capítulo>/`. Ele não lê `final-manifest.json` em cada exportação; confere o SHA-256 dos arquivos entre simulação e cópia. `textoff_merged` é somente a chave da API de exportação, não uma pasta de origem. O capítulo e a página devem permanecer identificáveis sem consultar pastas auxiliares.

## Manifesto e referências

`json/final-manifest.json` contém `schema`, `version`, `provider`, `manga`, `chapter`, `source_intermediate_manifest_sha256`, `updated_at`, `page_count`, `pages` e `history`. `pages` mapeia o nome do PNG ao registro vigente. Cada registro produzido contém `page`, `artifact`, `sha256` e `origin`; os campos de tratamento e procedência variam conforme a origem. `artifact` é **exatamente o nome do arquivo na raiz**, por exemplo `page-001.png`, e não `clean/page-001.png` nem um caminho absoluto. `sha256` é o digest hexadecimal SHA-256 dos bytes desse PNG.

O produtor grava `page_count` como tamanho de `pages` e preserva `source_intermediate_manifest_sha256` nas promoções. O leitor oficial verifica schema v1, versão, identidade da obra e capítulo, `artifact == page`, caminho restrito ao capítulo, existência e SHA-256 de cada PNG listado. Ele **não** verifica `page_count` nem arquivos extras na pasta. A comparação Antes & Depois exige também que o conjunto de páginas do manifesto corresponda ao conjunto comparado. A exportação confia na varredura dos PNGs elegíveis e em seus próprios hashes; validação de manifesto por exportação exigiria outro contrato.

## Histórico e procedência

Ao substituir uma página, o manifesto mantém seu registro anterior em `history[]` como `superseded`, com `page` e `superseded_at`. Eventos produzidos pela montagem automática e pelos Pincéis podem conter apenas metadados; isso documenta a linhagem, mas não garante que os bytes anteriores sejam restauráveis.

Ao aplicar um resultado do Laboratório, a versão anterior é copiada para `history/<sha256>/<página>.png` e o resultado escolhido para `laboratorio/<run_id>/<página>.png`. O novo registro em `pages` usa `origin: LABORATORIO` e registra tratamento, execução, origem e hash da fonte, snapshot, revisão visual e transação. O evento histórico inclui `reason: laboratorio_apply`, `archived_artifact` e `archived_sha256`. A restauração só oferece revisões com arquivo histórico cujo caminho, registro e SHA-256 conferem; ela arquiva também a versão substituída e registra `reason: laboratorio_restore` e `restored_revision_id`. Aplicações repetidas acrescentam eventos sem apagar a sequência anterior.

As publicações usam estágio temporário e verificação antes da troca; aplicação e restauração do Laboratório usam o diário transacional. Um manifesto sem PNG correspondente, com hash divergente ou identidade incompatível não é uma versão final válida para esses leitores.

## Compatibilidade atual e regras para futura migração

| Caso | Leitura atual |
| --- | --- |
| Final v1 no caminho canônico, PNG na raiz e manifesto em `json/` | Suportada pelos leitores oficiais e pelo exportador, dentro dos limites acima. |
| `clean/` ou `mask/` vazias no Final v1 | Toleradas; não mudam a localização do PNG vigente. |
| Histórico antigo sem `archived_artifact` verificável | Metadados legíveis; restauração dessa revisão indisponível. |
| Manifesto final plano fora de `json/` ou PNG final apenas em `clean/` | Não suportado como Final v1. |
| Antigo diretório `04_TEXTO_OFF/CONSOLIDADO_FINAL/` | Não há garantia de leitura somente leitura: `stage_chapter()` pode movê-lo para `07_CONSOLIDADO_FINAL/` se o destino faltar. O exportador não o consulta. |

O fallback de `artifact_paths.py` para referências planas e o registro de migração de `TO_MERGED_CONSOLIDADO` pertencem a **outras etapas**; não ampliam o contrato do Final v1. Uma futura migração do Final exige: inventariar consumidores e arquivos legados; aprovar a mudança de layout em ADR; disponibilizar leitura compatível sem movimentação implícita; testar formatos antigo e novo, inclusive exportação, histórico e restauração; comparar conjunto de páginas e SHA-256 antes e depois; preservar manifesto, procedência e backups; e só então habilitar publicação atômica no novo formato. Este BL-03 não executa a migração nem autoriza remover pastas.

## Verificação do contrato

- `dev/tests/test_final_consolidated.py`: montagem, promoção e preservação do histórico.
- `dev/tests/test_exportacao.py`: origem física do PNG e cópia protegida por hash.
- `dev/tests/test_central_v2_laboratorio_final_apply.py`: `artifact` plano, hash, exportação, snapshot e aplicação repetida.
- `dev/tests/test_central_v2_laboratorio_final_history.py`: revisão arquivada e restauração.
