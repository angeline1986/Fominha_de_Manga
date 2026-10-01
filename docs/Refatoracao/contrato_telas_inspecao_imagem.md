# Contrato visual — telas de inspeção de imagem

Este contrato registra os padrões compartilhados por telas que permitem inspecionar duas versões de uma página. A primeira aplicação é **Comparar Capítulo**, dentro da Central V2. Ele descreve estrutura, comportamento e semântica; não depende de valores de demonstração do HTML de referência.

## Estrutura da tela

- O cabeçalho identifica a tarefa e mantém o contexto do capítulo visível.
- Uma lateral lista as páginas do capítulo. Ela oferece busca por nome, seleção explícita, prévia da imagem original ao passar o ponteiro e paginação de 13 páginas por vez. O conteúdo do canvas não deve ser alterado ao pesquisar ou trocar a página da lista.
- O canvas tem uma barra de ferramentas própria, uma área de inspeção rolável e um rodapé contextual. A tela não deve criar rolagem horizontal ou vertical no documento inteiro.
- A página escolhida exibe o nome do arquivo e o capítulo. Os rótulos “ORIGINAL” e “TEXTO OFF” deixam explícito o lado de cada versão.

## Visualização e controles

- A visão única sobrepõe as imagens alinhadas e revela a original por meio de um divisor acessível por ponteiro e teclado.
- O modo lado a lado mostra as imagens completas na mesma escala e reserva exatamente 18 px entre elas. Os dois modos mantêm o zoom selecionado.
- O zoom começa em 40%. Os controles de reduzir e ampliar avançam em passos de 10 pontos percentuais; “1:1” define 100%. A interface deve expor o valor atual e limitar a escala ao intervalo suportado pelo canvas.
- Comparações só são habilitadas quando as duas imagens carregam e têm dimensões iguais. Enquanto carregam, a tela comunica o estado; em falhas ou dimensões incompatíveis, informa o motivo e desabilita os controles dependentes da imagem.
- O modo Foco oculta a navegação lateral e expande o canvas. A navegação anterior/próxima só aparece nesse modo. `F` entra no foco e `Esc` sai; fora do foco, `Esc` retorna à tela chamadora.

## Reuso e limites arquiteturais

- A Central V2 hospeda a tela; o módulo de comparação concentra modelo, estados e interação do slider.
- Busca e paginação usam o contrato compartilhado da Central V2. O tamanho específico da lista de inspeção fica na configuração compartilhada de paginação, sem alterar os tamanhos de outras tabelas.
- O modo Foco usa o primitive `_shared/focus_mode`; ícones, tokens e controles comuns continuam vindo dos componentes compartilhados.
- A origem do contexto é responsabilidade do chamador e não deve ser adivinhada pela interface. A tela recebe capítulo, etapa e identificadores necessários para resolver os dois arquivos.
- A comparação não modifica as imagens ou os dados de origem. O descarte da tela cancela a busca, remove prévias e observadores e solta listeners.
- Este contrato não autoriza mudanças na Central V1.

## Acessibilidade e adaptação

Controles têm nomes acessíveis em português, estados selecionados são expostos por atributos ARIA, a divisão pode ser ajustada sem ponteiro e os estados de carregamento e erro são anunciados. Em larguras menores, ferramentas podem quebrar linha e a lista lateral pode ficar mais estreita; controles permanecem identificáveis e operáveis sem depender apenas de cor ou ícones.
