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
                                               ├── Validar Faixa
                                               └── Novos Cortes

Merge final
    │
    ├── Balanceamento
    ├── Gerar PDF
    └── Texto Off
```

Cada etapa trabalha sobre artefatos derivados. O conteúdo original deve permanecer preservado.

O fluxo detalhado de Auto-Merge e Merge Manual também está disponível em [HTML](docs/fluxo_auto_merge_merge_manual.html).

## Visão Geral

A tela **Visão geral** apresenta o estado atual da obra selecionada e serve como ponto de acompanhamento do processamento.

## Validar Imagens

A etapa **Validar imagens** inspeciona as imagens antes do processamento de merge.

Ela permite identificar capítulos ou imagens que precisam de atenção antes de avançarem pelo fluxo.

## Auto-Merge e Merge Manual

Este é o fluxo da Central V2. Os cinco níveis automáticos trabalham em sequência, e cada nível posterior recebe apenas as regiões que o anterior deixou pendentes. O Merge Manual trata os resíduos que continuarem sem uma composição segura após o Nível V.

```text
IMG/<capítulo>/page-*.png
        │
        ▼
  Auto-Merge I ── completo ──► MERGE oficial
        │ parcial
        ▼
  Auto-Merge II ─ completo ─► MERGE oficial
        │ parcial
        ▼
  Auto-Merge III ─ completo ► MERGE oficial
        │ parcial
        ▼
  Auto-Merge IV ─ completo ─► MERGE oficial
        │ parcial
        ▼
  Auto-Merge V ─ completo ──► MERGE oficial
        │ residual / Revisão Merge
        ▼
  Validar Faixa (Merge Manual)
        │ selecionar capítulo, bloco e páginas
        ▼
  Novos Merges ─► Gerar proposta ─► Visualizar resultado
                                      │
                                      ├─ voltar e ajustar cortes
                                      └─ Aplicar composição final
