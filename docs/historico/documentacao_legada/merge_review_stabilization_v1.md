# Fluxos de Auto-Merge e Revisão Merge — Estabilização e Arquitetura

> **Versão consolidada — 02/09/2026**
>
> Este documento substitui a documentação fragmentada de estabilização e fluxo.
> Ele registra o estado funcional atual, a arquitetura de artefatos por estágio,
> as regras de segurança e o escopo das próximas evoluções.

## 1. Status atual dos fluxos

| Fluxo | Status | Situação |
|---|---|---|
| **Auto-Merge — Nível I** | **CONCLUÍDO** | Fluxo automático conservador estabilizado e com persistência própria em `AUTO_MERGE/<cap>`. |
| **Auto-Merge — Nível II** | **CONCLUÍDO** | Segunda estratégia automática real, restrita ao residual do Nível I, com busca adaptativa, faixas uniformes independentes de cor e balanceamento seguro. |
| **Auto-Merge — Nível III** | **PENDENTE** | Permanece fora do escopo atual. A arquitetura e as diretrizes abaixo representam planejamento/evolução futura, não conclusão funcional. |
| **Revisão Merge** | **PENDENTE** | Permanece pendente até retomada específica desse fluxo. |
| **Revisão Merge V2** | **PENDENTE** | Permanece pendente. Deve evoluir posteriormente como revisão assistida e fonte de aprendizado para o Auto-Merge. |

**Marco atual:** os fluxos considerados concluídos neste momento são **Auto-Merge Nível I** e **Auto-Merge Nível II**. O desenvolvimento de **Auto-Merge Nível III**, **Revisão Merge** e **Revisão Merge V2** fica explicitamente suspenso por enquanto.

---

## 2. Objetivo

O sistema deve produzir merges automaticamente sem cortar conteúdo visual importante e reduzir progressivamente a necessidade de intervenção humana.

A regra de produto é:

> **Revisão manual deve ser a exceção da exceção.**

Cada estágio automático deve:

1. atuar somente sobre a região sob sua responsabilidade;
2. preservar integralmente o que já foi resolvido;
3. falhar de forma segura quando não puder demonstrar uma solução;
4. registrar diagnóstico suficiente para explicar a decisão;
5. persistir somente os artefatos que ele próprio produziu.

---

## 3. Visão geral do fluxo

```text
Imagens originais
      │
      ▼
AUTO-MERGE — NÍVEL I                         [CONCLUÍDO]
      │
      ├── tudo resolvido ───────────────► MERGE final
      │
      └── residual
             │
             ▼
AUTO-MERGE — NÍVEL II                        [CONCLUÍDO]
             │
             ├── tudo resolvido ────────► MERGE final
             │
             └── residual
                    │
                    ▼
AUTO-MERGE — NÍVEL III                       [PENDENTE]
                    │
                    └── residual
                           │
                           ▼
REVISÃO MERGE / REVISÃO MERGE V2             [PENDENTES]
                           │
                           ▼
                      MERGE final
```

O princípio fundamental é:

> **Um estágio não recria, reinterpreta ou modifica aquilo que o estágio anterior já resolveu.**

---

## 4. Arquitetura de persistência por estágio

Cada diretório representa autoridade sobre os artefatos efetivamente produzidos naquele estágio.

```text
FLUXO_SECUNDARIO/
├── AUTO_MERGE/<cap>/
│   └── somente artefatos resolvidos pelo Nível I
│
├── MERGE_LEVEL2/<cap>/
│   └── somente artefatos adicionais resolvidos pelo Nível II
│
├── MERGE_LEVEL3/<cap>/
│   └── futuramente: artefatos adicionais resolvidos pelo Nível III
│
├── MERGE_REVIEW/<cap>/
│   └── futuramente: exceções resolvidas pela revisão
│
└── MERGE/<cap>/
    └── composição final de todos os estágios, em ordem global exata
```

`MERGE/<cap>` não representa um estágio intermediário. É exclusivamente a saída consolidada final.

A composição final deve garantir:

- cobertura integral do capítulo;
- ordem global correta;
- ausência de gaps;
- ausência de overlaps;
- preservação byte a byte dos artefatos já materializados quando aplicável.

---

## 5. Conceitos fundamentais

### 5.1 SAFE / PASSED

