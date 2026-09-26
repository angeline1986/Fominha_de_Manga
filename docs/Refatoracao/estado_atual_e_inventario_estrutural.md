# Estado Atual e Inventário Estrutural

**Projeto:** Fominha_de_Manga  
**Fase:** 0 — Proteção antes da refatoração  
**Natureza:** inventário estrutural classificado  
**Regra:** este documento é descritivo. Não autoriza mover, excluir, renomear ou refatorar arquivos.

---

## 1. Objetivo

Registrar a estrutura física e arquitetural atualmente observada no repositório antes do início da Fase 1.

A classificação diferencia código ativo, frontend, processamento/domínio, configuração, testes, documentação, experimentos, diagnóstico, artefatos, backups, cache, temporários, legado candidato e itens cuja responsabilidade ainda precisa ser confirmada.

A presença de um item neste inventário não significa recomendação de permanência ou remoção.

---

## 2. Estrutura principal do repositório

| Área | Classificação atual | Papel observado |
|---|---|---|
| `config/` | configuração | configuração e resolução de caminhos |
| `interface_web/` | produção / frontend / adaptação Web | Central de Processamento Web |
| `orquestracao/` | produção / orquestração | entrypoint e fluxos de orquestração CLI |
| `processamento/` | produção / processamento e domínio | algoritmos e serviços especializados |
| `dev/tests/` | testes | suíte principal de caracterização/regressão |
| `dev/experiments/` | experimentos | implementações e provas experimentais |
| `dev/archive/` | legado/arquivo candidato | pacotes e evidências históricas |
| `dev/artifacts/` | artefatos | área de artefatos de desenvolvimento |
| `docs/` | documentação | documentação ativa, histórica e da refatoração |
| `requirements-locks/` | configuração / reprodutibilidade | locks dos ambientes críticos |
| `download/` | integração externa / submódulo | conteúdo omitido da coleta ampla; tratado separadamente |
| `reports/` | artefatos operacionais | saídas e relatórios; conteúdo omitido da coleta ampla |
| `tests/` | residual local | diretório sem arquivos efetivos fora de `__pycache__` e sem arquivos versionados |

---

## 3. Entrypoints observados

### 3.1 Central Web

`interface_web/processing_web.py`

Responsabilidades observadas:

- servidor HTTP;
- inicialização de `ThreadingHTTPServer`;
- roteamento GET/POST;
- jobs;
- resolução de estado;
- observabilidade/eventos;
- leitura e validação de manifests;
- promoção de estágios de Auto-Merge;
- validação de imagens;
- Balanceamento;
- Auto-Merge I–V;
- PDF;
- Texto Off;
- Review.

O arquivo possui aproximadamente **2.836 linhas**, **93 funções de primeiro nível** e duas classes.

É o principal hotspot estrutural atualmente observado.

### 3.2 Orquestração CLI

`orquestracao/menu.py`

Possui `main()` próprio e atua como outro entrypoint do sistema.

Também referencia fluxos de Merge, Review, Texto Off, PDF e módulos explicitamente experimentais.

### 3.3 CLIs especializados

Foram observados entrypoints próprios em módulos especializados, incluindo:

- Cleaner V2;
- Cleaner V2 Nível II;
- diagnóstico de máscara;
- Level3 Regional;
- correção assistida de Texto Off;
- Bubble Cleaner;
- analisador de dimensões.

Esses entrypoints não devem ser confundidos com a Central Web.

---

## 4. Frontend atual

O bootstrap principal ocorre em:

`interface_web/index.html`

A página carrega módulos especializados e o núcleo atual da aplicação.

### 4.1 Hotspots de tamanho

| Arquivo | Linhas aproximadas |
|---|---:|
| `app.js` | 1539 |
| `styles.css` | 1525 |
| `merge_manual.js` | 1047 |
| `balanceamento.js` | 1034 |
| `textoff_compare.js` | 547 |
| `merge_manual_novos_merges.js` | 509 |
| `merge_manual.css` | 441 |
| `textoff_special.js` | 416 |

Tamanho isolado não caracteriza defeito. Esses números servem apenas como indicadores para análise de responsabilidade na Fase 1.

### 4.2 Módulos especializados já existentes

Foram observados arquivos próprios para:

- Balanceamento;
- Merge Manual;
- novos merges;
- comparação Texto Off;
- Studio/QC Texto Off;
- tratamentos especiais;
- Exportação;
- Mega Menu;
- viewer compartilhado.

A arquitetura atual, portanto, já possui alguma decomposição funcional, embora `app.js` e `styles.css` permaneçam concentradores relevantes.

---

## 5. Processamento e domínio

### 5.1 Unificação de imagens

`processamento/unificacao_imagens/`

Contém:

- `image_stitcher.py`;
- `image_stitcher_level2.py`;
- `image_stitcher_level3.py`;
- `image_stitcher_level4.py`;
- `image_stitcher_level5.py`;
- módulo de Review.

Os contratos funcionais e parâmetros calibrados desses estágios são protegidos pela baseline de testes e documentação específica.

