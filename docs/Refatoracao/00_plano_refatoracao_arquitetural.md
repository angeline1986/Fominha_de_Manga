# Plano de Refatoração Arquitetural --- Fominha_de_Manga

**Versão:** 2.0\
**Atualizado em:** 2026-09-25\
**Branch de referência:** `develop`\
**Baseline de referência:** `c6adae7efacf289f4ca3894c1abe0dd96364f32a`

## 1. Objetivo

Executar uma refatoração significativa e incremental do backend e
frontend, reduzindo acoplamento, responsabilidades excessivas e
desorganização estrutural **sem alterar o comportamento funcional
validado**.

O principal hotspot continua sendo `interface_web/processing_web.py`,
com múltiplas responsabilidades. A refatoração deve preservar contratos
entre interface, backend, pipelines, filesystem, jobs, manifests,
artefatos e runtimes especializados.

> **Princípio central:** não reescrever o sistema. Auditar,
> caracterizar, proteger, extrair e validar uma responsabilidade por
> vez.

------------------------------------------------------------------------

## 2. Regras imutáveis da refatoração

1.  Não realizar Big Bang.
2.  Não misturar refatoração estrutural com mudança funcional.
3.  Não alterar algoritmos, thresholds, classificadores, manifests,
    paths, autoridade de estágios ou regras de negócio sem demanda e
    aprovação específicas.
4.  Não remover arquivo/teste porque "parece antigo"; provar primeiro.
5.  Não recriar ou normalizar venvs durante a refatoração sem
    necessidade comprovada.
6.  Não criar novas funções em `interface_web/processing_web.py`; nova
    lógica deve ir para módulo próprio.
7.  Toda extração deve manter compatibilidade observável com os
    chamadores.
8.  Cada mudança deve ser pequena, validável e reversível.
9.  Em regressão, reverter a menor unidade possível.
10. `processing_web.py` deve terminar como camada de
    entrada/orquestração/delegação, não apenas repartido em arquivos
    menores.
11. Teste vermelho preexistente não autoriza mudança de produção.
12. Auto-Merge I--V, Review, Merge Manual, Texto Off, Balanceamento, PDF
    e Exportação são fluxos críticos.
13. Auto-Merge I--V é uma **baseline formalmente protegida**.

Fluxo operacional obrigatório:

``` text
AUDITAR
  ↓
PROVAR O ESTADO/CAUSA
  ↓
IDENTIFICAR CONTRATO
  ↓
PROTEGER / CARACTERIZAR
  ↓
PROPOR MUDANÇA MÍNIMA
  ↓
APROVAR
  ↓
IMPLEMENTAR
  ↓
VALIDAR AUTOMATICAMENTE
  ↓
VALIDAR CASO REAL, QUANDO APLICÁVEL
  ↓
COMPARAR COM BASELINE
  ↓
DOCUMENTAR
  ↓
COMMIT
```

------------------------------------------------------------------------

# 3. Fase 0 --- Baseline, recuperação e proteção

**Objetivo:** conhecer o estado real antes da refatoração e garantir
recuperação.

**Status geral: EM FECHAMENTO.**

Nenhuma refatoração de produção deve começar enquanto os gates restantes
desta fase não forem concluídos.

## 3.1 Baseline Git e repositório

**Status: CONCLUÍDO para a baseline auditada.**

Registrados:

-   branch `develop`;
-   HEAD `c6adae7efacf289f4ca3894c1abe0dd96364f32a`;
-   estado do working tree;
-   submódulo `download/mangago_downloader`;
-   arquivos versionados, ignorados e locais relevantes;
-   movimentações deliberadas de documentação.

Antes de iniciar a primeira alteração estrutural, confirmar novamente
`git status` e HEAD.

## 3.2 Proteção dos ambientes especializados

**Status: CONCLUÍDO.**

Ambientes auditados:

-   Cleaner V2;
-   Gradiente Suave;
-   Level3 Regional.

