# Tratamentos especiais — Central V2

## Implementação e fronteira

Rotas: `textoff_special.py`, `special_treatments.py`, `auto_cleaner_check_special_treatments.py`; domínio: `central_v2/backend/orchestration/textoff_special/` e `textoff_merged/special_*`; UI: `frontend/texto_off/especiais/` e Laboratório. Workers resolvem a fonte aprovada, isolam execução, gravam artefatos, revisão e procedência. Alguns adapters importam módulos legados/compartilhados em `processamento/limpeza_baloes/`.

Tratamentos conhecidos por mapeamento de `final_consolidated.py`: Degradê (`PINCEL_DEGRADE`), Artístico (`PINCEL_ARTISTICO`) e Gradiente (`PINCEL_SUAVE`). Outros tratamentos possuem rotas e status próprios; a matriz fechada de todos os ids/algoritmos não está confirmada aqui.

## Entrada e saída

A execução usa input aprovado no fluxo V2, pode exigir regiões/componentes autorizados, e persiste execução/proposta no estágio do tratamento. Cada artefato é descrito por registro e hash. Aprovação/revisão, reexecução, restauração e promoção são ações distintas. Um tratamento concluído computacionalmente não é automaticamente promovido.

O Consolidado Final só aceita tratamento listado em `PINCEL_STAGES` e registros `processed` ou `no_change`; antes de copiar saída revalida hash da entrada, manifest consolidado e hash do arquivo de saída persistido.

## Parâmetros e compatibilidade

Os algoritmos residem em adapters especializados; os parámetros não devem ser inferidos de telas ou experiências datadas. Os documentos antigos `inventario_e_contrato_v2.md`, `executor_e_comparacao_v2.md`, relatório de recuperação e evidências continuam valiosos como histórico. Confirmar seus valores contra os adapters ativos antes de migrá-los para especificação normativa.

## Lacunas

Falta uma matriz por treatment ID com módulo executor, algoritmo, runtime/lock, ROI e política de autorização, outputs, status, rota, promoção/restauração e parâmetros exatos. Até conclusão, marcar detalhes não confirmados como **não verificados**.
