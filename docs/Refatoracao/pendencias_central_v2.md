# Central V2 — Índice operacional de pendências

## Baseline e uso

- **HEAD base desta revisão:** `8c0b443e` — `feat(central-v2): protege residuos manuais no nivel II`.
- A revisão documental anterior registrava P1.1 em `561d413d`; P1.2 foi publicado em `8c0b443e`.
- Este arquivo consolida estado, evidência e próxima investigação. Não substitui os documentos especializados nem transforma hipóteses em diagnósticos.
- Prioridades são orientação prática, não bloqueios automáticos ao desenvolvimento funcional.

## P1 — Catálogo de resíduos por capítulo

**Status:** CONCLUÍDO — validado funcionalmente e publicado em `561d413d`.

- **Implementado:** estado confirmado separado do estado editável por página; dirty state determinístico por identidade/conteúdo, independente da ordem do array; bolinha consultando o estado atual do catálogo, incluindo rascunhos válidos e remoções locais.
- **Implementado:** rascunhos permanecem na store por página ao navegar; “Catalogar resíduo” considera páginas dirty do capítulo, inclusive quando outra página está selecionada.
- **Implementado:** POST retrocompatível aceita `pages` para batch do mesmo passo/capítulo. O backend valida todas as páginas e ocorrências antes de atualizar o manifesto com uma única substituição atômica. Página dirty com `occurrences=[]` remove o conteúdo persistido daquela página/passo.
- **Implementado:** falha de validação preserva estado dirty; erro de rede ou HTTP 5xx reconcilia o snapshot via GET; retry substitui por IDs estáveis e não duplica ocorrências.
- **Validação automatizada:** testes focados de comparação/catálogo frontend e backend passaram; sintaxe JS/Python e `git diff --check` passaram.
- **Pendente:** validação funcional manual pela sequência descrita no pedido de implementação. Não marcar concluído nem avançar à integração com o Passo 2 antes dessa revisão.

## P1 — Autoridade do catálogo sobre o Auto-Cleaner Passo 2

**Status:** IMPLEMENTADO — AGUARDANDO VALIDAÇÃO FUNCIONAL

- **Implementado:** a orquestração do Passo 2 lê o manifesto oficial `RESIDUE_OCCURRENCES/<capítulo>` via `stage_chapter()` e `read_manifest()`, validando provider, obra e capítulo. Consome exclusivamente `pages[page].steps["1"].ocorrencias`; o catálogo continua sem depender da UI durante o runtime.
- **Autoridade:** `residuo_degrade` e `residuo_gradiente` protegem pixels da região catalogada. `texto_residual` e `residuo_transparencia` não protegem nem forçam limpeza. `fragmento_balao` e `outro` permanecem neutros.
- **Ordem:** máscara automática por balão → dilatações normais do Passo 2 → subtração da protection mask → inpainting. A proteção usa `box_normalized` rasterizado na dimensão real da imagem, sem padding/dilatação adicional. Não altera elegibilidade da página.
- **No-change:** se a proteção remover toda a máscara automática, o inpainting é ignorado; a página gera máscara vazia, `clean: null` e `no_change_reason=manual_protection_removed_all_level2_mask`, preservando o contrato de fallback do Nível I.
- **Observabilidade estruturada:** relatório e manifesto Nível II incluem `protected_occurrences`, `protected_pixels` (pixels removidos da máscara automática), `mask_pixels_before_protection`, `mask_pixels_after_protection`, `protected_types` e motivo de no-change por página. O detalhe de progresso informa proteção aplicada somente quando pixels foram removidos; não inclui bboxes.
- **Testes automatizados:** cobertura para catálogo ausente, seis tipos, step/página/contexto, proteção parcial e total, página mista, dilatação, bordas/coordenadas, não chamada do inpainting no no-change e encaminhamento pelo worker batch. Testes focados de catálogo, comparação, Passo 2, máscaras, manifest, query, consolidação/fallback e processamento incompleto passaram.
- **Pendente:** comparar manualmente imagem, catálogo, máscara automática, região protegida e saída. Não executar Passo 2 real antes dessa revisão.

## P1 — Diagnósticos funcionais dos Passos 3 e 4

As ocorrências abaixo permanecem em diagnóstico e **não estão confirmadas como regressões**. Uma mensagem de falha isolada não determina se houve ausência legítima de insumo, capítulo não elegível, incompatibilidade de contrato ou regressão.

## P2 — Auto-Cleaner: diagnosticar Passos 3 e 4

### Passo 3 — Transparência Normal (nível técnico IV)

**Status:** PENDENTE DE DIAGNÓSTICO

