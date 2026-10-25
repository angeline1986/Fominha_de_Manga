# LAB-APPLY-FINAL | Aplicar resultado do Laboratório ao Consolidado Final

**Prioridade:** ALTA
**Status:** **ETAPAS 1 A 5 IMPLEMENTADAS**
**Área:** Laboratório da Central V2
**Alvo limitado:** página selecionada em `07_CONSOLIDADO_FINAL` e seus metadados oficiais

## Contexto

O Laboratório pode gerar uma imagem melhor do que a versão atualmente vigente no fluxo oficial. A Central V2 permite selecionar o resultado no cartão, aplicá-lo pelo painel e restaurar versões anteriores com procedência registrada no Consolidado Final.

## Problema resolvido

A substituição manual no disco exigia Terminal e podia deixar imagem, manifesto e hash divergentes ou perder o histórico e a procedência. O fluxo implementado faz a publicação pela interface e preserva a versão anterior.

## Objetivo

Definir um fluxo controlado na Central V2 para aplicar, mediante confirmação, o resultado aprovado do Laboratório a uma única página do `07_CONSOLIDADO_FINAL`, preservando histórico, proveniência, consistência dos metadados e possibilidade de restauração.

## Escopo funcional implementado

### Ação e validação prévia

- Exibir **“Aplicar no Consolidado Final”** no painel após seleção explícita de um tratamento concluído no cartão e validação da proposta.
- Confirmar provider, obra, capítulo e página; existência e integridade do artefato; dimensões; destino; e hash da versão final vigente.
- Exibir no painel o tratamento, capítulo e página oficiais. O original e o resultado tratado permanecem visíveis nos cartões do Laboratório.
- Antes de publicar, confirmar que a página final e o resultado não mudaram desde a seleção. Em conflito, interromper e solicitar nova seleção.

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

- [x] O Laboratório apresenta **“Aplicar no Consolidado Final”** após selecionar um cartão de resultado concluído e obter uma proposta válida.
- [x] Provider, obra, capítulo, página, artefato, dimensões, hash e destino são validados antes da publicação.
- [x] O cartão selecionado é destacado e o painel mostra o destino oficial antes da confirmação.
- [x] Mudança concorrente da página final desde a seleção bloqueia a publicação até nova seleção.
- [x] A publicação afeta somente a página selecionada em `07_CONSOLIDADO_FINAL`.
- [x] Imagem, manifesto e hash são publicados por transação recuperável, com rollback em falha simulada.
- [x] Versão anterior e dados necessários para restauração permanecem preservados e rastreáveis.
- [x] Proveniência registra run_id, artefato, tratamento, página e data/hora, com origem oficial reconhecida pelos leitores.
- [x] A operação não altera a pasta do tratamento original nem outras páginas do capítulo nos testes focados.
- [x] Reset, composição e recuperação do Artístico, reconstrução e Combo Turbo têm testes de compatibilidade focados.
- [x] O fluxo dispensa substituição manual por Terminal.
- [ ] Confirmar visualmente na Central V2, após reinício, a seleção no cartão, aplicação pelo painel e restauração em uma obra real.

## Riscos e dependências

- **Integridade de imagem e manifesto:** atualizar somente um dos dois pode tornar o Consolidado Final inconsistente; publicação precisa de protocolo recuperável e validação posterior.
- **Concorrência:** uma versão final pode mudar entre a seleção e a aplicação; é necessário controle de versão/hash esperado e conflito explícito.
- **Origem não reconhecida:** um novo valor de origem pode quebrar leitores, comparadores, Reset ou tratamentos posteriores. Confirmar contrato oficial antes de gravá-lo.
- **Rollback incompleto:** guardar apenas o hash, sem preservar a referência recuperável aos bytes anteriores, não permite restaurar a imagem.
- **Escopo acidental:** resolução incorreta de IDs/caminhos pode afetar outra página ou o diretório do tratamento; validar todos os identificadores e limitar a escrita.
- **Aprovação visual ambígua:** definir qual estado/evidência comprova aprovação e como ela se mantém vinculada ao artefato exato que será publicado.
- **Compatibilidade de histórico:** leitores atuais podem assumir um tipo de origem ou layout diferente; mapear produtores, leitores e contratos antes da implementação.
- **Dependência operacional:** acesso ao artefato do Laboratório, persistência da versão anterior, atualização do manifesto e auditoria devem participar do mesmo protocolo de publicação e recuperação.

