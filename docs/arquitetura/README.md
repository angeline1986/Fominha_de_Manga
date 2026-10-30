# Arquitetura do projeto para Limpeza de Balões

- [Matriz Central V1 × Central V2](limpeza_baloes_v1_v2.md): fronteiras de UI, API, orquestração e domínio.
- [Módulos compartilhados](modulos_compartilhados_limpeza_baloes.md): imports confirmados entre aplicações.
- [Algoritmos especiais compartilhados](algoritmos_especiais_compartilhados.md): parâmetros e limites confirmados nos adapters raiz.
- [Contrato v1 do Consolidado Final](contrato_consolidado_final_v1.md): árvore, manifesto, hashes, histórico e limites de compatibilidade.
- Estrutura operacional: V1 em `interface_web/`, `orquestracao/` e `processamento/`; V2 em `central_v2/frontend/`, `backend/` e `runtime/`.
- Dependências: locks e requisitos são por pacote/runtime. O [manual de reconstrução](../reconstrucao/README.md) registra os ambientes conhecidos e lacunas.
- Manuais por fluxo: [Central V1](../reconstrucao/central_v1.md), [Central V2](../reconstrucao/central_v2.md) e [componentes compartilhados](../reconstrucao/componentes_compartilhados.md).

Não há uma única lista de dependências que represente toda a aplicação: Cleaner V2, Sommelier e workers especiais têm requisitos/ambientes próprios. As capturas em `docs/Refatoracao/99_evidencias_transversais/environment_baseline/2026-09-25/` são snapshots históricos.