- **Fato observado:** validação manual em 04/10/2026 terminou em `failed`; a interface mostrou `Nível I não forneceu máscaras válidas para o ajuste fino.` na rota `/api/textoff/merged/levelIV/execute`.
- **Fato observado:** a requisição chegou ao job e a UI apresentou a falha.
- **Hipótese atual:** a mensagem aponta para pré-condição/artefatos produzidos pelo Passo 1. Isso ainda não determina se o insumo está legitimamente ausente, se o capítulo não era elegível, se há incompatibilidade de contrato ou se existe regressão.
- **Próxima investigação:** verificar lineage, manifesto, máscaras esperadas, critérios de validade e elegibilidade do capítulo; classificar o resultado entre ausência legítima de insumo, capítulo não elegível, incompatibilidade de contrato ou regressão funcional.
- **Não fazer:** não marcar o Passo 3 como quebrado com base somente na mensagem; não alterar algoritmo, thresholds ou contrato antes do diagnóstico.

### Passo 4 — Transparência Legada (nível técnico V)

**Status:** PENDENTE DE DIAGNÓSTICO

- **Fato observado:** validação manual em 04/10/2026 terminou em `failed`; a interface mostrou `Nível I não forneceu texto adiado para o Nível V.`
- **Hipótese atual:** ainda é preciso determinar se o capítulo deveria conter texto adiado e se a mensagem corresponde a ausência legítima de trabalho, pré-condição não satisfeita, incompatibilidade de contrato ou regressão.
- **Próxima investigação:** verificar contrato, manifesto, lineage, elegibilidade e existência esperada do texto adiado.
- **Não fazer:** não tratar a mensagem como diagnóstico definitivo. Nível V é apenas o identificador técnico interno do Passo 4 atual; a interface continua com quatro passos.

**Limite de nomenclatura da interface:** existem exatamente quatro passos de Auto-Cleaner: Passo 1; Passo 2; Passo 3 — Transparência Normal; Passo 4 — Transparência Legada. Nível IV e Nível V só aparecem como nomes técnicos internos entre parênteses quando ajudam a localizar código, rotas, manifests ou mensagens.

## P2 — Auto-Cleaner Passo 1: boxes pequenos `unknown` descartados antes da Raw Mask

**Status:** DIAGNÓSTICO CONCLUÍDO — CORREÇÃO FUTURA

- **Casos comprovados em `comix / Gazing at you / capítulo 1`:** `page-009-013.png` — `IT'S COLD.`, bbox `[659,2769,807,2800]`, área `4.588 px²`, máscara refinada com `1.132 px` na ROI; `page-021-025.png` — `REALLY?`, bbox `[429,408,565,438]`, área `4.080 px²`, máscara refinada com `2.205 px` na ROI. Nos dois casos a Raw Mask exportada do Cleaner tem `0` pixels na ROI.
- **Causa comprovada:** o ComicTextDetector detecta ambos e os classifica como `unknown`. O pré-processador do Panel Cleaner converte `unknown` para idioma nulo e descarta boxes abaixo de `suspicious_box_min_size = 40.000`; a perda ocorre antes da Raw Mask exportada. Não é falha da autorização N1, deferred/transparência, Nível II, LaMa, proteção manual P1.2, Sommelier, catálogo de resíduos nem do `min_area=20`.
- **Diretriz para a correção:** revisar o descarte de boxes pequenos `unknown`; não reduzir globalmente `suspicious_box_min_size`. Preservar a proteção contra falsos positivos e evitar regressão no tratamento dos balões transparentes.
- **Validação futura obrigatória:** confirmar `IT'S COLD.` e `REALLY?` na Raw Mask, verificar a remoção final dos dois textos, executar regressão do capítulo 1, avaliar falsos positivos e confirmar que balões transparentes continuam funcionando.
- **Proveniência diagnóstica:** MERGE SHA-256 `14067e5df29960233f0ff57605cbeb8add23a314a1facb8ac0b2df3c92614789`; execução isolada em `/private/tmp/fominha_level1_rawmask_diagnostic/n1/1/diagnostics/`.

## P2 — Auditoria de Qualidade: Antes & Depois

**Status:** IMPLEMENTADO — AGUARDANDO VALIDAÇÃO FUNCIONAL

