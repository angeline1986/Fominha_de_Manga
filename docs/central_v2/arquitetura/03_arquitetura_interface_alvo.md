# Arquitetura-alvo --- Central V2

**Status:** arquitetura-alvo aprovada para migração progressiva\
**Estratégia:** construir a Central V2 em paralelo à Central atual e
descontinuar a implementação legada somente após equivalência funcional
validada.

## 1. Decisão arquitetural

A estratégia principal deixa de ser desmontar progressivamente
`interface_web/processing_web.py`.

A Central atual passa a ser a **baseline operacional e referência
comportamental** durante a migração. A nova aplicação nasce isolada em
`central_v2/`, consumindo os domínios existentes sem copiar algoritmos,
thresholds, manifests ou regras de autoridade.

Não criar `processing_web_v2.py` nem copiar o monólito atual para
refatorá-lo depois.

``` text
Central atual (legada)
        │
        │ referência comportamental
        │ migração por fluxo
        ▼
Central V2
        │
        ├── transporte / UI / jobs / projeções
        ▼
orquestracao/
        │
        ▼
processamento/
        │
        ▼
manifests / SHA / artefatos autoritativos
```

## 2. Fronteiras da solução

### 2.1 Central legada

`interface_web/` permanece operacional durante a migração.

-   `processing_web.py` não é desmontado como pré-requisito da V2.
-   Correções indispensáveis podem continuar ocorrendo.
-   Não adicionar novas responsabilidades quando a feature puder nascer
    na V2.
-   A implementação atual serve como referência de comportamento e
    contratos durante a migração.

### 2.2 Central V2

A V2 fica fisicamente isolada:

``` text
central_v2/
├── backend/
│   ├── server.py
│   ├── routes/
│   ├── jobs/
│   └── state/
├── runtime/
│   └── textoff/
│       ├── merged_nivel_i/.venv/
│       ├── merged_nivel_ii/.venv/
│       ├── legado/.venv/
│       ├── correcao_assistida/
│       └── especiais/
└── frontend/
    ├── _app/
    │   ├── api/
    │   ├── state/
    │   └── router/
    ├── _shared/
    ├── _shell/
    ├── visao_geral/
    ├── processamento/
    ├── balanceamento/
    ├── gerar_pdf/
    ├── texto_off/
    └── exportar_arquivos/
```

Os ambientes especializados de processamento da V2 ficam sob
`central_v2/runtime/`, organizados por feature. Os diretórios `.venv` são
locais e ignorados pelo Git; requisitos, resolvedor de runtime e baselines
reproduzíveis são versionados. A migração preserva as venvs atuais usadas
pela Central V1, cria cada ambiente V2 separadamente, valida o worker e só
então direciona a feature para o novo runtime. O mapa operacional completo
de Texto Off está em `01_ambientes_virtuais.md`, seção 15.

### 2.3 Orquestração

`orquestracao/` representa casos de uso e coordenação entre domínios.

``` text
orquestracao/
├── menu.py
├── proc_merge.py
├── proc_textoff.py
├── proc_balance.py
├── proc_pdf.py
└── proc_export.py
```

A orquestração pode decidir sequência, pré-condições e qual serviço
chamar, mas não deve duplicar algoritmos do domínio.

### 2.4 Domínios existentes

`processamento/` continua sendo a camada que executa regras
especializadas:

``` text
processamento/
├── unificacao_imagens/
├── merge_manual/
├── balanceamento/
├── limpeza_baloes/
├── validacao_imagens/
├── pdf_original/
└── exportacao/
```

Os algoritmos e contratos protegidos permanecem nesses módulos.

### 2.5 Artefatos e autoridade

Manifests, hashes, artefatos oficiais e relações de predecessor fazem
parte do contrato funcional.

A V2 deve **consumir e preservar** a autoridade existente. Não deve
criar uma segunda interpretação concorrente para determinar conclusão,
residual, promoção ou elegibilidade.

## 3. Fluxo de dependências

``` text
┌─────────────────────────────────────┐
│            CENTRAL V2               │
│ HTTP · UI · DTO · Jobs · navegação  │
└──────────────────┬──────────────────┘
                   ▼
┌─────────────────────────────────────┐
│            ORQUESTRAÇÃO             │
│ casos de uso · sequência · decisão  │
└──────────────────┬──────────────────┘
                   ▼
┌─────────────────────────────────────┐
│              DOMÍNIO                │
│ merge · textoff · balance · PDF ... │
└──────────────────┬──────────────────┘
                   ▼
┌─────────────────────────────────────┐
│       ARTEFATOS / AUTORIDADE        │
│ manifests · SHA · filesystem        │
└─────────────────────────────────────┘
```