Foram registrados Python, freeze, pacotes diretos, configurações, hashes
e modelos aplicáveis.

Existe baseline lógica em:

``` text
docs/Refatoracao/environment_baseline/2026-09-25/
```

Existe backup físico externo das venvs e modelos críticos, com hashes
verificados.

Documentação:

``` text
docs/Refatoracao/ambientes_virtuais_fominha_de_manga.md
```

### Gate

> Ambientes críticos não devem ser alterados como efeito colateral da
> refatoração.

## 3.3 Baseline da suíte e relevância dos testes

**Status: CONCLUÍDO.**

Baseline:

``` text
162 executados
139 passaram
20 failures
2 errors
1 skipped
```

A suíte já estava vermelha antes da refatoração.

Os reds foram auditados e classificados como
contratos/fixtures/imports/assertions históricos, sem evidência
suficiente para alterar produção.

Documento:

``` text
docs/Refatoracao/baseline_testes_e_contratos_protegidos.md
```

Categorias adotadas:

-   `KEEP`
-   `MIGRATE`
-   `REPLACE`
-   `RETIRE` somente com prova explícita

### Regra

> O objetivo da refatoração não é tornar artificialmente verdes fixtures
> históricas. É preservar os contratos atuais e migrar conscientemente a
> proteção antiga.

## 3.4 Proteção formal do Auto-Merge I--V

**Status: PARCIAL --- gate obrigatório pendente.**

Cadeia protegida:

``` text
Auto-Merge I
  ↓
Auto-Merge II
  ↓
Auto-Merge III
  ↓
Auto-Merge IV — directed
  ↓
Auto-Merge V — global/exhaustive fallback
  ↓
Review / Merge Manual
  ↓
MERGE oficial
```

Devem permanecer protegidos:

-   algoritmos;
-   thresholds;
-   SAFE-only;
-   ausência de forced cut;
-   manifests;
-   hashes do predecessor;
-   autoridade do residual;
-   cobertura sem GAP/OVERLAP;
-   materialização;
-   promoção;
-   integridade dos artefatos;
-   fail-closed.

### GAP-TEST-AM45

Foi identificada lacuna real de cobertura:

-   Nível IV não possui caracterização dedicada proporcional à
    criticidade;
-   Nível V possui apenas referências incidentais, não caracterização
    suficiente.

### Gate obrigatório

Antes de refatorar qualquer código que possa afetar IV/V:

``` text
[ ] caracterização dedicada do Auto-Merge IV
[ ] caracterização dedicada do Auto-Merge V
[ ] testes de autoridade/manifests/SHA/residual aplicáveis
[ ] baseline relacionada reexecutada
```

## 3.5 Dívida documental do Nível V

**DOC-AM5-01 --- PENDENTE, não bloqueia caracterização.**

A docstring de `image_stitcher_level5.py` descreve uma arquitetura
anterior e não representa integralmente a autoridade atual nem o partial
SAFE progress.

Corrigir documentação separadamente, sem alterar algoritmo.

## 3.6 Inventário estrutural classificado

**Status: PENDENTE / precisa ser formalizado.**

O plano original previa classificação explícita de:

-   produção;
-   frontend;
-   processamento/domínio;
-   configuração;
-   testes;
-   documentação;
-   experimentos;
-   diagnóstico;
-   artefatos;
-   backups;
-   cache;
-   temporários;
-   legado candidato;
-   origem desconhecida.

Não mover nem excluir nesta etapa.

**Saída atualizada sugerida:**

``` text
docs/Refatoracao/estado_atual_e_inventario_estrutural.md
```

## 3.7 Catálogo dos fluxos críticos e smoke baseline

**Status: PENDENTE.**

Formalizar ao menos:

-   Central;
-   seleção de obra/capítulo;
-   jobs;
-   Auto-Merge I--V;
-   Review;
-   Merge Manual;
-   Texto Off;
-   tratamentos especiais;
-   Balanceamento;
-   PDF;
-   Exportação.