### 5.2 Merge Manual

`processamento/merge_manual/`

Módulos observados:

- API;
- serviço;
- proposta;
- estado de Review;
- finalização/promoção oficial.

### 5.3 Balanceamento

`processamento/balanceamento/`

Módulos observados:

- `balanceador.py`;
- `balanceamento.py`.

Há dependências observadas com detecção de balões e análise estrutural do Auto-Merge Nível III.

### 5.4 Texto Off / limpeza de balões

`processamento/limpeza_baloes/`

Área com múltiplos fluxos:

- Cleaner;
- Cleaner V2;
- Nível III;
- análise de resíduos;
- correção assistida;
- tratamentos especiais;
- Gradiente Suave;
- Level3 Regional;
- comparação;
- diagnóstico;
- módulos experimentais.

Foram observadas dependências internas entre módulos, inclusive consumo de símbolos privados (`_...`). Isso deve ser tratado como evidência de acoplamento para a Fase 1, não como autorização para alteração imediata.

### 5.5 PDF

`processamento/pdf_original/`

Contém validação em lote e revisão de divergências.

### 5.6 Exportação

`processamento/exportacao/`

Contém o serviço de simulação/execução de exportação consumido pela Central Web.

### 5.7 Validação de imagens

`processamento/validacao_imagens/`

Contém o analisador de dimensões utilizado pela Central.

---

## 6. Dependências estruturais relevantes observadas

### 6.1 `processing_web.py` como hub

A Central Web importa diretamente componentes de:

- orquestração;
- Balanceamento;
- Exportação;
- Cleaner V2;
- Texto Off;
- Merge Manual;
- Auto-Merge I–V;
- Review;
- validação de imagens.

Isso caracteriza `processing_web.py` como hub de integração atual.

### 6.2 Dependências cruzadas

Foram observadas, entre outras:

- Balanceamento → Bubble Cleaner;
- Balanceamento → Auto-Merge Nível III;
- Auto-Merge IV/V → análise estrutural do Nível III;
- Merge Manual → `image_stitcher`;
- Texto Off → outros módulos internos de Texto Off/Cleaner;
- orquestração → módulos de processamento e módulos experimentais.

A direção dessas dependências será analisada arquiteturalmente na Fase 1.

---

## 7. Testes

### 7.1 Suíte principal observada

`dev/tests/`

Contém testes de:

- Auto-Merge;
- autoridade de estágios;
- Review;
- Merge Manual;
- Exportação;
- PDF;
- UI/estado;
- contratos de providers;
- segurança de composição.

A baseline completa atual está documentada separadamente em:

`docs/Refatoracao/02_baseline_testes_e_contratos.md`

### 7.2 `tests/`

O diretório existe localmente, mas não possui arquivos efetivos fora de `__pycache__` e não possui arquivos versionados.

**Classificação:** diretório local residual.

Essa classificação não autoriza remoção nesta etapa.

---

## 8. Configuração e reprodutibilidade

### 8.1 Configuração

`config/`

Inclui atualmente:

- inicialização do pacote;
- `data_paths.py`.

### 8.2 Locks

`requirements-locks/`

Locks observados para:

- Cleaner V2;
- Gradiente Suave;
- Level3 Regional;
- mangago_downloader;
- PatchMatch.

Esses arquivos pertencem à proteção de reprodutibilidade e não devem ser classificados como cache.

### 8.3 Ambientes virtuais especializados

Foram observados ambientes locais em áreas especializadas, incluindo Cleaner V2, Gradiente Suave e Level3 Regional.

Sua proteção e recuperação estão documentadas em:

`docs/Refatoracao/01_ambientes_virtuais.md`

---

## 9. Documentação

### 9.1 Documentação ativa da refatoração

`docs/Refatoracao/`

Inclui:

- plano arquitetural;
- ambientes;
- baseline de testes/contratos;
- arquitetura de interface alvo;
- checkpoints do mapa do metrô;
- evidências históricas/técnicas.

### 9.2 Documentação histórica

`docs/OLD/`

Classificada como documentação histórica/legada.

Não excluir durante a Fase 0.

### 9.3 Documentação de desenvolvimento

`dev/docs/`

Área separada de documentação técnica de desenvolvimento.

---

## 10. Experimentos e diagnóstico

### 10.1 Experimentos formalmente separados

`dev/experiments/`

Contém gerações experimentais do Bubble Cleaner e respectivas documentações/testes.

### 10.2 Experimentos dentro da árvore de processamento

Foram observados módulos com identificação explícita de experimento em `processamento/limpeza_baloes/`, incluindo patches de:

- balão estilizado;
- balão transparente;
- degradê.

Alguns são referenciados por fluxos atuais. Portanto, o nome `experimento` não é suficiente para classificá-los como código morto.

### 10.3 Diagnóstico

`processamento/limpeza_baloes/diagnostico/`

Contém ferramenta de diagnóstico de máscara.

Classificação: diagnóstico/ferramenta especializada.

---

## 11. Artefatos, cache e temporários

### 11.1 Cache observado

Foram observados:

