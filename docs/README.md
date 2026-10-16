# Documentação técnica

Este índice separa a aplicação legada (Central V1), a Central V2 e os módulos de domínio que ambas ainda compartilham. A implementação no código é a fonte de verdade; notas datadas e evidências históricas servem para explicar decisões e resultados, mas não substituem a leitura do código atual.

## Limpeza de Balões

- [Arquitetura e limites de versão](arquitetura/limpeza_baloes_v1_v2.md)
- [Central V1](central_v1/README.md)
- [Central V2](central_v2/README.md)
- [Módulos compartilhados](arquitetura/modulos_compartilhados_limpeza_baloes.md)
- [Reconstrução e equivalência](reconstrucao/README.md)
- [Pendências técnicas da reconstrução](reconstrucao/pendencias_tecnicas.md)
- [Inventário e plano de migração documental](organizacao_limpeza_baloes.md)

## Outras áreas

O conteúdo não relacionado à Limpeza de Balões permanece no índice geral do projeto ([README da raiz](../README.md)) e nas áreas existentes de `docs/Refatoracao/`. Os itens do backlog da Central V2 e evidências históricas permanecem preservados até a revisão do plano de migração.

## Convenções

- **V1** significa a Central legada em `interface_web/` e sua orquestração em `orquestracao/`.
- **V2** significa o aplicativo em `central_v2/`.
- **Compartilhado** indica importação explícita pelos dois caminhos ou por componentes de domínio; não significa que as interfaces ou as orquestrações sejam iguais.
- Um item marcado **não verificado** é uma lacuna, não uma afirmação sobre o comportamento.