O estágio encontrou evidência suficiente para considerar aquele trecho seguro segundo os critérios técnicos sob sua responsabilidade.

### 5.2 FAILED / RESIDUAL

O estágio não conseguiu demonstrar segurança suficiente para resolver automaticamente aquela região. Isso não significa que a imagem esteja errada.

### 5.3 INCONCLUSIVE

Não existe evidência suficiente para uma decisão automática segura. O comportamento correto é preservar a região, não forçar um corte.

### 5.4 Região residual

É somente a parte ainda não resolvida. Os trechos já resolvidos não seguem para reprocessamento.

```text
0 ───────────────────────────────────────────── 100000 px
PASSED        PASSED       RESIDUAL        PASSED
0..20000      20000..40000 40000..52000    52000..100000
                               │
                               └── somente este intervalo segue adiante
```

### 5.5 Imagens-fonte não são páginas semânticas

Os arquivos `page-XXX.png` são partes de um conteúdo vertical contínuo. A fronteira entre arquivos-fonte:

- não é automaticamente um ponto seguro;
- não deve ser usada como preferência de corte;
- não impede que um residual comece ou termine no meio de um arquivo.

Por isso os estágios trabalham com coordenadas globais e spans exatos, incluindo `source_y_start` e `source_y_end`.

---

# 6. Auto-Merge — Nível I

**Status: CONCLUÍDO**

## 6.1 Responsabilidade

É a primeira tentativa automática e conservadora. Procura pontos seguros com baixo custo computacional e resolve a maior quantidade possível de situações simples sem análise estrutural pesada.

## 6.2 Regras principais

O Nível I:

- trabalha sobre o capítulo;
- utiliza os critérios conservadores do Auto-Merge V3;
- não força cortes;
- não considera fronteiras de `page-XXX.png` como pontos preferenciais;
- persiste imediatamente aquilo que efetivamente resolveu;
- encaminha somente o residual ao Nível II.

## 6.3 Persistência

```text
AUTO_MERGE/<cap>/
```

Esse diretório contém somente os artefatos produzidos pelo Nível I e seu manifesto.

Se o capítulo for parcialmente resolvido:

```text
parte resolvida     → AUTO_MERGE/<cap>
parte não resolvida → residual do Nível II
```

## 6.4 Critério de conclusão

O Nível I está funcionalmente concluído no estado atual do projeto. Seus thresholds e sua estratégia conservadora não devem ser alterados incidentalmente durante evoluções dos níveis posteriores.

---

# 7. Auto-Merge — Nível II

**Status: CONCLUÍDO**

## 7.1 Responsabilidade

O Nível II é uma segunda estratégia automática real. Ele recebe **somente as regiões residuais do Nível I** e tenta encontrar uma nova composição segura sem reprocessar o capítulo inteiro.

```text
AUTO_MERGE/<cap>      → autoridade do Nível I
MERGE_LEVEL2/<cap>    → autoridade do Nível II
```

Nenhum artefato do Nível I deve ser duplicado ou modificado pelo Nível II.

## 7.2 Unidade de processamento

A unidade real é o intervalo global residual.

Um residual pode começar no meio de `page-029.png` e terminar no meio de `page-037.png`. O Nível II deve respeitar exatamente:

- `global_start`;
- `global_end`;
- `source_y_start`;
- `source_y_end`;
- spans reais das fontes.

Nenhum pixel já pertencente a um merge do Nível I pode voltar a fazer parte do residual.

## 7.3 Estratégia adaptativa

A estratégia atual é baseada em busca de caminho seguro limitada ao residual.

O Nível II amplia **a forma de procurar** uma composição, não reduz a exigência de segurança.

A ordem conceitual é:

```text
1. procurar candidatos visualmente SAFE
2. construir caminhos válidos dentro do residual
3. comparar somente caminhos já SAFE
4. escolher a composição mais equilibrada
5. usar edge chunk seguro apenas como fallback final
```

## 7.4 Faixas brancas seguras

As faixas brancas continuam sendo um sinal visual válido e conservador. Os critérios existentes de segurança para esse tipo de candidato permanecem protegidos.

## 7.5 Faixas largas de cor uniforme

O Nível II também realiza uma segunda procura por **faixas largas de cor uniforme**, independentemente da cor.

