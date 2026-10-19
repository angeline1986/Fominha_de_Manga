# Backlog técnico: PostgreSQL para controle da pipeline de limpeza

**Status:** backlog, implementação não autorizada
**Escopo inicial:** pipeline de limpeza de balões da Central V2
**Persistência escolhida:** PostgreSQL para metadados; filesystem para imagens e demais binários

## Objetivo

Centralizar o catálogo de obras, capítulos, páginas, execuções, artefatos, dependências e publicações da pipeline. O banco deve apontar para imagens armazenadas nas pastas das etapas; não deve armazenar PNGs, PDFs ou máscaras, nem criar cópias apenas para versionamento.

O índice central deve permitir resolver a imagem ativa por página, conferir integridade e dependências, controlar aprovação e publicação, identificar resultados desatualizados e manter auditoria. Os manifests existentes continuam sendo evidências das execuções e não devem ser substituídos por uma cópia integral de seu conteúdo no banco.

## Diagnóstico arquitetural

O código possui dois consolidadores com contratos diferentes:

- `TO_MERGED_CONSOLIDADO` seleciona logicamente resultados de Nível I e Nível II, registra origem e SHA-256 e já oferece um resolvedor. Em determinadas páginas, copia para sua pasta o resultado selecionado de Nível II.
- `07_CONSOLIDADO_FINAL` contém imagens físicas por página, registra proveniência e histórico e recebe tratamentos especiais promovidos. Tratamentos e exportação dependem de seus contratos atuais.

Os dois devem ser preservados durante a transição. Recomenda-se evoluir o consolidado lógico como fonte canônica das referências ativas e manter o Consolidado Final como contrato compatível até que seus leitores e publicadores sejam adaptados. Eliminar cópias internas só deve ser considerado depois da migração dos consumidores.

O caso de continuidade Sólidos → Nível II é arquitetural, mas o PostgreSQL não o corrige sozinho. Sólidos atualmente publica uma prévia (`preview_only: true`); o Nível II usa MERGE, resultados e máscaras do Nível I e não incorpora essa prévia. A compatibilidade do algoritmo do Nível II com uma imagem acumulada deve ser validada separadamente, sem presumir que trocar o caminho de entrada seja suficiente.

## Escopo

### Incluir na primeira integração

- Auto-Cleaner Nível I;
- Mapear;
- Bubble Sommelier;
- Auto-Cleaner Check;
- Auto-Cleaner Sólidos;
- Auto-Cleaner Nível II / Glass;
- consolidado lógico e referências ao Consolidado Final;
- catálogo de artefatos, dependências, revisões, aprovações e publicações;
- resolvedor central, validação de integridade e invalidação.

### Manter fora do escopo inicial

Download de mangás, biblioteca geral, Auto-Merge, geração e organização de PDFs, fluxos independentes e migração integral dos dados da aplicação. PDF e exportação entram como regressões de compatibilidade, não como integrações iniciais com o banco.

## Modelo conceitual inicial

Começar com as entidades `works`, `chapters`, `pages`, `pipeline_stages`, `stage_runs`, `artifacts`, `artifact_dependencies`, `active_artifacts` e `artifact_publications`. Avaliar `pipeline_events`, `approval_records` e `integrity_checks` somente quando um caso de uso justificar essas tabelas.

Usar identificadores internos estáveis, chaves estrangeiras, restrições de unicidade e índices orientados às consultas reais por página, etapa e execução. Manter migrations versionadas. Não guardar credenciais no repositório.

### Estados

Manter aprovação e atividade como propriedades distintas: um artefato pode continuar aprovado mesmo quando outra versão passa a ser ativa. Os estados conceituais incluem `PREVIEW`, `APPROVED`, `ACTIVE`, `STALE`, `INVALID` e `HISTORICAL`; a semântica e as transições devem ser formalizadas antes da implementação. A existência de um arquivo não constitui aprovação.

