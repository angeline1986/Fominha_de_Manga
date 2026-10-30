# CV2-AUD-02 — Selecionar 2 a 4 quadros em Antes & Depois

- **Prioridade:** P2
- **Status:** DONE (30/10/2026)
- **Visão:** Limpeza de Balões · Antes & Depois
- **Responsável:** A definir

## Problema

A auditoria mostra sempre quatro quadros — Original, Auto-Cleaner I, Auto-Cleaner II e Consolidado Final. A largura obriga a rolagem horizontal mesmo quando a comparação desejada envolve apenas dois ou três estágios.

## Decisão de interface

Adicionar um botão **“Quadros”** na barra superior que abre quatro caixas de seleção: Original, Auto-Cleaner I, Auto-Cleaner II e Consolidado Final. Todos começam marcados. O usuário pode manter qualquer combinação de dois, três ou quatro quadros; a ordem visual dos estágios permanece fixa. Com apenas dois marcados, o controle impede desmarcar outro até que um quadro seja selecionado.

## Proposta para implementação

Adicionar “Quadros” apenas ao modo Antes & Depois. Ao marcar ou desmarcar uma opção, ocultar ou mostrar o cartão correspondente e recalcular a largura da grade no visualizador existente. Manter o zoom, a página e a posição vertical; guardar a escolha no `viewState` que o launcher já transfere entre capítulos. Não alterar imagens, resultados, endpoints nem os demais modos de comparação.

## Critérios de aceite

- [x] A tela abre com os quatro quadros visíveis; o botão “Quadros” apresenta as quatro caixas de seleção com seus estados atuais.
- [x] É possível exibir qualquer combinação de dois ou três quadros; não é possível deixar apenas um visível.
- [x] A grade usa apenas a largura dos quadros visíveis, sem espaço vazio para os ocultos.
- [x] A troca de quadros não recarrega a página nem altera o zoom ou a posição vertical da comparação.
- [x] A seleção permanece ao navegar entre páginas e capítulos na mesma sessão da tela.
- [x] O controle pode ser usado por teclado e informa quais quadros estão ativos.
- [x] Os outros visualizadores continuam com o layout atual.

**Referência técnica:** `central_v2/frontend/texto_off/comparison/model.js`, `slider.js` e `screen_template.js`.
