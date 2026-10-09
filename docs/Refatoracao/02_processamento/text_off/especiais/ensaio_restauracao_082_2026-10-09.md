# Ensaio isolado de restauração — `Gazing at you`, capítulo 1, página 082

Data: 2026-10-09. **Nenhuma restauração operacional foi feita.** O ensaio usou uma cópia em `/private/tmp/fominha-restore-082-5sh9b16w`. Não houve reexecução de Artístico, Degradê ou Suave, nem alteração de algoritmos, ROIs ou parâmetros.

## Origem e bloqueio encontrado

O histórico de `07_CONSOLIDADO_FINAL/1/json/final-manifest.json` registra a última imagem automática anterior aos especiais como `AUTO_CLEANER_TRANSPARENCIA`, SHA-256 `040a5126353036557cbba057693cda66958b0b4820c05ca29d48ff9a4ff9d539`. O primeiro Suave (`d4a022bb47e8413abd11785f65c188cf`) recebeu esse SHA e produziu `225b6370b11e5c652d3d128f1873ff687988c4636ac905efb1584088e8c66698`; o segundo (`2759006bbd5a41aca2976b1a78df5984`) recebeu esse resultado e produziu o estado atual, SHA `23fa46ae4ea31997eb493cffd08def1744077b8ad4ca84c7dd77b31197611f05`.

O snapshot exato pré-especial existe em `06_PINCEL/SUAVE/1/input/d4a022bb47e8413abd11785f65c188cf/page-082-086.png`. Seu SHA confere com o registro `input_artifact` do run arquivado em `06_PINCEL/SUAVE/1/json/suave-manifest.json` (SHA do manifest `e68fc38df3df53e8ca2735e5c2b03ed6ae15ffd24bc01b1e977e42678554846c`) e com o histórico final. O manifest do run também liga a saída ao SHA `225b6370…`. Esse é um snapshot de entrada de tratamento, preservado pelo sistema, e não uma inferência a partir da aparência da página.

**Bloqueio da restauração operacional atual:** `special_page_restore._context()` chama `special_styled_recovery._resolve_source()` para procurar a entrada automática no Nível II vigente. `TO_MERGED_NIVEL_II/1/clean/page-082-086_clean.png` tem SHA `c0bc08119514c138937b0ae48620858e4931ebf9723fefe3a9c71372de4f9007`, diferente do SHA histórico `040a5126…`; `inspect()` retorna `ValueError: Hash do artefato de entrada histórica Artístico divergente.` O manifest Nível II vigente não autentica o antigo snapshot. O endpoint e a interface de restauração, sem adaptação, estão portanto bloqueados para esta página.

## Método do ensaio

Foram copiados para o diretório temporário o capítulo inteiro do Consolidado Final (18 páginas), o manifest Especial e o Check do capítulo, além de todo o estágio Suave do capítulo, incluindo entradas, máscaras de autoria, resultados e histórico. Nenhum caminho da cópia é symlink. Um adaptador **somente em memória, no processo do ensaio**, substituiu exclusivamente `_resolve_source` por uma seleção do snapshot histórico. Ele exige coincidência de página, run, origem, hashes de entrada e saída, referência do artefato no manifest do Suave e conteúdo do arquivo. A implementação existente de `inspect()`, `images()`, `restore()`, confirmação, SHA, backup e publicação transacional permaneceu em uso. Nenhum arquivo de código do repositório foi alterado para viabilizar o ensaio.

| Item | SHA-256 |
|---|---|
| Página atual antes do ensaio e no backup | `23fa46ae4ea31997eb493cffd08def1744077b8ad4ca84c7dd77b31197611f05` |
| Snapshot pré-especial e página restaurada na cópia | `040a5126353036557cbba057693cda66958b0b4820c05ca29d48ff9a4ff9d539` |
| Manifest Final antes do ensaio | `a6e5bc0dc459ca5825f78a662f8cfc49bc717cdb57a709755cd6602235d71975` |
| Manifest Especial antes do ensaio | `289dfa4485b01f75d3b074bc402d03ca93615861b7cb8d30931812e9ac62b6dd` |
| Check antes e depois | `8e570d1b2629c1c57579a40ae473b6182f3083812bf4d588bef48f9b45ea0ed7` |
| Manifest Especial após restauração na cópia | `319e7081dd554b84eab48bba12c502367483bc0c74693cdfce5116a85fca6ea6` |

