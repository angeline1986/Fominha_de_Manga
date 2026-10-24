# Backlog técnico: desempenho, progresso e logs do Degrade na Central V2

**Tipo:** investigação e melhoria de desempenho/observabilidade
**Prioridade sugerida:** a priorizar
**Status:** **BACKLOG — NÃO AUTORIZADO**
**Escopo:** tratamento Degrade na Central V2
**Evidência:** relato fornecido para capítulo 4, página `page-075-078.png`; não revalidado nesta atividade.

## Objetivo

Investigar e planejar melhorias para progresso, desempenho, observabilidade e desconexões HTTP durante o tratamento Degrade. Qualquer futura otimização deve preservar a qualidade visual aprovada e os algoritmos, máscaras e thresholds calibrados até que uma alteração específica seja investigada e autorizada.

Este documento registra trabalho futuro. Não autoriza implementação, perfilamento executado, tratamento de imagens, testes, mudança de algoritmos ou alteração de arquivos operacionais.

## Contexto e evidências relatadas

| Campo | Evidência reportada |
|---|---|
| Capítulo | 4 |
| Página | `page-075-078.png` |
| Duração total | 1385,3 segundos (aproximadamente 23 minutos) |
| Cleaner V2 | Concluído em 40,1 segundos |
| Progresso observado | Permaneceu em 80% por aproximadamente 22 minutos |
| Estado final | `processed`; qualidade aprovada |
| Worker | CPU elevada durante o processamento |
| Logs | Operações iterativas NumPy |
| HTTP | Múltiplos `BrokenPipeError` após a conclusão |

Esses dados apontam para trabalho significativo após o Cleaner V2 e um indicador de progresso que não representa esse trabalho de forma útil. As operações NumPy iterativas são uma hipótese para investigação de desempenho, não uma causa já comprovada. Os `BrokenPipeError` ocorreram após a conclusão segundo o relato; a origem das requisições interrompidas e a relação com a conclusão ainda precisam ser identificadas.

## Diretrizes e limites

- Preservar os pixels finais e a qualidade aprovada como requisito central de qualquer otimização.
- Manter algoritmos e parâmetros calibrados, inclusive máscaras e thresholds. Qualquer proposta que possa alterar resultados exige análise comparativa e autorização própria.
- Expor somente progresso que corresponda a trabalho real; não estimar percentuais para aparentar avanço.
- Distinguir processamento ativo, etapa lenta e possível travamento usando eventos/heartbeat e duração observável.
- Tratar desconexões esperadas sem ocultar exceções HTTP ou erros reais de processamento.
- Escopo exclusivo da Central V2 e do fluxo Degrade. Não alterar Central V1 nem interferir na migração PostgreSQL.
- Não executar tratamentos, testes ou medições como parte deste registro.

## Tickets

### DG-01 — Progresso real do processamento

**Problema:** o progresso permaneceu em 80% durante a maior parte do tempo total, apesar de o trabalho continuar por cerca de 22 minutos depois da conclusão do Cleaner V2.

**Investigar e planejar:**

- Como o percentual atual é calculado e quais eventos o atualizam.
- Quais etapas posteriores ao Cleaner contribuem para o tempo total.
- Como mostrar a etapa/componente corrente e o total de componentes sem presumir duração.
- Como atualizar o estado até 100% somente após a conclusão efetiva, inclusive em erro, cancelamento e desconexão da interface.

**Aceite futuro:**

- [ ] O percentual corresponde às etapas reais concluídas, ou a interface apresenta etapas sem inventar precisão percentual.
- [ ] Etapa atual, componente atual e progresso `atual/total` são identificáveis quando houver componentes enumeráveis.
- [ ] A interface não permanece em 80% enquanto etapas conhecidas continuam executando.
- [ ] 100% só aparece quando o processamento termina com sucesso; falha/cancelamento têm estado próprio.
- [ ] Atualizações ausentes ou processo ainda ativo não são apresentados como conclusão.

### DG-02 — Gargalo e desempenho sem mudança visual

**Problema:** a duração total reportada foi 1385,3 segundos, com CPU elevada; o Cleaner V2 levou 40,1 segundos. Logs citam operações iterativas NumPy, mas não há medição por componente/operação para confirmar o gargalo.

**Investigar e planejar:**

- Capturar baseline por etapa, componente e operação relevante, incluindo contagem de componentes, duração e indicadores de CPU/memória quando disponíveis.
- Identificar chamadas iterativas e custo por componente antes de propor otimizações.
- Avaliar alternativas que mantenham os mesmos parâmetros, máscaras e pixels finais.
- Comparar resultados de referência de forma reprodutível; qualquer diferença visual deve ser explicada e submetida à aprovação antes de adoção.

**Aceite futuro:**

