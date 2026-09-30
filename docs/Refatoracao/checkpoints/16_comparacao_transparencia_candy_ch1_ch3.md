# Comparação de transparência — teste_Candy YumYum, capítulos 1 e 3

Data: 29/09/2026. Testes solicitados pelo usuário sobre as duas pastas MERGE.

## Entradas e preparação

- RIDI / `teste_Candy YumYum`, `Ch. 3/page-034-038.png` (720×5980).
- RIDI / `teste_Candy YumYum`, `Ch. 1/page-024-026.png` (720×3594).

Havia uma imagem por pasta e nenhum Nível I/II V2 para esses capítulos.
Foram feitas cópias verificadas em
`reports/experimentos/textoff_especiais_v2/candy_comparison_2026-09-29/work/`.
O Nível I foi gerado com o executor V2 existente, direcionado exclusivamente
para essa área experimental. O Nível II foi executado por seu worker V2
sem chamar a promoção oficial. Nenhum algoritmo ou parâmetro foi alterado.

As duas imagens e os dois manifestos MERGE oficiais mantiveram seus hashes.
As pastas oficiais de Níveis I/II continuaram ausentes. Os quatro resultados
válidos permanecem em staging. Não houve promoção ou aprovação visual.

## Comparação

As três opções foram executadas para cada imagem:

| Imagem | Nível II | Transparência Legado sobre I | Transparência normal sobre I |
|---|---|---|---|
| Ch. 3 / page-034-038 | Válido; 112.743 pixels alterados | Válido; 159.050 pixels alterados | Sem componentes autorizados |
| Ch. 1 / page-024-026 | Válido; 68.810 pixels alterados | Válido; 65.563 pixels alterados | Sem componentes autorizados |

Nos quatro resultados válidos, a verificação independente confirmou zero
mudanças fora das respectivas máscaras. Diferença de pixels não mede
qualidade visual. As duas falhas da Transparência normal foram registradas
com o motivo retornado pelo domínio: Balloon Authorization não autorizou
nenhum componente, portanto nenhuma reconstrução foi executada.

As ROIs dos especiais são as caixas dos dez balões identificados como
transparentes pelo Nível I: quatro no capítulo 3 e seis no capítulo 1,
ordenadas verticalmente para revisão. Ambos os especiais recebem exatamente
as mesmas ROIs e bytes de entrada. O Nível II usa suas máscaras adiadas
nativas, sem transformar essas ROIs em novo parâmetro de seu algoritmo.

O Nível II usa o MERGE para reconstrução e compõe sobre o Nível I. Os
especiais processam diretamente os bytes do Nível I. Isso faz parte das
receitas comparadas, não de uma troca de entrada acidental. Diferenças não
podem ser atribuídas apenas à dilatação ou apenas ao modelo.

## Observações visuais

O Legado ficou mais completo na remoção de texto em regiões importantes:

- Ch. 3, região 3: o Nível II manteve o texto inteiro do balão que começa
  com “HMM. I DON'T KNOW.”; o Legado o removeu.
- Ch. 1, regiões 2 e 3: o Nível II deixou resíduos/traços visíveis nos
  balões “HERE!” e “HAHA.”; o Legado apresentou remoção mais limpa.
- Ch. 1, região 4: o rabisco no balão permanece nas duas opções.
- Ch. 1, região 6: os traços expressivos abaixo do texto diferem entre as
  reconstruções; precisam de atenção na revisão, além da remoção das letras.

Essas observações favorecem o Legado para remoção nesses casos específicos,
mas não demonstram superioridade universal nem preservação perfeita do
cenário. Texturas e linhas atrás dos balões continuam sujeitas à síntese.

## Artefatos e reprodução

Relatório portátil com dez regiões e páginas completas, 48 PNGs incorporados:
`reports/experimentos/textoff_especiais_v2/candy_comparison_2026-09-29/review/index.html`.
São cerca de 21 MB; não depende de PNGs vizinhos nem de servidor HTTP.

Evidência versionável:
`../evidencias/textoff_especiais/2026-09-29/candy_comparison.json`.
Inclui entradas, hashes, preparação, relatórios do Nível II, execuções dos
especiais, versões/locks, hashes de código/modelos e validação independente.
As duas execuções de Nível II registraram `device=mps` no Mac ARM64.

Ferramentas, todas abaixo de 200 linhas:

- `dev/tools/textoff_prepare_comparison.py`: gera I/II em uma área nova,
  fora da obra; recusa reaproveitar o diretório experimental existente.
- `dev/tools/textoff_special_matrix.py`: executa os especiais. A identidade
  passou a incluir capítulo para não omitir páginas homônimas ao retomar.
- `dev/tools/textoff_threeway_report.py`: gera a comparação solicitada,
  reutilizando o estilo e ampliador do relatório portátil anterior.

Exemplo de geração do relatório a partir das evidências locais:

```sh
central_v2/runtime/textoff/especiais/balao_transparente/.venv/bin/python dev/tools/textoff_threeway_report.py \
  --inventory reports/experimentos/textoff_especiais_v2/candy_comparison_2026-09-29/inventory.json \
  --matrix reports/experimentos/textoff_especiais_v2/candy_comparison_2026-09-29/matrix.json \
  --output reports/experimentos/textoff_especiais_v2/candy_comparison_2026-09-29/review
```

Validação: 20 testes focados passaram, incluindo retomada de capítulos com
nomes de imagem iguais. As 48 imagens incorporadas foram decodificadas e
validadas; 60 painéis presentes, incluindo os estados sem proposta.
