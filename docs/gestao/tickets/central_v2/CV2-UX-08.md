# CV2-UX-08 — Padronizar a navegação por capítulo e página nos visualizadores de Limpeza de Balões

- **Prioridade:** P2
- **Status:** DONE (25/10/2026)
- **Categoria:** UI/UX · Navegação de páginas
- **Escopo:** Central V2 — visualizadores da feature Limpeza de Balões
- **Referência:** sidebar com título “Páginas”, seletores `Cap.` e `Pág.` na mesma linha e lista de páginas abaixo, como no Auto-Cleaner Check e no Laboratório.

## Inventário em 24/10/2026

| Tela de visualização | Situação atual | Código |
|---|---|---|
| Auto-Cleaner (Passo 1), Glass Básica, Glass Normal e Legada, Auto-Cleaner: Sólidos, Degradê, Artístico, Suave e Antes & Depois | Usam o visualizador compartilhado com capítulo fixo no cabeçalho, busca e lista de páginas; os seletores de capítulo e página aparecem somente no modo Check. | `central_v2/frontend/texto_off/comparison/screen.js` |
| Mapear — balões identificados | Tem sidebar e lista de páginas mapeadas, mas capítulo fixo no cabeçalho e nenhum dos dois seletores. | `central_v2/frontend/texto_off/comparison/mapear_screen.js` |
| Bubble Sommelier — revisão do capítulo | Tem sidebar de páginas, mas usa badge de capítulo e campo de busca, sem seletores de capítulo e página. | `central_v2/frontend/texto_off/sommelier/review.js` |

O Auto-Cleaner Check (`comparison/screen.js`, modo `check`) e o Laboratório (`laboratorio/view.js`) já exibem os dois seletores. São referências para apresentação e sincronização, respeitando as diferenças de cada tela. O seletor de capítulos do comparador hoje recebe capítulos disponíveis apenas no modo Check (`comparison/launcher.js`); os demais fluxos precisarão fornecer os capítulos elegíveis e carregar seus dados ao trocar a seleção.

## Comportamento esperado

- Exibir capítulo e página selecionáveis na mesma linha acima da lista em cada visualizador inventariado.
- Oferecer somente capítulos e páginas disponíveis para a modalidade atual; não navegar para resultados inexistentes.
- Sincronizar seletores, lista, imagem/comparação, indicadores e painel de dados da página ao trocar capítulo ou página.
- Preservar a seleção inicial vinda da tabela, a ordenação, o estado de zoom/foco e as regras de edição e salvamento de cada tela.
- Evitar requisição duplicada ao selecionar a página ativa; tratar carregamento, capítulo vazio e falha de consulta.
- Preservar a acessibilidade dos seletores e manter a navegação por teclado compatível com CV2-UX-06.

## Critérios de aceite

- [x] Todas as telas inventariadas mostram `Cap.` e `Pág.` e permitem navegar entre os resultados elegíveis da obra.
- [x] Seletor de página, lista e conteúdo exibido permanecem sincronizados após troca de capítulo e página.
- [x] Dados de Mapear, Bubble Sommelier e tratamentos especiais correspondem à página ativa; alterações não salvas bloqueiam a troca de capítulo no comparador.
- [x] O Check e o Laboratório preservam seus comportamentos atuais, inclusive a escolha IMG/MERGE e o explorador do Laboratório.
- [x] Tabelas de execução, o modal de candidatos do Mapear, a antiga tela manual `especiais/view.js` não usada nas rotas atuais e a ação Correção Assistida sem rota implementada ficaram fora deste ajuste.

## Entrega em 25/10/2026

Seletores compartilhados no comparador e no Mapear; revisão do Bubble Sommelier usa os mesmos controles. A troca de capítulo usa apenas resultados elegíveis, mantém zoom e foco no comparador e no Mapear e conserva a página inicial aberta pela tabela. Arquivos de código alterados ou criados têm até 200 linhas. Testes direcionados de navegação passaram. A suíte JavaScript completa ainda possui falhas anteriores em contratos e mocks de outras áreas.
