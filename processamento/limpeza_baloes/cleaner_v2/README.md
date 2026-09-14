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

`bubble_cleaner.py` permanece no projeto porque outras funcionalidades ainda dependem dele.
