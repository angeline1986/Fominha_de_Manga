# Política de investigação de regressões

Uma falha só deve ser classificada como regressão quando houver evidência de que o comportamento mudou em relação ao estado anterior.

## Procedimento obrigatório

1. Reproduzir a falha em ambiente isolado, com obra, capítulo, comando e condições registrados.
2. Comparar o resultado com a HEAD anterior à mudança suspeita.
3. Se a falha for exclusiva do estado atual, guardar evidência reproduzível, como log, captura ou artefato com hash.
4. Registrar causa, escopo e evidências no ticket.
5. Sem reprodução ou comparação suficiente, manter o status **Em Investigação**. Não abrir correção afirmando regressão.

## Limite de bloqueio

Itens de Saúde Arquitetural não bloqueiam desenvolvimento funcional sem dependência técnica explícita, registrada no ticket e confirmada pelo responsável da feature.
