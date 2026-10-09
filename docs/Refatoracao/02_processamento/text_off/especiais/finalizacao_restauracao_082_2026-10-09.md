# Finalização da restauração segura — página 082

Data: 2026-10-09. Obra `comix/Gazing at you`, capítulo `1`, `page-082-086.png`.

## Resultado

A restauração foi executada pelo fluxo real da Central V2 **somente na cópia independente** `/private/tmp/fominha-restore-082-real-ndqb8n13`. Não houve adaptação em memória, execução de tratamento, escrita na obra operacional, commit ou push.

| Evidência | Valor |
|---|---|
| Página atual preservada no backup | SHA-256 `23fa46ae4ea31997eb493cffd08def1744077b8ad4ca84c7dd77b31197611f05` |
| Página restaurada na cópia | SHA-256 `040a5126353036557cbba057693cda66958b0b4820c05ca29d48ff9a4ff9d539` |
| Imagem usada pelo Check | SHA-256 `c0bc08119514c138937b0ae48620858e4931ebf9723fefe3a9c71372de4f9007` |
| Check preservado | SHA-256 `8e570d1b2629c1c57579a40ae473b6182f3083812bf4d588bef48f9b45ea0ed7` |
| Backup transacional na cópia | `SPECIAL_PAGE_RESTORE_BACKUPS/1/e21beeeddd884413a9edf5d2f679bff6` |

## Causa e resolução dos três bloqueios

### 1. Origem histórica

O resolvedor anterior (`special_styled_recovery._resolve_source`) só encontrava a imagem automática pelo artefato atualmente listado no Nível II. Esse estágio tem SHA `c0bc0811…`, embora o primeiro Suave tenha registrado como entrada o SHA `040a5126…`. O resolvedor não consultava o snapshot imutável salvo pelo próprio run.

O novo resolvedor tenta primeiro a origem de estágio já suportada. Se o hash atual não comprovar a entrada histórica, procura o snapshot do **primeiro tratamento especial**. Exige manifesto com schema, obra, capítulo, algoritmo e tratamento compatíveis; página e run únicos; mesma origem, SHA de entrada, SHA de saída e SHA do manifesto de entrada registrados no histórico Final; artefato no caminho `input/<run>/<página>`; hash do snapshot; e saída histórica presente ou arquivada com hash correto. Caminhos absolutos, travessia de diretório, registros ausentes ou ambiguidades bloqueiam a restauração.

No ensaio, o snapshot foi obtido de `PINCEL_SUAVE/1/input/d4a022bb47e8413abd11785f65c188cf/page-082-086.png`, vinculado ao manifest Suave e ao primeiro elo especial do histórico Final.

### 2. Efeitos históricos Suave

O manifest Especial é uma projeção das decisões atualmente aprovadas no Check. O Check atual contém apenas a ocorrência manual Artística; por isso, os dois Suave históricos não aparecem como ocorrências ativas. A restauração anterior atualizava apenas os registros ativos e não marcava os efeitos históricos descartados.

A restauração agora grava os dois runs em `invalidated_runs`, tanto no evento de restauração do manifest Final quanto em `page_restoration_history` do manifest Especial. Mantém as identidades, hashes e vínculos de entrada/saída. Não cria ocorrências Suave. A ocorrência Artística `b1e110cf-6ec7-4711-a931-981ecf898fef` permaneceu a única ocorrência ativa desta página e voltou de `failed` para `pending`. A comparação histórica do Suave retorna `effect_active: false` e o ID da restauração que invalidou o run.

Runs invalidados:

- `d4a022bb47e8413abd11785f65c188cf`: `040a5126…` → `225b6370…`.
- `2759006bbd5a41aca2976b1a78df5984`: `225b6370…` → `23fa46ae…`.

Os artefatos e máscaras de autoria desses runs permaneceram no estágio Suave copiado, sem alterações.

### 3. Compatibilidade com o Check

A comparação leu a imagem de revisão pela seleção vigente do Check, verificou manifest, origem, SHA e dimensões naturais, e comparou os pixels nas coordenadas aprovadas.

| Região | Pixels diferentes entre snapshot restaurado e imagem do Check |
|---|---:|
| ROI aprovada `[288,3587,427,97]` | **0** de 41.419 — coincide pixel a pixel |
| Fora da ROI | **23.933** |

A inspeção visual dos recortes confirma o texto `…COMING THIS WAY RIGHT NOW?` visível tanto na página restaurada quanto na imagem do Check dentro da ROI aprovada. A página inteira, porém, não é equivalente. Como a autorização efetiva do Artístico pode alcançar pixels fora do retângulo da ROI, compatibilidade somente dentro da ROI não prova que a composição preserve os pixels corretos. A validação de Artístico agora bloqueia a página antes do worker enquanto essa diferença existir. A lista de trabalho apresenta `execution_blocked` e a razão; o seletor da ocorrência fica desabilitado. O detalhe da proposta de restauração também informa as contagens.

