# Atalhos de teclado — Limpeza de Balões V2

**Escopo verificado:** Laboratório V2 e listener compartilhado de paginação tabular.\
**Mudança de referência:** commit `cef3cd42`.

| Tecla | Superfície | Efeito | Limites verificados |
|---|---|---|---|
| `Esc` | Laboratório, `workspace_controls.js` | sai do modo Foco | só previne default e desativa o foco se `lab-focus-mode` está ativo; listener respeita modal aberto. |
| `F` | Laboratório, `workspace_controls.js` | alterna o modo Foco | ignora campos editáveis e modificadores Alt/Ctrl/Meta; não opera se o root foi desmontado. |
| `←` / `→` | paginação do Laboratório, `page_navigation.js` | página anterior/próxima | listener exige root ativo, botão disponível, sem repetição/modificadores, foco fora de controles/editáveis e sem modal. |
| `←` / `→` | uma `nav.pagination` visível | página anterior/próxima | listener de `frontend/_shared/pagination/pagination.js`; exige exatamente um pager visível e ignora botões/campos, modal, modo de foco global de imagem e lock de foco do Laboratório. |

Os arquivos `page_navigation.js` e `_shared/pagination/pagination.js` têm listeners distintos. A chamada de `dispose()` da navegação do Laboratório os remove conforme seus ciclos de vida; o listener de paginação compartilhada é único no módulo.

## Não coberto

Não afirmar que Escape ou as setas tenham o mesmo efeito na tela Comparação, Especiais, Solids, Sommelier, Auto-Cleaner Check ou na Central V1. Um handler global só afeta a superfície que passa seus próprios critérios de ativação.

## Referências

- [`workspace_controls.js`](../../../central_v2/frontend/texto_off/laboratorio/workspace_controls.js)
- [`page_navigation.js`](../../../central_v2/frontend/texto_off/laboratorio/page_navigation.js)
- [`pagination.js`](../../../central_v2/frontend/_shared/pagination/pagination.js)
- [Laboratório](../limpeza_baloes/laboratorio.md)
