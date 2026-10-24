# LAB-APPLY-FINAL | Aplicar resultado do Laboratório ao Consolidado Final

**Prioridade:** ALTA
**Status:** **ETAPAS 1 A 5 IMPLEMENTADAS**
**Área:** Laboratório da Central V2
**Alvo limitado:** página selecionada em `07_CONSOLIDADO_FINAL` e seus metadados oficiais

## Contexto

O Laboratório pode gerar uma imagem melhor do que a versão atualmente vigente no fluxo oficial. Ainda falta um caminho oficial na Central V2 para promover uma proposta aprovada e rastrear sua origem até o Consolidado Final.

## Problema atual

A substituição é feita manualmente no disco, por Terminal. Esse procedimento pode deixar a imagem final divergente de manifestos e hashes, perder o histórico da versão substituída ou não registrar a proveniência do artefato do Laboratório. A origem da substituição também pode não ser reconhecida por leitores futuros.

## Objetivo

Definir um fluxo controlado na Central V2 para aplicar, mediante confirmação, o resultado aprovado do Laboratório a uma única página do `07_CONSOLIDADO_FINAL`, preservando histórico, proveniência, consistência dos metadados e possibilidade de restauração.

## Escopo funcional futuro

### Ação e validação prévia

- Exibir a ação **“Aplicar no Consolidado Final”** somente quando existir resultado válido e aprovado visualmente.
- Confirmar provider, obra, capítulo e página; existência e integridade do artefato; dimensões; destino; e hash da versão final vigente.
- Comparar a versão atual do Consolidado Final com a proposta do Laboratório lado a lado.
- Antes de publicar, confirmar que a página final não mudou desde a versão carregada/comparada na interface. Em conflito, interromper e solicitar nova comparação; nunca sobrescrever silenciosamente uma atualização concorrente.

### Publicação e histórico

- Promover somente a página selecionada e atualizar a imagem, o manifesto e o hash correspondente como uma operação logicamente atômica.
- Preservar a versão anterior, com referência suficiente para restauração/rollback, sem sobrescrever histórico.
- Registrar proveniência verificável: run_id, artefato de origem, tratamento, identificadores do provider/obra/capítulo/página e data/hora.
- Definir e aprovar uma origem oficial reconhecida pelo sistema para resultados vindos do Laboratório. Não introduzir um valor de origem até confirmar compatibilidade com os contratos e leitores existentes.
- Em falha, não deixar imagem e metadados em estado parcial. A operação não pode afetar outras páginas do capítulo.

### Limites de compatibilidade

- A alteração afeta exclusivamente `07_CONSOLIDADO_FINAL` e seus metadados oficiais.
- Não modificar a pasta original do tratamento (Artistico, Degrade, Suave etc.) nem consumir sua saída por meio de substituição no disco.
- Validar compatibilidade com comparador, reset/restauração, leitura do Consolidado Final, manifestos e futuros tratamentos posteriores, se existirem.
- Resolver se a publicação usará versionamento/rollback já reconhecido pelos leitores ou se algum contrato de leitura precisa ser atualizado; não criar um formato de origem incompatível.

## Fora de escopo

- Alterar algoritmos, thresholds ou parâmetros dos tratamentos.
- Modificar a Central V1.
- Migrar ou reorganizar o armazenamento dos experimentos neste item.
- Substituir arquivos manualmente.
- Alterar páginas além da selecionada ou pastas de tratamentos originais.

## Critérios de aceite futuros

