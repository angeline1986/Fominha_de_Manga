# Plano de Refatoração Arquitetural --- Fominha_de_Manga

## 1. Objetivo

Executar uma refatoração significativa e incremental do backend e
frontend, reduzindo acoplamento, responsabilidades excessivas e
desorganização estrutural **sem alterar o comportamento funcional já
validado**.

O principal hotspot inicial é `interface_web/processing_web.py`,
atualmente com aproximadamente 2.837 linhas e múltiplas
responsabilidades. A refatoração deve preservar os contratos existentes
entre interface, backend, pipelines de processamento, filesystem, jobs,
manifests, artefatos e ambientes Python especializados.

> **Princípio central:** não reescrever o sistema. Caracterizar,
> proteger, extrair e validar uma responsabilidade por vez.

------------------------------------------------------------------------

## 2. Regras de segurança

1.  Não iniciar alterações antes de concluir a baseline arquitetural e
    funcional.
2.  Não realizar refatoração Big Bang.
3.  Não misturar refatoração estrutural com mudança funcional.
4.  Não alterar algoritmos, thresholds, contratos, formatos de
    manifests, paths ou regras de negócio sem uma demanda específica e
    aprovação separada.
5.  Não remover arquivo por parecer obsoleto. Primeiro provar ausência
    de uso.
6.  Não recriar, atualizar ou normalizar `venv` durante a refatoração
    sem necessidade comprovada.
7.  Toda extração deve manter compatibilidade com os chamadores
    existentes.
8.  Cada fase deve produzir evidência objetiva de validação e um commit
    isolado.
9.  Em caso de regressão, reverter a menor unidade de mudança possível.
10. `processing_web.py` deve ser reduzido progressivamente a uma camada
    de entrada/orquestração; não deve ser simplesmente repartido em
    arquivos menores mantendo o mesmo acoplamento.

------------------------------------------------------------------------

# 3. Fase 0 --- Baseline antes da refatoração

**Objetivo:** registrar o estado atual e garantir capacidade de
recuperação.

**Não alterar código nesta fase.**

## 3.1 Registrar baseline Git

Documentar:

-   branch;
-   commit/HEAD;
-   `git status`;
-   submódulos e respectivos commits;
-   arquivos modificados/não rastreados;
-   `.gitignore`;
-   arquivos relevantes que deliberadamente não são versionados.

Criar uma tag ou branch de segurança da baseline aprovada.

## 3.2 Inventariar a estrutura

Classificar diretórios e arquivos em:

-   código de produção;
-   frontend;
-   domínio/processamento;
-   configuração;
-   testes;
-   documentação;
-   experimentos;
-   diagnóstico;
-   artefatos gerados;
-   backups;
-   cache;
-   temporários;
-   legado candidato à remoção;
-   origem ainda desconhecida.

O inventário atual já mostra separação entre `interface_web/`,
`processamento/`, `orquestracao/`, `dev/`, `reports/` e o subprojeto
`download/mangago_downloader`.

**Saída:**

`docs/architecture/00-current-state.md`

Nenhum arquivo deve ser movido ou excluído nesta etapa.

## 3.3 Auditar ambientes Python e dependências externas

Para **cada venv/runtime utilizado**, registrar:

-   finalidade;
-   caminho;
-   versão do Python;
-   `pip freeze`;
-   requirements associado;
-   pacotes críticos e versões;
-   modelos externos;
-   arquivos `.ini`/configuração;
-   binários/comandos externos;
-   variáveis de ambiente necessárias;
-   hashes já disponíveis;
-   módulo que utiliza o ambiente;
-   procedimento para reconstrução.

Comparar os snapshots existentes com os ambientes efetivamente
utilizados.

Critério obrigatório:

> Deve ser possível explicar como recuperar cada ambiente crítico sem
> depender apenas da venv local atual.

**Saída:**

`docs/architecture/01-runtime-environments.md`

## 3.4 Baseline funcional

