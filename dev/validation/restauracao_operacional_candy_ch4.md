# Restauração operacional — Candy YumYum (Yaoi), Ch. 4, page-049-054.png

Data: 08/10/2026. Execução autorizada pelo usuário somente para esta página.
Nenhum tratamento posterior foi executado. Nenhum commit ou push foi feito.

## Resultado

| Artefato | Antes | Depois |
| --- | --- | --- |
| Página `page-049-054.png` | `573dabb2f7bcac06865a8c29de1587938c8eb9330d6091d063f7794f92ef2ef3` | `5b9492d0b7de07bad4dc2d9b039b7ce2c3c24b1ce4b5e4fbfb0ff5d64b3de76c` |
| Manifesto do Consolidado Final | `592043736ea2dde2c7ced5eff665ee5083ec15351530102295ab584d921d8538` | `36c741e29d20b6bb4db111cb7f822ff7b6088c4f788de30aefd59d6d2b5cf442` |
| Manifesto Especial | `9eccfeaaca6bf646a56ffcb30ba2ed6a5d5fb8f12ddb5bea6a53aa068dd431f2` | `66d9172c5dd099051d1e92e3399a13170038da3938dceb2394b41a530a144e67` |
| Check | `c85c2ab24fa97476662ae365a90c26a46607dc7ab9736956540f954876adef8b` | Igual |

A entrada pré-Artístico `TO_MERGED_NIVEL_II` permaneceu no SHA de destino
`5b9492d0b7de07bad4dc2d9b039b7ce2c3c24b1ce4b5e4fbfb0ff5d64b3de76c`.
A proposta foi conferida antes da execução e novamente dentro da transação,
imediatamente antes da publicação.

Backup completo e verificado:

`/Users/alinesouza/Documents/FominhaData/output/mangago/Candy YumYum (Yaoi)/SPECIAL_PAGE_RESTORE_BACKUPS/Ch. 4/26bcaaa00719481f922b281d681e7179`

Ele contém o capítulo completo do Consolidado Final anterior, seu manifesto,
o Manifesto Especial anterior e `backup.json`. Todos os arquivos referidos pelo
Manifesto Final do backup foram validados por SHA. O diretório tem cerca de 40 MB.

## Isolamento e estados

A auditoria calculou os hashes dos arquivos de todos os capítulos nos estágios
Consolidado Final, Tratamentos Especiais, Check e Pincel antes e após a operação.
Somente estes três arquivos existentes mudaram:

1. `07_CONSOLIDADO_FINAL/Ch. 4/page-049-054.png`
2. `07_CONSOLIDADO_FINAL/Ch. 4/json/final-manifest.json`
3. `SPECIAL_TREATMENTS/Ch. 4/special-treatments-manifest.json`

Além deles, foram criados o backup autorizado e o lock/diretório vazio de
transação. As outras 14 páginas do capítulo, seus registros no Manifesto Final,
as demais ocorrências do Manifesto Especial e os outros capítulos permaneceram
idênticos. Não ficou journal de transação pendente.

| Tratamento | ID | Estado após |
| --- | --- | --- |
| Degradê | `7877387a-f547-48a7-8d61-b232dca35587` | `pending` |
| Degradê | `7ff4a128-821c-405d-8500-0e0ad60011b6` | `pending` |
| Artístico | `14423d52-9633-4305-b30d-b9ec1f5d97de` | `pending` |
| Artístico | `2f1c20d7-13f8-4e9e-9f97-4b6d88f06d6f` | `pending` |
| Artístico | `7b8aed20-b787-4759-bdf2-e79915a2e208` | `pending` |
| Artístico | `c28bbd23-2ac7-4405-b1f0-a4cef799fe07` | `pending` |

As seis ROIs foram comparadas com o Manifesto Especial anterior no backup e
permaneceram iguais. A auditoria técnica em JSON está em
`/private/tmp/candy_restore_operational_audit.json`.
