# Backlog Central V2: armazenamento e organização de experimentos

**Prioridade:** URGENTE
**Status:** **BACKLOG — NÃO INICIADO — NÃO AUTORIZADO**
**Escopo:** experimentos de Laboratório e tratamentos especiais da Central V2
**Repositório de destino proposto:** `FominhaData/<provider>/<obra>/experimentos/`

## Objetivo

Planejar a saída da estrutura atual de experimentos identificada por UUID no repositório `Fominha_de_Manga/reports/experimentos/` e centralizar os arquivos na pasta da obra em `FominhaData`. A hierarquia deve permitir localizar uma execução pela obra, capítulo, página e tratamento, mantendo o UUID como identificador interno da execução.

Este registro não autoriza implementação, migração, cópia, movimentação ou exclusão de arquivos. Não altera Central V1, algoritmos, parâmetros de tratamento ou o trabalho M3 de PostgreSQL.

## Situação atual relatada

```text
Fominha_de_Manga/reports/experimentos/
├── textoff_especiais_v2/
└── textoff_laboratorio/

experimentos/<UUID>/
```

O inventário real de produtores, leitores, rotas e formatos ainda precisa ser confirmado antes de qualquer mudança. A árvore acima descreve a situação fornecida no pedido; não foi inspecionada nem alterada nesta atividade.

## Estrutura de destino proposta

```text
FominhaData/
└── <provider>/
    └── <obra>/
        └── experimentos/
            └── <capitulo-original>/
                └── <pagina-original>/
                    └── <tratamento>/
                        └── <execucao_id-UUID>/
                            ├── input/
                            ├── treatment/
                            ├── logs/
                            ├── manifest.json
                            ├── request.json
                            └── worker-error.json (quando houver)
```

Exemplo:

```text
experimentos/14/page-039-044.png/artistico/bb1bfa1dd9354ea586d8ccbc9d012772/
```

O capítulo e a página devem usar as identificações originais. O UUID permanece no último nível como ID interno da execução: assim várias execuções da mesma página e tratamento coexistem sem colisão nem sobrescrita. A forma de representar nomes de provider/obra/capítulo/página no filesystem deve preservar a identidade original e tratar separadores, caracteres reservados e diferenças de caixa sem colisões.

## Tickets

### EXP-01 — Migrar armazenamento para FominhaData

**Prioridade:** URGENTE
**Escopo:** Laboratório e tratamentos especiais.

Centralizar no diretório da obra os experimentos hoje associados a `textoff_especiais_v2/` e `textoff_laboratorio/`. Mapear e adaptar produtores, leitores e rotas HTTP para a nova autoridade de armazenamento, mantendo compatibilidade com a interface. Preservar imagens, máscaras, logs, manifestos, requisições e diagnósticos. Evitar duplicação no fluxo normal.

Históricos só podem ser migrados após inventariar conteúdo e validar identidade e integridade (incluindo hashes/checksums disponíveis, manifestos e referências). Divergências, arquivos sem metadados e colisões devem gerar relatório e permanecer sem promoção automática. Os diretórios antigos não devem ser removidos sem autorização específica e reconciliação aprovada.

### EXP-02 — Organizar por capítulo, página e execução

**Prioridade:** URGENTE
**Escopo:** hierarquia e ciclo de vida das execuções.

Substituir a navegação operacional `experimentos/<UUID>/` por obra/capítulo/página/tratamento/UUID de execução, mantendo o UUID apenas no nível da execução. Permitir reexecuções da mesma página e tratamento, preservar os resultados anteriores e identificar estado `sucesso`, `falha` ou `interrompido`. Logs e erros devem estar associados à execução e à página corretas, com acesso compatível com a Central V2.

Cada execução deve ser create-only: uma nova tentativa recebe um novo UUID; nenhum resultado existente pode ser sobrescrito. `manifest.json`, `request.json`, logs e eventuais `worker-error.json` devem registrar ou permitir rastrear obra, capítulo, página, tipo de tratamento, execução e estado final, respeitando os contratos existentes. Definir a regra de conclusão para arquivos parciais e interrupções antes de iniciar a migração.