- **Estado anterior:** a tela abria um par por etapa (`Original ↔ Nível I` ou `Nível I ↔ Nível II`) com alternância entre divisor/visão única e lado a lado; a lista do Passo 2 omitia páginas não candidatas.
- **Implementado:** a resposta de comparação em layout `triptych` fornece uma lista única de páginas e metadados para ORIGINAL, AUTO-CLEANER I e AUTO-CLEANER II. As imagens são resolvidas pelos helpers oficiais de MERGE, manifesto Nível I e `_valid_level2`; o par legado continua disponível para consumidores existentes.
- **Fallback/status:** Nível II alterado usa seu `clean`; candidato analisado sem alteração usa Nível I; página não candidata também usa Nível I com status próprio. Candidato pendente é identificado separadamente. Falta de imagem Nível I ou falta de saída Nível II declarada como alterada retorna erro visível.
- **Interface:** três colunas fixas sem visão única, mesmo zoom/ponto de scroll numa viewport compartilhada, troca atômica de página, 13 páginas por página na sidebar, busca, preview da imagem original, foco e catálogo de resíduos preservados. O estado do Nível II aparece discretamente no cabeçalho dessa coluna.
- **Automatizado:** testes focados frontend/backend, navegação/paginação, zoom, catálogo compartilhado, fallback e artefato obrigatório ausente passaram nesta revisão.
- **Pendente:** validar visualmente em `comix / Gazing at you / capítulo 1`, nas páginas `page-050-057.png` e `page-013-016.png`. Não inferir eficácia da proteção manual apenas pela tela.

## P3 — Inconsistência visual da Curadoria

### Espaçamento entre toolbar e tabela

**Status:** PENDÊNCIA VISUAL

- **Fato observado:** a toolbar com busca, filtros, perfil e botão Executar Curadoria não tem espaçamento vertical adequado em relação ao cabeçalho da tabela.
- **Impacto:** hierarquia visual/alinhamento da tela de Curadoria.
- **Próxima investigação:** comparar telas equivalentes, localizar token, classe ou gap compartilhado e reutilizar o padrão existente; conferir responsividade e alinhamento.
- **Não fazer:** não introduzir margem arbitrária específica da Curadoria antes de verificar o contrato compartilhado.

### Feedback e barra de progresso — resolvidos

**Status:** RESOLVIDO em `0f8a7a76` (`fix(central-v2): padroniza feedback da curadoria de baloes`).

A Curadoria usa a barra compartilhada na posição padrão, sem variante inline; mantém contagem/agregação em páginas; apresenta `showOperationSummary()` no sucesso e `showMessage()` no erro. Esses itens não são pendências abertas.

### Nomenclatura Bubble Sommelier

**Status:** PENDÊNCIA VISUAL / UX

- **Fato observado:** ainda existe nomenclatura relacionada a “Curadoria” na navegação/tela da feature cuja nomenclatura oficial escolhida é “Bubble Sommelier”.
- **Diretriz futura:** substituir a nomenclatura de Curadoria por “Bubble Sommelier”. Quando o contexto da tela/navegação já identificar a feature, evitar repetir “BUBBLE SOMMELIER” como título externo redundante; revisar a hierarquia visual sem alterar a funcionalidade.
- **Não fazer nesta pendência:** não alterar execução, contratos ou comportamento funcional.

### Breadcrumb na navegação

**Status:** PENDÊNCIA VISUAL / UX

- **Fato observado:** “Limpeza de Balões” não comunica claramente a posição da tela na hierarquia e funciona como retorno genérico para a seção.
- **Diretriz futura:** substituir essa apresentação por breadcrumb/migalhas de pão que reflita a hierarquia oficial das rotas e nomenclaturas, por exemplo `Texto OFF > Limpeza de Balões > Bubble Sommelier` ou `Texto OFF > Limpeza de Balões > Pincel & Retoques de Arte > Degradê`.
- **Pré-condição:** ao retomar, conferir primeiro as rotas e nomenclaturas oficiais existentes. Os exemplos são conceituais, não uma decisão fechada de hierarquia.
- **Não fazer nesta pendência:** não implementar breadcrumb nem alterar navegação nesta etapa documental.

## Backlog de UX — refinamentos da Central V2

**Status geral:** REGISTRADO / NÃO IMPLEMENTADO. Os itens abaixo são pendências para priorização futura; este registro não altera a interface, o domínio nem contratos de API.

### BL-01 — Mapear Balões: filtro inicial

- **Estado atual:** `Pincel & Retoques — Mapear Balões` abre com o filtro `Mapear` selecionado.
- **Desejado:** abrir e recarregar com `ALL` selecionado, sem selecionar `Mapear` automaticamente.
- **Critério futuro:** conferir o estado inicial e o estado após recarga da página.

### BL-02 — Mapear Balões: acesso ao comparador