Para cada fluxo:

``` text
entrada
→ endpoint/evento
→ orquestração
→ módulo responsável
→ artefatos/manifests
→ estado final esperado
→ teste automatizado existente
→ smoke/caso real disponível
```

**Saída sugerida:**

``` text
docs/Refatoracao/catalogo_fluxos_criticos.md
```

## 3.8 Gate de saída da Fase 0

A Fase 0 somente termina quando:

``` text
[x] baseline Git conhecida
[x] ambientes críticos recuperáveis
[x] modelos/hashes críticos protegidos
[x] baseline de testes registrada
[x] reds preexistentes classificados
[x] contratos Auto-Merge I–V identificados
[ ] GAP-TEST-AM45 coberto
[ ] inventário estrutural formalizado
[ ] catálogo de fluxos críticos formalizado
[ ] smoke baseline mínimo registrado
[ ] riscos/lacunas consolidados
[ ] documentação da Fase 0 revisada
```

------------------------------------------------------------------------

# 4. Fase 1 --- Mapeamento arquitetural real

**Status: NÃO INICIADA.**

Ainda sem refatoração.

## 4.1 Mapear `processing_web.py`

Catalogar funções/classes/blocos por responsabilidade:

-   bootstrap/configuração;
-   HTTP/API;
-   validação;
-   jobs;
-   filesystem/path resolution;
-   serialização;
-   estado;
-   Auto-Merge I--V;
-   Review;
-   Merge Manual;
-   Texto Off;
-   Balanceamento;
-   PDF;
-   Exportação;
-   integração externa;
-   erros;
-   helpers;
-   legado/desconhecido.

Para cada item:

``` text
símbolo
responsabilidade
quem chama
o que chama
inputs
outputs
efeitos colaterais
paths
manifests/artefatos
estado compartilhado
exceções
testes protetores
risco de extração
```

## 4.2 Mapear dependências

Representar as cadeias reais, sem impor arquitetura alvo prematuramente:

``` text
Frontend
  ↓
HTTP/API
  ↓
processing_web
  ↓
serviço/módulo especializado
  ↓
processamento
  ↓
filesystem / subprocess / runtime / artefatos
```

Identificar:

-   imports cruzados;
-   dependências circulares;
-   estado global;
-   paths espalhados;
-   chamadas diretas ao filesystem;
-   subprocessos;
-   duplicação;
-   fronteiras já existentes.

**Saída:**

``` text
docs/Refatoracao/mapa_componentes_e_dependencias.md
```

## 4.3 Mapa de autoridade

Novo requisito do plano.

Para pipelines com múltiplos estágios, registrar explicitamente:

``` text
quem produz
quem é autoridade
qual manifest prova a autoridade
qual SHA encadeia predecessor
qual residual segue adiante
quem pode promover
quem pode finalizar
```

Prioridade máxima: Auto-Merge I--V → Review → Merge Manual.

------------------------------------------------------------------------

# 5. Fase 2 --- Matriz de contratos e caracterização

A antiga Fase 2 continua válida, mas agora parte da baseline já foi
antecipada pela auditoria.

Construir matriz por fluxo:

  --------------------------------------------------------------------------------------
  Fluxo           Contrato    Teste atual Estado         Cobertura    Ação
                                                         suficiente   
  --------------- ----------- ----------- -------------- ------------ ------------------
  Auto-Merge I    ...         ...         KEEP/MIGRATE   ...          ...

  Auto-Merge II   ...         ...         ...            ...          ...

  Auto-Merge III  ...         ...         ...            ...          ...

  Auto-Merge IV   ...         GAP         Não            Não          Characterization

  Auto-Merge V    ...         GAP         Não            Não          Characterization

  Review          ...         ...         ...            ...          ...

  Merge Manual    ...         ...         ...            ...          ...

  Texto Off       ...         ...         ...            ...          ...

  Balanceamento   ...         ...         ...            ...          ...

  PDF             ...         ...         ...            ...          ...

  Exportação      ...         ...         ...            ...          ...
  --------------------------------------------------------------------------------------

