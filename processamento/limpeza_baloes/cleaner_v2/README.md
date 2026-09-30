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

O relatório `level1-balloon-report.json` registra caixas e métricas dos balões protegidos, componentes adiados, pixels da máscara protegidos e decisões por componente. O `clean-manifest.json` resume os totais de balões transparentes e componentes adiados. Para componentes adiados, o Nível I também salva `*_deferred_text.png`, limitado aos pixels do componente dentro das máscaras dos balões; o Nível II usa essa evidência de texto do Cleaner sem modificar a saída do Nível I.

Na Central V2, Merged Nível I grava em `04_TEXTO_OFF/MERGED_NIVEL_I/<capítulo>/` e não chama o pós-processamento histórico. Legado continua em `04_TEXTO_OFF/MERGED/<capítulo>/` e mantém o processamento combinado anterior.

### Nível II: segunda rodada delimitada por balão

O Nível II usa a união da máscara Cleaner adiada do Nível I com os pixels de texto localizados pelas caixas CRAFT do EasyOCR detector-only. A detecção por CRAFT complementa a máscara; não reconhece nem classifica o idioma. A máscara combinada recebe dilatação elíptica 3×3 e depois 9×9, sempre recortada ao interior segmentado dos balões transparentes. O LaMa recebe 120 px de contexto e somente pixels autorizados são compostos na imagem Nível I. O manifesto registra algoritmo, fontes das máscaras, detector, modelo, dispositivo e contagens.

O A/B manual em `page-179-187.png` mostrou que o Patch Transparente Legado removeu o texto das duas ROIs selecionadas. A máscara CRAFT do primeiro Nível II deixou resíduos; a expansão adicional dessa mesma máscara, mesmo recortada aos balões e com 120 px de contexto, também não resolveu o caso. Isso aponta para cobertura insuficiente na máscara-base, não apenas falta de dilatação ou contexto. A máscara Cleaner adiada pretende corrigir essa lacuna. O Legado não é promovido automaticamente: não usa autorização por balão e depende de ROIs manuais.

As máscaras adiadas são geradas ao reexecutar o Nível I. Resultados Nível II antigos não são considerados atuais após a troca de algoritmo ou de manifesto do Nível I. Os quatro exemplos observados (`page-051-059`, `page-078-083`, `page-156-163` e `page-179-187`) continuam exigindo validação visual; sucesso técnico de integridade não significa remoção visual completa.

O teste de referência do Nível I usou `page-156-163.png` e `page-179-187.png` do capítulo 3 de *Things that deserve to die*. Foram encontrados dois balões transparentes em cada imagem. A checagem da saída confirmou preservação pixel a pixel dos balões e nenhuma máscara Cleaner aplicada dentro deles. As saídas isoladas de teste não substituem o MERGE oficial.

### Limites conhecidos

- A classificação só pode proteger balões encontrados pelo segmentador. Um balão não segmentado não pode ser encaminhado por essa regra.
- Os limiares são conservadores e empiricamente verificados nos exemplos citados; cenas claras e outros estilos de transparência precisam de cobertura adicional.
- Preservação significa manter imagem e máscara da primeira rodada intactas; o processamento especializado dos casos adiados numa segunda rodada ainda precisa ser implementado.
- No perfil `outlined-text.ini`, `ocr_language=detect_box`, `ocr_engine=auto` e `ocr_use_tesseract=False`. Com Tesseract desativado, o Panel Cleaner força MangaOCR, cujo idioma efetivo é japonês. A detecção de idioma por caixa reporta `ja` e `eng`, mas não habilita OCR coreano ou chinês.

`bubble_cleaner.py` permanece no projeto porque outras funcionalidades ainda dependem dele.
