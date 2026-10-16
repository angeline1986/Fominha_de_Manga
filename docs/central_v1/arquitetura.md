# Arquitetura da Central V1

## Fronteiras

```text
interface_web JavaScript + HTML/CSS
  → HTTP Handler em interface_web/processing_web.py
  → dispatcher/job e estado local do handler
  → orquestracao/* / processamento/*
  → filesystem da obra e manifests do fluxo
```

`processing_web.py` usa `BaseHTTPRequestHandler` e concentra `do_GET()`/`do_POST()`, resolução de provider/obra, catálogo, estado e jobs. A aplicação mistura roteamento e domínio de alguns fluxos; a separação por domínio em `processamento/` é parcial.

## Interface

`interface_web/app.js` inicia a UI. Para Texto Off, os módulos mais diretamente relevantes são `textoff_compare.js`, `textoff_qc_studio.js` e `textoff_special.js`, com CSS próprio e `viewer_core.js`. A estrutura da UI e os eventos não são compartilhados com a V2.

## HTTP e processos

`processing_web.py` atende catálogo/estado, comparação e Nível III, especiais, jobs e mídia, além de outros domínios que não pertencem a Limpeza de Balões. A ação geral passa pelo handler de POST e dispatcher local; ações especiais têm rotas explícitas e separam `process_special_image()` de `promote_special_result()`.

Referências de função atuais: `do_GET`, `do_POST`, `do_clean`, `do_clean_merged`; endpoints textoff estão distribuídos no bloco de roteamento próximo ao fim do handler. A extração endpoint → payload → função ainda não está completa; não usar lista de endpoints histórica como contrato integral.

## Domínio e execução

- Merged chama `orquestracao/textoff/merged.py` que usa o motor Cleaner compartilhado.
- Correção assistida passa por `textoff_level3.py`, analyzer e correction.
- Especial chama adapters sob `processamento/limpeza_baloes/`.

## Persistência

V1 escreve arquivos e manifests sob a obra, em `FLUXO_SECUNDARIO/04_TEXTO_OFF/`, além de estado/registro de processamento. Paths e schemas pertencem a cada módulo; não se assume compatibilidade com a organização canônica V2.

## Fonte e lacunas

Fonte atual: `interface_web/processing_web.py`, `orquestracao/textoff/merged.py` e consumidores acima. A divisão completa de endpoints, estados de job, exceções HTTP e transações por versão de API permanece **não verificada**.
