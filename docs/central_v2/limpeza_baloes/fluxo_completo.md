# Fluxo completo de Limpeza de Balões — Central V2

## Contexto arquitetural

A V2 é uma aplicação própria: frontend em `central_v2/frontend`, transporte/handlers em `central_v2/backend/routes` e composição de serviços em `central_v2/backend/orchestration`. Runtime especializado fica separado quando a execução o requer. Alguns motores e adaptadores continuam no pacote raiz `processamento/limpeza_baloes`; ver [módulos compartilhados](../../arquitetura/modulos_compartilhados_limpeza_baloes.md).

## Sequência e dependências

```text
Contexto da obra e capítulo
  → consultar fontes e estado de revisão
  → verificar pré-condições/manifests do estágio
  → executar ou revisar etapa elegível
  → validar artifacts, fontes e integridade
  → publicar o resultado/manifest da etapa
  → consolidar referências válidas
  → disponibilizar comparação, correção ou restauração explícita
```

Esse é um mapa de dependências em alto nível, não uma única transação cobrindo toda a Central. Cada ação tem rota e writer próprios.

## Etapas atuais localizadas

1. **Consulta/estágios:** `routes/textoff_merged.py` despacha consulta e execução para níveis; `orchestration/textoff_merged/query.py`, `overview.py`, `stages.py` leem a situação publicada.
2. **Nível I:** `level1_cleaner.py`, `level1_worker.py` e `cleaner.py` adaptam `processamento/limpeza_baloes/cleaner_v2`. O worker registra autorização de balões; integração do Cleaner usa ambiente e perfil configurados.
3. **Nível II:** `level2.py`/`level2_process.py` validam fontes e coordenam o motor; `cleaner_v2/level2.py` contém o processamento de refinamento.
4. **Consolidação:** `consolidated.py` seleciona saídas válidas por página, confere manifests/hashes e publica o manifesto do capítulo consolidado.
5. **Sommelier:** runtime Node separado analisa/cataloga balões e backend V2 serve consulta, execução, revisão e recortes. É etapa V2, não comportamento V1 confirmado.
6. **Check e Sólidos:** módulos de checagem/extração e rotas próprias. Seu critério algorítmico completo precisa de documentos específicos.
7. **Especiais:** domínio V2 resolve tratamentos, executa worker e grava artefatos/revisão próprios. Adaptadores podem importar algoritmos compartilhados.
8. **Finalização/restauração:** manifest final autocontido e operação explícita de restauração têm validação própria.

## Falhas e bloqueios

Os módulos da V2 verificam se a etapa anterior e seus artefatos continuam válidos. `consolidated.py` compara algoritmo, manifests precursores, listas de fontes e hashes dos outputs. Os domínios de restauração criam proposta vinculada aos hashes atuais e validam novamente imediatamente antes de promover.

Não foi comprovado que todas as rotas/etapas usam o mesmo sistema de job ou o mesmo modelo de falha. Consultar o handler específico antes de reconstruir uma transição.

## Entradas e saídas

Os pedidos carregam contexto selecionado (provedor/obra/capítulo), identificadores da etapa e opções específicas. Para imagens, backend valida caminho/identificador e resolve artefato a partir da fonte conhecida. A forma exata de payload por endpoint está nas funções `response`/`execute_*_response` das rotas; não há schema global único.

Os resultados são organizados por etapa sob `FLUXO_SECUNDARIO/04_TEXTO_OFF/`, com diretórios de imagem, máscaras e JSON. O manifesto é parte do contrato: consumidores V2 devem resolver arquivos nele declarados em vez de confiar em caminhos arbitrários do cliente.

## Invariantes a preservar numa reconstrução

- Separar consulta, processamento e promoção quando são ações distintas.
- Revalidar fonte e manifesto no momento de publicação.
- Vincular artefatos à fonte por hashes e referências relativas onde o schema atual o exige.
- Manter status de análise, execução e revisão separados quando a implementação oferece esses estados.
- Tratar uma saída sem mudança visual conforme seu manifesto explícito; zero mudanças não implica etapa executada com sucesso sem evidência.
- Não publicar arquivos parciais como resultado válido.

## Lacunas

- Passo a passo de cada rota e formato de payload por fase.
- Especificação comparada de algoritmos Auto-Cleaner Check e Solids.
- Inventário de parâmetros de Sommelier e de Especiais por algoritmo.
- Matriz abrangente de estados recuperáveis e políticas de retry por etapa.