As duas imagens têm 940 × 7306 pixels. Diferem em 108.126 pixels, na caixa `[230,3534,764,3737)`; 41.419 pixels diferem dentro da ROI Artística aprovada `[288,3587,427,97]`. Esses números localizam a alteração, mas não substituem a revisão visual.

## Integridade, estados e recuperação

- O backup transacional está em `SPECIAL_PAGE_RESTORE_BACKUPS/1/7fffe59099db44938c5c2a175e4b31df`, **dentro da cópia**. `special_page_restore_backup.verify()` validou a página anterior, os manifests anteriores e os SHAs da proposta. O teste focado de rollback e os demais testes do módulo passaram: 8 testes em `dev.tests.test_special_page_restore`.
- A restauração alterou, entre os arquivos preexistentes da cópia, somente `page-082-086.png`, `final-manifest.json` e `special-treatments-manifest.json`. As outras 17 páginas do capítulo preservaram seus SHAs; seus registros no manifest Final permaneceram iguais. As ocorrências das outras páginas no manifest Especial permaneceram iguais. Nenhum outro capítulo foi copiado para o ensaio.
- O Check preservou exatamente seus bytes e a ocorrência manual `b1e110cf-6ec7-4711-a931-981ecf898fef`, tipo `balao_estilizado`, ROI `[288,3587,427,97]`. O manifest Especial preservou a mesma ocorrência e seus dados; seu status passou de `failed` a `pending`, sem `error` nem `result` antigos. O histórico Final anterior foi preservado e recebeu um registro de restauração; `page_restoration_history` aponta para o backup.
- Os dois runs Suave anteriores permanecem rastreáveis no histórico Final e no manifest do Suave. **Eles não foram marcados como pendentes no manifest Especial ativo**, pois esse manifest e o Check atuais contêm apenas a ocorrência Artística da página. A restauração remove os pixels Suave da imagem final, mas o contador `affected_occurrences` retorna somente 1. Esse descompasso precisa ser resolvido antes de considerar a restauração operacional concluída.
- Os seis arquivos operacionais usados como fontes tiveram os mesmos SHAs antes e depois do ensaio. A execução de escrita recebeu apenas o caminho da cópia em `/private/tmp`; a cópia não contém symlinks para a obra operacional. Não houve commit ou push.

## Revisão visual

Abrir [comparador interativo](</private/tmp/fominha-restore-082-5sh9b16w/visual/comparador.html>). Ele usa cópias byte a byte das imagens reais atual e restaurada, lado a lado, com zoom e rolagem sincronizados e atalhos para a página completa e o balão rosado. As imagens também estão em [atual](</private/tmp/fominha-restore-082-5sh9b16w/visual/current.png>) e [restaurada](</private/tmp/fominha-restore-082-5sh9b16w/visual/restored.png>). [Evidências em JSON](</private/tmp/fominha-restore-082-5sh9b16w/evidence.json>) registram proposta, hashes, arquivos alterados e estados. `node --check` passou para o script do comparador; a inspeção visual humana na Central V2 ainda é necessária.

## Conclusão e pendências antes da restauração real

O ensaio comprova que o mecanismo transacional restaura a página para o snapshot histórico autenticado e preserva backup, Check, ROIs, histórico e outras páginas **quando a origem histórica é entregue ao resolvedor**. O fluxo operacional atual bloqueia a própria proposta porque procura o SHA antigo no Nível II vigente. Além disso, descartar os dois Suave não cria duas ocorrências pendentes no manifest atual. A imagem de revisão do Check vigente usa o Nível II de SHA `c0bc0811…`, enquanto o estado restaurado é `040a5126…`; portanto, o ensaio não comprova que uma nova execução Artística possa ser promovida sem novo conflito de linhagem.

Revisar visualmente o comparador e definir a política de proveniência e de estados históricos antes de solicitar uma autorização operacional específica. **Não aplicar esta restauração na obra operacional com o fluxo atual.**