```

### Como executar pela Central V2

1. Inicie a Central pelo menu do projeto e selecione a Central V2.
2. Selecione provider e obra no contexto da aplicação.
3. Abra **Processamento → Auto Merge** e escolha o nível desejado no seletor I–V.
4. Confira os capítulos elegíveis e os dados da consulta. Marque os capítulos que quer processar.
5. Acione a execução e confirme a seleção. A tela acompanha o job e apresenta um resumo por capítulo.
6. Se o resumo indicar que todos os intervalos foram resolvidos e o MERGE foi validado, o capítulo termina o fluxo automático. Se indicar residual e próxima etapa, execute o nível seguinte.
7. Depois do Nível V, trate os capítulos ainda pendentes em **Merge Manual → Validar Faixa**.

Uma execução é explícita e limitada aos capítulos selecionados. Os resultados, erros, quantidade de artefatos, páginas residuais e próxima etapa são apresentados por capítulo. A ação **Abrir pasta** aponta para o estágio correspondente.

### O que cada nível faz

| Nível | Entrada autorizada | Estratégia em linhas gerais | Se não resolver tudo |
| --- | --- | --- | --- |
| I | Imagens-fonte do capítulo | Reutiliza a análise e os limites seguros do image stitcher V3. Persiste os trechos que podem ser cortados sem forçar um limite inseguro. | Registra intervalos residuais para o Nível II. |
| II | Somente resíduos declarados pelo manifesto I | Procura caminhos seguros no residual usando faixas brancas e faixas de cor uniforme; prefere uma divisão equilibrada quando há alternativas válidas. | Salva os trechos seguros e encaminha o restante ao Nível III. |
| III | Somente resíduos declarados pelo manifesto II | Faz busca estrutural local, mantendo as decisões SAFE/UNSAFE/INCONCLUSIVE do classificador existente. Materializa apenas cortes SAFE. | Preserva como residual o trecho sem limite estrutural seguro e encaminha ao Nível IV. |
| IV | Somente resíduos declarados pelo manifesto III | Procura uma composição global dirigida e estruturalmente segura para cada residual. | Guarda os trechos comprovados e encaminha o residual ao Nível V. |
| V | Somente resíduos declarados pelo manifesto IV | Faz busca global exaustiva SAFE. Quando possível, conserva um prefixo seguro e deixa o sufixo exato como residual. | Expõe o residual ao estado de Revisão Merge, consumido pela fila do Merge Manual. |

Os critérios próprios de cada nível não são intercambiáveis. Altura, quantidade de imagens, cor ou preferência por equilíbrio não bastam para declarar um corte seguro. Quando o algoritmo não comprova um limite permitido, a região permanece pendente; o sistema não inventa um corte para fechar a composição.

### Estágios, manifestos e promoção

Os arquivos-fonte são lidos em ordem natural de página e tratados em um eixo vertical global. Cada intervalo segue a convenção semiaberta `[início, fim)`, o que permite representar trechos contíguos sem repetir pixels de fronteira. Os artefatos derivados preservam a ordem e os pixels cobertos pelas fontes.

Cada estágio guarda imagens e um manifesto por capítulo:

| Etapa | Diretório dentro de `FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/<etapa>/<capítulo>/` | Manifesto |
| --- | --- | --- |
| I | `AUTO_MERGE` | `auto-merge-manifest.json` |
| II | `MERGE_LEVEL2` | `merge-level2-manifest.json` |
| III | `MERGE_LEVEL3` | `merge-level3-manifest.json` |
| IV | `MERGE_LEVEL4` | `merge-level4-manifest.json` |
| V | `MERGE_LEVEL5` | `merge-level5-manifest.json` |

Os identificadores atuais dos algoritmos registrados são `auto_merge_level1_complete` ou `auto_merge_level1_resolved_segments` (I), `merge_level2_bounded_safe_path_v1` (II), `merge_level3_structural_safe_v1` (III), `merge_level4_directed_structural_safe_v1` (IV) e `merge_level5_global_structural_safe_v1` (V). Cada leitor também valida o schema e os dados mínimos definidos para seu nível.

O manifesto registra, conforme o contrato do nível, algoritmo e schema, capítulo, dimensões e altura total, intervalos e arquivos materializados, resíduos pendentes, diagnósticos e proveniência da etapa anterior. Os níveis II–V verificam que a entrada autorizada ainda corresponde ao manifesto anterior; a cadeia usa hashes SHA-256 nos pontos definidos pelo contrato. Um manifesto ausente, inválido ou desatualizado não autoriza a etapa seguinte.

Um estágio intermediário pode conter artefatos SAFE sem constituir um MERGE oficial completo. A promoção ao diretório oficial `FLUXO_SECUNDARIO/02_MERGE/<capítulo>/` só ocorre quando a composição cobre o capítulo inteiro, em ordem, sem lacunas, sobreposições ou dimensões incompatíveis. A promoção combina os artefatos dos estágios já existentes; não precisa renderizar de novo os níveis anteriores.

Os originais em `IMG/` permanecem preservados. A V2 usa diretórios de estágio isolados, não sobrescreve silenciosamente estágios ou destinos oficiais ocupados e valida fontes e saídas antes de promover. Uma mudança de fonte ou proveniência pode invalidar a continuação de um estágio.

Na Central V2, cada nível tem consulta e execução próprias. O Nível I processa capítulos selecionados com até três workers; II–IV usam até dois por execução; V processa sequencialmente para limitar o pico de memória da busca global. A V2 mantém transporte, jobs, interface e orquestração próprios e delega as decisões de corte aos módulos de domínio correspondentes. Ela não chama a Central V1 para executar esses níveis. O menu oficial serializa a abertura das Centrais e a execução V2 faz preflight contra uma V1 ativa; não abra as duas sobre a mesma obra ao mesmo tempo.

### Merge Manual: fila e escolha do intervalo

O Merge Manual começa em **Validar Faixa**. A fila é uma consulta dos capítulos que têm um residual autoritativo elegível, conforme o estado usado pela Revisão Merge; a tela não executa novamente os níveis automáticos para recalcular esse residual. Capítulos fora da fila não têm pendência manual reconhecida. Estados bloqueados ou manifestos incompatíveis precisam ser corrigidos na origem do estado antes de gerar uma proposta.

Ao expandir a tabela e selecionar um capítulo:

1. A Central apresenta os blocos residuais pendentes daquele capítulo.
2. A sessão de configuração permite escolher **Início** e **Fim** dentro do mesmo bloco. O fim não pode preceder o início.
3. A prévia apresenta as páginas que compõem o intervalo selecionado. Selecionar outra página ajusta o trecho correspondente no editor de cortes.
4. **Submeter a Novos Cortes** abre o editor isolado para a faixa selecionada.

Os intervalos podem terminar no meio de uma imagem-fonte. Nesse caso, a faixa usa somente o recorte residual permitido, preservando os offsets de origem; a imagem original não é alterada.

### Merge Manual: editor de cortes

O editor apresenta a sequência vertical do residual e as ferramentas **Réguas**, seletor de cor, marca-texto das páginas ímpares, lista de páginas, zoom e botão **Gerar proposta**.

As visualizações com zoom — prévia do intervalo, editor de cortes e resultado — também oferecem **Modo Foco**. O botão ou a tecla **F** expande a visualização para a janela; **Esc** retorna. No editor, o dock lateral mantém seleção de régua, adição de cortes, marca-texto, zoom e geração de proposta sincronizados com os controles da barra lateral. O dock não exibe um rótulo “Esc” nem cria rolagem horizontal; a tecla continua disponível como atalho.

- Adicione quantas réguas forem necessárias e posicione-as clicando na prévia ou arrastando a linha. A posição é medida no eixo vertical da faixa montada. As cores padrão se repetem ciclicamente quando todas as opções da paleta já foram usadas.
- Clique no seletor de uma régua para escolher sua cor.
- O marca-texto destaca páginas ímpares na prévia; ele é apenas visual e não altera os pixels.
- Clique em uma página na lista para rolar até o trecho dela no visualizador. Passe o cursor para abrir sua miniatura.
- Revise a ordem e a posição dos cortes antes de gerar. A proposta exige pelo menos uma régua e cortes válidos, internos à faixa, sem coordenadas duplicadas.

### Gerar, visualizar e aplicar uma proposta

**Gerar proposta** materializa as partes da faixa selecionada, grava imagens e um manifesto em:

```text
FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/MERGE_MANUAL_PROPOSALS/<capítulo>/<proposta>/
```

O manifesto `merge-manual-manifest.json` identifica a proposta, o bloco e as páginas de origem, os offsets, os cortes, os arquivos resultantes e as assinaturas das fontes/estado de revisão usados. Seu estado inicial é `PROPOSTA_GERADA`. Gerar a proposta não altera o MERGE oficial nem os originais.

Após a geração, a Central abre **Resultado**. A página mostra todas as imagens resultantes dos cortes lado a lado dentro de um único quadro de composição. Sob cada segmento aparece somente o intervalo de páginas que o delimita, por exemplo `page-226.png → page-232.png`; não há o rótulo “Páginas” nem uma lista extensa de todos os arquivos intermediários. Limites coincidentes com o fim de uma página usam essa página como fronteira, que pode aparecer nos intervalos dos dois segmentos adjacentes. A tela também oferece zoom e modo foco. **Voltar aos cortes** retorna ao editor preservando as réguas e os cortes para ajustes; uma nova geração cria uma nova proposta.

**Aplicar composição final** é uma ação separada e pede confirmação pelo popup compartilhado da Central V2. Sucesso e falhas também são comunicados pelo popup compartilhado. O backend revalida a proposta, as imagens-fonte e o estado autoritativo da revisão. Ele combina os artefatos automáticos fora da faixa com os resultados manuais dentro dela e valida que a cobertura final do capítulo seja contínua, completa, sem lacunas ou sobreposições, e com dimensões compatíveis. Se ainda houver outros resíduos pendentes fora da faixa selecionada, a aplicação é recusada; resolva-os antes.

Quando a validação passa, a composição é montada em uma área temporária e promovida transacionalmente para `FLUXO_SECUNDARIO/02_MERGE/<capítulo>/`. O manifesto oficial registra a proposta utilizada e a proposta manual muda para `EFETIVADO`. Se a validação ou promoção falhar, a tentativa é revertida e a composição anterior é restaurada.

Uma proposta fica obsoleta se o estado de revisão ou qualquer fonte usada mudar depois de sua criação. Nesse caso, volte à fila, recarregue o estado e gere uma proposta atualizada; não reutilize o resultado antigo.

### Diagnóstico de estados comuns

| Situação | Interpretação / próximo passo |
| --- | --- |
| Capítulo não aparece em Validar Faixa | Não há residual manual elegível reconhecido para o capítulo nesse estado. Confira os resultados e manifestos dos níveis automáticos. |
| Nível seguinte não lista o capítulo | A entrada anterior pode estar completa, ausente, inválida, obsoleta ou sem resíduos autorizados para esse nível. Leia o resumo do nível anterior e valide sua proveniência. |
| Estágio já existe e nova execução é bloqueada | O estágio não é substituído automaticamente. Inspecione seus arquivos e manifesto antes de decidir qualquer limpeza ou nova execução. |
| Execução parcial apresenta residual | Os trechos seguros ficam registrados; continue no nível indicado pelo resumo. O residual não foi descartado. |
| Aplicação manual informa pendências fora da faixa | Há outros intervalos ainda pendentes no capítulo. Gere e valide propostas para eles antes de aplicar a composição completa. |
| Proposta ficou obsoleta | As fontes ou o estado autoritativo mudaram. Recarregue a fila e gere uma proposta com os dados atuais. |

### Testes dos contratos

Para verificar a Central V2 a partir da raiz do projeto:

```sh
python3 -m unittest discover -s dev/tests -p 'test_central_v2_*.py'
python3 -m unittest dev.tests.test_merge_manual_readonly dev.tests.test_merge_manual_proposal dev.tests.test_merge_manual_apply_final
node --experimental-vm-modules --test dev/tests/central_v2_frontend/*.test.mjs
```

Os testes HTTP que iniciam servidor local podem exigir permissão para abrir portas. Os testes em memória e de domínio não executam processamento sobre suas obras reais.

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