Executar a suíte existente sem modificar código.

Registrar:

-   total de testes;
-   aprovados;
-   falhas;
-   skips;
-   duração;
-   falhas já existentes;
-   testes por domínio.

Não corrigir falhas nesta etapa; documentá-las para não atribuí-las
posteriormente à refatoração.

**Saída:**

`docs/architecture/02-test-baseline.md`

## 3.5 Smoke tests reais

Definir um conjunto pequeno e reproduzível de casos reais cobrindo os
fluxos críticos.

No mínimo:

-   carregamento da Central;
-   seleção de obra/capítulo;
-   jobs assíncronos;
-   Auto-Merge;
-   Review/Merge Manual;
-   Texto Off;
-   tratamentos especiais;
-   Balanceamento;
-   PDF;
-   Exportação.

Para cada fluxo registrar:

`entrada → endpoint/evento → serviço/módulo → artefatos → estado final esperado`

------------------------------------------------------------------------

# 4. Fase 1 --- Mapeamento arquitetural

**Ainda sem refatorar.**

## 4.1 Decompor `processing_web.py` conceitualmente

Catalogar todas as funções/classes/blocos e classificá-los por
responsabilidade:

-   bootstrap/configuração;
-   rotas/endpoints;
-   validação de request;
-   jobs/polling;
-   filesystem/path resolution;
-   serialização;
-   estado;
-   Merge;
-   Texto Off;
-   Balanceamento;
-   PDF;
-   Exportação;
-   integração com módulos externos;
-   tratamento de erros;
-   helpers puros;
-   legado/desconhecido.

Para cada item registrar:

-   quem chama;
-   o que chama;
-   inputs;
-   outputs;
-   efeitos colaterais;
-   arquivos lidos/escritos;
-   estado compartilhado;
-   exceções;
-   testes que o protegem.

## 4.2 Construir mapa de dependências

Documentar as cadeias relevantes:

``` text
Frontend
   ↓
HTTP/API
   ↓
processing_web
   ↓
Application/Service
   ↓
Processamento/Domínio
   ↓
Filesystem / subprocess / venv / artefatos
```

Identificar:

-   dependências circulares;
-   imports cruzados;
-   estado global;
-   conhecimento de paths espalhado;
-   chamadas diretas ao filesystem;
-   subprocessos;
-   duplicação de regras;
-   fronteiras já existentes.

**Saída:**

`docs/architecture/03-component-and-dependency-map.md`

------------------------------------------------------------------------

# 5. Fase 2 --- Caracterização e contratos

Antes de extrair uma responsabilidade sem cobertura suficiente, criar
**characterization tests** que descrevam o comportamento atual.

Priorizar:

1.  contratos HTTP;
2.  estados de jobs;
3.  resolução de paths;
4.  formatos JSON/manifests;
5.  promoção de artefatos;
6.  regras de seleção/validação;
7.  integração entre etapas;
8.  erros e respostas esperadas.

Não testar implementação interna quando o contrato externo puder ser
testado.

Criar uma matriz:

  Fluxo           Contrato   Teste existente   Cobertura suficiente   Ação
  --------------- ---------- ----------------- ---------------------- ------
  Merge           ...        ...               Sim/Não                ...
  Texto Off       ...        ...               Sim/Não                ...
  Balanceamento   ...        ...               Sim/Não                ...

**Gate:** nenhuma responsabilidade crítica sai de `processing_web.py`
sem contrato observável protegido.

------------------------------------------------------------------------

# 6. Fase 3 --- Arquitetura alvo

Somente após conhecer o estado atual definir a estrutura final.

Preferir fronteiras por responsabilidade, não por tamanho de arquivo.

Exemplo conceitual:

``` text
interface_web/
├── app/bootstrap
├── routes/
├── controllers/
├── schemas/
└── adapters/

application/
├── jobs/
└── services/

processamento/
├── balanceamento/
├── exportacao/
├── limpeza_baloes/
├── merge_manual/
├── pdf_original/
├── unificacao_imagens/
└── validacao_imagens/

infrastructure/
├── filesystem/
├── process/
└── runtime/
```

