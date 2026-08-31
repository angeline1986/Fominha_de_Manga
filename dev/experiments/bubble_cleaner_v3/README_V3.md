# Bubble Cleaner Experimental V3

V3 mantém V1 e V2 intactas e troca o ponto fraco observado na V2: a detecção
geométrica de balões.

## Detector especializado

A V3 usa o modelo público `Kiuyha/Manga-Bubble-YOLO`, treinado em 5.595 páginas
com Manga109-s e páginas MangaDex em vários idiomas. O modelo Nano publicado
tem 2,4M parâmetros e checkpoint de aproximadamente 5,3 MB.

O download é feito pelo `huggingface_hub` no primeiro uso e o SHA256 do
checkpoint é validado antes da inferência.

## Barreiras antes de apagar

1. detector YOLO especializado precisa encontrar a região;
2. a região precisa passar por um gate visual independente;
3. EasyOCR precisa detectar texto;
4. o OCR precisa estar >= 94% contido no interior protegido da detecção;
5. confiança OCR >= 0,60;
6. máscara final é apenas a interseção autorizada;
7. qualquer OCR fora da região é preservado;
8. pós-checagem exige zero alteração fora da máscara;
9. original nunca é sobrescrito.

Portanto uma onomatopeia detectada por OCR, mas fora de uma região aprovada,
continua preservada.

## Saída

- `authorized-mask.png`
- `overlay.png`
- `cleaned-preview.png`
- `report.json`

Overlay:
- azul: detecção especializada aprovada pelo gate;
- magenta: detecção especializada rejeitada pelo gate;
- verde: OCR autorizado;
- amarelo: OCR preservado.

## Teste recomendado

```bash
python experiments/bubble_cleaner_v3/bubble_cleaner_v3.py \
  "mangago_downloader/output/comix/Emergency_Youth Record Book/IMG/28/page-001.png" \
  --output "bubble_cleaner_output/v3-teste-28"
```

Esta é uma feature experimental. Não há integração com menu, IMG, MERGE ou PDF.
