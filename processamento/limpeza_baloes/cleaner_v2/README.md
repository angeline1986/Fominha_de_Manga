# Cleaner V2 — integração oficial do Texto Off

Motor de limpeza em lote baseado no Panel Cleaner 2.11.11.

A Central usa este módulo em Texto Off — Original e Texto Off — Merged.

Execução oficial: `outlined-text.ini`, `--offline`, timeout total de 900 s e `.venv` isolado.

## Instalação

```bash
cd processamento/limpeza_baloes/cleaner_v2
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`clean-manifest.json` só é promovido após lote completo. O artefato obrigatório é `*_clean`; máscaras são registradas por `masks_total`/`mask_complete`.

## Nível I: preservação de balões transparentes

Depois da saída temporária do Panel Cleaner, o Nível I segmenta os balões usando o modelo de balões Manga109 fixado no código. Para cada interior erodido, `transparency_classifier.py` ignora pixels escuros de texto e mede variação em pixels claros (`gray >= 200`). Classifica a área como transparente quando o desvio-padrão de tons de cinza é pelo menos `9.0` ou quando ao menos `5%` dos pixels amostrados têm saturação HSV acima de `5`. Amostras menores que `500` pixels são inconclusivas e não classificadas como transparentes.

Se qualquer componente da máscara do Cleaner intersectar o interior de um balão transparente, o Nível I preserva o componente inteiro. A decisão conservadora evita deixar franjas de máscara dentro de um balão, ainda que parte do componente esteja fora dele. As demais máscaras só são autorizadas quando pelo menos `90%` de seus pixels estão dentro de um único balão; componentes ambíguos ficam preservados.

O relatório `level1-balloon-report.json` registra caixas e métricas dos balões protegidos, componentes adiados, pixels da máscara protegidos e decisões por componente. O `clean-manifest.json` resume os totais de balões transparentes e componentes adiados. Essa identificação prepara os casos para uma rodada dedicada; não executa ainda um fluxo separado de TextOff Merged Nível II.

O teste de referência usou `page-156-163.png` e `page-179-187.png` do capítulo 3 de *Things that deserve to die*. Foram encontrados dois balões transparentes em cada imagem. A checagem da saída confirmou zero pixels diferentes das fontes e zero pixels de máscara dentro das caixas detectadas. As saídas isoladas de teste não substituem o MERGE oficial.

### Limites conhecidos

- A classificação só pode proteger balões encontrados pelo segmentador. Um balão não segmentado não pode ser encaminhado por essa regra.
- Os limiares são conservadores e empiricamente verificados nos exemplos citados; cenas claras e outros estilos de transparência precisam de cobertura adicional.
- Preservação significa manter imagem e máscara da primeira rodada intactas; o processamento especializado dos casos adiados numa segunda rodada ainda precisa ser implementado.
- No perfil `outlined-text.ini`, `ocr_language=detect_box`, `ocr_engine=auto` e `ocr_use_tesseract=False`. Com Tesseract desativado, o Panel Cleaner força MangaOCR, cujo idioma efetivo é japonês. A detecção de idioma por caixa reporta `ja` e `eng`, mas não habilita OCR coreano ou chinês.

`bubble_cleaner.py` permanece no projeto porque outras funcionalidades ainda dependem dele.
