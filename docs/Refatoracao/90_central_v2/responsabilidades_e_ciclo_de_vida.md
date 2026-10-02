# Central V2 — responsabilidades e ciclo de vida

Data: 2026-09-27.

## Escopo autorizado

Corrigir os acoplamentos identificados na auditoria da Central V2, com
responsabilidade única e limite obrigatório de 200 linhas por arquivo de código.
Essa regra substitui o antigo gatilho flexível de aproximadamente 200 linhas.

Não inclui migração funcional do Auto-Merge, alteração da V1, de algoritmos,
manifests, regras de promoção ou runtimes especializados.

## Responsabilidades resultantes

| Local | Responsabilidade |
| --- | --- |
| `backend/server.py` | Inicialização e encerramento dos recursos do servidor |
| `backend/http_handler.py` | Adaptação HTTP e integração com o ciclo de vida do servidor |
| `backend/routes/` | Roteamento e contratos das respostas, incluindo encerramento |
| `_app/api/shutdown.js` | Transporte e validação da confirmação de encerramento |
| `_shell/shutdown.js` | Confirmação, botão e apresentação do encerramento |
| `_shell/shell.js` | Composição da interface e limpeza de seus componentes |
| `_shell/context.js` | Ligação do seletor visual com controller e store de contexto |
| `_shell/merge_levels.js` | Apresentação e seleção dos níveis na navegação |
| `_app/state/manga_state.js` | Dados da obra e suas notificações |
| `_app/router/router.js` | Navegação e ciclo de vida da página ativa por contêiner |
| `visao_geral/resumo_operacao.js` | Apresentação reativa dos dados estruturais |

O CSS foi consolidado por responsabilidade: shell, navegação, movimento,
seletor de níveis, contexto, botões e tela de encerramento. Regras antigas
substituídas foram consolidadas; não houve redesenho da interface.

## Contratos corrigidos

- O Resumo observa diretamente `mangaState`, inclusive limpeza e conclusão
  do carregamento. Não depende da notificação antecipada de outro store.
- Respostas de uma seleção antiga continuam sendo descartadas pelo controller.
- A página retorna sua função de limpeza; o router a executa antes da próxima
  montagem e no encerramento da aplicação.
- Navegações assíncronas antigas não sobrescrevem a navegação mais recente.
- Uma rota inválida não destrói a página ativa.
- O encerramento só apresenta sucesso após HTTP válido e confirmação
  `status: shutting_down`. Falhas restauram o botão e preservam a interface.
- `POST /api/shutdown` mantém seu contrato e encerra o servidor fora da
  thread que atende a requisição. GET e POST desconhecidos permanecem 404.

## Evidências

- 19 testes Python da V2 passaram, incluindo HTTP real em porta temporária,
  encerramento e verificações arquiteturais.
- 12 testes JavaScript passaram, sem dependências externas: troca de obra,
  respostas fora de ordem, falha de carregamento, assinatura/limpeza,
  navegação concorrente e encerramento com sucesso/erro/cancelamento.
- Chrome headless: bootstrap, navegação, seleção do Nível III, retorno por
  Escape, troca entre duas obras e atualização do Resumo validados.
- Chrome headless: falha HTTP e confirmação de encerramento validadas.
- Estilos computados comparados com o CSS anterior: menu em 1280 e 640 px,
  navegação Auto-Merge, Nível III selecionado e Resumo com obra selecionada.
  As propriedades visuais comparadas permaneceram equivalentes.
- Os casos de navegador usaram catálogo e obras fictícios; não processaram
  capítulos reais nem validaram algoritmos de Merge.
- Sintaxe Python/JavaScript e `git diff --check` passaram.
- 37 arquivos de código na V2; maior arquivo com 171 linhas.

Comandos reproduzíveis, executados na raiz:

```sh
python3 -m unittest discover -s dev/tests -p 'test_central_v2_*.py'
node --experimental-vm-modules --test dev/tests/central_v2_frontend/*.test.mjs
```

O teste de arquitetura verifica tamanho, localização das chamadas HTTP,
referências de assets e ausência de imports da interface legada no backend.
Responsabilidade única continua exigindo revisão; contagem de linhas não
substitui avaliação de coesão.

## Continuidade

Regras locais registradas em `central_v2/AGENTS.md` e nos dois documentos de
arquitetura-alvo disponíveis no repositório.

A próxima frente escolhida pelo usuário é o Auto-Merge, começando pela
auditoria dos contratos do Nível I. A migração deverá usar a fronteira
V2 → orquestração → domínio existente → artefatos autoritativos.

As alterações deste checkpoint permanecem no working tree, sem commit.
O teste de persistência do Nível I já tinha alterações locais antes deste
trabalho e não foi modificado nesta unidade.
