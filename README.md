# Fominha de Mangá

Fominha de Mangá é um hub local para extração, validação e processamento de mangás, manhwas e webtoons.

O projeto centraliza diferentes etapas do fluxo de processamento e mantém os arquivos originais preservados, isolando os resultados derivados em estruturas próprias.

## Central de Processamento

A principal interface operacional do projeto é a **Central de Processamento Web**.

Ela permite selecionar o provider e a obra e acompanhar as diferentes etapas do processamento em uma única interface.

### Inicialização

O acesso pode ser feito pelo menu de terminal:

```bash
cd Fominha_de_Manga
python3 orquestracao/menu.py
```

No menu, selecione **Central de Processamento**.

A Central é iniciada por padrão em:

```text
http://127.0.0.1:8766
```

O servidor utilizado pela interface está em:

```text
interface_web/processing_web.py
```

A porta padrão pode ser configurada pela variável de ambiente `FOMINHA_PROCESSING_PORT`.

## Fluxo de Processamento

A Central organiza o processamento em etapas independentes e progressivas.

De forma simplificada:

```text
Imagens originais
        │
        ▼
Validar imagens
        │
        ▼
Auto-Merge
        │
        ├── Nível I
        ├── Nível II
        ├── Nível III
        ├── Nível IV
        └── Nível V
                │
                ├── resolvido ─────────────► Merge final
                │
                └── residual ──────────────► Merge Manual
                                               │
                                               ├── Validar resíduos
                                               └── Novos Cortes

Merge final
    │
    ├── Balanceamento
    ├── Gerar PDF
    └── Texto Off
```

Cada etapa trabalha sobre artefatos derivados. O conteúdo original deve permanecer preservado.

## Visão Geral

A tela **Visão geral** apresenta o estado atual da obra selecionada e serve como ponto de acompanhamento do processamento.

## Validar Imagens

A etapa **Validar imagens** inspeciona as imagens antes do processamento de merge.

Ela permite identificar capítulos ou imagens que precisam de atenção antes de avançarem pelo fluxo.

## Auto-Merge

O Auto-Merge é dividido em níveis progressivos de processamento:

```text
Auto-Merge
   │
   ├── Nível I
   ▼
Nível II
   │
   ▼
Nível III
   │
   ▼
Nível IV
   │
   ▼
Nível V
```

Cada nível tenta resolver automaticamente os segmentos que atendem aos seus critérios.

Os níveis posteriores trabalham sobre resíduos que não foram completamente resolvidos pelas etapas anteriores.

### Auto-Merge Nível V

O **Nível V** executa a etapa final do fluxo automático.

Quando encontra uma composição completa válida, o capítulo pode seguir como resolvido automaticamente.

Quando ainda resta uma região residual após a análise do Nível V, o fluxo atual é:

```text
Auto-Merge Nível V
        │
        └── residual
              │
              ▼
         Merge Manual
```

A própria interface do resultado do Nível V permite abrir **Validar Merge Manual** para continuar o tratamento do capítulo.

## Merge Manual

O **Merge Manual** recebe resíduos que precisam de intervenção após o processamento automático.

Ele é dividido em:

### Validar resíduos

Apresenta os resíduos autoritativos ainda pendentes para o capítulo.

### Novos Cortes

Permite trabalhar manualmente nos cortes necessários para resolver os resíduos selecionados.

## Balanceamento

O fluxo de **Balanceamento** possui duas etapas:

```text
Balanceamento
   │
   ├── Validar
   └── Novos Cortes
```

### Validar

Permite analisar os merges existentes e identificar regiões que podem precisar de redistribuição.

### Novos Cortes

Permite trabalhar sobre uma proposta de novos cortes para a região selecionada.

O balanceamento é tratado como fluxo próprio e não deve alterar indiscriminadamente outras etapas do processamento.

## Revisão Merge

A Central ainda possui as áreas:

- **Revisão Merge**
- **Revisão Merge V2**

Essas funcionalidades permanecem existentes por compatibilidade com fluxos e estados já suportados pelo projeto.

