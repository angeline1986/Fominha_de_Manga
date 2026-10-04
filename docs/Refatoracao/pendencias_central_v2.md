# Central V2 — Índice operacional de pendências

## Baseline e uso

- **HEAD desta revisão:** `8ccf35d7` — `docs(central-v2): consolida pendencias e conformidade de enderecamentos`.
- O índice foi revisado contra o código vigente em `8ccf35d7`; a atualização de conformidade de endereçamentos mencionada no histórico já está nesse commit.
- Este arquivo consolida estado, evidência e próxima investigação. Não substitui os documentos especializados nem transforma hipóteses em diagnósticos.
- Prioridades são orientação prática, não bloqueios automáticos ao desenvolvimento funcional.

## P1 — Catálogo de resíduos por capítulo

**Status:** IMPLEMENTADO — AGUARDANDO VALIDAÇÃO FUNCIONAL MANUAL

- **Implementado:** estado confirmado separado do estado editável por página; dirty state determinístico por identidade/conteúdo, independente da ordem do array; bolinha consultando o estado atual do catálogo, incluindo rascunhos válidos e remoções locais.
- **Implementado:** rascunhos permanecem na store por página ao navegar; “Catalogar resíduo” considera páginas dirty do capítulo, inclusive quando outra página está selecionada.
- **Implementado:** POST retrocompatível aceita `pages` para batch do mesmo passo/capítulo. O backend valida todas as páginas e ocorrências antes de atualizar o manifesto com uma única substituição atômica. Página dirty com `occurrences=[]` remove o conteúdo persistido daquela página/passo.
- **Implementado:** falha de validação preserva estado dirty; erro de rede ou HTTP 5xx reconcilia o snapshot via GET; retry substitui por IDs estáveis e não duplica ocorrências.
- **Validação automatizada:** testes focados de comparação/catálogo frontend e backend passaram; sintaxe JS/Python e `git diff --check` passaram.
- **Pendente:** validação funcional manual pela sequência descrita no pedido de implementação. Não marcar concluído nem avançar à integração com o Passo 2 antes dessa revisão.

## P1 — Autoridade do catálogo sobre o Auto-Cleaner Passo 2

**Status:** PENDENTE — NÃO IMPLEMENTADO NESTA ENTREGA

- **Fato confirmado:** o Auto-Cleaner Passo 2 **não consulta** `RESIDUE_OCCURRENCES`. A elegibilidade vem do relatório/manifesto do Passo 1; a máscara processada vem das máscaras de balão transparente e de texto adiado do Passo 1.
- **Fato observado:** há classificações manuais de regiões como degradê/gradiente no resultado do Passo 1.
- **Objetivo:** proteger somente as regiões classificadas manualmente com tipos fora da responsabilidade de transparência do Passo 2, sem excluir toda a página; outras regiões candidatas da mesma página devem continuar elegíveis.
- **Tipos atualmente persistidos:** `residuo_degrade` (“Resíduo do degradê”) e `residuo_gradiente` (“Resíduo do gradiente”). Não renomear nem ampliar os tipos protegidos sem decisão funcional.
- **Ponto de integração recomendado:** orquestração backend carrega e valida as ocorrências do Passo 1 e as passa como exclusões estruturadas por página; o processamento do Passo 2 subtrai as regiões protegidas da máscara efetiva antes do inpainting. Usar a interseção espacial com a máscara real, sem threshold geométrico novo e sem tornar a página inteira inelegível.
- **Evidência:** `query_merged_level2()` deriva páginas candidatas do relatório do Passo 1; `execute_merged_level2()` envia esses nomes ao worker; `level2_process.process()` constrói a máscara a partir de texto adiado ∩ balão transparente. Não há leitura de `RESIDUE_OCCURRENCES` nesses módulos.
- **Próxima etapa:** integrar leitura do catálogo, exclusão regional e testes de coexistência na mesma página; preservar detector, thresholds, inpainting, candidate discovery e manifests existentes.

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