- **Desejado:** oferecer, a partir de uma página do Mapear, acesso a `Comparar página` para inspecionar as marcações existentes sobre a imagem.
- **Escopo:** somente visualização; não criar edição nem iniciar processamento por esse acesso.
- **Critério futuro:** abrir o comparador da página escolhida e ver suas marcações correspondentes.

### BL-03 — Filtros da Curadoria e nomenclatura visual

- **Desejado na Curadoria de Balões:** `Todos | ⏳ Do | ✓ Done | ◉ Aptos`, com contadores `Todos (N) | ⏳ Do (N) | ✓ Done (N) | ◉ Aptos (N)`.
- **Regra visual global:** quando `Candidatos` representar esse mesmo conceito/status na Central V2, apresentar `Aptos` em filtros, contadores, cabeçalhos, labels e textos de status relacionados.
- **Limite:** preservar nomes técnicos internos, schemas, chaves JSON e contratos de API; a mudança futura é somente da apresentação ao usuário.

### BL-04 — Curadoria: seletor de perfil

- **Estado atual:** o label externo `Perfil` repete o placeholder `Selecione o perfil`.
- **Desejado:** remover o label redundante e mostrar `Perfil` no próprio select enquanto não houver opção selecionada, conforme o protótipo/print de referência.

### BL-05 — Curadoria: espaçamento antes da tabela

- **Desejado:** aumentar o espaço vertical entre busca/filtros/ações e a tabela, reutilizando exatamente o espaçamento adotado nas páginas equivalentes da Central V2; não criar valor arbitrário.
- **Relação com registro existente:** detalha a pendência `P3 — Inconsistência visual da Curadoria / Espaçamento entre toolbar e tabela` acima; não é uma segunda implementação.

### BL-06 — Paginação padronizada

- **Desejado:** nas páginas envolvidas, adicionar seletor `Exibir:` com opções `15`, `20`, `30`, `40`, `50` e default `15`.
- **Preservar:** página atual, total de páginas e controles anterior/próximo.
- **Implementação futura:** reutilizar o componente/padrão existente; evitar paginadores independentes para Mapear e Curadoria.

### BL-07 — Auto-Cleaner Check: quantidade de marcações por página

- **Estado atual:** a lista `Páginas` usa uma bolinha para indicar ocorrências, sem quantidade.
- **Desejado:** exibir indicador e contagem juntos, preferencialmente como badge compacto; por exemplo, `page-013-016.png    ● 3`. Página sem marcações não mostra indicador.
- **Fonte da contagem:** marcações efetivamente disponíveis para revisão naquela página. Não alterar a lógica das ROIs para compor o badge.

### BL-08 — Auto-Cleaner Check: feedback ao salvar decisão

- **Estado atual:** `Salvar decisão do Check` não apresenta confirmação visual suficientemente clara após o salvamento.
- **Desejado:** depois que o backend confirmar a persistência, mostrar uma mensagem de sucesso clara e temporária, como `Decisão do Check salva com sucesso.`
- **Padrão visual:** reutilizar o componente de feedback de sucesso já adotado nas demais páginas da Central V2, sem criar variante exclusiva para o Check.
- **Falhas:** continuar apresentando erros como erros; nunca mostrar sucesso sem confirmação real do backend.
- **Escopo:** somente feedback visual. Preservar a lógica de persistência, as decisões, as ROIs e o manifesto do Auto-Cleaner Check.

### Diretrizes para a implementação futura de BL-01 a BL-08

- Preservar o visual minimalista, reutilizar componentes existentes e evitar CSS/JS duplicado.
- Separar ajustes visuais de mudanças de domínio; não alterar contratos funcionais sem necessidade.
- Usar `Aptos` na apresentação quando corresponder ao conceito hoje exibido como `Candidatos`, preservando identificadores técnicos.
- Respeitar o limite de 200 linhas para arquivos novos de código/teste e não ampliar violações preexistentes.
- Validar visualmente cada item antes de marcá-lo como concluído.

## P4 — Sanitização arquitetural

**Status:** ADIADA DELIBERADAMENTE. O detalhe e a evidência permanecem em [`sanitizacao_pendente_central_v2.md`](sanitizacao_pendente_central_v2.md); este índice não os duplica.

Frentes resumidas na triagem especializada:

- scanner de arquitetura inclui `node_modules` e acaba inspecionando código de dependências;
- teste de navegação do Auto-Cleaner usa expectativa histórica/desatualizada;
- teste do Job Manager conserva expectativa antiga de `completed` mesmo com capítulo falho;
- mock do teste `http_handler.log_message` não fornece `path`/`command` ao handler;
- cinco testes HTTP não alcançam as rotas porque o ambiente bloqueia `socket.bind`;
- teste arquitetural define limite de 200 linhas: há arquivos que já excediam esse limite no HEAD da triagem e arquivos que o cruzaram no working tree então analisado;
- a sanitização especializada também registra regras para validação em `/tmp` e `/private/tmp`, sem executar cópia modificada do código operacional.

