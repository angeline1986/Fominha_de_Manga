# Restauração isolada: Candy YumYum (Yaoi), Ch. 4, page-049-054.png

Data: 08/10/2026. Nenhuma alteração foi publicada na obra operacional.

## Ponto autenticado

O Consolidado Final registra `AUTO_CLEANER_TRANSPARENCIA` antes do Artístico, com
SHA-256 `5b9492d0b7de07bad4dc2d9b039b7ce2c3c24b1ce4b5e4fbfb0ff5d64b3de76c`.
O arquivo `TO_MERGED_NIVEL_II/Ch. 4/clean/page-049-054_clean.png` e seu manifesto
de estágio foram verificados na cópia. A cadeia no Consolidado Final segue
Artístico → Degradê até a imagem vigente. A restauração não depende da saída
Artística antiga nem de máscaras de autoria por ocorrência.

## Ensaio em cópia isolada

Cópia: `/private/tmp/candy-page-reset-reviewed-ctjlu40l/mangago/Candy YumYum (Yaoi)`.
Foi copiado o capítulo completo do Consolidado Final, além do Check, Manifesto
Especial, manifesto do Nível II e imagem pré-Artístico necessários. O fluxo
`inspect` → `restore` foi executado apenas nessa cópia.

| Verificação | Resultado |
| --- | --- |
| SHA final antes | `573dabb2f7bcac06865a8c29de1587938c8eb9330d6091d063f7794f92ef2ef3` |
| SHA após restauração | `5b9492d0b7de07bad4dc2d9b039b7ce2c3c24b1ce4b5e4fbfb0ff5d64b3de76c` |
| Páginas cujos hashes mudaram | Apenas `page-049-054.png` |
| Pixels diferentes entre antes/depois | 170.343 de 4.896.720 |
| Ocorrências nessa página | Quatro Artísticos e dois Degradês, todos `pending` após reset |
| Outras páginas e ROIs aprovadas | Preservadas |
| Backup | Capítulo completo do Consolidado Final e Manifesto Especial; hashes conferidos |
| Artefatos operacionais | Página, Manifesto Final, Manifesto Especial e Check com hashes inalterados |

A imagem anterior está em
`SPECIAL_PAGE_RESTORE_BACKUPS/Ch. 4/76297e14a0864b7ba7de815d40478559/consolidado_final/page-049-054.png`
dentro da cópia. A restaurada está em
`FLUXO_SECUNDARIO/04_TEXTO_OFF/07_CONSOLIDADO_FINAL/Ch. 4/page-049-054.png`.
Uma comparação local com rolagem sincronizada está em
`/private/tmp/candy-page-reset-reviewed-ctjlu40l/comparacao-restauracao.html`.
Na visão geral, o texto anterior reaparece nos balões tratados, como esperado
ao voltar ao estado pré-Artístico. A revisão visual humana detalhada permanece
pendente antes de autorizar a operação na obra real.

## Garantias e testes

- Backend: `python3 -m unittest dev.tests.test_special_page_restore` — 8/8.
  Cobre linhagem, SHA obsoleto, prévia de ambas as imagens, confirmação explícita,
  restauração de uma só página, preservação de ROI/outras ocorrências, backup e
  rollback após falha simulada de publicação e mudança do Check imediatamente
  antes da publicação.
- Tratamentos especiais: 70/70 testes focados passaram.
- Interface: prévia com duas imagens e confirmação separada; 15/15 testes focados
  passaram. Regressão frontend completa: 113/114 passaram; a única falha do menu
  Limpeza de Balões já havia sido reproduzida em `develop` limpo.
- Regressão Python da Central V2: 134 testes, 35 falhas e 5 erros, mesmas classes
  previamente classificadas. As 35 falhas são anteriores a esta correção;
  os cinco erros HTTP do sandbox passaram em rerun fora dele (5/5).

## Publicação operacional

Não realizada. A interface exige prévia carregada e confirmação explícita.
O servidor verifica os SHAs da página, manifestos, Check e origem histórica
antes de preparar a transação e novamente antes de publicar. Se qualquer valor
mudar desde esta inspeção, uma nova prévia será necessária. A operação real
depende de aprovação após revisão visual das duas imagens da cópia.