### Prioridades

1.  autoridade entre estágios;
2.  manifests e SHA;
3.  promoção de artefatos;
4.  paths;
5.  estados;
6.  HTTP/jobs;
7.  erros/fail-closed;
8.  integração frontend/backend.

### Gate

> Nenhuma responsabilidade crítica sai de `processing_web.py` sem
> contrato observável protegido.

------------------------------------------------------------------------

# 6. Fase 3 --- Arquitetura alvo

Somente depois do mapa real e da matriz de contratos.

Preferir fronteiras por responsabilidade, não por tamanho.

A estrutura alvo é uma decisão derivada da auditoria; não criar
diretórios apenas para encaixar um desenho teórico.

Possíveis fronteiras:

``` text
interface_web/
  routes/
  controllers/
  schemas/
  adapters/

application/
  jobs/
  services/

processamento/
  balanceamento/
  exportacao/
  limpeza_baloes/
  merge_manual/
  pdf_original/
  unificacao_imagens/
  validacao_imagens/

infrastructure/
  filesystem/
  process/
  runtime/
```

## ADRs

Decisões relevantes devem gerar ADR curto contendo:

-   contexto;
-   evidência;
-   decisão;
-   alternativas;
-   consequências;
-   contratos preservados;
-   estratégia de rollback.

Destino sugerido:

``` text
docs/Refatoracao/adr/
```

------------------------------------------------------------------------

# 7. Fase 4 --- Higienização estrutural

Somente após mapear referências reais.

Antes de mover/remover:

1.  imports/referências;
2.  chamadas dinâmicas;
3.  scripts/documentação;
4.  subprocessos/paths;
5.  testes;
6.  smoke relevante;
7.  impacto em recuperação.

Separar progressivamente código ativo, experimentos, diagnósticos,
backups, artefatos, temporários e legado comprovado.

------------------------------------------------------------------------

# 8. Fase 5 --- Refatoração incremental do backend

Padrão obrigatório:

``` text
SELECT
→ PROTECT
→ EXTRACT
→ DELEGATE
→ VALIDATE
→ COMPARE
→ DOCUMENT
→ COMMIT
```

Para cada unidade:

### Selecionar

Responsabilidade coesa e de baixo risco.

### Proteger

Confirmar testes e contratos.

### Extrair

Mover implementação para módulo responsável.

### Delegar

`processing_web.py` fica somente com adaptação/orquestração necessária.

### Validar

Executar sintaxe, testes específicos, contratos, regressão relacionada e
smoke real quando aplicável.

### Comparar

Confirmar invariância de:

-   endpoint;
-   payload;
-   status;
-   manifest;
-   paths;
-   artefatos;
-   autoridade;
-   estado;
-   consumidor frontend.

### Commit

Um commit por unidade lógica estável.

------------------------------------------------------------------------

# 9. Ordem de extração de `processing_web.py`

A ordem definitiva será definida pelo mapa da Fase 1.

Heurística:

1.  helpers puros;
2.  serialização/schemas;
3.  path resolution;
4.  validações;
5.  delegações para serviços já existentes;
6.  endpoints bem delimitados;
7.  jobs;
8.  estado compartilhado;
9.  integrações acopladas;
10. bootstrap/roteamento restante.

**Exceção:** não escolher uma área apenas por parecer fácil se ela tocar
Auto-Merge IV/V ou outro contrato sem caracterização suficiente.

KPI principal não é número de linhas.

Objetivo:

> `processing_web.py` deve conter principalmente composição, registro de
> endpoints e delegação.

------------------------------------------------------------------------

# 10. Fase 6 --- Frontend

Mapear antes:

-   navegação;
-   estado global;
-   obra/capítulo;
-   API;
-   polling;
-   renderizadores;
-   viewer;
-   Auto-Merge/Review/Merge Manual;
-   Texto Off;
-   Balanceamento;
-   Exportação;
-   Mega Menu;
-   modos de foco.