## Contratos que precisam ser definidos

### Referência ativa

Por página, registrar a etapa produtora, artefato, caminho relativo seguro, SHA-256, dimensões, estado de aprovação, revisão, publicação e dependências relevantes. Aprovação não deve significar automaticamente que o artefato está ativo.

### Image Resolver

Receber obra, capítulo, página e contexto da etapa. Resolver a referência no banco; validar autorização, contenção do caminho, existência, hash, dimensões quando necessárias e dependências aplicáveis. Retornar caminho validado, identidade do artefato, origem, revisão e proveniência. Na ausência ou divergência, bloquear o consumo e registrar contexto suficiente. Não escolher outra imagem silenciosamente.

### Publicação

1. O executor grava a saída e seu manifesto na pasta da etapa.
2. O publicador valida arquivo, hash, manifesto, aprovação e dependências.
3. Em transação PostgreSQL, compara a revisão esperada, registra a publicação e atualiza a referência ativa.
4. Em conflito de revisão, recusa a publicação sem apagar artefatos.

PostgreSQL não fornece uma transação atômica conjunta com o filesystem. O arquivo precisa estar completo e validado antes do commit. Se a transação falhar, a saída permanece inativa e auditável; se houver interrupção, a recuperação deve identificar publicações pendentes sem excluir dados automaticamente.

### Imutabilidade e identidade física

O histórico no banco não preserva um arquivo cujo caminho seja posteriormente sobrescrito. Antes de ativar publicações centrais, garantir que uma versão publicada não seja regravada sob a mesma identidade física. Usar os diretórios de saída da execução, sem criar cópias adicionais apenas para versionamento, ou outro mecanismo equivalente de imutabilidade.

### Dependências e invalidação

Registrar dependências comprováveis entre artefatos e invalidar por página sempre que possível. Ao mudar o Check, identificar saídas dependentes, marcá-las como desatualizadas e impedir nova promoção; preservar arquivos e histórico, sem reexecutar etapas automaticamente. Mapear, Sommelier e Check devem guardar o hash e a revisão da imagem analisada.

## Integração por componente

| Componente | Observação de integração |
|---|---|
| Nível I | Parte do MERGE. Reexecução deve ser um reinício explícito a partir dessa origem, sem rebaixar silenciosamente referências posteriores. |
| Mapear | Usa hoje o consolidado lógico. Deve registrar a revisão e o hash analisados; resultados ficam desatualizados se a referência mudar. |
| Bubble Sommelier | Executa hoje sobre o diretório MERGE. A adoção da imagem ativa exige adaptar o contrato de entrada e os crops. |
| Check | Mantém decisões e pode congelar snapshots. Diferenciar snapshot histórico da imagem ativa atual. |
| Sólidos | Usa decisões aprovadas e produz prévia. Só publicar após promoção explícita e revalidar o Check de origem. |
| Nível II / Glass | Precisa da imagem ativa candidata e dos auxiliares necessários do Nível I/MERGE. Validar compatibilidade e ordem dos tratamentos antes de mudar o consumo. |
| Consolidado lógico | Evoluir para referência canônica; validar hashes e dependências. |
| Consolidado Final | Manter como compatibilidade para tratamentos, recuperação e consumidores que exigem arquivos físicos. |
| Exportação | Hoje lê `07_CONSOLIDADO_FINAL`; preservar o contrato ou migrá-lo para o resolvedor com testes de regressão. |
| PDFs | Fora do escopo de integração; o exportador usa `03_PDF_MERGE`. Validar que a mudança não os afete. |

## Importação dos manifests existentes

Criar importador somente leitura para catalogar obras, páginas, caminhos, hashes e dependências comprovadas. Validar hashes conforme a política definida e relatar arquivos ausentes ou divergências. Proveniência incompleta deve receber estado como `LEGACY_UNVERIFIED` e não pode ser promovida automaticamente.