## Validação na cópia

- A função real `inspect()` recuperou a origem autenticada e reportou dois runs históricos para invalidação.
- `images()` serviu os bytes atuais e restaurados, conferidos contra os hashes da proposta.
- `restore(..., confirmed=True)` publicou somente na cópia; o hash da página restaurada é o esperado.
- `special_page_restore_backup.verify()` confirmou o backup e os manifests anteriores.
- O Check permaneceu byte a byte igual; a ROI e sua identidade permaneceram iguais.
- O histórico Final recebeu um evento de restauração com os dois runs invalidados. O manifest Especial manteve a única ocorrência Artística da página pendente e removeu o erro antigo.
- A leitura da comparação Suave marcou o último resultado como histórico, `effect_active: false`.
- A consulta da worklist mostrou a ocorrência Artística pendente, `execution_blocked: true` e preview da imagem usada no Check.
- A elegibilidade de Artístico falhou antes de iniciar o worker, com a razão de divergência fora da ROI.
- As outras 17 páginas mantiveram os hashes e registros. Os manifests Check e Suave e os artefatos de autoria permaneceram iguais na cópia.
- Inventário SHA-256 de 251 arquivos operacionais antes e depois: `e1e11fce81ff4f29fd88882f726bea9ae91ada570755c2d353eb122f61e373ba` em ambos os momentos.

## Comparação visual

Abrir o [comparador interativo atualizado](</private/tmp/fominha-restore-082-real-fn8zuoq9/visual/comparador.html>). Ele apresenta a página atual, o snapshot restaurado e a imagem do Check lado a lado. Zoom e rolagem são sincronizados; o contorno vermelho marca a ROI aprovada. Os três PNGs foram copiados sem transformação e têm hashes registrados em [hashes.json](</private/tmp/fominha-restore-082-real-fn8zuoq9/visual/hashes.json>). O registro completo está em [evidence.json](</private/tmp/fominha-restore-082-real-fn8zuoq9/evidence.json>).

A inspeção deve considerar a página inteira e o contexto do balão. A ROI coincide; a diferença fora dela é a razão objetiva para não liberar outra execução Artística.

## Arquivos alterados

- `special_page_restore.py`: usa a origem histórica autenticada, fixa os dados de compatibilidade/invalidação na proposta e os revalida antes da publicação.
- `special_page_restore_source.py` (novo): verifica snapshots associados a runs especiais anteriores.
- `special_page_restore_prepare.py` (novo): preserva e registra os efeitos invalidados nos históricos Final e Especial.
- `special_page_restore_check.py` (novo): compara a restauração com a imagem e a ROI do Check e fornece o bloqueio preventivo.
- `special_styled_input.py`: impede iniciar Artístico incompatível em página restaurada.
- `special_treatments_query.py`: mostra bloqueio e motivo na worklist.
- `special_smooth_review.py`: identifica saídas históricas cujos efeitos foram invalidados.
- `page_restore.js`: mostra número de runs invalidados, comparação com Check e motivo do bloqueio.
- `dev/tests/test_special_page_restore.py`, `dev/tests/test_special_page_restore_source.py` (novo) e `dev/tests/central_v2_frontend/special_styled_table.test.mjs`: cobrem os estados e as validações alterados.
- Este relatório.

Nenhum algoritmo protegido foi alterado.

## Testes

- `python3 -m unittest dev.tests.test_special_page_restore dev.tests.test_special_page_restore_source` — 11 testes aprovados.
- `python3 -m unittest dev.tests.test_special_smooth_review dev.tests.test_special_smooth_execution` — 7 testes aprovados.
- `node --experimental-vm-modules --test dev/tests/central_v2_frontend/special_styled_table.test.mjs` — 7 testes aprovados.
- `node --check` do JavaScript do comparador — aprovado.
- `git diff --check` — aprovado.
- Ensaio integrado na cópia independente — todas as verificações acima de integridade e bloqueio aprovadas; nenhum worker de tratamento foi iniciado.

## Situação final

Na cópia, a página está restaurada ao SHA `040a5126…`, as ROIs estão preservadas, os dois efeitos Suave estão registrados como invalidados e a ocorrência Artística está pendente. **Artístico segue bloqueado até que a diferença entre a imagem restaurada e a imagem de revisão seja resolvida e aprovada.**

A página operacional continua no SHA `23fa46ae…`; nenhuma alteração operacional foi publicada. A restauração real aguarda aprovação explícita.