## Dependências e decisões necessárias

- Inventário de produtores, leitores diretos/indiretos, rotas HTTP, tarefas em background e consumidores da Central V2 para Laboratório e Especiais.
- Identificadores canônicos e regras de mapeamento para provider, obra, numeração original do capítulo, nome original da página e tipo de tratamento.
- Contrato versionado de `manifest.json`, `request.json`, nomes de diretório, status terminal e tratamento de execuções incompletas.
- Estratégia de escrita atômica/create-only e comportamento em retry, colisão, falha do worker e processo interrompido.
- Plano de compatibilidade da interface e eventual janela de leitura dos caminhos legados, sem manter duas cópias em escrita normal.
- Procedimento de inventário e reconciliação histórica, com critérios de integridade e aprovação explícita para qualquer retirada posterior dos diretórios antigos.

## Riscos

- Mapeamento incorreto de UUIDs existentes pode associar experimento à obra, capítulo, página ou tratamento errado.
- Nomes originais podem conter caracteres inválidos, caminhos aninhados, diferenças de caixa ou colisões após normalização; normalização silenciosa pode perder identidade.
- Atualizar só os produtores ou só os consumidores pode quebrar listagem, download, polling de status, logs de erro ou reabertura de resultados na interface.
- Retry reutilizando caminho pode sobrescrever histórico; o ID da execução precisa ser novo e protegido contra criação concorrente.
- Migração parcial, manifests incompletos ou hashes divergentes podem dar aparência de histórico íntegro sem garantir conteúdo completo.
- Cópia durante coexistência pode aumentar duplicação e produzir duas fontes divergentes; a autoridade e o período de compatibilidade precisam ser explícitos.
- Armazenamento por obra pode concentrar grande volume; espaço, backup, retenção e desempenho precisam ser medidos antes do rollout.
- Mudanças acidentais de algoritmos, parâmetros, resultados, Central V1 ou PostgreSQL estão fora do escopo e devem ser evitadas.

## Critérios de aceite futuros

- [ ] Experimentos novos são gravados em `FominhaData/<provider>/<obra>/experimentos/`.
- [ ] Caminhos refletem capítulo e página originais e tipo de tratamento.
- [ ] UUID identifica a execução no último nível, permitindo múltiplas execuções por página/tratamento.
- [ ] Laboratório e tratamentos especiais produzem e leem os registros pela Central V2.
- [ ] Interface continua acessando resultados, status, logs e erros da página correta.
- [ ] Nenhum resultado anterior é sobrescrito; retries e concorrência criam execuções isoladas.
- [ ] Status `sucesso`, `falha` e `interrompido` é persistido e interpretado corretamente.
- [ ] Imagens, máscaras, manifestos, requisições, logs e diagnósticos são preservados e rastreáveis.
- [ ] Históricos só são migrados após validação de integridade; divergências ficam reportadas e não promovidas automaticamente.
- [ ] Fluxo normal não mantém duplicações desnecessárias; diretórios legados não são excluídos sem autorização.
- [ ] Algoritmos e resultados de tratamento não são alterados; Central V1 e M3 não são afetados.

## Próximo passo proposto

Quando houver autorização de implementação, começar pelo inventário somente leitura dos produtores, consumidores, rotas e formatos atuais; em seguida aprovar os identificadores canônicos e o contrato de execução create-only. Antes de migrar históricos, gerar plano de reconciliação por execução e demonstrar compatibilidade da interface em dados sintéticos. Migração e retirada dos caminhos antigos exigem autorização própria.

## Estado de autorização

**BACKLOG — URGENTE — NÃO INICIADO — NÃO AUTORIZADO.** Registrar este item não autoriza implementar, copiar, mover ou excluir dados existentes; alterar algoritmos/parâmetros, Central V1 ou M3; nem fazer commit ou push.