O fluxo atual de resíduos produzidos pelo **Auto-Merge Nível V**, entretanto, segue para **Merge Manual**.

## Gerar PDF

A geração de PDF está dividida em:

### Original

Gera o PDF utilizando as imagens correspondentes ao fluxo original.

### Merge

Gera o PDF a partir do resultado do processamento de merge.

## Texto Off

O fluxo **Texto Off** trata a remoção de texto das imagens processadas.

A Central possui atualmente:

```text
Texto Off
   │
   ├── Original
   ├── Merged
   ├── Comparar resultados
   └── Correção assistida
```

### Original

Processamento das imagens provenientes do fluxo original.

### Merged

Processamento das imagens provenientes do fluxo de merge.

### Comparar resultados

Permite inspecionar visualmente os resultados produzidos pelo Texto Off.

### Correção assistida

Permite selecionar manualmente uma região que ainda precisa de correção, gerar uma proposta temporária e comparar o resultado antes da aprovação.

A promoção da correção ocorre somente após confirmação explícita.

## Princípios do Processamento

O projeto segue alguns princípios importantes:

- preservar as imagens originais;
- manter processamentos secundários isolados;
- evitar alterações destrutivas em etapas anteriores;
- utilizar manifests e estados para representar resultados intermediários;
- promover resultados somente quando a etapa correspondente estiver validada;
- tratar correções manuais de forma explícita;
- evitar que uma etapa posterior modifique silenciosamente a fonte de uma etapa anterior.

## Estrutura do Projeto

```text
Fominha_de_Manga/
│
├── interface_web/
│   └── Central de Processamento Web
│
├── processamento/
│   └── módulos de processamento
│
├── orquestracao/
│   └── menu e orquestração do projeto
│
├── download/
│   └── mangago_downloader
│
├── dev/
│   ├── testes
│   └── artefatos de desenvolvimento
│
├── docs/
│   └── documentação técnica
│
├── reports/
│   └── relatórios e artefatos auxiliares
│
└── README.md
```

## Mangago Downloader

`download/mangago_downloader` é mantido como um projeto independente e referenciado pelo Fominha de Mangá através de um **Git submodule**.

O hub registra uma versão específica do downloader sem misturar o histórico dos dois projetos.

Alterações realizadas no Fominha de Mangá não devem modificar automaticamente o conteúdo do submodule.

## Clone

Para clonar o projeto juntamente com seus submodules:

```bash
git clone --recurse-submodules https://github.com/angeline1986/Fominha_de_Manga.git
```

Caso o repositório já tenha sido clonado sem os submodules:

```bash
git submodule update --init --recursive
```

## Atualizar o Submodule

O downloader possui histórico Git independente.

Para atualizar sua referência:

```bash
cd download/mangago_downloader
git pull origin main
cd ../..

git add download/mangago_downloader
git commit -m "chore: update mangago_downloader submodule"
```

A atualização do ponteiro do submodule no Fominha deve ser feita conscientemente e separada das alterações funcionais do hub.

## Desenvolvimento

A branch utilizada atualmente para desenvolvimento e estabilização é:

```text
recovery/merge-stable-baseline
```

Alterações funcionais devem ser realizadas de forma incremental e validadas antes de serem promovidas.

O fluxo recomendado é:

```text
Auditar
   ↓
Diagnosticar
   ↓
Comprovar a causa
   ↓
Propor a alteração
   ↓
Implementar
   ↓
Validar tecnicamente
   ↓
Validar com caso real
   ↓
Revisar o diff
   ↓
Commit
```

Para informações sobre Git e submodules, consulte:

```text
dev/docs/git_workflow.md
```

## Estado Atual

A Central de Processamento reúne atualmente os principais fluxos de validação, Auto-Merge, Merge Manual, Balanceamento, geração de PDF e Texto Off.

O desenvolvimento continua sendo feito de forma incremental, preservando compatibilidade com artefatos existentes e evitando alterações destrutivas no pipeline.
