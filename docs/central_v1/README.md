# Central V1

**Escopo:** aplicação legada de processamento web e orquestração raiz. Não confundir `processamento/limpeza_baloes/cleaner_v2` com a Central V2: o nome do motor indica sua versão interna, não a versão da interface.

## Componentes

- UI e servidor: [`interface_web/`](../../interface_web/), com dispatcher principal em [`processing_web.py`](../../interface_web/processing_web.py).
- Menu e despacho de ações tradicionais: [`orquestracao/menu.py`](../../orquestracao/menu.py).
- Domínio de limpeza: [`processamento/limpeza_baloes/`](../../processamento/limpeza_baloes/).
- Integração Merged legada: [`orquestracao/textoff/merged.py`](../../orquestracao/textoff/merged.py).
- Contratos detalhados: [visão geral](limpeza_baloes/visao_geral.md) e [pipeline](limpeza_baloes/pipeline.md).
- Algoritmos chamados pelas duas versões: [módulos compartilhados](../arquitetura/modulos_compartilhados_limpeza_baloes.md) e [tratamentos especiais](../arquitetura/algoritmos_especiais_compartilhados.md).
- [Arquitetura V1](arquitetura.md): servidor, endpoints e fronteiras da aplicação legada.

## Fonte de verdade e limites

O código V1 contém integração HTTP, jobs e partes de autoridade junto ao handler; módulos de domínio também são chamados diretamente. Documentos antigos em `docs/OLD/` e planos em `docs/Refatoracao/` são contexto, não descrição normativa.

V1 e V2 importam alguns algoritmos comuns. A V2 mantém seu próprio backend e workflow. Consulte [matriz de versões](../arquitetura/limpeza_baloes_v1_v2.md) e [módulos compartilhados](../arquitetura/modulos_compartilhados_limpeza_baloes.md).

Para reconstrução orientada pelo fluxo e pelos contratos atualmente rastreados, consulte o [manual Central V1](../reconstrucao/central_v1.md) e o [manual de componentes compartilhados](../reconstrucao/componentes_compartilhados.md).

## Escopo não verificado

O manual documenta as rotas TextOff localizadas e o contrato do Cleaner; ainda não inventaria todos os payloads de `/api/action`, estados de job e schemas de cada tratamento especial. Esses itens devem ser rastreados nos respectivos escritores antes de reconstruir esses subfluxos.