A estrutura real deve ser decidida a partir do mapa de dependências,
**não criada antecipadamente apenas para encaixar o código**.

## ADRs

Toda decisão relevante deve gerar um ADR curto:

``` text
docs/architecture/adr/
ADR-001-...
ADR-002-...
```

Cada ADR contém:

-   contexto;
-   decisão;
-   alternativas consideradas;
-   consequências;
-   contratos preservados.

------------------------------------------------------------------------

# 7. Fase 4 --- Higienização estrutural

Só após identificar referências reais.

Separar:

-   código ativo;
-   experimentos;
-   backups;
-   diagnósticos;
-   artefatos;
-   temporários;
-   legado.

Antes de remover/mover:

1.  buscar imports/referências;
2.  buscar chamadas dinâmicas;
3.  verificar scripts e documentação;
4.  verificar subprocessos/paths;
5.  executar testes;
6.  executar smoke test relevante.

Evitar manter ZIPs, caches, backups históricos e artefatos gerados
misturados ao código ativo quando houver destino apropriado, mas **não
fazer essa limpeza por aparência**.

------------------------------------------------------------------------

# 8. Fase 5 --- Refatoração incremental do backend

Aplicar padrão **extract → delegate → validate → commit**.

Para cada responsabilidade:

### A. Selecionar

Escolher uma responsabilidade coesa e de baixo risco.

### B. Proteger

Confirmar testes e contratos.

### C. Extrair

Mover a implementação para módulo responsável.

### D. Delegar

Manter temporariamente em `processing_web.py` apenas a chamada/adaptação
necessária.

### E. Validar

Executar:

-   lint/sintaxe aplicável;
-   testes do módulo;
-   testes de contrato;
-   suíte relacionada;
-   smoke test real.

### F. Comparar

Confirmar que:

-   endpoint não mudou;
-   payload não mudou;
-   status HTTP não mudou;
-   manifest não mudou;
-   paths não mudaram;
-   artefatos não mudaram;
-   estados não mudaram;
-   UI continua consumindo o mesmo contrato.

### G. Commit

Um commit por unidade lógica.

Exemplo:

``` text
refactor(web): extract balance job orchestration
```

Somente depois iniciar a próxima responsabilidade.

------------------------------------------------------------------------

# 9. Ordem recomendada para `processing_web.py`

A ordem definitiva depende da auditoria, mas utilizar esta estratégia:

1.  helpers puros e sem estado;
2.  schemas/serialização;
3.  resolução de paths;
4.  validações;
5.  serviços já implementados fora do arquivo;
6.  endpoints de domínio bem delimitado;
7.  jobs/orquestração;
8.  estado compartilhado;
9.  integrações mais acopladas;
10. bootstrap/roteamento restante.

Não usar número de linhas como KPI principal.

Objetivo arquitetural:

> `processing_web.py` deve terminar contendo principalmente composição,
> registro de endpoints e delegação --- não regras de negócio.

------------------------------------------------------------------------

# 10. Fase 6 --- Frontend

Aplicar o mesmo princípio.

Mapear antes:

-   navegação;
-   estado global;
-   seleção de obra/capítulo;
-   chamadas API;
-   polling;
-   renderizadores;
-   viewer;
-   módulos de Merge;
-   Texto Off;
-   Balanceamento;
-   Exportação;
-   Mega Menu.

Separar progressivamente:

``` text
UI rendering
state
API client
domain controllers
shared components
viewer
```

Não alterar simultaneamente contrato backend e consumidor frontend.

Quando um contrato precisar mudar:

1.  criar compatibilidade;
2.  migrar consumidor;
3.  validar;
4.  remover contrato antigo em fase posterior.

------------------------------------------------------------------------

# 11. Fase 7 --- Configuração e ambientes

