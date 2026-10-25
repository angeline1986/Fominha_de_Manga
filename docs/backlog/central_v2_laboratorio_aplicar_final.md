# LAB-APPLY-FINAL | Aplicar resultado do Laboratório ao Consolidado Final

**Prioridade:** ALTA
**Status:** **ETAPAS 1 A 5 IMPLEMENTADAS**
**Área:** Laboratório da Central V2
**Alvo limitado:** página selecionada em `07_CONSOLIDADO_FINAL` e seus metadados oficiais

## Contexto

O Laboratório pode gerar uma imagem melhor do que a versão atualmente vigente no fluxo oficial. A Central V2 agora permite comparar, aplicar e restaurar essa imagem com procedência registrada no Consolidado Final.

## Problema resolvido

A substituição manual no disco exigia Terminal e podia deixar imagem, manifesto e hash divergentes ou perder o histórico e a procedência. O fluxo implementado faz a publicação pela interface e preserva a versão anterior.

## Objetivo

Definir um fluxo controlado na Central V2 para aplicar, mediante confirmação, o resultado aprovado do Laboratório a uma única página do `07_CONSOLIDADO_FINAL`, preservando histórico, proveniência, consistência dos metadados e possibilidade de restauração.

## Escopo funcional implementado

### Ação e validação prévia

- Exibir a ação **“Aplicar no Consolidado Final”** após comparação válida e seleção explícita da prévia pela pessoa.
- Confirmar provider, obra, capítulo e página; existência e integridade do artefato; dimensões; destino; e hash da versão final vigente.
- Comparar a versão atual do Consolidado Final com a proposta do Laboratório lado a lado.
- Antes de publicar, confirmar que a página final não mudou desde a versão carregada/comparada na interface. Em conflito, interromper e solicitar nova comparação; nunca sobrescrever silenciosamente uma atualização concorrente.

### Publicação e histórico

- Promover somente a página selecionada e atualizar a imagem, o manifesto e o hash correspondente como uma operação logicamente atômica.
- Preservar a versão anterior, com referência suficiente para restauração/rollback, sem sobrescrever histórico.
- Registrar proveniência verificável: run_id, artefato de origem, tratamento, identificadores do provider/obra/capítulo/página e data/hora.
- Registrar a origem `LABORATORIO` reconhecida pelos leitores do Consolidado Final.
- Em falha, não deixar imagem e metadados em estado parcial. A operação não pode afetar outras páginas do capítulo.

### Limites de compatibilidade

- A alteração afeta exclusivamente `07_CONSOLIDADO_FINAL` e seus metadados oficiais.
- Não modificar a pasta original do tratamento (Artistico, Degrade, Suave etc.) nem consumir sua saída por meio de substituição no disco.
- Validar compatibilidade com comparador, reset/restauração, leitura do Consolidado Final, manifestos e futuros tratamentos posteriores, se existirem.
- Usar o histórico e a transação recuperável do Consolidado Final para preservar versões e manter os leitores compatíveis.

## Fora de escopo

- Alterar algoritmos, thresholds ou parâmetros dos tratamentos.
- Modificar a Central V1.
- Migrar ou reorganizar o armazenamento dos experimentos neste item.
- Substituir arquivos manualmente.
- Alterar páginas além da selecionada ou pastas de tratamentos originais.

## Critérios de aceite e validação

- [x] O Laboratório apresenta **“Aplicar no Consolidado Final”** após selecionar um resultado comparado e válido.
- [x] Provider, obra, capítulo, página, artefato, dimensões, hash e destino são validados antes da publicação.
- [x] A comparação lado a lado fornece a versão atual e a proposta do Laboratório.
- [x] Mudança concorrente da página final desde a comparação bloqueia a publicação até nova revisão.
- [x] A publicação afeta somente a página selecionada em `07_CONSOLIDADO_FINAL`.
- [x] Imagem, manifesto e hash são publicados por transação recuperável, com rollback em falha simulada.
- [x] Versão anterior e dados necessários para restauração permanecem preservados e rastreáveis.
- [x] Proveniência registra run_id, artefato, tratamento, página e data/hora, com origem oficial reconhecida pelos leitores.
- [x] A operação não altera a pasta do tratamento original nem outras páginas do capítulo nos testes focados.
- [x] Reset, composição e recuperação do Artístico, reconstrução e Combo Turbo têm testes de compatibilidade focados.
- [x] O fluxo dispensa substituição manual por Terminal.
- [ ] Confirmar visualmente na Central V2, após reinício, a comparação, aplicação e restauração em uma obra real.

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

## Correção da prévia — 24/10/2026

- **Sintoma:** após Artístico ou Suave concluir, a comparação mostrava “Resultado não corresponde à página selecionada” e os dois quadros de imagem ficavam vazios.
- **Causa:** o pedido experimental identifica o tratamento por nome, mas o manifesto real registra `treatment` como objeto com o algoritmo. A validação esperava o nome também no manifesto.
- **Correção:** a proposta confere o nome no pedido e o algoritmo correspondente no manifesto, mantendo as validações de página, origem, dimensões e SHA-256.
- **Verificação:** 30 testes focados de backend e 12 de frontend passaram. As execuções reais de Artístico e Suave para `page-050-057.png` (Cap. 1) produziram propostas válidas; os quatro endpoints de imagem da comparação retornaram PNGs em leitura, sem publicar nada.
- **Pendente:** confirmação visual após reiniciar a Central V2. As suítes gerais ainda têm falhas anteriores, fora deste item.

### Arquivo `clean` do Glass selecionado pelo explorador

- **Sintoma:** a comparação mostrava `Cap. clean · page-050-057_clean.png`, “Consolidado Final indisponível” e imagens vazias.
- **Causa:** o explorador usava a pasta e o nome físico da imagem tratada como identidade da página final. O Consolidado Final registra essa página no capítulo `1` como `page-050-057.png`.
- **Correção:** para a estrutura conhecida do Auto-Cleaner Glass (`05_AUTO_CLEANER_TRANSPARENCIA/<perfil>/<capítulo>/clean/<página>_clean.png`), resolver o destino oficial antes de ler o Final; manter o vínculo com a execução e sua origem verificada. O histórico usa o mesmo destino. Arquivos fora dessa estrutura não recebem destino presumido.
- **Verificação:** a proposta real do Artístico retornou `Cap. 1 · page-050-057.png`; as imagens atual e experimental responderam HTTP 200, sem publicação. Passaram 31 testes focados de backend e 16 de frontend, incluindo comparação e aplicação em dados isolados. A conferência visual na interface continua pendente.

Cada etapa deve manter arquivos de código com até 200 linhas e passar pelos testes focados antes de avançar.