Portanto, uma faixa não precisa ser branca para ser candidata.

Exemplos possíveis:

```text
branco
bege
cinza
preto
outra cor visualmente uniforme
```

A cor em si não autoriza o corte. A região precisa satisfazer os critérios conservadores de uniformidade e ausência de conteúdo relevante usados pelo detector.

Essa capacidade foi introduzida a partir de um caso real em que uma grande área aproximadamente `#dfdad2` constituía um ponto visualmente melhor para divisão do residual.

## 7.6 Score de balanceamento

Depois que os candidatos foram classificados como seguros, o Nível II pode comparar diferentes composições por um **score de balanceamento**.

Regra fundamental:

> **O score nunca transforma um candidato inseguro em candidato seguro.**

Segurança vem primeiro. Balanceamento apenas ordena soluções já consideradas SAFE.

O objetivo é evitar composições desproporcionais quando existe uma alternativa segura mais equilibrada.

Exemplo conceitual:

```text
Opção A
2253 px + 10537 px

Opção B
6200 px + 6590 px
```

Se ambas forem SAFE, a composição B é preferível por ser mais equilibrada.

## 7.7 Preferência aproximada por quatro arquivos-fonte

A ideia de agrupar aproximadamente quatro imagens-fonte pode participar do score como **preferência suave de balanceamento**, nunca como regra de segurança.

Isso significa:

- não é obrigatório haver quatro fontes;
- uma solução não é rejeitada apenas por conter menos ou mais fontes;
- fronteiras de arquivos não se tornam pontos preferenciais de corte;
- a preferência não autoriza cortes inseguros;
- o critério serve somente para desempatar/rankear composições já SAFE.

Essa distinção é necessária porque os arquivos-fonte possuem alturas variáveis e não representam páginas semânticas.

## 7.8 Edge chunk

O refinamento de edge chunk está **concluído e validado**.

O tamanho mínimo normal continua sendo preferencial para a composição. Entretanto, quando uma solução segura existe próxima da borda real do residual, é permitido um segmento menor que o mínimo exclusivamente na extremidade inicial ou final.

```text
segmento interno
→ respeita o mínimo normal

segmento inicial/final do residual
→ pode ficar abaixo do mínimo
→ somente se o corte continuar SAFE
→ somente como fallback
```

Nunca é permitido:

- criar chunk pequeno arbitrário no meio da sequência;
- forçar corte;
- relaxar o critério visual para justificar o edge chunk;
- expandir o residual para pixels já resolvidos.

## 7.9 Critérios de segurança preservados

O Nível II deve continuar garantindo:

- nenhum corte forçado;
- limite máximo de altura;
- proteção dos critérios das faixas brancas;
- critérios próprios conservadores para faixas uniformes;
- nenhuma análise fora do residual;
- nenhum artefato do Nível I modificado;
- nenhum score capaz de promover candidato inseguro.

## 7.10 Resultados possíveis

### Resolução completa

```text
residual
   ↓
Nível II
   ↓
todos os intervalos resolvidos
   ↓
MERGE_LEVEL2/<cap>
   ↓
residual = 0
   ↓
composição final
```

### Resolução parcial

A parte resolvida é materializada em `MERGE_LEVEL2/<cap>` e somente o restante permanece residual.

### Nenhuma resolução

Nenhum corte artificial é criado. O residual é preservado com diagnóstico.

## 7.11 Diagnóstico obrigatório

O manifesto deve permitir identificar:

- intervalo global recebido;
- spans reais das imagens-fonte;
- candidatos avaliados;
- classe do candidato, quando aplicável;
- candidatos seguros e rejeitados;
- cortes selecionados;
- estratégia usada;
- score/critério de balanceamento;
- uso ou não de edge chunk;
- artefatos produzidos;
- regiões residuais;
- motivo de eventual impossibilidade de solução.

## 7.12 Validação concluída

O Nível II passou por testes automatizados cobrindo, entre outros:

- faixa uniforme sem exigência de branco;
- detector independente de cor;
- rejeição de linhas com conteúdo;
- preferência suave de quatro fontes;
- impossibilidade de o balanceamento tornar candidato inseguro elegível;
- edge chunk inicial e final;
- proibição de chunk pequeno interno;
- ausência de corte forçado;
- promoção com proteção contra gap, overlap e artefato ausente;
- autoridade de estado.