- [ ] O Laboratório apresenta **“Aplicar no Consolidado Final”** apenas para resultado válido e aprovado visualmente.
- [ ] Provider, obra, capítulo, página, artefato, dimensões, hash e destino são validados antes da publicação.
- [ ] A comparação lado a lado mostra a versão atual e a proposta do Laboratório.
- [ ] Mudança concorrente da página final desde a comparação é detectada e bloqueia a publicação até nova revisão.
- [ ] A publicação afeta somente a página selecionada em `07_CONSOLIDADO_FINAL`.
- [ ] Imagem, manifesto e hash são atualizados de forma logicamente atômica, sem estado parcial em falha.
- [ ] Versão anterior e dados necessários para rollback/restauração permanecem preservados e rastreáveis.
- [ ] Proveniência registra run_id, artefato, tratamento, página e data/hora, com origem oficial reconhecida pelos leitores.
- [ ] A operação não altera a pasta do tratamento original nem outras páginas do capítulo.
- [ ] Compatibilidade com comparador, reset/restauração, Consolidado Final, manifestos e leitores relevantes foi validada.
- [ ] O fluxo dispensa substituição manual por Terminal e não causa regressão nos tratamentos oficiais.

## Riscos e dependências

- **Integridade de imagem e manifesto:** atualizar somente um dos dois pode tornar o Consolidado Final inconsistente; publicação precisa de protocolo recuperável e validação posterior.
- **Concorrência:** uma versão final pode mudar enquanto a tela de comparação está aberta; é necessário controle de versão/hash esperado e conflito explícito.
- **Origem não reconhecida:** um novo valor de origem pode quebrar leitores, comparadores, Reset ou tratamentos posteriores. Confirmar contrato oficial antes de gravá-lo.
- **Rollback incompleto:** guardar apenas o hash, sem preservar a referência recuperável aos bytes anteriores, não permite restaurar a imagem.
- **Escopo acidental:** resolução incorreta de IDs/caminhos pode afetar outra página ou o diretório do tratamento; validar todos os identificadores e limitar a escrita.
- **Aprovação visual ambígua:** definir qual estado/evidência comprova aprovação e como ela se mantém vinculada ao artefato exato que será publicado.
- **Compatibilidade de histórico:** leitores atuais podem assumir um tipo de origem ou layout diferente; mapear produtores, leitores e contratos antes da implementação.
- **Dependência operacional:** acesso ao artefato do Laboratório, persistência da versão anterior, atualização do manifesto e auditoria devem participar do mesmo protocolo de publicação e recuperação.

## Prioridade e status

**Prioridade ALTA.** A ação pode substituir conteúdo oficial, portanto cada etapa deve ser verificada antes de habilitar a escrita.

**ETAPAS 1 A 5 IMPLEMENTADAS:** proposta verificada, comparação lado a lado, publicação confirmada e restauração de versões arquivadas pela interface. A linhagem vigente após uma restauração é usada pelo Reset e pela composição e recuperação do Artístico. Pincéis bloqueiam a origem Laboratório até que a página seja restaurada.

## Etapas controladas

1. **Proposta somente leitura — concluída:** validar execução, página, hashes e dimensões; comparar versões com token de revisão.
2. **Interface de revisão — concluída:** escolher a prévia concluída e comparar com o Consolidado Final antes de selecionar o resultado. A seleção local é invalidada quando a prévia ou a página muda.
3. **Publicação segura — concluída:** arquivar os bytes anteriores, registrar procedência, verificar versão esperada e publicar imagem e manifesto por transação recuperável. Reconstrução e Combo Turbo preservam a origem Laboratório; novos Pincéis são bloqueados até a restauração dessa página.
4. **Histórico e restauração — concluída:** listar apenas versões com PNG e hash verificáveis, comparar com a versão atual e restaurar uma delas sem apagar as demais; exigir confirmação e versão vigente.
5. **Compatibilidade — concluída:** reconstrução e Combo Turbo preservam a origem Laboratório; Reset, composição e recuperação do Artístico seguem a linhagem ativa após restaurações; novos Pincéis são bloqueados antes da execução enquanto a versão Laboratório estiver vigente. Fluxos integrados e falhas foram verificados em fixtures sintéticas.

Cada etapa deve manter arquivos de código com até 200 linhas e passar pelos testes focados antes de avançar.