Dependências apontam para baixo. O domínio não conhece HTTP, frontend ou
componentes da Central.

## 4. Frontend V2

### 4.1 Infraestrutura da aplicação

`_app/` contém infraestrutura transversal da aplicação, não componentes
visuais reutilizáveis:

``` text
frontend/_app/
├── api/
│   └── client.js
├── state/
│   └── store.js
└── router/
```

API client, roteamento e estado global **não pertencem a `_shared/`**.

### 4.2 Componentes compartilhados

`_shared/` contém componentes reutilizáveis e independentes:

``` text
frontend/_shared/
├── table/
├── zoom/
├── viewer/
├── pager/
├── toolbar/
├── filter/
├── focus/
├── modal/
├── feedback/
├── layout/
└── tokens/
```

`_shared/` não pode virar um novo monólito.

### 4.3 Regra das páginas

A página compõe componentes e mantém apenas comportamento específico.

``` text
am3_page.js
├── usa _shared/table/
├── usa _shared/filter/
├── usa _shared/pager/
├── usa _shared/toolbar/
└── contém somente comportamento específico do Nível III
```

A mesma regra vale para CSS: tokens, layout e componentes compartilhados
primeiro; CSS local apenas para particularidades reais da página.

## 5. Navegação-alvo

### Visão Geral

-   Resumo
-   Validar imagens

### Processamento

-   Auto Merge
    -   Nível I
    -   Nível II
    -   Nível III
    -   Nível IV
    -   Nível V
-   Revisão
    -   Revisão Merge
    -   Revisão Merge V2
-   Merge Manual
    -   Validar
    -   Novos Merges

### Balanceamento

-   Validar
-   Novos Cortes

### Gerar PDF

-   Original
-   Merge

### Texto Off

-   Original
-   Merged
-   Comparar resultados
-   Correção assistida
-   Especiais

### Exportar arquivos

-   Exportar

## 6. Regras de engenharia

1.  **Máximo de 200 linhas por arquivo de código da Central V2.**
    Limite obrigatório definido na revisão de 2026-09-27. Separar por
    responsabilidade e feature, preservando coesão e contratos; não
    compactar código artificialmente para cumprir o limite.
2.  **Sem nomes redundantes.** O contexto da pasta já comunica parte do
    domínio.
3.  **Shared não vira monólito.** Table, zoom, viewer, pager, focus,
    modal, toolbar e feedback permanecem independentes.
4.  **Página compõe.** Não reimplementar componentes recorrentes em cada
    página.
5.  **Orquestração coordena; processamento executa.** Não duplicar
    responsabilidades.
6.  **V2 não duplica domínio.** Algoritmos, thresholds e regras
    protegidas continuam nas implementações autoritativas existentes.
7.  **Autoridade é preservada.** Manifests, SHA e artefatos continuam
    definindo o contrato persistido.
8.  **Central legada permanece estável.** Não desmontá-la enquanto a V2
    ainda depender dela como baseline.
9.  **Ciclo de vida explícito.** Páginas observam os stores dos dados que
    apresentam e devolvem sua função de limpeza ao router. Assinaturas
    são encerradas ao sair da página.
10. **Features possuem módulos próprios.** O shell compõe a interface;
    transporte HTTP do frontend pertence a `_app/api/`.

## 7. Estratégia de migração

A migração é **vertical por fluxo**, não uma reescrita completa antes da
validação.

``` text
contrato atual
→ rota V2
→ orquestração
→ domínio existente
→ autoridade/artefatos existentes
→ projeção de estado V2
→ página V2
→ validação funcional
→ fluxo considerado migrado
```

Uma feature nova pode nascer diretamente na V2 quando isso não exigir
duplicar regras de domínio.

## 8. Critério de descontinuação da Central atual

A Central legada só poderá ser descontinuada após equivalência funcional
validada dos fluxos aplicáveis:

-   seleção de obra/capítulo;
-   Auto-Merge I--V;
-   Review;
-   Merge Manual;
-   Balanceamento;
-   PDF;
-   Texto Off;
-   Tratamentos Especiais;
-   Exportação;
-   jobs, progresso e erros;
-   mídia e previews;
-   autoridade dos manifests preservada;
-   casos reais críticos validados.

A descontinuação deve ser uma decisão explícita. Até esse ponto, V1 e V2
coexistem, mas **não possuem implementações concorrentes dos algoritmos
de domínio**.

## 9. Princípio de evolução

``` text
preservar V1
→ implementar uma fatia vertical na V2
→ reutilizar domínio existente
→ validar equivalência/contrato
→ migrar o próximo fluxo
→ descontinuar V1 somente ao final
```

O objetivo é reduzir acoplamento sem regressão funcional e permitir a
entrega de features durante a migração.
