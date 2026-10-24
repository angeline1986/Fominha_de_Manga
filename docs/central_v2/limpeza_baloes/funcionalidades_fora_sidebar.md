# Funcionalidades fora do sidebar

**Status:** ocultas da navegação principal da Central V2; código preservado. A remoção dos atalhos não desativa rotas, APIs ou executores.

## Combo Turbo

O Combo Turbo coordena a execução de **Sólidos** e **Glass** em lote por capítulo. O planejador verifica as páginas elegíveis e a validade/reutilização dos artefatos. A execução ocorre em um workspace isolado, criado como cópia descartável da obra; ao final, há uma etapa própria de publicação dos resultados válidos.

- Interface: `central_v2/frontend/texto_off/combo_turbo/`.
- Rota de interface: ação `combo-turbo`, ainda registrada em `central_v2/frontend/_app/router/routes.js`.
- Backend: `central_v2/backend/routes/combo_turbo.py` e `central_v2/backend/orchestration/combo_turbo/`.
- A remoção do item do sidebar não apaga nem desativa esses componentes. A rota não é mais oferecida pela navegação normal.
- O Combo Turbo é um executor separado do fluxo direto do Glass. Suas regras de isolamento e publicação não devem ser interpretadas como contrato geral de Reset do Glass.

## Texto Off Legado

“Texto Off Legado” é a tela antiga de execução em lote baseada no fluxo Merged genérico. Ela consulta capítulos Merged e inicia a execução sem selecionar um nível explícito na tela; o executor identifica o fluxo como “Legado”. Os níveis atuais possuem telas e ações próprias.

- Interface: ação `texto-off-legacy`, ainda registrada em `central_v2/frontend/_app/router/routes.js`, apontando para `central_v2/frontend/texto_off/merged/index.js`.
- Execução e apresentação compartilhadas: `central_v2/frontend/texto_off/merged/execution.js` e `view.js`.
- Backend: endpoints e execução compartilhados com o fluxo Merged em `central_v2/backend/routes/textoff_merged.py` e `central_v2/backend/orchestration/textoff_merged/`.
- O item saiu do grupo “LEGADO” do sidebar, mas a rota e o código permanecem no repositório para compatibilidade e referência.

## Não confundir com Glass “Legada”

A opção **Legada** dentro do controle **Auto-Cleaner: Glass** é uma modalidade distinta, associada à ação `texto-off-merged-v` e à tela de nível V. Ela continua no fluxo de limpeza. A remoção do atalho **Texto Off Legado** não remove essa modalidade.