O importador não deve alterar imagens, manifests ou backups, inferir aprovação, inventar dependências nem remover dados. A saída da importação deve incluir relatório de cobertura e exceções.

## Fases propostas

1. **Infraestrutura:** escolher versões suportadas, ambiente operacional, usuário restrito, configuração de segredos, backup/restauração e migrations iniciais. Não impactar a execução da pipeline.
2. **Schema e repositórios:** implementar entidades, restrições, índices e transações; testar migrations, integridade e rollback em ambiente isolado.
3. **Catálogo:** importar manifests em modo somente leitura e medir cobertura, divergências e proveniência incompleta.
4. **Resolvedor em sombra:** comparar referência do banco com o resolvedor atual sem alterar a fonte usada pelos executores.
5. **Publicação isolada:** validar aprovação, revisão concorrente, invalidação e recuperação de falhas antes de usar dados reais.
6. **Integração progressiva:** migrar por contratos, observando as fontes distintas do Mapear, Sommelier, Check, Sólidos e Nível II. A ordem definitiva depende dessas dependências reais.
7. **Compatibilidade:** preservar os dois consolidadores, tratamentos, previews, comparação e recuperação; validar exportação e PDFs como regressões.
8. **Ativação controlada:** habilitar por etapa, monitorar divergências e manter procedimento de reversão sem apagar artefatos ou manifests.

## Testes de aceite

Usar exclusivamente cópias isoladas e descartáveis, incluindo o caso `comix / Gazing at you / capítulo 12 / page-061-065.png`. Validar catalogação e hashes; prévia sem alteração da referência ativa; aprovação e publicação; entrada do Nível II e compatibilidade dos auxiliares; preservação das regiões tratadas; ausência de Sólidos; invalidação após alteração do Check; operação com banco indisponível; falhas antes e depois do commit; concorrência; preservação histórica; ausência de cópias criadas pelo catálogo; exportação e PDFs; e ausência de regressão nos algoritmos.

Os testes de continuidade Sólidos → Nível II não podem ser considerados aprovados apenas porque o banco aponta para Sólidos. Precisam comprovar, em isolamento, que o executor é compatível com a imagem e mantém os pixels esperados.

## Regras de implementação e preservação

- Limite de 200 linhas físicas por arquivo de código; documentação Markdown pode exceder esse limite.
- Reutilizar componentes existentes, separar responsabilidades e evitar duplicar regras de negócio.
- Preservar contratos e nomenclaturas atuais durante a migração.
- Usar logs com etapa, página, operação e resultado, sem credenciais.
- Não modificar algoritmos, thresholds, máscaras, Central V1 ou submódulo de download.
- Não apagar, sobrescrever ou mover resultados históricos, manifests ou backups sem autorização.
- Não executar tratamentos em dados reais durante desenvolvimento.
- Não fazer commit ou push sem autorização.

## Critérios de conclusão

Considerar o backlog concluído somente quando PostgreSQL, schema, migrations, backup/restauração, catálogo, resolvedor, publicador, dependências, invalidação e logs estiverem validados; quando a continuidade Sólidos → Nível II estiver comprovada; quando os resultados históricos e os contratos dos consolidadores forem preservados; e quando testes automatizados, exportação e PDFs não apresentarem regressão.

## Estado atual do repositório na revisão do backlog

Na inspeção de leitura, não foram encontrados módulo PostgreSQL, camada de persistência correspondente ou dependências Python de PostgreSQL no projeto. O estado local também continha alterações e backups não commitados, incluindo arquivos de paginação numérica. Qualquer retomada deve reexaminar o estado do repositório e preservar esse trabalho antes de editar.

## Decisão

PostgreSQL fica registrado como tecnologia escolhida para controlar metadados e referências da pipeline de limpeza. A implementação permanece em backlog e requer priorização e autorização próprias. O filesystem continua armazenando imagens, máscaras, relatórios e manifests; o banco passa a controlar estado somente após migração gradual e validação.