**Próxima investigação:** retomar a triagem pelo documento especializado e comparar seus números/estados com o HEAD da tarefa de sanitização. O resumo acima descreve o registro da triagem, não uma nova execução das suítes.

## P5 — Endereçamentos e layout de dados

**Status:** ADIADO / REVALIDADO contra `0f8a7a76` em 04/10/2026.

Autoridade específica: [`central_v2_conformidade_enderecamentos.md`](../central_v2_conformidade_enderecamentos.md). O levantamento original declara snapshot estático de 30/09/2026; cada achado foi reclassificado no HEAD atual. Há itens ainda aplicáveis, parcialmente resolvidos e alterados por implementação posterior; nenhum item de centralização de raízes/estágios foi considerado totalmente resolvido.

Pontos resumidos para retomada:

- BubbleSommelier introduziu uma árvore persistida própria, que precisa integrar o futuro contrato de layout.
- O Job Manager guarda jobs em memória e não introduz árvore persistida própria.
- A política do fluxo legado `MERGED` continua sendo decisão necessária antes de alterar escritores.
- Primeiro separar identificador lógico, nome físico/canônico, alias legado, valor persistido e caminho físico resolvido.
- Não presumir autorização para mover dados, renomear diretórios, invalidar manifests, alterar hashes, remover aliases ou mudar algoritmos.
- Não fazer substituição textual global de `MERGED_NIVEL_*`/`TO_MERGED_NIVEL_*`; classificar cada ocorrência semanticamente.

**Próxima investigação:** seguir a reavaliação e o plano registrados no documento de endereçamentos antes de alterar consumidores. Definir leitura legada e política do destino de escrita antes de mudar escritores.

## P6 — Expandir padronização dos logs

**Status:** PENDENTE / EVOLUÇÃO FUTURA

- **Fato observado:** o commit `72944631` (`refactor(central-v2): padroniza logs operacionais`) teve escopo deliberadamente limitado. BubbleSommelier e Cleaner I já usam o formato `HH:MM:SS.mmm LEVEL [COMPONENTE][job] ...`; outros fluxos podem continuar emitindo `[central-v2][job ...] ...`, inclusive nos fluxos técnicos dos Passos 3 e 4 observados nos testes manuais.
- **Impacto:** apresentação e correlação operacional entre fluxos; não é, por si, falha funcional.
- **Próxima investigação:** auditar um fluxo por vez e mapear progresso, callbacks, erros, subprocessos e contratos antes de expandir a padronização.
- **Não fazer:** não substituir prefixos globalmente nem descartar mensagens antes de verificar sua função operacional.

## P7 — Harness e melhorias cosméticas

### Seleção de capítulo no harness

**Status:** PENDÊNCIA DE INFRAESTRUTURA DE TESTE

- **Fato observado:** numa validação, o harness estava configurado para capítulo 3, mas a seleção real permaneceu no capítulo 2; o Nível I do capítulo 2 foi reexecutado e os artefatos foram substituídos. A integridade posterior foi validada.
- **Próxima melhoria:** selecionar por identidade estável, confirmar a seleção real antes do POST e abortar se o capítulo selecionado não for o esperado.
- **Escopo:** harness; não atribuir esse comportamento ao runtime funcional da Central.

### Seletor do diálogo final

**Status:** MELHORIA DE HARNESS

- **Fato observado:** o seletor `Fechar` era ambíguo; o job já havia terminado corretamente.
- **Próxima melhoria:** usar seletor estável e específico do componente. Não atribuir o incidente ao processamento.

### Favicon

**Status:** BAIXA PRIORIDADE / OPCIONAL

- **Fato observado:** navegador solicita `/favicon.ico`, recebe 404 e a ocorrência aparece como WARNING.
- **Próxima melhoria:** se desejado, fornecer um favicon válido.
- **Não fazer:** não esconder o WARNING para suprimir o 404; a política atual mantém erros de assets visíveis.

## Critério de retomada

Uma pendência só bloqueia trabalho funcional quando sua evidência demonstrar dependência direta com a tarefa em andamento. Mensagens de erro, hipóteses e dívidas de harness não devem ser promovidas a regressões sem investigação. Atualizar este índice e o documento especializado correspondente quando uma frente mudar de estado.
