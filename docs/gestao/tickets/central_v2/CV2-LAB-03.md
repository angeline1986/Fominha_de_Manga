# CV2-LAB-03 — Alinhar as imagens do Laboratório para comparação visual

- **Prioridade:** P1
- **Status:** DONE
- **Área:** Limpeza de Balões · Laboratório
- **Categoria:** Interface · Comparação visual

## Problema

No cartão Original, a imagem começa logo abaixo do cabeçalho. Nos cartões de tratamento, a faixa de estado (“Concluído”) e o botão “Selecionar para o Consolidado Final” aparecem antes da imagem. A imagem tratada fica mais baixa que a original, comprometendo a comparação visual da mesma região. A diferença muda conforme o tratamento passa de aguardando para concluído e conforme o botão aparece.

## Solução escolhida

Usar um **cabeçalho único e compacto**, de mesma altura em todos os cartões. O Original mostra apenas o título. Cada tratamento mostra o título à esquerda e, quando houver resultado, um indicador discreto de estado e o botão “Selecionar” à direita, na mesma linha. As imagens começam imediatamente abaixo dos cabeçalhos, sem faixa de estado ou ação entre cabeçalho e imagem. Ao escolher um resultado, o botão muda para “Selecionado” sem alterar suas dimensões nem deslocar a imagem. Em cartões estreitos, manter a linha única sem sobrepor os controles; conferir zoom e rolagem horizontal.

## Alternativas consideradas

1. **Controles abaixo da imagem, dentro do cartão.** O botão pode ficar longe da região analisada em páginas longas; um rodapé fixo exigiria cuidado para não cobrir a imagem.
2. **Faixa de controles com altura igual em todos os cartões.** Alinha o início das imagens, mas consome altura acima de todas elas, inclusive no Original.

## Critérios de aceite

- [x] A borda superior do conteúdo das imagens Original e tratadas coincide na mesma página e escala, nos estados aguardando, executando, concluído, falhou e selecionado.
- [x] A conclusão, reexecução, recuperação de resultado e troca de página não deslocam verticalmente a imagem de um cartão em relação aos outros.
- [x] O cabeçalho permanece em uma única linha e com a mesma altura em todos os cartões; estado e seleção não criam uma faixa acima da imagem.
- [x] A ação de selecionar o resultado permanece no cartão do tratamento; aplicar ao Consolidado Final permanece no painel lateral.
- [x] Estado e ação continuam visíveis e acessíveis sem encobrir pixels da imagem ou ROIs, inclusive com zoom, rolagem horizontal e cartões reordenados.
- [x] Conferir visualmente uma página com resultado concluído e outra sem resultado, além de cobrir o alinhamento com um teste de layout apropriado.

## Validação

O navegador Chromium confirmou cabeçalhos de 40 px e a mesma posição vertical para as cinco imagens antes e depois de exibir “Selecionar” e “Selecionado”, inclusive com mensagem longa de falha. Os testes de composição, feedback, seleção, recuperação e aplicação do Laboratório passaram.

## Limites

Alterar somente a apresentação. Preservar imagens, coordenadas naturais, ROIs, resultados, ordem de execução, seleção e contratos do Consolidado Final.
