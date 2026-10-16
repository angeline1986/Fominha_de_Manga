# Módulos compartilhados pela Limpeza de Balões

**Escopo:** módulos de domínio importados pela Central V1 e/ou V2.\
**Estado:** inventário inicial confirmado por imports no código; dependências indiretas continuam sendo aprofundadas.

## Responsabilidade e consumidores verificados

| Módulo | Função observada | Consumidores confirmados |
|---|---|---|
| `processamento/limpeza_baloes/cleaner_v2/integration.py` | integração do lote Cleaner, execução do Nível II, validação e publicação de saída de capítulo | `orquestracao/textoff/merged.py`, `interface_web/processing_web.py`, `central_v2/backend/orchestration/textoff_merged/cleaner.py` |
| `cleaner_v2/main.py`, `launcher.py` | invocação do processo Panel Cleaner, argumentos offline/perfil/progresso/timeout | integração acima e diagnósticos V1 |
| `cleaner_v2/balloon_authorization.py` | autorização/adiamento de componentes da máscara em relação a balões | Cleaner V2, adaptadores especiais V1 e `central_v2/.../level1_worker.py` |
| `cleaner_v2/transparency_classifier.py` | medidas e gates de classificação/proteção de transparência | autorização compartilhada |
| `cleaner_v2/level2.py` | refinamento de máscara e processamento LaMa local | integração do Cleaner; também importado em correção V1 |
| `textoff_special_*_roi.py` e `textoff_special_approval.py` | adaptação das seleções de região e aprovação de resultados especiais | V1 diretamente; `central_v2/backend/orchestration/textoff_special/domain.py` carrega adaptadores dinamicamente |
| `patch_degrade_experimento.py`, `patch_balao_transparente_experimento.py`, `patch_balao_estilizado_experimento.py` | implementações de base usadas pelos adaptadores especiais e fluxos experimentais | V1, e adaptação sob backend V2 |
| `gradiente_suave/gradiente_suave.py` | reconstrução de gradiente suave | import dinâmico por `textoff_special_web.py`; consumidor V2 exato deve ser confirmado antes de classificar o algoritmo como compartilhado |
| `bubble_cleaner.py` | detector/limpador auxiliar de balões, API `detect_regions`, `process_image` | `bubble_cleaner_flow.py`, balanceamento e diagnóstico V1; consumidor ativo V2 não encontrado na busca direta |

## Implicações para manutenção

1. Interface, API, estado de job, projeção de tabela e persistência não se tornam compartilhados só por usarem o mesmo motor.
2. Alterar um destes módulos compartilhados pode mudar ambas as versões e também tarefas de diagnóstico/balanceamento. O dono e o contrato de cada chamador precisam ser lidos antes de alterar comportamento.
3. As rotas de V2 devem permanecer independentes da V1; compartilhar algoritmo não autoriza importar `interface_web` ou delegar o workflow V2 à V1.
4. Os arquivos `*.before_*`, `*.bak`, experimentos e diretórios `dev/experiments/` são evidências/fontes históricas ou experimentais, não são automaticamente implementações oficiais.

## Dependências e parâmetros ainda em inventário

Defaults e versões estão distribuídos entre `requirements.txt`, `requirements-locks/`, perfis INI, código e runtime isolado. Os valores que foram confirmados para Cleaner V2 estão em [Cleaner V2](../central_v2/limpeza_baloes/etapas/cleaner_v2.md); os demais algoritmos devem receber páginas próprias antes de se declarar a matriz completa.
