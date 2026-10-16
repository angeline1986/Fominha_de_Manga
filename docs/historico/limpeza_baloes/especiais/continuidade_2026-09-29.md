# Cápsula de continuidade — TextOff e Casos Especiais

**Data:** 29/09/2026

**Branch:** `develop`

**Propósito:** retomar o trabalho em outra sessão sem depender de arquivos temporários nem perder decisões e evidências.

## Estado confirmado

As mudanças de hoje foram commitadas e enviadas para `origin/develop`:

- `73dff47a Fix TextOff Merged Level II transparency flow`
- `453b6fa0 Fix per-page balloon mask label validation`
- `52af0926 Organize TextOff Merged chapter artifacts`

O defeito que impedia o Nível II de aceitar o Capítulo 3 foi corrigido. A validação agora trata os rótulos das máscaras por página, pois os rótulos reiniciam em cada imagem; antes, exigia-se unicidade no capítulo inteiro e páginas válidas eram classificadas como `missing_level1`.

Os artefatos de Nível I e II do Capítulo 3 foram reorganizados sem alterar o conteúdo dos PNGs. Os manifestos e relatórios apontam para os novos caminhos relativos, e os leitores continuam compatíveis com artefatos antigos no formato plano.

Estrutura adotada dentro de cada capítulo:

```text
MERGED_NIVEL_I/<capitulo>/
  clean/  imagens finais
  mask/   máscaras do Cleaner, balões transparentes e texto adiado
  json/   manifestos e relatórios

MERGED_NIVEL_II/<capitulo>/
  clean/  imagens finais do capítulo
  mask/   máscaras de texto autorizadas por página
  json/   manifesto e relatório do Nível II
```

Na migração do Capítulo 3, foram organizados 104 arquivos do Nível I e 63 do Nível II. Os hashes dos 163 PNGs foram preservados. A consulta posterior confirmou 17 balões transparentes em 10 páginas, 17 componentes adiados e 8 páginas com texto processado no Nível II.

## Abordagem e justificativas

- O trabalho ficou dentro da Central V2; não houve alteração de código da Central V1.
- O algoritmo e os parâmetros visuais previamente validados foram preservados. A referência continua sendo máscara-base 3×3, autorização 9×9 e contexto LaMa de 120 px. Testes com dilatação maior não trouxeram melhora visual significativa.
- Não foi feita otimização especulativa: primeiro é necessário medir as fases. Há uma oportunidade provável de evitar uma segunda inferência YOLO durante a autorização e a gravação dos artefatos adiados, mas isso só deve ser implementado com comparação pixel a pixel e igualdade das máscaras/saídas.
- O resultado do Capítulo 3 mostra 31 imagens de entrada, 8 páginas com texto e 1.654.872 pixels alterados no Nível II. As páginas prioritárias para avaliação visual continuam sendo `page-051-059`, `page-078-083`, `page-156-163` e `page-179-187`; ainda há resíduos visíveis em balões.
- Os testes executados passaram: 17 testes focados de TextOff, 80 testes Python da Central V2, 46 testes de frontend e `git diff --check`.

## Estado local a preservar

Ao encerrar a sessão, o `git status` também mostrava duas alterações locais fora deste trabalho:

- `m download/mangago_downloader`
- `M processamento/limpeza_baloes/cleaner_v2/README.md`

Elas foram deliberadamente mantidas fora dos commits de hoje. Verifique o estado atual antes de qualquer operação Git e não descarte essas alterações.

## Direcionamento: iniciar TextOff — Casos Especiais

O próximo trabalho deve começar por levantamento e contrato, antes de implementar processamento automático:

1. Inventariar na Central V1 a tela **Tratamentos especiais**, seus tipos, parâmetros, ordem de operações, exemplos Antes/Depois e comportamento de comparação. Os tratamentos de interesse já identificados são **Patch Balão Transparente** e **Balão Transparente — Legado**. São operações manuais hoje; o legado usa uma sequência diferente e foi mantido para comparação histórica.
2. Registrar por tratamento o que entra, o que pode ser alterado, formato de saída, limites da ROI, parâmetros e evidências. Não inferir que o melhor resultado de um caso vale para todos os demais. `04_lama_text_only_legacy_roi.png` foi apontado como melhor resultado num teste anterior e deve ser tratado como referência daquele teste, com proveniência e parâmetros recuperados antes de promovê-lo.
3. Definir uma implementação isolada na Central V2: rota, interface, orquestração, armazenamento, manifesto com duração e proveniência, e ambiente virtual dedicado para a feature. Não mover nem alterar a implementação V1; compartilhar código só após confirmar que isso não muda seu comportamento.
4. Definir se o primeiro fluxo recebe uma imagem escolhida manualmente ou um resultado do Merged, e como seleciona o tratamento. Preservar o original, produzir saída em staging e exigir revisão visual antes de considerar qualquer resultado validado.
5. Criar casos de validação com as quatro páginas prioritárias (`page-156-163`, `page-051-059`, `page-078-083`, `page-179-187`). Comparar pixels e aparência, registrando parâmetros e versão do código. Só então promover uma configuração validada para o fluxo de produção da Central V2.

## Primeiras verificações na próxima sessão

1. Atualizar `develop` e confirmar que os três commits acima estão presentes.
2. Verificar se a Central V2 em execução foi reiniciada para carregar as mudanças.
3. Conferir os manifestos do Capítulo 3 e abrir as quatro imagens de validação para estabelecer a linha de base atual.
4. Ler `docs/Refatoracao/02_processamento/text_off/correcao_assistida/analise_correcao_assistida_e_tratamentos_especiais.md`, `docs/Refatoracao/00_arquitetura/01_ambientes_virtuais.md` e o contrato arquitetural da Central V2 antes de desenhar a feature.
5. Começar por um inventário comparativo dos tratamentos V1 e uma proposta de contrato V2; só depois implementar.
