# Execução inicial Artística — entrada do Check e conflito na página 082

Data: 2026-10-09. Obra `comix/Gazing at you`, capítulo `1`, página
`page-082-086.png`, ocorrência `b1e110cf-6ec7-4711-a931-981ecf898fef`,
ROI natural `[288,3587,427,97]`. Nenhuma imagem ou manifest operacional foi
modificado neste ensaio; não houve commit nem push.

## Causa raiz e seleção corrigida

A execução inicial usava `special_degrade_input.selected_input`, que retornava
sempre `CONSOLIDADO_FINAL`. O arquivo tinha SHA
`23fa46ae4ea31997eb493cffd08def1744077b8ad4ca84c7dd77b31197611f05`
e origem `PINCEL_SUAVE`; a máscara Cleaner daquela tentativa tinha zero pixels
na ROI. A revisão do Check, por sua vez, seleciona a imagem do
`TO_MERGED_NIVEL_II` via `TO_MERGED_CONSOLIDADO`, SHA
`c0bc08119514c138937b0ae48620858e4931ebf9723fefe3a9c71372de4f9007`.
Ambas medem 940 × 7306 pixels; os 41.419 pixels da ROI diferem.

O novo `special_styled_source.detection_input` resolve a seleção efetiva do
Check no manifest `TO_MERGED_CONSOLIDADO`, valida provider, obra, capítulo,
página, identidade, tipo, ROI, hashes do Check e dos manifests, hash do artefato
de estágio e dimensões naturais. O ensaio real de leitura resolveu
`TO_MERGED_NIVEL_II/1/clean/page-082-086_clean.png`, com o SHA acima e
manifest intermediário SHA
`427961c0a31f1cc92e60a09f4eb9779de20ea93ad91b250fc4d55ed0cbbb4760`.
O resolvedor escolhe Nível I ou II conforme a seleção, sem fixar Nível II.

O Check atual registra hashes de relatórios de sugestão, mas não salva um hash
por imagem de revisão no instante da aprovação. A implementação autentica a
seleção e a imagem atuais do estágio, além de verificar que o Check aprovado
continua o mesmo; ela **não prova criptograficamente** que os pixels eram
idênticos no instante histórico da aprovação. Esse vínculo exige evolução
separada do manifest do Check para decisões futuras.

## Ensaio isolado

Entrada e modelos foram copiados para
`/private/tmp/fominha-artistico-082.gFYtx8`. A execução do worker ficou em
`staging/040b9a44818c451db7572df63a665816` sob esse diretório. O snapshot
de entrada tem SHA `c0bc0811...9007`; o resultado técnico
`treatment/01_local_heal.png` tem SHA
`dcebd6928a3647b831b41137b13e75fd38b0bf76e851edb874b65e1fbf558883`.
O manifest da prévia registra `execution_status=succeeded`, algoritmo
`textoff_special_roi_styled_v1`, uma seleção, e `promotion_allowed=false`.

| Evidência | Resultado |
|---|---:|
| Componentes na máscara Cleaner | 4 |
| Componentes autorizados pelo classificador | 3 |
| Componentes autorizados que intersectam a ROI | 1 |
| Componente selecionado | bbox `[275,3581,442,112]`, área 49.504 px |
| Máscara autorizada após filtro por ROI | 49.504 px |
| Pixels efetivamente alterados no resultado técnico | 46.806 |
| Pixels alterados fora da máscara autorizada | 0 |
| Pixels alterados dentro da ROI retangular | 39.803 |
| Pixels alterados fora da ROI, dentro do componente autorizado | 7.003 |

SHAs dos artefatos principais: máscara Cleaner
`a4d3c40115ea11e7fadad99a4aa5da8d8d862a4f324cfff258ba19d0d463d0a1`;
máscara autorizada efetiva
`ec5adfbf1bb88b1059e5da6d94c9d80ec65cf13b85df756818ef4c28c67e0475`;
máscara efetiva de escrita
`d105ab20030aa06cf17c712f3c4d3ae618dfcebd5d51a1cfeb1d9e0e78ff1c15`.
Logs, `roi_report.json`, máscaras, snapshot e resultado bruto permanecem na
pasta temporária do run. As duas tentativas preparatórias que falharam por
restrições de cache/modelos também permanecem nesse staging.

## Conflito com Suave e publicação

As máscaras de autoria dos runs Suave `d4a022bb...` e `2759006b...` foram
verificadas por SHA. A primeira cobre todos os 49.504 pixels do componente
autorizado; a segunda cobre 24.124 pixels desse componente. A interseção da
**escrita efetiva** Artística com cada máscara é, respectivamente, 46.806 e
23.945 pixels. A união tem **46.806 pixels conflitantes**, sem contagem dupla.

`initial_composition.json` e as máscaras de escrita, de tratamentos posteriores
e de conflito estão no mesmo staging. A composição retornou
`Composição Artístico bloqueada: 46806 pixels em conflito.` e não produziu
`candidate.png`. Mesmo sem essa interseção, a linhagem do Consolidado Final
atual não chega ao SHA da imagem de revisão vigente: seu histórico de Nível II
registra `040a5126...`, distinto de `c0bc0811...`. Portanto não há base para
publicar por simples substituição de pixels.

A página operacional continua com SHA `23fa46ae...7611f05`; o manifest final
continua com SHA `a6e5bc0d...a21ed75`, o Check com
`8e570d1b...ea0ed7`, e o manifest Especial com
`289dfa44...2e6dd`. O estágio `PINCEL_ARTISTICO/1` segue ausente.

## Implementação e validação

Arquivos novos: `special_styled_source.py`,
`special_styled_initial_composition.py`,
`special_styled_initial_publication.py`,
`dev/tests/test_special_styled_source.py` e
`dev/tests/test_special_styled_initial_composition.py`.

Arquivos ajustados para esta correção: `special_styled_execution.py`,
`special_styled_transaction.py`, `special_treatments_query.py`,
`routes/special_treatments.py`, `frontend/_app/api/textoff.js`,
`frontend/texto_off/especiais/artistico_preview.js` e os testes focados de
Artístico e da tabela compartilhada. Outros arquivos já modificados no
workspace antes desta tarefa foram preservados.

A execução inicial agora separa entrada de detecção e base final, registra o
resultado técnico em staging e só monta uma composição após validação da
linhagem e da interseção das máscaras. A promoção de Artístico, Final e
manifest Especial usa a transação recuperável existente, com SHA verificado
imediatamente antes da publicação. A reexecução individual segue seu caminho
histórico próprio; nenhum algoritmo protegido foi alterado.

Testes focados: 31 testes Python de entrada, preview, composição, execução,
rotas, Degradê e Suave; 22 testes Python de autoria, reexecução e transação;
12 testes Python de revisão/rotas Degradê e Suave; 13 testes frontend de
Artístico, Degradê e Suave. Todos passaram. `git diff --check` passou.

## Decisão operacional

O caso está no cenário **entrada correta + resultado técnico válido + conflito
verificável**. Não restaurar nem publicar a página. As alternativas são:

1. Planejar e validar uma reconstrução ordenada das duas execuções Suave após
   Artístico, em cópia isolada, preservando autoria e verificando qualidade.
2. Se essa reconstrução não for segura, avaliar a prévia de Restaurar página e
   explicitar quais tratamentos seriam descartados ou voltariam a pendente.

Nenhuma dessas alternativas foi executada. A qualidade visual do resultado
técnico ainda exige revisão humana; a contagem de pixels não a aprova.
