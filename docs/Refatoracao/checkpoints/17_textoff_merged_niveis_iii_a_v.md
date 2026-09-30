# TextOff Merged — Níveis III, IV e V

Estado atual (30/09/2026): o Nível III foi retirado da interface e do executor
da Central V2 após avaliação insatisfatória. O histórico experimental abaixo
foi preservado; somente IV e V permanecem disponíveis no fluxo.

Data: 30/09/2026

## Contrato de entrada

Os níveis III, IV e V ficam elegíveis quando o capítulo tem manifesto de
Merged Nível I íntegro e seus artefatos correspondem ao MERGE. Não consultam
nem exigem manifesto do Nível II. Todos partem da imagem limpa e das máscaras
de texto adiado do Nível I.

## Tratamentos

- **III — Ajuste fino:** usa a máscara de texto adiado do Nível I, dilata 3×3
  e 9×9 dentro do balão rotulado e permite proteger pixels com pincel antes do
  LaMa. O runtime é o da Transparência normal.
- **IV — Transparência normal:** aplica a receita normal à máscara autorizada
  do Nível I, limitada à área dos balões detectados. Usa
  `balao_transparente/.venv`.
- **V — Transparência Legado:** parte do texto adiado do Nível I, aplica as
  dilatações 3×3 e 9×9 sem recortar a expansão no contorno do balão. Usa
  `balao_transparente_legado/.venv`.

Os três são previews não promovíveis; as imagens e manifestos oficiais não são
substituídos. O executor confere a identidade da imagem e das máscaras, registra
runtime/hash/validação e confirma zero alterações fora da máscara de saída.

## Seleção manual

Uma ROI manual é compatível com esse contrato. Ela pode filtrar quais balões
identificados pelo Nível I entram no tratamento. No IV, a máscara continua
recortada ao rótulo do balão. No V, a dilatação legada pode ultrapassar esse
contorno; se for preciso um limite rígido, a máscara final também deve ser
intersectada com a ROI. A tela atual seleciona capítulos e páginas; IV/V usam
as ROIs derivadas das caixas do Nível I. A seleção manual por página fica como
extensão pendente.

## Ensaio Candy YumYum

Entradas: `Ch. 1/page-024-026.png`, `Ch. 3/page-034-038.png` e
`Ch. 4/page-049-053.png`. Os três tinham Nível I válido. III foi executado
com pincel de proteção em cada imagem; IV e V foram executados nas venvs
dedicadas. Todos os nove previews passaram na validação técnica, com zero
pixels alterados fora da máscara. Isso não substitui a revisão visual. As
coordenadas do pincel usadas no teste exercitam o controle; não marcam o dedo
da imagem enviada anteriormente.

Comparação para revisão: `reports/experimentos/textoff_merged_special_levels/review/index.html`.
Relatórios de execução e hashes ficam ao lado, em
`reports/experimentos/textoff_merged_special_levels/`.
