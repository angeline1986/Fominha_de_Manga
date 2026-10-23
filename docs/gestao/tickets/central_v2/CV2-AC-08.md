# CV2-AC-08 — Avaliar preenchimento uniforme no Auto-Cleaner · Sólidos

- **Prioridade sugerida:** Média-alta
- **Status:** TODO
- **Visão:** Limpeza de Balões
- **Responsável:** A definir

## Objetivo

Avaliar e, após validação, adicionar ao Auto-Cleaner · Sólidos uma alternativa que substitua integralmente cada área aprovada no Auto-Cleaner Check pela cor de fundo estimada. O Auto-Cleaner — Passo 1 deve permanecer inalterado.

## Evidência experimental

Cenário: `comix / Gazing at you_v2`, capítulo `7`, página `page-026-030.png`.

O experimento isolado em `/tmp/solid_uniform_fill` estimou RGB `(255, 255, 255)` para as quatro caixas, substituiu 81.740 pixels dentro delas e alterou zero pixels fora. Não houve dano visual aparente aos contornos dos balões. As áreas 1 e 2 ainda exibiram fragmentos de texto fora das caixas aprovadas. A pasta temporária pode ser removida; os resultados não são artefatos oficiais.

## Comportamento desejado

- Usar somente regiões aprovadas no Auto-Cleaner Check.
- Estimar a cor com amostras confiáveis próximas e verificar se o fundo é uniforme.
- Preencher integralmente a caixa, sem detectar letras por threshold.
- Não alterar pixels fora das caixas aprovadas nem expandir automaticamente as caixas. Texto fora da seleção deve ser corrigido na revisão do Check.
- Sinalizar para revisão e não preencher quando a estimativa for ambígua.
- Registrar parâmetros, máscaras, fontes e hashes utilizados.

## Investigação e validação

- Definir critérios objetivos de uniformidade e confiança da estimativa.
- Validar em fundos brancos e sólidos coloridos e verificar caixas que contenham contornos ou desenhos.
- Avaliar resultados e reexecuções existentes e garantir que a técnica não interfira em balões transparentes, degradês ou estilizados.
- Comparar casos positivos e negativos visualmente antes de recomendar ativação geral.

## Critérios de aceite

- Remover texto e fantasmas dentro de caixas válidas com fundo uniforme.
- Preservar contornos, desenhos e outros elementos legítimos.
- Alterar zero pixels fora das caixas aprovadas.
- Não preencher fundos ambíguos; sinalizar esses casos para revisão.
- Não sobrescrever resultados históricos sem reexecução explicitamente autorizada.
- Preservar compatibilidade com manifestos e hashes existentes.
- Validar com testes automatizados e comparações visuais antes de implementar no fluxo oficial.

## Restrições

- Não modificar o Auto-Cleaner — Passo 1, regras originais de detecção/classificação, Auto-Merge Níveis I–III ou Glass.
- Não implementar preenchimento automático em fundos ambíguos.
- Preferir módulo próprio e reutilizar validação, versionamento e persistência existentes.
- Respeitar o limite de 200 linhas por arquivo de código, exceto `.md`.

## Referências

- `central_v2/backend/orchestration/textoff_merged/solid_stage.py`
- `central_v2/backend/routes/laboratorio_solidos.py`
- `central_v2/backend/orchestration/textoff_merged/solid_reexecution.py`
- Experimento temporário: `/tmp/solid_uniform_fill` (pode ser removido; resultados não oficiais).
