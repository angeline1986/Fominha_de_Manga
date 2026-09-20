# Texto Off — contrato funcional M0

## Escopo e situação

Esta milestone congela o contrato funcional. Não implementa classificadores,
heurísticas, limpeza, persistência nova ou UI. Este documento distingue o alvo
funcional do comportamento já existente; não declara as milestones seguintes
implementadas nem a M0 validada antes da aplicação e dos testes focados.

## Responsabilidades

O Nível I detecta candidatos; detectar não autoriza apagar. O Nível II avalia
elegibilidade, perfil visual e destino por região. Evidência técnica, inclusive
encaixe de máscara, não equivale a autorização semântica para remoção.

| Situação com evidência suficiente | Destino | Responsabilidade |
| --- | --- | --- |
| Texto removível em balão branco convencional | LEVEL_3 | Limpeza convencional preservando o fundo |
| SFX/onomatopeia, título, To be continued, editorial ou texto integrado à arte | PROTEGER | Preservação |
| Balão semitransparente | LEVEL_4 | Tratamento específico do fundo visível |
| Balão colorido, de cor intensa, degradê ou textura | LEVEL_5 | Tratamento específico de cor/degradê/textura |
| Evidência insuficiente, contraditória ou remoção insegura | REVIEW | Preservar e aguardar decisão humana |

INCERTO implica preservar/REVIEW, nunca autorização automática para apagar.
III, IV e V são responsabilidades independentes por região. IV não é passagem
obrigatória para V. A página é unidade de exibição; a autoridade é regional.
Uma página pode ter pendências simultâneas III e V, sem qualquer pendência IV.
Panel Cleaner é uma capacidade de execução, não a definição de um nível.
Não se cria regra específica para rosa, BAL 01 ou Capítulo 4.

## Vocabulário e compatibilidade

A constante ROUTE_PROTECT mantém o valor serializado `PROTEGER`. O termo
conceitual PROTECT usado no plano corresponde a essa rota; não implica migração
ou renomeação. Rota e estado são conceitos diferentes.

| Estado regional | Significado |
| --- | --- |
| PROTECTED | Resolvido por preservação; não é residual |
| RESOLVED | Tratamento do nível responsável concluído |
| PENDING | Tratamento automático do nível responsável ainda pendente |
| REVIEW | Decisão humana pendente; não pertence a fila automática III/IV/V |

O estado inicial de PROTEGER é PROTECTED; o de REVIEW é REVIEW; o de cada rota
LEVEL_3/4/5 é PENDING. Resolver uma região não resolve regiões irmãs, inclusive
irmãs do mesmo nível, nem autoriza modificar regiões de outros destinos.

## Projeção da página

- `level3_pending`, `level4_pending` e `level5_pending`: existe região PENDING
  da respectiva rota. Só esses indicadores determinam as filas automáticas.
- `review_pending`: existe região REVIEW, exigindo decisão humana.
- `has_residual`: indicador agregado atual de pendência automática OU revisão
  humana. Não significa exclusivamente tratamento automático pendente.
- Uma página contendo somente PROTECTED não tem residual nem filas pendentes.
- Uma página contendo somente REVIEW tem residual e revisão pendente, mas
  nenhuma fila automática.
- Uma página com III + V sai da fila III quando suas regiões III forem resolvidas
  e continua na fila V enquanto houver região V pendente; não entra por isso em IV.

Essas definições preservam a API atual de `state.py`. Não introduzem campos nem
alteram o schema. Ausência de residual, isoladamente, não prova cobertura da
detecção, execução de tratamento ou integridade dos artefatos oficiais.

## PROCESSADO, CLASSIFICADO e CONCLUÍDO

- PROCESSADO: o mecanismo terminou sua execução técnica.
- CLASSIFICADO: cada região relevante tem destino conhecido, incluindo PROTEGER
  ou REVIEW. Não exige compreensão semântica absoluta de toda a página.
- CONCLUÍDO: o trabalho automático foi resolvido, as preservações respeitadas e
  não há tratamento automático pendente. REVIEW pendente impede declarar
  conclusão automática, mas não invalida PROCESSADO/CLASSIFICADO.

São definições funcionais, não novos campos implementados nesta M0. PROTECTED é
resolução válida mesmo sem alteração de pixels. Conclusão não se mede pela
quantidade de pixels apagados ou pela taxa de automação.

## Primeiro golden case: Candy YumYum (Yaoi), Ch. 4

Página principal: `page-049-054.png`. O plano relata quatro splits do Cleaner e
os textos “FIRST, HER EYES WERE CUTE!” e “SHE HAD BIG EYES AND LONG EYELASHES.
HER FEATURES WERE SO DELICATE.” no BAL 01 da página MERGED.

Expectativas registradas a partir do plano, não reclassificadas nesta milestone:

- BAL 01: nunca tratar como branco convencional apenas pelo interior neutro;
  expectativa LEVEL_5 ou REVIEW enquanto inconclusivo.
- BAL 06 e BAL 11: expectativa LEVEL_5 e preservação frente ao tratamento III.
- Balões brancos: evitar falsos positivos por cor da cena/pele na borda.
- Não usar isoladamente saturação interior, pixels rosa na borda ou quantidade
  de candidatos para decidir a rota.

Essas referências não constituem novos golden labels aprovados automaticamente.
A matriz e a confirmação de amostras pertencem à M1. Evidência/classificação e
E2E usarão o Capítulo 4 nas milestones pertinentes, com regressão adicional para
evitar regras exclusivas da obra. Nenhuma imagem é requisito de teste da M0.

## Aceite da M0 e limites

Após revisão e aplicação pela usuária:

1. Confirmar este contrato e a manutenção de PROTEGER como valor serializado.
2. Executar os testes focados de contrato e os seis testes existentes de estado.
3. Verificar que o diff adiciona somente este documento e o novo arquivo de testes.
4. Confirmar que produção, pixels e artefatos oficiais não foram alterados.

O aceite da M0 NÃO depende de execução ou validação real do Capítulo 4. Os testes
sintéticos verificam o contrato de estado; não provam qualidade de classificação.
Não modificar thresholds, guard, roteamento, Cleaner, UI, fontes, 02_MERGE,
Auto-Merge, Merge Manual, Balanceamento, PDF, providers ou submódulo nesta M0.
Não instalar dependências nem alterar branch, commit ou push. Apresentar os
resultados e obter nova confirmação antes de qualquer avanço para M1.
