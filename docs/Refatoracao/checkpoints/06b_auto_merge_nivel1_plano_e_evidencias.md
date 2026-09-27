# Auto-Merge Nível I — fronteiras, lacunas e primeira unidade V2

Data: 2026-09-27. Base: [contrato observado](06a_auto_merge_nivel1_contrato.md).
Status: auditoria concluída; nenhuma execução de Auto-Merge implementada na V2.

Atualização: a consulta AM1-A foi implementada e validada; ver
[checkpoint 07](07_auto_merge_nivel1_consulta_v2.md). A execução segue pendente.

## Restrições confirmadas

- V1 intacta: sem extração, movimentação, cópia ou alteração de seus arquivos.
- V2 tem interface, transporte, jobs e orquestração próprios.
- Reutilizar domínio existente; não duplicar os algoritmos ou seus defaults.
- Manifests, cobertura, artefatos, origem e encaminhamento preservam autoridade.
- Arquivos novos com até 200 linhas e uma responsabilidade por arquivo.
- Teste do legado pode usá-lo como referência em dados temporários; código de
  produção V2 não importa `interface_web` nem chama seu servidor para executar.

## Fronteira comprovada

| Capacidade | Situação | Direção para V2 |
| --- | --- | --- |
| Analisar fontes e escolher cortes | Domínio existente | Reutilizar funções V3 |
| Executar V3 com destino de estágio | Domínio existente | Usar `output_dir_override` |
| Nomenclatura e colisão | Domínio existente | Reutilizar helpers existentes |
| Reconhecer MERGE fisicamente | Domínio existente | Reutilizar em validação de execução |
| Projeção estrutural de obra | V2 existente | Consumir estado estrutural |
| Recuperação parcial após região extensa | Somente V1 | Lacuna de capacidade de domínio |
| Materialização dos segmentos parciais | Somente V1 para esse contrato | Lacuna de persistência do estágio |
| Promoção específica Nível I | Somente V1 | Lacuna de aplicação/persistência |
| Job, progresso e eventos Nível I | Somente V1 | Implementação própria, por contrato |
| Estado transversal I–V | V1 `row_state` | Não copiar nem presumir equivalência |

**Conclusão:** apenas chamar `merge_chapter()` não entrega equivalência ao
Auto-Merge Nível I da Central. O caminho completo é reaproveitável em parte;
o salvamento parcial e a promoção exigem capacidades adicionais.

Em especial, `_next_safe_band_after` e a retomada da partição são decisões
algorítmicas, não mera serialização. Não serão recriadas silenciosamente em
routes, jobs, frontend ou em um arquivo chamado "orquestração".

Manter V1 intacta, não importá-la e não duplicar algoritmos é compatível com
reutilizar o domínio disponível, mas não resolve por si só essa capacidade
ausente. Sua solução precisa ser definida antes de liberar execução completa.
Esta auditoria não autoriza relaxar nenhuma dessas restrições.

## Primeira unidade proposta: AM1-A — consulta do estágio

Implementar uma fatia somente de leitura de Auto-Merge Nível I na V2:

1. Receber provider e obra; resolver capítulos dentro do catálogo autorizado.
2. Consultar tentativas e manifests existentes, sem gerar/reparar/regravar nada.
3. Projetar evidências do Nível I: manifesto reconhecido, arquivos declarados,
   intervalos residuais e erros de leitura. Distinguir ausência de corrupção.
4. Apresentar a página em Processamento → Auto Merge → I.
5. Usar componentes pequenos para tabela, seleção e feedback quando necessários.
6. Reagir à troca de contexto e encerrar recursos ao sair da rota.

Não inferir conclusão de pasta ou PNG existente. Não anunciar integridade
física quando somente metadados foram lidos. Não recalcular residual, criar
um `merge_state` transversal alternativo nem disponibilizar botão de execução
como se o serviço de processamento já estivesse disponível.

Esta unidade torna a primeira tela útil sem alterar artefatos. É parcial e
não pode ser marcada como migração funcional completa do Auto-Merge.

### Responsabilidades propostas, ainda não criadas

| Local | Responsabilidade |
| --- | --- |
| `central_v2/backend/routes/auto_merge.py` | Entrada HTTP da consulta |
| `orquestracao/auto_merge/consulta.py` | Caso de uso e coordenação da consulta |
| `processamento/unificacao_imagens/auto_merge/leitura.py` | Leitura do contrato persistido do estágio |
| `central_v2/backend/state/auto_merge.py` | DTO de evidências para a página |
| `central_v2/frontend/_app/api/auto_merge.js` | Transporte da consulta |
| `central_v2/frontend/_app/state/auto_merge.js` | Estado da consulta e notificações |
| `central_v2/frontend/processamento/auto_merge/nivel1.js` | Composição da página |