## Prioridade e status

**Prioridade ALTA.** A ação pode substituir conteúdo oficial, portanto cada etapa deve ser verificada antes de habilitar a escrita.

**ETAPAS 1 A 5 IMPLEMENTADAS:** proposta verificada, seleção no cartão, publicação confirmada pelo painel e restauração de versões arquivadas pela interface. A linhagem vigente após uma restauração é usada pelo Reset e pela composição e recuperação do Artístico. Pincéis bloqueiam a origem Laboratório até que a página seja restaurada.

## Etapas controladas

1. **Proposta somente leitura — concluída:** validar execução, página, hashes e dimensões; comparar versões com token de revisão.
2. **Interface de revisão — concluída:** selecionar o tratamento concluído no cartão; o painel mostra o destino oficial e exige confirmação compacta para aplicar. A seleção local é invalidada quando a prévia ou a página muda.
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
- **Correção inicial:** a estrutura conhecida do Auto-Cleaner Glass (`05_AUTO_CLEANER_TRANSPARENCIA/<perfil>/<capítulo>/clean/<página>_clean.png`) passou a apontar para o destino oficial. O histórico usa o mesmo destino.
- **Verificação:** a proposta real do Artístico retornou `Cap. 1 · page-050-057.png`; as imagens atual e experimental responderam HTTP 200, sem publicação. Passaram 31 testes focados de backend e 16 de frontend, incluindo comparação e aplicação em dados isolados. A conferência visual na interface continua pendente.

### Arquivo `images` do Auto-Cleaner Check

- **Sintoma:** uma execução Artístico sobre `04_AUTO_CLEANER_CHECK/3/images/page-060-068.png` voltou a mostrar “Consolidado Final indisponível” porque a comparação usou `images` como capítulo.
- **Causa:** a resolução anterior cobria apenas a pasta `clean` do Glass. O explorador pode escolher imagens de outras etapas.
- **Correção:** localizar o nome da página nos manifestos do Consolidado Final; quando ele existir em vários capítulos, conferir o capítulo presente no caminho verificado da origem Check ou Glass. Sem capítulo comprovado, bloquear com erro explícito. O histórico também reconhece essas estruturas.
- **Verificação:** a proposta real retornou `Cap. 3 · page-060-068.png`, e as duas imagens da comparação responderam HTTP 200 em leitura, sem publicação final. Testes focados cobrem seleção de arquivos Check/Glass, aplicação isolada e ambiguidade. A conferência visual na interface continua pendente.

### Nome repetido em vários capítulos

- `page-075-078.png` apareceu em cinco capítulos do Consolidado Final. O arquivo selecionado pertencia a `04_AUTO_CLEANER_CHECK/4/images/`, mas a busca anterior usava apenas o nome e recusava a proposta.
- O capítulo `4` do caminho da origem é aceito somente quando o manifesto desse capítulo contém a página. A proposta real passou a retornar `Cap. 4 · page-075-078.png`; as duas imagens responderam HTTP 200 em leitura, sem publicação.
- **Interface simplificada:** o cartão do tratamento concluído permite selecionar o resultado; o painel mostra tratamento, capítulo e página oficiais e solicita confirmação compacta para aplicar. O popup de comparação foi retirado deste fluxo. O comparador do histórico permanece para restauração.
- **Verificação da seleção no cartão:** 19 testes focados de frontend e 32 de backend passaram nessa etapa. Falta a conferência visual e uma aplicação real pela Central V2.

### Recuperação da última execução do Artístico

- Ao selecionar novamente a mesma imagem de origem, a Central V2 procura a execução concluída mais recente do Artístico. A prévia só reaparece se a origem, seu SHA-256, o snapshot, o manifesto e o PNG ainda forem verificáveis.
- O cartão mostra **“Resultado recuperado”** e permite selecionar essa execução para o Consolidado Final, sem executar o filtro de novo. Uma execução nova ou mudança de página invalida respostas de recuperação atrasadas.
- A execução real `91021c3f2a5e470585e994d76bdeaede` de `page-075-078.png` permanece no disco; a consulta de recuperação e a leitura do PNG retornaram HTTP 200 sem alterar o Consolidado Final.
- Verificação focada atual: 33 testes de backend e 20 de frontend passaram. A conferência visual na Central V2 ainda está pendente.

Cada etapa deve manter arquivos de código com até 200 linhas e passar pelos testes focados antes de avançar.
