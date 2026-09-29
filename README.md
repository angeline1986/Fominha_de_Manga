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

As visualizações com zoom — prévia do intervalo, editor de cortes e resultado — também oferecem **Modo Foco**. O controle exibe somente o ícone e a palavra **Foco**; a tecla **F** continua sendo atalho para expandir a visualização à janela e **Esc** para retornar. No editor, o dock lateral mantém seleção de régua, adição de cortes, marca-texto, zoom e geração de proposta sincronizados com os controles da barra lateral. O dock não exibe um rótulo “Esc” nem cria rolagem horizontal.

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

O fluxo de **Balanceamento** é independente do Auto-Merge e do Merge Manual. A tela **Validar Estado** consulta o MERGE oficial e apresenta o diagnóstico por capítulo. A regra atual sinaliza merges internos com altura inferior a 50% da média dos dois vizinhos; primeiro e último merge ficam fora da comparação.

A validação usa um layout dividido: a lateral reúne capítulos, filtros e merges; o canvas mostra as imagens selecionadas lado a lado, em escala proporcional às alturas reais. A tela inicia no primeiro capítulo e pré-seleciona o primeiro desvio com seus vizinhos (ou os dois primeiros merges quando não há desvios). É possível alternar entre barras relativas e valores em pixels, filtrar desvios, conferir miniaturas no hover, ajustar zoom de 30% a 120% e abrir o Modo Foco. A seleção enviada para Novos Cortes precisa conter pelo menos dois merges contíguos.

```text
02_MERGE/<capítulo>/merge-manifest.json
        │
        ├── consulta somente leitura ──► Validar Estado
        │                                  │
        │                                  └── selecionar merges contíguos
        │                                               ▼
        │                                        Preparar editor
        │                                               ▼
IMG/<capítulo>/page-*.png ────────────────► Ajustar réguas e gerar proposta
                                                        │
                                      Aplicar composição final (confirmação)
                                                        ▼
                                      validar e promover para 02_MERGE
```

### Consulta e validação explícita

Ao abrir a tela, a consulta lê os manifestos e dimensões existentes; não grava validações nem modifica arquivos. O botão **Atualizar** inicia um job explícito que registra o diagnóstico. A interface mostra o estado, a altura e o motivo das pendências por merge. Para editar, selecione pelo menos dois merges adjacentes na ordem do manifesto.

### Editor e proposta manual

**Novos Cortes** reconstrói a região escolhida a partir de `IMG/`, prepara uma prévia, e carrega as fronteiras atuais como réguas iniciais. As réguas podem ser adicionadas sem limite fixo, removidas, selecionadas e arrastadas; cada posição deve permanecer dentro da região e ser distinta. O zoom e o Modo Foco são controles de apresentação. Gerar a proposta cria novos segmentos em área de processamento e não altera `IMG/` nem `02_MERGE/`.

Use **Aplicar composição final** para substituir a sequência selecionada. A confirmação usa o popup compartilhado da Central. Antes de promover, o domínio valida a proposta persistida, a contiguidade e a cobertura global; os segmentos candidatos são montados e conferidos numa área temporária. Só então a nova composição e seu manifesto substituem o capítulo em `FLUXO_SECUNDARIO/02_MERGE/<capítulo>/`. Uma falha durante a promoção restaura a pasta anterior. As imagens originais continuam em `IMG/`.

Os manifestos de editor, proposta e status ficam sob `FLUXO_SECUNDARIO/01_MERGE_PROCESSAMENTO/`; arquivos temporários da proposta não são tratados como MERGE oficial. A tela de resultado apresenta os artefatos da proposta antes da confirmação. A consulta de imagens aceita somente arquivos declarados nos manifestos.

**Limite funcional atual:** a tela V2 expõe a geração manual de cortes. O gerador automático de partições visuais ainda não é ligado a este fluxo, pois seu contrato de proposta não é aceito pela operação de efetivação manual. O domínio existente permanece responsável pelos algoritmos e pela promoção.

## Gerar PDF

A geração de PDF está dividida em:

### Original

Gera o PDF utilizando as imagens correspondentes ao fluxo original.

### Merge

Gera o PDF a partir do resultado do processamento de merge.

## Texto Off

O fluxo **Texto Off** trata a remoção de texto das imagens processadas.

A Central organiza o fluxo Merged em níveis explícitos e mantém a execução anterior em Legado:

```text
Texto Off
   ├── Merged
   │   ├── Nível I
   │   └── Nível II
   ├── Legado
   ├── Comparar resultados
   └── Correção assistida
```

### Original

Processamento das imagens provenientes do fluxo original.

### Merged · Nível I

Processa imagens do MERGE oficial em `FLUXO_SECUNDARIO/02_MERGE/<capítulo>/` com Cleaner V2 e a proteção de balões transparentes. Os resultados são publicados em `FLUXO_SECUNDARIO/04_TEXTO_OFF/MERGED_NIVEL_I/<capítulo>/`, separados em `clean/`, `mask/` e `json/`; o pós-processamento legado não roda nesta tela.

