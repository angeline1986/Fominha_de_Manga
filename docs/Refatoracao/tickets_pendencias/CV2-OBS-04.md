# CV2-OBS-04 — Investigar classificação de transparência e resíduos no Auto-Cleaner Nível I

- **Prioridade:** P1 (alta)
- **Status:** TODO
- **Categoria:** Saúde Arquitetural · Observabilidade · Qualidade de Processamento
- **Escopo:** Central V2 — Auto-Cleaner · Nível I / Passo 1
- **Responsável:** A definir

## Contexto

Na revisão do capítulo 6 de `Gazing at you`, página `page-016-020.png`, foi identificado um balão visualmente suspeito de semitransparência cujo texto foi removido pelo Auto-Cleaner, deixando um resíduo esbranquiçado. O componente 7 é a correspondência mais provável.

O relatório registra `best_balloon=4`, `inside_ratio=0.9844`, `decision=remove` e `reason=inside_single_balloon`. O balão nº 4 foi detectado, mas não aparece entre os classificados como transparentes. Como 98,44% do componente estava dentro do balão, acima do limiar de 90%, o autorizador permitiu a remoção.

**A classificação incorreta de transparência é uma hipótese, não uma causa-raiz comprovada.** As métricas dos balões não classificados como transparentes não foram persistidas, impedindo explicar por que o balão nº 4 recebeu esse resultado.

## Justificativa

O comportamento pode processar prematuramente balões que exigem tratamento especializado, causando remoção inadequada, resíduos visuais, retrabalho manual e perda de oportunidade de encaminhamento ao Nível II. A instrumentação atual não permite distinguir com segurança se o problema está na classificação, autorização, máscara ou reconstrução.

## Objetivo

Aprimorar a rastreabilidade da classificação de transparência e da execução do Auto-Cleaner Nível I para explicar a classificação de cada balão, as evidências da decisão de autorização/preservação, a máscara utilizada e a possível origem de resíduos visuais.

## Escopo esperado

- Persistir métricas para balões classificados como transparentes e não transparentes, incluindo amostra analisada, desvio-padrão, cromaticidade e resultado da barreira secundária, quando aplicáveis.
- Associar cada decisão ao identificador do balão e aos componentes de texto correspondentes.
- Preservar evidências para diferenciar classificação, autorização, máscara e reconstrução.
- Avaliar a preservação controlada da máscara bruta do Cleaner e da imagem intermediária anterior à composição.
- Vincular entrada, saída, hashes, parâmetros, máscaras, relatórios e execução de forma rastreável.
- Documentar a interpretação das métricas e decisões.
- Separar os dados de diagnóstico das regras de negócio.
- Controlar a persistência de imagens e máscaras intermediárias para evitar duplicações e crescimento excessivo do armazenamento.

## Critérios de aceite

- [ ] O diagnóstico registra métricas para resultados positivos e negativos da classificação de transparência.
- [ ] É possível explicar por que cada balão foi classificado como transparente ou não transparente.
- [ ] Cada componente de texto registra o balão associado, a decisão de autorização e sua justificativa.
- [ ] As evidências distinguem autorização incorreta de falha na máscara ou na reconstrução.
- [ ] Os artefatos correlacionam entrada, saída, parâmetros e execução de forma inequívoca.
- [ ] Após instrumentação e execução controlada autorizada, o componente 7 e o balão nº 4 da página de referência têm evidências suficientes para confirmar ou descartar a hipótese de falso negativo.
- [ ] A instrumentação não altera as decisões atuais de classificação ou autorização.
- [ ] Para entradas e parâmetros idênticos, o resultado permanece funcionalmente equivalente antes e depois da instrumentação.
- [ ] A documentação descreve métricas, artefatos e procedimento de diagnóstico.

## Fora de escopo e restrições

- Não modificar thresholds, trocar o modelo ou alterar automaticamente classificações.
- Não alterar regras de autorização com base apenas neste caso.
- Não introduzir tratamento especializado automático sem aprovação.
- Não corrigir imagens já processadas nem alterar contratos dos Níveis II e III.
- Preservar a Central V1 e demais fluxos estáveis.
- Este ticket não autoriza implementação ou reexecução imediata de tratamentos.

## Diretrizes para implementação futura

- Preferir módulos com responsabilidade única e arquivos de código de até 200 linhas, sem ampliar módulos legados extensos sem necessidade.
- Reutilizar contratos existentes, evitando mecanismos paralelos.
- Separar coleta e persistência de evidências do processamento.
- Implementar mudanças pequenas e independentes.
- Exigir testes de regressão e equivalência antes de aprovar mudanças.
- Não realizar commit ou push sem autorização.

## Evidência de referência

- **Obra/capítulo/página:** `Gazing at you` / 6 / `page-016-020.png`
- **Componente/balão:** 7 / 4
- **Inclusão:** 98,44%
- **Decisão/motivo:** `remove` / `inside_single_balloon`
- O relatório registra sete balões detectados, três classificados como transparentes; o balão nº 4 não recebeu essa classificação.
- As alterações observadas ficaram dentro da máscara final autorizada. Os artefatos atuais não permitem determinar se o resíduo veio da reconstrução ou da preservação de conteúdo original fora da máscara.

**Referências técnicas:** `processamento/limpeza_baloes/cleaner_v2/balloon_authorization.py`, `processamento/limpeza_baloes/cleaner_v2/transparency_classifier.py`, `level1-balloon-report.json` e `clean-manifest.json`.

## Dependências

Não há dependência obrigatória de implementação com `CV2-OBS-03`. Se os dois tickets identificarem necessidades comuns de observabilidade, avaliar posteriormente uma infraestrutura compartilhada sem unificar os escopos funcionais.

## Resultado esperado

Permitir investigar e comprovar causas de classificações de transparência potencialmente incorretas e resíduos do Auto-Cleaner Nível I, preservando as regras atuais de segurança e processamento.