Separar progressivamente:

``` text
renderização
estado
API client
controllers de domínio
componentes compartilhados
viewer
```

Não alterar simultaneamente contrato backend e consumidor frontend.

------------------------------------------------------------------------

# 11. Fase 7 --- Configuração e runtimes

Após estabilização estrutural:

-   centralizar configuração realmente compartilhável;
-   documentar configuração específica;
-   remover hardcodes apenas quando seguro;
-   documentar seleção de runtime/venv;
-   preservar ambientes especializados quando tecnicamente necessários;
-   manter snapshots reproduzíveis.

Não consolidar venvs por estética.

------------------------------------------------------------------------

# 12. Fase 8 --- Remoção de legado

Remover somente com evidência de que não é:

-   importado;
-   chamado dinamicamente;
-   usado por subprocesso;
-   referenciado por configuração;
-   necessário para recuperação;
-   usado por fluxo manual;
-   necessário para compatibilidade transitória.

Testes e smoke devem continuar compatíveis com a baseline vigente.

------------------------------------------------------------------------

# 13. Gate obrigatório por mudança

Cada unidade de trabalho deve terminar com:

``` text
[ ] git status conhecido
[ ] diff revisado
[ ] nenhuma alteração fora do escopo
[ ] sintaxe válida
[ ] testes específicos executados
[ ] contratos relacionados preservados
[ ] nenhum novo red não explicado
[ ] smoke real quando aplicável
[ ] artefatos/manifests comparados quando aplicável
[ ] documentação atualizada
[ ] rollback conhecido
[ ] commit isolado
```

------------------------------------------------------------------------

# 14. Definition of Done

A refatoração termina quando:

-   responsabilidades arquiteturais estiverem explícitas;
-   `processing_web.py` não concentrar regras de múltiplos domínios;
-   frontend tiver fronteiras claras;
-   paths/configuração tiverem autoridade conhecida;
-   runtimes especializados estiverem documentados e recuperáveis;
-   contratos críticos estiverem cobertos;
-   Auto-Merge I--V tiver proteção adequada;
-   autoridade entre estágios estiver explícita;
-   ativos/experimentos/diagnósticos/backups estiverem separados;
-   código morto comprovado tiver sido removido;
-   documentação refletir implementação real;
-   fluxos produzirem resultados equivalentes à baseline;
-   não houver regressão funcional introduzida pela refatoração.

------------------------------------------------------------------------

# 15. Estado atual do plano --- 2026-09-25

``` text
FASE 0 — BASELINE E PROTEÇÃO
  [x] Git / estado inicial
  [x] ambientes especializados
  [x] modelos / hashes / recuperação
  [x] baseline de testes
  [x] classificação dos reds
  [x] contratos críticos I–V identificados
  [ ] caracterização dedicada IV
  [ ] caracterização dedicada V
  [ ] inventário estrutural formal
  [ ] catálogo de fluxos críticos
  [ ] smoke baseline mínimo
  [ ] fechamento documental da Fase 0

FASE 1 — MAPEAMENTO ARQUITETURAL
  [ ] não iniciada

FASE 2 — MATRIZ DE CONTRATOS
  [ ] não iniciada formalmente
  [~] parte da caracterização já antecipada na Fase 0

FASES 3–8
  [ ] não iniciadas
```

------------------------------------------------------------------------

# 16. Próximo trabalho autorizado

O próximo trabalho **não é refatorar `processing_web.py`**.

A prioridade imediata é fechar o gate de proteção do Auto-Merge:

``` text
1. caracterizar Auto-Merge IV;
2. validar;
3. caracterizar Auto-Merge V;
4. validar;
5. formalizar inventário estrutural;
6. catalogar fluxos/smokes;
7. fechar Fase 0;
8. somente então iniciar Fase 1.
```

A execução continua incremental: **uma ação por vez**, com evidência
antes da próxima decisão.
