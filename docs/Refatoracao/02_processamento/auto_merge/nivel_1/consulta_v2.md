# Auto-Merge Nível I — consulta funcional na V2

Data: 2026-09-27. Unidade AM1-A implementada.

## Como testar

1. Reiniciar a Central V2 para carregar o backend atualizado.
2. Em `fominha`, escolher `2. Central V2`.
3. Abrir Processamento → Auto Merge → I.
4. Selecionar provider e obra.
5. Conferir capítulos, registros, arquivos, residual e ocorrências.

Busca, filtros e atualização da consulta estão disponíveis. A página acompanha
trocas de contexto e cancela suas requisições ao sair da rota.

## Escopo entregue

Consulta dos registros existentes, sem execução ou reparação de arquivos.
Nenhum botão de processamento foi habilitado e POST nessa rota retorna 404.
A migração funcional completa do processamento Nível I continua pendente.

Fluxo:

```text
Página Nível I
→ API client / controller / store próprios
→ GET /api/auto-merge/level1?provider=...&manga=...
→ rota HTTP → orquestracao/auto_merge/consulta.py
→ leitores em processamento/unificacao_imagens/auto_merge/
→ DTO de consulta → tabela da página
```

O componente de tabela é compartilhado e não conhece o domínio Auto-Merge.
A página compõe os componentes; apresentação dos registros, consulta,
transporte e estado estão em arquivos próprios.

## Semântica da consulta

- `level1.status`: `absent`, `recorded`, `invalid` ou `unsupported`.
- `kind`: completo ou parcial conforme algoritmo declarado no estágio.
- Arquivos declarados mostram presença ou ausência; pixels não são abertos.
- Residual é o registrado no Nível I, não o residual atual de toda a cadeia.
- A presença de registro oficial não afirma integridade física do MERGE.
- Tentativas antigas são lidas sem completar partições ou regravar JSON.
- Erro em um registro não impede os demais capítulos de aparecerem.
- Contexto é limitado ao catálogo; caminhos externos e artefatos que escapam
  do diretório esperado não são aceitos como resultados presentes.

O DTO não expõe `merge_state` transversal, não decide elegibilidade nem
substitui os manifests como autoridade para executar níveis posteriores.

## Validação

- 32 testes Python da V2 passaram, incluindo consulta HTTP real e POST 404.
- 18 testes JavaScript passaram, incluindo cancelamento, respostas antigas,
  mudança de contexto, erros e nova tentativa de consulta.
- Chrome headless com backend real e dados temporários: navegação até Nível I,
  registros completos/parciais/inválidos/ausentes, busca, filtros, troca de
  obra, saída/retorno à rota, erro HTTP e atualização validados.
- Texto de ocorrência contendo HTML permaneceu texto, sem criar elementos.
- Caso real somente de leitura: `comix / Gazing at you`, HTTP 200,
  65 capítulos e 65 registros de Nível I reconhecidos.
- Testes comparam hashes e mtimes dos arquivos antes/depois da consulta.
- Todos os arquivos novos de código têm até 200 linhas; o guardrail também
  cobre os novos módulos de orquestração e domínio.
- Os 92 arquivos existentes monitorados de V1, domínio e orquestração
  permaneceram idênticos por SHA-256. Nenhum código foi movido da V1.

Comandos, na raiz:

```sh
python3 -m unittest discover -s dev/tests -p 'test_central_v2_*.py'
node --experimental-vm-modules --test dev/tests/central_v2_frontend/*.test.mjs
```

## Próxima unidade

AM1-B: resolver as capacidades faltantes para execução identificadas em
`06b_auto_merge_nivel1_plano_e_evidencias.md`, preservando as restrições sobre
V1 e algoritmos. Esta consulta não resolve recuperação parcial, promoção,
jobs de processamento ou exclusão de escrita entre as Centrais.