Também foi validado em caso real, no qual a nova busca por faixa uniforme e o balanceamento produziram uma composição visualmente melhor do residual.

**Conclusão funcional:** Auto-Merge Nível II está concluído no marco atual.

---

# 8. Auto-Merge — Nível III

**Status: PENDENTE**

O Nível III permanecerá pendente por enquanto. As definições desta seção representam **diretrizes de evolução**, não uma declaração de que o fluxo esteja concluído.

## 8.1 Responsabilidade planejada

Receber somente o residual que permanecer após o Nível II e aplicar análise estrutural mais sofisticada.

A pergunta central será:

> **Existe evidência estrutural de que este ponto pode ser cortado sem interromper um objeto ou uma continuidade visual importante?**

## 8.2 Capacidades previstas

A evolução pode utilizar OpenCV e sinais como:

- escala de cinza e denoise;
- Canny Edge Detection;
- Connected Components;
- continuidade estrutural;
- bordas diagonais;
- densidade de bordas;
- uniformidade;
- projeções estruturais;
- heurística de texto/efeitos visuais;
- busca local por alternativa segura;
- proteção de cenas contínuas.

Essas capacidades devem ser retomadas e validadas quando o trabalho do Nível III for reaberto.

## 8.3 Resultado conceitual

O resultado deverá distinguir:

- `SAFE`: evidência suficiente para decisão automática;
- `UNSAFE`: evidência estrutural contrária ao corte;
- `INCONCLUSIVE`: segurança não demonstrada.

“Nível III analisado” não deve ser confundido com “residual resolvido”.

## 8.4 Diagnóstico esperado

Quando retomado, o Nível III deverá registrar de forma explicável:

- candidatos avaliados;
- quantidade SAFE/UNSAFE/INCONCLUSIVE;
- motivos de rejeição;
- proteções acionadas;
- residual efetivamente reduzido ou preservado.

---

# 9. Revisão Merge

**Status: PENDENTE**

A Revisão Merge permanecerá pendente por enquanto.

## 9.1 Papel pretendido

Tratar somente exceções que os níveis automáticos disponíveis não conseguiram resolver com segurança, sem modificar os segmentos já aprovados.

Ela não deve ser usada para mascarar uma capacidade automática ainda não implementada.

## 9.2 Registro histórico — Estabilização V1

A estabilização inicial da Revisão Merge foi construída sem desfazer as melhorias visuais e de diagnóstico existentes no estado `d77dc49`.

Naquele marco foram realizadas as seguintes correções:

- unificação da definição de capítulo pendente no frontend usando `merge_state == "pendente"`, `merge_failed` ou `review`;
- correção do uso indevido de `pending` em inglês;
- remoção do fallback silencioso que podia trocar o capítulo selecionado pelo primeiro item da fila;
- diagnóstico estruturado devolvendo somente `ch.name`;
- preservação do diagnóstico estruturado de falha de proposta;
- restauração da ordem conservadora de avaliação dos fins naturais;
- restauração da proteção de altura mínima do bloco seguinte;
- remoção da estratégia experimental de absorção automática de cortes;
- preservação das melhorias de UI, PDF Merge, abertura de pasta e mensagens.

Naquele momento ficaram fora do escopo alterações nos thresholds de `std`, `edge` ou `score` e revisão manual por trecho. A regra de falha determinística e diagnosticável permanece conceitualmente válida.

**Importante:** esse histórico não significa que a Revisão Merge esteja concluída no estado atual. O fluxo permanece **PENDENTE** para retomada posterior.

---

# 10. Revisão Merge V2

**Status: PENDENTE**

A Revisão Merge V2 permanecerá pendente por enquanto.

Quando retomada, deverá combinar duas responsabilidades.

## 10.1 Responsabilidade operacional

Permitir que o usuário resolva uma exceção real de maneira controlada.

## 10.2 Responsabilidade de evolução

Explicar por que o caso chegou à intervenção humana e produzir evidências reutilizáveis para melhorar os níveis automáticos.

Deverá responder, por exemplo:

- qual intervalo falhou;
- quais níveis tentaram resolvê-lo;
- quais estratégias foram aplicadas;
- quais candidatos foram avaliados;
- principais motivos de rejeição;
- proteção final acionada;
- decisão humana que resolveu o caso.