```text
MERGED_NIVEL_I/<capítulo>/
├── clean/  imagens limpas
├── mask/   máscaras Cleaner, balões e texto adiado
└── json/   manifestos e relatórios
```

O Nível I segmenta os balões e aplica uma proteção conservadora aos que mostram variação de cor/textura do desenho através do interior. Componentes de máscara que tocam um balão classificado como transparente são preservados da limpeza e registrados no relatório para uma rodada específica futura. Balões opacos continuam sujeitos à validação normal; componentes fora de um único balão ou ambíguos também são preservados.

O teste focado de *Things that deserve to die*, capítulo 3, nas imagens `page-156-163.png` e `page-179-187.png`, detectou dois balões transparentes por imagem. A comparação confirmou que as áreas desses quatro balões permaneceram pixel a pixel iguais às fontes e sem pixels de máscara aplicados. A consulta da tabela usa o manifesto e a presença dos arquivos, sem decodificar todas as páginas durante a listagem.

### Merged · Nível II

A tela consulta os relatórios do Nível I e lista capítulos com balões transparentes detectados ou componentes adiados. O Nível II usa a máscara Cleaner adiada pelo Nível I, aplica as dilatações elípticas 3×3 e 9×9 e reconstrói com LaMa e contexto de 120 px, limitado ao interior do balão correspondente. Essa sequência deriva do Patch Transparente Legado que teve resultado aprovado no teste manual; CRAFT não faz parte da máscara automática. Cada capítulo também separa os arquivos finais em `clean/`, as máscaras em `mask/` e manifestos/relatórios em `json/`.

```text
MERGED_NIVEL_II/<capítulo>/
├── clean/  composição final do capítulo
├── mask/   máscara autorizada de texto por página
└── json/   manifesto e relatório da rodada
```

A tabela distingue o total de imagens do MERGE das páginas candidatas ao Nível II. No Cap. 3 de *Things that deserve to die*, o relatório mostra 31 imagens oficiais, 10 páginas com balões transparentes e 17 balões; portanto, 31 é a composição completa do capítulo, não o número de páginas com casos transparentes. O Nível II grava uma composição completa para manter o capítulo íntegro.

O Patch Transparente Legado manual limpou as duas regiões selecionadas em `page-179-187.png`. A execução automática anterior não aplicou a máscara: embora o relatório Nível I registrasse 17 balões transparentes, ele não vinculava cada balão ao rótulo da imagem de máscara. O Nível II ignorava os balões sem `mask_label` e ainda marcava o capítulo como concluído com zero pixels alterados. O contrato foi corrigido e versionado como Nível I v4/Nível II v1; agora a execução falha se esse vínculo estiver ausente ou divergente e informa separadamente quando não houve alteração visual.

Cada balão é reconstruído em uma região de contexto própria. Isso impede que balões distantes criem uma única área LaMa do tamanho da página. No dispositivo MPS, o modelo é reciclado a cada três inferências e a cache de inferência é liberada entre regiões para limitar o uso acumulado de memória. O processamento também carrega uma página por vez.

Teste integral de *Things that deserve to die*, capítulo 3: 31 páginas analisadas, 10 páginas candidatas, 8 páginas com texto na máscara Nível II, 1.689.843 pixels cobertos, 1.654.872 pixels alterados e zero pixels modificados fora das máscaras. O Nível II terminou em 100,448 s; o Nível I anterior registrou 207,947 s. A validação visual ainda encontrou marcas residuais nas páginas `page-051-059`, `page-078-083`, `page-156-163` e `page-179-187`. Testes com dilatação 15×15 e 31×31 ampliaram a área alterada, mas não trouxeram melhora visual relevante; os parâmetros 3×3 + 9×9 permanecem como receita de referência até testar outra técnica de reconstrução. A oportunidade de desempenho identificada é reaproveitar as inferências YOLO do Nível I, atualmente repetidas na autorização e na gravação das máscaras. Essa otimização fica pendente de instrumentação e comparação pixel a pixel; nenhuma etapa foi paralelizada e os parâmetros visuais não mudaram.

### Legado

Mantém a tela anterior e a execução completa existente em `FLUXO_SECUNDARIO/04_TEXTO_OFF/MERGED/<capítulo>/`, incluindo seus níveis internos automáticos. Os resultados existentes permanecem no mesmo local.

O manifesto registra a configuração OCR aplicada pelo perfil. No perfil atual do Cleaner V2, `detect_box` e `auto` são configurados, mas Tesseract está desligado; o Panel Cleaner acaba usando MangaOCR em japonês. Isso não fornece OCR coreano ou chinês. A classificação por cor/textura também é uma heurística conservadora: cobertura universal de estilos transparentes ainda requer mais amostras e validação.

Detalhes de arquitetura, métricas, regras de autorização, campos de observabilidade e limitações estão em [TextOff Merged e preservação de balões transparentes](docs/textoff_merged_transparencia.html). As dependências do motor ficam descritas em [Cleaner V2](processamento/limpeza_baloes/cleaner_v2/README.md).

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