- [ ] O gargalo é identificado por medições reproduzíveis, com unidade e escopo claros.
- [ ] Há baseline de duração por componente/operação e da duração total.
- [ ] A otimização proposta demonstra ganho sem alterar os pixels finais nos casos de referência aprovados.
- [ ] Algoritmos, masks, thresholds e parâmetros calibrados permanecem iguais, salvo autorização explícita separada.
- [ ] Resultados e limites da comparação ficam registrados para revisão.

### DG-03 — Observabilidade por componente

**Problema:** os logs disponíveis indicam operações iterativas NumPy, mas não dão visibilidade suficiente sobre início/fim, duração, total de componentes e etapa atual para distinguir lentidão de travamento.

**Investigar e planejar:**

- Registrar início, fim, duração, etapa, identificador do componente e posição `atual/total`.
- Definir heartbeat ou sinal equivalente para indicar atividade em operações longas.
- Definir como reportar conclusão, falha, cancelamento e ausência de heartbeat sem classificar lentidão como travamento automaticamente.
- Manter logs úteis para diagnóstico sem volume excessivo ou dados sensíveis.

**Aceite futuro:**

- [ ] Cada componente registra início, fim e duração, ou uma razão explícita quando esses dados não se aplicam.
- [ ] Quantidade total de componentes e etapa/componente corrente ficam disponíveis durante a execução.
- [ ] Atividade recente é distinguível de possível travamento por limite/heartbeat documentado.
- [ ] Conclusão, falha e cancelamento têm estados e registros distintos.
- [ ] Logs identificam execução/página/etapa sem expor credenciais ou conteúdo sensível.

### DG-04 — Desconexões e `BrokenPipeError`

**Problema:** múltiplos `BrokenPipeError` foram reportados após a conclusão do processamento. Não está estabelecido se a origem é cliente desconectado, polling, resposta streaming ou outro caminho HTTP.

**Investigar e planejar:**

- Identificar rota, método, cliente e padrão temporal das requisições interrompidas.
- Verificar se a interrupção ocorreu depois da resposta/conclusão ou antes de o cliente receber estado final.
- Tratar somente desconexões confirmadas como esperadas, evitando traceback repetido para eventos normais de fechamento de conexão.
- Preservar logs, status e traceback para falhas reais do servidor, do worker ou do processamento.

**Aceite futuro:**

- [ ] A origem e o ciclo de vida das requisições que geram `BrokenPipeError` estão documentados com evidência.
- [ ] Desconexões esperadas não geram traceback repetido nem alteram o estado final do tratamento.
- [ ] Erros HTTP/servidor/processamento reais continuam visíveis e acionáveis.
- [ ] Reconexão ou polling do cliente obtém o estado final correto sem reiniciar o tratamento.

## Critérios globais de aceite futuro

- [ ] Progresso representa etapas reais e chega a 100% somente após sucesso efetivo.
- [ ] Interface não permanece artificialmente em 80% durante trabalho conhecido.
- [ ] Duração por componente/operação e total de componentes ficam registradas.
- [ ] Gargalo é identificado com evidências antes de otimizar.
- [ ] Resultado visual aprovado é preservado, sem alterações não autorizadas em algoritmos, máscaras ou thresholds.
- [ ] Desconexões HTTP esperadas são tratadas adequadamente e erros reais continuam visíveis.
- [ ] Não há regressões nos demais tratamentos da Central V2.
- [ ] Central V1, dados operacionais e migração PostgreSQL não são afetados.

## Riscos e dependências

- A evidência é de uma execução relatada e ainda não constitui baseline reproduzível; duração pode variar por hardware, imagem, carga e quantidade de componentes.
- Otimizar operações vetorizadas pode mudar arredondamento, ordem de escrita ou pixels de borda; equivalência visual precisa ser medida antes de qualquer adoção.
- Progresso por peso estimado pode voltar a parecer artificial quando entradas e custos variam. Preferir unidades de trabalho reais ou etapas nomeadas se não houver estimativa confiável.
- Heartbeat sem limiar calibrado pode classificar processamento intenso como travado ou atrasar a identificação de travamento verdadeiro.
- Suprimir amplamente `BrokenPipeError` pode ocultar falhas reais ou perda de resposta final; o tratamento futuro deve limitar-se a desconexões identificadas.
- A implementação futura deve respeitar contratos e observabilidade existentes da Central V2 e evitar dependência com mudanças da migração PostgreSQL.

## Próximo passo proposto

Quando este backlog for priorizado e autorizado, iniciar por investigação do cálculo de progresso e instrumentação de baseline por etapa/componente, usando cópia isolada e casos de referência aprovados. Só depois de confirmar o gargalo, avaliar otimizações sob comparação visual; investigar separadamente a origem dos `BrokenPipeError`. Nenhuma dessas ações está autorizada pelo registro atual.

## Estado de autorização

**BACKLOG — NÃO AUTORIZADO.** Este documento não autoriza implementar correções, executar tratamentos, medições ou testes, alterar algoritmos/máscaras/thresholds, modificar Central V1 ou arquivos operacionais, interferir na migração PostgreSQL, fazer commit ou push.
