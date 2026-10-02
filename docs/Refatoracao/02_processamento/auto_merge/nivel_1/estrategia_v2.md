# Auto-Merge Nível I — estratégia própria da V2

Data: 2026-09-27. Base: comportamento observado em 06a e lacunas em 06b.

Obra indicada para a validação controlada posterior: provider `comix`, obra
`Gazing at you_centrav2`. A conferência somente de leitura encontrou 65
capítulos e nenhum diretório de estágio AUTO_MERGE ou MERGE oficial na obra.
Essa conferência não executou processamento nem criou arquivos.

## Intenção funcional a preservar

O Nível I procura dividir a sequência vertical em imagens sem cortar conteúdo.
Quando a sequência inteira pode ser dividida por limites seguros, gera uma
composição completa e só a torna oficial após validar cobertura e arquivos.
Quando não pode, conserva os intervalos comprovadamente seguros, registra os
intervalos que precisam de outra etapa e não promove uma composição incompleta.
Uma falha nunca transforma um intervalo sem corte seguro em um corte forçado.

Essa é a ideia do fluxo a reproduzir. Funções, estruturas internas, nomes locais
e decisões incidentais da Central V1 não são interfaces de implementação V2.

## Responsabilidades da implementação

1. A rota valida provider, obra e lista de capítulos; remove duplicatas ou
   rejeita-as explicitamente antes de criar trabalho.
2. Um serviço V2 cria um job próprio, publica progresso/resultados e coordena
   os capítulos. Transporte HTTP não executa operações de imagem.
3. Um planner de domínio puro recebe páginas e análise V3 já disponível,
   devolvendo intervalos completos, seguros parciais e pendentes, com razões.
   Ele consome thresholds e cortes de `image_stitcher`; não contém defaults
   paralelos nem faz leitura/gravação de manifests.
4. Um materializador grava somente intervalos aprovados no diretório de estágio
   Nível I e valida dimensões, nomes e cobertura declarada.
5. Um promotor valida cobertura integral contínua e destino livre; publica os
   artefatos e o manifesto oficial de forma recuperável. Artefatos existentes
   ou inválidos não são sobrescritos.
6. Resíduo parcial fica identificado como Nível I e pode ser consumido pelo
   Nível II; nenhum estado transversal I–V é inferido nessa unidade.

Cada função de domínio é determinística e testada com imagens sintéticas.
Os cenários completos, parciais e sem cortes seguros são comparados com as
evidências da V1 quanto à cobertura, aos pixels fonte e aos destinos. A
comparação valida a intenção; não carrega código da V1 em produção.

## Escrita e concorrência

A V2 serializa jobs submetidos e processa até três capítulos selecionados em
paralelo, com progresso granular agregado. Também registra requisições e etapas
do job no terminal. Não reexecuta sobre estágio existente nem substitui destino
oficial ocupado. A abertura das Centrais pelo menu
`fominha` mantém um lease de processo: V1 e V2 não podem ser abertas ao mesmo
tempo nesse fluxo. A V2 também recusa iniciar ou continuar um job se detectar
o servidor V1 no endpoint configurado. Como a V1 precisa permanecer intacta,
uma inicialização manual da V1 que não passe pelo menu não participa do lease;
o teste real deve usar o fluxo oficial e não abrir a V1 durante a execução.

Cada execução usa um identificador e staging isolado. A promoção não substitui
destino oficial ocupado. Falha antes da promoção mantém fontes e composição
oficial anteriores intactas; a recuperação de staging segue política explícita
e auditável, nunca remoção ampla de diretórios sem comprovar propriedade.

## Fatias de entrega

- **AM1-B:** concluída como unidade de domínio sintética. O planner consome
  `analyze_chapter`/`choose_cuts` V3 e emite intervalos seguros/pendentes; o
  materializador só grava intervalos seguros em estágio vazio, valida cobertura
  das fontes/dimensões e remove somente saídas que ele próprio criou se falhar.
  Testes cobrem completo, parcial com retomada, sem corte seguro, pixels exatos,
  estágio e destino ocupados. Os módulos foram validados somente em dados
  temporários.
- **AM1-C:** concluída para a V2: job serializado em background, capítulos
  paralelos até o limite V1 (3), progresso granular e agregado,
  eventos append-only, validação de capítulos, recusa de V1 ativa e política
  explícita de reexecução sem sobrescrita. O endpoint foi validado em imagem
  sintética com promoção completa e bloqueios de segurança.
- **AM1-D:** concluída em interface: confirmação no popup compartilhado com o
  padrão da V1 (`Confirmar`, quantidade de capítulos, `Cancelar`/`Executar`),
  progresso, espera pelo job e atualização dos resultados. A conclusão usa o
  popup compartilhado para apresentar resumo da operação, situação por
  capítulo e detalhes expansíveis de merges, resíduos e próxima etapa, seguindo
  a hierarquia visual do resumo da V1 sem reutilizar seu código. Testes
  automatizados: 28 testes de frontend e 9 testes focados de backend passaram.
  O teste real controlado em
  `comix/Gazing at you_centrav2` ainda é necessário antes de avançar ao Nível II.