Depois da estabilização estrutural:

-   centralizar configuração compartilhável;
-   documentar configuração específica por pipeline;
-   remover paths hardcoded quando seguro;
-   documentar seleção de runtime/venv;
-   manter ambientes especializados quando houver justificativa técnica;
-   garantir snapshots reproduzíveis.

Não consolidar venvs apenas para "simplificar".

Ambientes diferentes podem representar dependências incompatíveis e
devem ser tratados como fronteiras operacionais legítimas.

------------------------------------------------------------------------

# 12. Fase 8 --- Remoção de legado

Um arquivo só pode ser removido quando houver evidência de que:

-   não é importado;
-   não é chamado dinamicamente;
-   não é usado por subprocesso;
-   não é referenciado por configuração;
-   não é necessário para recuperação;
-   não é utilizado por fluxo manual conhecido;
-   testes e smoke tests permanecem verdes.

Registrar remoções relevantes no ADR/changelog da refatoração.

------------------------------------------------------------------------

# 13. Validação obrigatória por fase

Cada fase deve terminar com:

``` text
[ ] git status conhecido
[ ] diff revisado
[ ] nenhuma alteração fora do escopo
[ ] sintaxe válida
[ ] testes específicos verdes
[ ] contratos relacionados verdes
[ ] regressão relevante verde
[ ] smoke test real aprovado
[ ] artefatos comparados quando aplicável
[ ] documentação atualizada
[ ] commit isolado
[ ] rollback conhecido
```

Se qualquer item crítico falhar, **não avançar para a próxima fase**.

------------------------------------------------------------------------

# 14. Definition of Done da refatoração

A refatoração estará concluída quando:

-   responsabilidades arquiteturais estiverem explícitas;
-   `processing_web.py` não concentrar regras de múltiplos domínios;
-   frontend possuir módulos com fronteiras claras;
-   paths/configuração tiverem autoridade conhecida;
-   ambientes especializados estiverem documentados e recuperáveis;
-   contratos críticos estiverem cobertos;
-   arquivos ativos, experimentais, diagnósticos e backups estiverem
    claramente separados;
-   código morto comprovado tiver sido removido;
-   documentação refletir a implementação real;
-   fluxos funcionais produzirem resultados equivalentes à baseline;
-   não houver regressão funcional conhecida introduzida pela
    refatoração.

------------------------------------------------------------------------

# 15. Regra operacional para o desenvolvedor

Para **cada etapa da refatoração**, seguir obrigatoriamente:

``` text
AUDITAR
   ↓
MAPEAR DEPENDÊNCIAS
   ↓
IDENTIFICAR CONTRATO
   ↓
PROTEGER COM TESTE
   ↓
PROPOR EXTRAÇÃO
   ↓
IMPLEMENTAR MUDANÇA MÍNIMA
   ↓
VALIDAR AUTOMATICAMENTE
   ↓
VALIDAR CASO REAL
   ↓
COMPARAR COM BASELINE
   ↓
DOCUMENTAR
   ↓
COMMIT
```

Nunca iniciar a próxima extração enquanto a anterior não estiver
comprovadamente estável.

------------------------------------------------------------------------

# 16. Primeiro trabalho autorizado

O primeiro trabalho **não é alterar `processing_web.py`**.

Executar somente:

> **Fase 0 --- Current State & Recovery Baseline**

Entregar:

1.  inventário estrutural classificado;
2.  baseline Git/submódulos;
3.  inventário de venvs/runtimes;
4.  comparação dos snapshots de ambiente existentes;
5.  baseline da suíte de testes;
6.  catálogo dos fluxos críticos;
7.  lista inicial de riscos;
8.  lacunas encontradas;
9.  evidências/comandos utilizados;
10. recomendação do próximo passo.

Após revisão e aprovação dessa baseline, iniciar a Fase 1.

**Nenhuma refatoração estrutural ou funcional está autorizada antes
desse gate.**