---

# 11. Review como fila de aprendizado

Quando a Revisão Merge V2 for retomada, cada decisão manual deverá gerar evidências que permitam avaliar:

- se o algoritmo está conservador demais;
- quais motivos mais levam ao Review;
- quando o humano aprova um ponto rejeitado automaticamente;
- quais elementos visuais ainda não são reconhecidos;
- quais classes recorrentes poderiam ser automatizadas.

A revisão deve funcionar como fonte de evolução, não como destino normal do pipeline.

---

# 12. Diretrizes para evolução futura

## 12.1 Evolução orientada por resíduos reais

Novas heurísticas, OpenCV ou IA não devem ser incorporados indiscriminadamente.

Primeiro devem ser observados os resíduos reais.

Possíveis capacidades futuras incluem:

- detector de balões;
- detector de painéis;
- detector de personagens/objetos;
- OCR ou detector de regiões de texto;
- modelos leves especializados.

Uma nova capacidade deve ser adicionada quando os dados demonstrarem que ela absorverá uma classe relevante de resíduos.

## 12.2 IA como proteção, não como autorização irrestrita

Um detector futuro pode produzir máscaras ou evidências de proteção. Ele não deve, isoladamente, escolher um corte sem passar pelas regras de segurança do estágio.

---

# 13. Métricas de qualidade

A qualidade não deve ser medida somente pela quantidade de capítulos processados.

Métricas importantes:

```text
% resolvido no Nível I
% residual após Nível I
% absorvido pelo Nível II
% residual após Nível II
% absorvido pelo Nível III
% residual após Nível III
% enviado para Review
motivos mais frequentes de Review
% de decisões humanas potencialmente automatizáveis
```

Para os níveis que recebem resíduos, uma métrica central é:

> **Taxa de absorção do residual.**

O objetivo é aumentar essa taxa sem reduzir a segurança.

---

# 14. Prioridades que nunca devem ser invertidas

```text
1. preservar conteúdo
2. evitar cortes visual ou estruturalmente incorretos
3. automatizar
4. minimizar intervenção humana
```

Reduzir Review não justifica cortes arriscados.

A evolução correta consiste em aumentar a capacidade do Auto-Merge de **demonstrar que uma decisão é segura**.

---

# 15. Resumo das responsabilidades

| Fluxo | Status | Responsabilidade | Persistência |
|---|---|---|---|
| Auto-Merge Nível I | **CONCLUÍDO** | Primeira busca automática conservadora. | `AUTO_MERGE/<cap>` |
| Auto-Merge Nível II | **CONCLUÍDO** | Segunda busca adaptativa somente sobre o residual; faixas seguras, uniformidade independente de cor e balanceamento entre soluções SAFE. | `MERGE_LEVEL2/<cap>` |
| Auto-Merge Nível III | **PENDENTE** | Futuramente, análise estrutural do residual restante. | `MERGE_LEVEL3/<cap>` |
| Revisão Merge | **PENDENTE** | Futuramente, resolução humana das exceções restantes. | `MERGE_REVIEW/<cap>` |
| Revisão Merge V2 | **PENDENTE** | Futuramente, revisão assistida + diagnóstico + aprendizado. | `MERGE_REVIEW/<cap>` |
| MERGE final | Composição | Consolidação dos artefatos dos estágios em ordem global exata. | `MERGE/<cap>` |

---

# 16. Marco de encerramento atual

Em **02/09/2026**, o desenvolvimento fica formalmente marcado da seguinte forma:

```text
AUTO-MERGE — NÍVEL I
STATUS: CONCLUÍDO

AUTO-MERGE — NÍVEL II
STATUS: CONCLUÍDO

AUTO-MERGE — NÍVEL III
STATUS: PENDENTE

REVISÃO MERGE
STATUS: PENDENTE

REVISÃO MERGE V2
STATUS: PENDENTE
```

O próximo trabalho sobre Nível III ou qualquer modalidade de Revisão deve começar a partir deste marco, sem reabrir incidentalmente as regras já estabilizadas dos Níveis I e II.

A meta de longo prazo permanece:

> **Resolver automaticamente, com segurança e explicabilidade, praticamente todos os casos previsíveis, deixando para a revisão humana apenas situações verdadeiramente excepcionais.**