Nomes são proposta de responsabilidade, não ordem para criar pastas vazias.
Separar leitor, validação e projeção quando a implementação exigir;
respeitar o limite de 200 linhas sem compactação artificial.

## Unidades posteriores à consulta

- AM1-B: especificar e prover as capacidades de domínio faltantes com testes
  de equivalência; preservar V1. Não confundir isso com copiar seu código.
- AM1-C: caso de uso próprio de execução Nível I, adaptador de progresso,
  job V2, persistência de eventos e endpoint de execução.
- AM1-D: conectar execução à página e validar completo, parcial, erro,
  reconhecimento de resultado anterior e promoção recusada.
- Fechar com caso real controlado e comparação de artefatos antes de Nível II.

## Pontos de atenção para a execução

1. A V1 remove AUTO_MERGE antes de nova tentativa e não verifica nessa entrada
   toda a cadeia consumidora posterior. Reexecução não é uma consulta inofensiva.
2. `OPLOCK` protege só o processo V1. Um lock apenas na V2 não exclui a V1.
   A política de operação simultânea sobre a mesma obra precisa ser explícita
   antes de habilitar escrita; não presumir proteção entre servidores.
3. `selected` não elimina capítulos repetidos, enquanto `do_merge` usa workers.
   A validação V2 deve ter contrato próprio para duplicatas antes da execução.
4. Destino oficial ocupado pode deixar manifesto completo em AUTO_MERGE,
   `status: error` e `auto_merge_saved: 0`. Estado de execução e arquivos
   existentes não são a mesma coisa; não corrigir a V1 nesta iniciativa.
5. `read_merge_failure` pode analisar/persistir quando chamado com o default.
   Uma consulta V2 não pode herdar esse efeito colateral.
6. Há diferenças entre seleção de capítulos por extensão e seleção de fontes
   `page-NNN`. Uma pasta listada não prova que V3 tem fontes válidas.

## Evidências executadas

22 testes existentes passaram:

| Arquivo em `dev/tests/` | Testes | Evidência |
| --- | --- | --- |
| `test_image_stitcher.py` | 3 | Corte, cobertura e saída ocupada |
| `test_image_stitcher_safety.py` | 1 | Rejeição antes de renderizar trecho extenso |
| `test_merge_page_range_naming_contract.py` | 6 | Nome, intervalo, colisão e compatibilidade |
| `test_merge_level1_auto_merge_persistence_contract.py` | 4 | Asserts textuais de persistência/UI |
| `test_mauto2_stage_authority_contract.py` | 4 | Asserts textuais de fronteira entre estágios |
| `test_merge_level2_direct_promotion_safety.py` | 4 | Barreira comum de promoção, bytes, GAP/OVERLAP |

Os testes textuais não demonstram sozinhos equivalência funcional do Nível I.
O teste de persistência já tinha alterações locais antes desta auditoria;
foram preservadas. Os 22 resultados descrevem a árvore de trabalho atual.

Sonda adicional com `do_merge` da V1 em fontes temporárias:

| Cenário | Resultado observado |
| --- | --- |
| Duas fontes de 4000 px | `ok`; estágio completo e MERGE oficial reconhecido |
| Mesmo capítulo já concluído | `skipped`; remove marcador antigo; preserva PNGs |
| 28000 px, faixas em 6000–6400 e 20000–20400 | `partial`; 2 artefatos; residual 6200–20200 |
| 14000 px sem faixa branca | `error`; 0 artefatos; residual 0–14000 para Nível II |
| Destino oficial ocupado | `error`; destino preservado; promoção recusada |

Hashes das fontes e pixels dos artefatos resolvidos comparados com os
intervalos originais em todos os cenários aplicáveis. Não houve caso real,
validação HTTP dessa ação nem prova de concorrência entre V1/V2 nesta unidade.

Reprodução da sonda, a partir da raiz:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 dev/diagnostics/audit_auto_merge_level1.py
```

Resultado persistido em
`docs/Refatoracao/evidencias/auto_merge_level1/cenarios_sinteticos.jsonl`.
Integridade de 93 arquivos de V1/domínio/orquestração e do teste local
monitorado foi comparada por SHA-256 antes/depois, sem alterações.

## Gate antes de liberar execução V2

- [ ] Resolver a capacidade de recuperação parcial sem violar as restrições.
- [ ] Caracterizar contratos de etapa/promoção em testes comportamentais V2.
- [ ] Definir reexecução e exclusão de escrita entre Centrais.
- [ ] Validar fluxo completo e parcial, erro e conservação dos artefatos.
- [ ] Comparar resultado em caso real controlado.

Nenhuma alteração de produção foi realizada nesta auditoria.
