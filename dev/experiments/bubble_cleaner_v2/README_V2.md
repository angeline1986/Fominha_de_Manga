# Bubble Cleaner Experimental V2

Esta versão substitui a hipótese simples da V1 por uma dupla checagem:

1. detectar uma região com geometria compatível com balão;
2. detectar texto com OCR independente;
3. exigir que o polígono do OCR esteja quase todo dentro do interior protegido do balão;
4. preservar qualquer OCR fora do balão, inclusive possíveis onomatopeias;
5. criar a máscara apenas da interseção autorizada;
6. aplicar inpainting somente nessa máscara;
7. validar que nenhum pixel fora da máscara foi alterado;
8. nunca modificar o arquivo de origem.

## Por que EasyOCR nesta V2

Foi escolhido como backend experimental por ter API Python simples e estável para
retornar polígonos + confiança. A arquitetura deixa o OCR isolado em uma classe,
portanto podemos substituir por PaddleOCR posteriormente sem mudar a política de
segurança.

No primeiro uso, EasyOCR pode baixar modelos de reconhecimento.

## Saída por imagem

- `authorized-mask.png`
- `overlay.png`
- `cleaned-preview.png`
- `report.json`

No overlay:

- azul: balão detectado;
- verde: OCR autorizado para limpeza;
- amarelo: OCR preservado/rejeitado.

## Importante

Esta versão continua sendo um experimento. Ela NÃO é integrada ao menu oficial e
NÃO escreve em IMG, MERGE ou PDF.

O aplicador instala em:

`experiments/bubble_cleaner_v2/`

A V1 existente também não é alterada.

## Teste inicial recomendado

Use exatamente a mesma página usada na V1 para comparação visual.

Depois de instalar as dependências:

```bash
python experiments/bubble_cleaner_v2/bubble_cleaner_v2.py \
  "mangago_downloader/output/comix/Emergency_Youth Record Book/IMG/28/page-001.png" \
  --output "bubble_cleaner_output/v2-teste-28"
```