- `.pytest_cache/`;
- diretórios `__pycache__/`;
- `processamento/limpeza_baloes/.cache/`.

Classificação: cache operacional/local.

### 11.2 Artefatos operacionais

`reports/`

Classificação: artefatos e relatórios gerados.

O conteúdo não foi atravessado nesta coleta devido ao potencial volume.

### 11.3 `dev/artifacts/`

O diretório contém somente `.DS_Store` na inspeção atual e não possui arquivos versionados.

Classificação atual: diretório local residual / metadado do sistema operacional.

### 11.4 Metadados locais

Foram encontrados arquivos `.DS_Store` em diferentes pontos da árvore.

Classificação: metadado local do sistema operacional.

---

## 12. Backups, snapshots e legado candidato

### 12.1 Archive de desenvolvimento

`dev/archive/legacy_update_package/`

Contém pacote ZIP, hashes, manifesto e diff.

Classificação: arquivo/legado candidato com evidência histórica.

### 12.2 Snapshots `before_*`

Foram observados arquivos como:

`patch_balao_transparente_experimento.py.before_*`

Classificação: snapshots históricos/backup candidato.

Não excluir sem auditoria específica.

### 12.3 ZIPs na raiz

Foram observados:

- `interface_web.zip` — aproximadamente 504 KB;
- `processamento.zip` — aproximadamente 178 KB.

Ambos existem localmente e não são versionados.

Classificação atual: artefatos/backups locais de finalidade histórica não comprovada.

Eles não integram a arquitetura versionada observada. Nenhuma remoção está autorizada.

---

## 13. Estruturas locais residuais identificadas

A inspeção complementar confirmou como estruturas locais residuais, sem arquivos efetivos versionados:

- `tests/`;
- `dev/artifacts/`;
- `processamento/limpeza_baloes/decision_pipeline/`;
- `processamento/limpeza_baloes/especial/`;
- `processamento/limpeza_baloes/pipeline/`.

Nos três diretórios sob `limpeza_baloes`, não foram encontrados arquivos fora de `__pycache__` nem arquivos registrados pelo Git.

Essas estruturas não são consideradas módulos da arquitetura versionada atual.

Os ZIPs da raiz permanecem classificados separadamente como artefatos/backups locais de finalidade histórica não comprovada.

Nenhuma dessas classificações autoriza exclusão durante a Fase 0.

---

## 14. Hotspots estruturais observados

### Backend

| Arquivo | Linhas | Funções de primeiro nível |
|---|---:|---:|
| `interface_web/processing_web.py` | 2836 | 93 |
| módulo Review de unificação | 1963 | 25 |
| `balanceador.py` | 1336 | 29 |
| `image_stitcher.py` | 969 | 23 |
| `balanceamento.py` | 969 | 20 |
| `textoff_level3_correction.py` | 802 | 20 |
| `image_stitcher_level3.py` | 781 | 13 |
| `orquestracao/menu.py` | 685 | 30 |

Esses números não determinam automaticamente extração ou divisão.

### Frontend

Os principais concentradores observados são:

- `app.js`;
- `styles.css`;
- `merge_manual.js`;
- `balanceamento.js`.

A decomposição futura deve considerar responsabilidade, coesão e contratos, não apenas quantidade de linhas.

---

## 15. Fronteiras já existentes que devem ser preservadas na análise

A estrutura atual já apresenta separações importantes:

- frontend especializado por algumas funcionalidades;
- algoritmos Auto-Merge em módulos próprios;
- Merge Manual em pacote próprio;
- Balanceamento em pacote próprio;
- Exportação em pacote próprio;
- validação de imagens em pacote próprio;
- Cleaner V2 com ambiente/configuração próprios;
- ferramentas especializadas de Texto Off.

A Fase 1 deve avaliar como reduzir hubs e acoplamentos sem destruir fronteiras que já funcionam.

---

## 16. Regras para a próxima fase

Este inventário não autoriza alteração estrutural.

Antes de mover responsabilidade crítica:

1. identificar contrato atual;
2. localizar testes de proteção;
3. identificar produtor/consumidor de estado e manifests;
4. preservar parâmetros calibrados;
5. definir destino arquitetural;
6. realizar extração mínima;
7. executar regressão relacionada;
8. executar baseline pertinente.

Permanece válida a regra:

> Não criar novas funções em `interface_web/processing_web.py`.

---

## 17. Estado do inventário

A estrutura física principal, entrypoints, hotspots, categorias e dependências estruturais relevantes foram levantados.

A classificação estrutural foi confrontada com:

- a estrutura física observada do repositório;
- os entrypoints identificados;
- o mapa de dependências/importações;
- os hotspots backend e frontend;
- o mapa do metrô e seus contratos de autoridade;
- a arquitetura-alvo já documentada;
- a inspeção complementar das estruturas locais não versionadas.

Nenhuma área relevante observada na raiz permanece sem classificação estrutural.

**Status deste documento:** FORMALIZADO — FASE 0.

Nenhum arquivo foi movido, excluído ou refatorado durante este levantamento.
