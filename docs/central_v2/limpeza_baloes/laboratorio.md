# Laboratório — Central V2

**Escopo:** Laboratório de Limpeza de Balões na V2. A página não descreve os controles das outras telas Foco da aplicação.

## Implementação

- Frontend: `central_v2/frontend/texto_off/laboratorio/{index,view,data_loader,file_explorer,page_navigation,workspace_controls,roi_selection,treatment_controller,tratamentos,degrade}.js` e `style.css`.
- API: `central_v2/frontend/_app/api/laboratorio.js`.
- Backend: rotas `laboratorio_pages.py`, `laboratorio_dispatch.py`, `laboratorio_degrade.py`, `laboratorio_degrade_jobs.py`, `laboratorio_tratamentos.py`, `laboratorio_solidos.py`, além de logging e locks.

## Operação e ferramentas

A view compõe o seletor de páginas, área de visualização e ações de tratamento. `data_loader.js` popula dados, `page_navigation.js` mantém página/capítulo e `roi_selection.js` coleta regiões na escala da imagem. `workspace_controls.js` altera estado de zoom, painel e modo Foco. Execução e autorização de tratamentos são encaminhadas pelos módulos de controller e pela API; o backend revalida a obra/fonte.

O fluxo Degradê pode solicitar candidatos e exigir confirmação de autorização antes de seguir. A decisão de autorização e gravação de execução ocorre no backend; o usuário não deve ser tratado como se a prévia fosse limpeza já aplicada.

## Modo Foco e paginação por teclado

O Modo Foco ativa classe `lab-focus-mode`, atualiza `aria-pressed` e trava o scroll do body. O footer de Foco expõe navegação de páginas e a indicação `F ou Esc para sair`.

- `Esc` em `workspace_controls.js`: só chama `setFocus(false)` quando `lab-focus-mode` está ativo. Antes disso, se houver `dialog[open]` ou `[role=dialog][aria-modal=true]`, o handler deixa a tecla para o modal. Não sai do foco quando ele já está inativo.
- `F` no mesmo arquivo alterna o modo, exceto quando o alvo é campo editável (`contenteditable`, `INPUT`, `TEXTAREA`, `SELECT`); modificadores Alt/Ctrl/Meta também impedem o atalho.
- `ArrowLeft`/`ArrowRight` em `page_navigation.js`: navegam anterior/próxima somente no Laboratório conectado, sem repetição/modificadores, fora de campos editáveis/controles e quando não há modal aberto. Botão desabilitado impede navegação. O listener é removido em `dispose()`.
- O listener geral em `frontend/_shared/pagination/pagination.js` opera para um único `nav.pagination` visível e ignora botões/campos/modais, o modo de foco de imagem e o lock do Laboratório. Os limites são descritos em [atalhos](../interfaces/atalhos.md).

Este comportamento deve ser referenciado ao commit `cef3cd42`. Não estender a descrição para outras telas ou para V1 sem verificar listeners locais.

## Seleção e efeitos

O zoom altera dimensões CSS da imagem original; ROI usa as coordenadas de origem e limites da imagem. Mudar zoom/visualização não muda pixels de origem. Ações de tratamento geram execução/job ou proposta conforme endpoint; leia o contrato da rota para distinguir prévia, autorização, conclusão e promoção.

## Lacunas

Contrato completo das mensagens de erro por ação, cobertura funcional do Laboratório V1 e equivalência de coordenadas em todos os tamanhos/resoluções devem ser levantados por revisão de código/testes existentes, sem executar em obra real.
