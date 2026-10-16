# Manuais de reconstrucao

Este indice encaminha para manuais que descrevem o comportamento atualmente rastreado no codigo. O checkout, dependencias baixadas, pesos de modelos e dados externos precisam ser registrados separadamente para uma reproducao; os snapshots em `docs/historico/` sao evidencias historicas, nao uma garantia do ambiente atual.

O codigo foi auditado no checkout `cef3cd42`. Antes de reconstruir, confirme o commit exato e eventuais diferencas locais.

## Manuais

- [Central V1](central_v1.md): aplicacao legada, operacoes Original/Merged, endpoints, contratos e limites.
- [Central V2](central_v2.md): rotas, jobs, etapas, manifests, consolidacao e restauracao.
- [Componentes compartilhados](componentes_compartilhados.md): imports/consumidores comprovados, algoritmos e regras de equivalencia.
- [Pendencias tecnicas](pendencias_tecnicas.md): quatro lacunas priorizadas com referencias ao codigo.

## Documentacao complementar

- [Matriz de versoes](../arquitetura/limpeza_baloes_v1_v2.md)
- [Mapa de componentes e dependencias](../arquitetura/mapa_componentes_e_dependencias.md)
- [Fluxos e manifests](../arquitetura/04a_mapa_metro_fluxos_manifestos.md)
- [Auditoria de proveniencia](../arquitetura/04b_mapa_metro_auditoria_proveniencia.md)
- [Ambientes virtuais](../arquitetura/01_ambientes_virtuais.md)
- [Baseline de testes e contratos](../arquitetura/02_baseline_testes_e_contratos.md)
- [Indice Central V1](../central_v1/README.md)
- [Indice Central V2](../central_v2/README.md)
- [Pipeline V1](../central_v1/limpeza_baloes/pipeline.md)
- [Fluxo completo V2](../central_v2/limpeza_baloes/fluxo_completo.md)
- [Contratos V2](../central_v2/limpeza_baloes/contratos_e_persistencia.md)
- [Cleaner V2](../central_v2/limpeza_baloes/etapas/cleaner_v2.md)
- [Modulos compartilhados](../arquitetura/modulos_compartilhados_limpeza_baloes.md)
- [Plano de migracao documental](../organizacao_limpeza_baloes.md)

## Regra de uso

Os caminhos e simbolos indicados sao pontos de partida verificaveis, nao uma especificacao independente do codigo. Antes de reconstruir, fixar o commit, ler os writers e validadores atuais, registrar versoes/runtime/perfis/modelos e preservar fixtures autorizadas. As lacunas abaixo nao devem ser preenchidas por inferencia.
