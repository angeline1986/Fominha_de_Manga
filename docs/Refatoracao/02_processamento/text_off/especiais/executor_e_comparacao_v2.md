# Casos Especiais V2 — executor isolado e comparação

Data: 29/09/2026. Continuação do contrato do checkpoint 14.

## Entrega desta unidade

Executor de prévia utilizável por CLI e pelo runner de comparação. Dois
runtimes independentes instalados, staging rastreável, validação de pixels
e relatório visual local. A interface HTTP/página da Central V2 ainda não
foi conectada nesta unidade; o contrato de rotas do checkpoint 14 continua
uma proposta, não uma API disponível. Não existe operação de promoção.

## Organização e independência da V1

Todos os módulos novos ficam em
`central_v2/backend/orchestration/textoff_special/`:

| Módulo | Responsabilidade |
|---|---|
| `catalog.py` | Identidades dos tratamentos e seleção estrita de runtime |
| `inputs.py` | Pertencimento ao manifesto, predecessor, hashes e ROIs finitas |
| `artifacts.py` | JSON atômico, hashes e resolução confinada de artefatos |
| `execution.py` | Snapshot, ciclo de vida e manifesto da proposta |
| `process.py` | Subprocesso, offline, timeout e encerramento dos descendentes |
| `domain.py` | Ligação dos adaptadores de imagem ao Python isolado |
| `provenance.py` | Versões, lock, código, configuração e modelos |
| `verification.py` | Verificação independente de dimensões e máscara |
| `worker.py` | Entrada do processo especializado e diagnóstico de falha |
| `cli.py` | Entrada de terminal para uma prévia |

Nenhum módulo importa `interface_web`, suas rotas ou o promotor V1. O
reuso é exclusivamente do domínio de imagem existente em `processamento/`.
Não foram copiados nem alterados os algoritmos. Nenhuma venv V1 é lançada.

Os adaptadores de domínio ainda não oferecem injeção pública de runtime.
Por isso `domain.py` configura `base.CLEANER_PY` apenas no worker exclusivo,
restaurando-o em `finally`. Essa ligação é proibida fora do prefixo da venv
do tratamento. Não há alteração global no processo do servidor. Testes
confirmam que os subprocessos Cleaner e LaMa recebem o Python da feature,
inclusive verificando restauração após erro.

Os 17 arquivos novos de código, incluindo testes e ferramentas, têm no
máximo 127 linhas após a correção do relatório portátil. O teste arquitetural da V2 também passou.
Algoritmos preexistentes do domínio não foram reorganizados como efeito
colateral desta implementação.

## Ambientes

Dois locks independentes de 86 pacotes, inicialmente iguais à baseline
Merged I, instalados em Python 3.12.7/macOS arm64. `pip check` passou nos
dois. O Legado conserva inicialmente as bibliotecas de autorização no lock
para reduzir variáveis de ambiente, mas não chama essa etapa.

Snapshots em `evidencias/2026-09-29/*_runtime.json`.
Reconstrução e uso em `central_v2/runtime/textoff/especiais/README.md`.

O worker compara as versões instaladas com seu lock antes de processar.
Mantém `preserve-colors.ini` e os modelos externos atuais. Os hashes do
código/configuração e dos modelos identificados ficam no manifesto da
execução. O commit sozinho não descreve mudanças locais; os hashes dos
arquivos complementam essa proveniência.

## Validações automatizadas

- 19 testes focados: entrada obsoleta, vínculo ao predecessor, escape de
  caminhos/symlinks, ROI não finita, falha de worker, resultado inválido,
  seleção de runtime, restauração de bindings e timeout.
- 75 testes Python da V2 dentro do sandbox e 5 testes HTTP fora dele.
- 46 testes de frontend passaram.
- Sintaxe, whitespace e limite de 200 linhas conferidos para os 17 arquivos.

A execução única da suíte geral encontrou interferências do ambiente:
dentro do sandbox os cinco testes HTTP não podiam abrir portas; fora dele,
dois testes de execução detectavam a V1 aberta e eram bloqueados pela
proteção existente. As duas partes passaram separadamente, sem desligar a
V1 ou remover a proteção. Não foi alterada a suíte antiga para ocultar o
estado do ambiente.

## Execução real e comparação

Obra e entradas autorizadas: RIDI / Things that deserve to die, capítulo 3,
quatro páginas nos Níveis I e II. São 16 combinações, registradas em
`reports/experimentos/textoff_especiais_v2/matrix.json`.

As ROIs são as caixas dos sete balões identificados no relatório Nível I,
inspecionadas visualmente nos dois níveis e fixadas no inventário. A
seleção foi feita pelo assistente para este teste; não representa uma nova
seleção automática no produto. Todos os tratamentos recebem as mesmas
coordenadas por página. Nenhum parâmetro visual foi alterado entre casos.

### Resultado final da matriz

16 combinações concluídas em 513,322 s somando suas durações: **5 propostas
válidas e 11 falhas de geração por ausência de componentes**. Os hashes das
oito entradas permaneceram iguais. Todas as cinco propostas tiveram zero
pixels alterados fora da máscara autorizada. Dados versionáveis em
`evidencias/2026-09-29/matriz_resultados.json`.

| Entrada | Transparente | Legado | Pixels alterados pelo Legado |
|---|---|---|---:|
| I / page-156-163 | Sem componentes autorizados | Proposta válida | 348.471 |
| I / page-051-059 | Sem componentes autorizados | Proposta válida | 120.074 |
| I / page-078-083 | Sem componentes autorizados | Proposta válida | 151.571 |
| I / page-179-187 | Sem componentes autorizados | Proposta válida | 398.074 |
| II / page-156-163 | Sem componentes autorizados | Proposta válida | 105.994 |
| II / page-051-059 | Cleaner sem componentes de texto | Sem componentes na ROI | — |
| II / page-078-083 | Cleaner sem componentes de texto | Sem componentes na ROI | — |
| II / page-179-187 | Cleaner sem componentes de texto | Sem componentes na ROI | — |

Esses resultados caracterizam as receitas atuais; não indicam falha de
instalação dos ambientes. A ausência de componentes não demonstra ausência
visual de resíduos. Não substituir uma execução sem proposta pela entrada
e apresentá-la como resultado gerado.

### Observações visuais do assistente

- `page-156-163`, segundo balão: o Legado remove o texto que permanece no
  Nível II atual, tanto partindo do I quanto do II. Entretanto, reconstrói
  detalhes do painel ao fundo, com perda/alteração de linhas e textura.
- `page-078-083`: a remoção pelo Legado deixa diferenças de tonalidade com
  contornos relacionados à máscara. Não há evidência para declarar melhora
  geral sobre o Nível II atual.
- `page-051-059`: texto removido pelo Legado; ainda se observam diferenças
  de textura/tonalidade nas regiões reconstruídas.
- `page-179-187`: os recortes disponíveis permitem comparar a remoção com o
  Nível II atual; contornos e texturas finas requerem revisão do usuário.

Conclusão desta comparação: há ganho de remoção em uma região específica
de `page-156-163`, com custo visual no cenário. Não foi estabelecida uma
configuração universalmente melhor. `visual_review_status` das propostas
continua `pending`, aguardando revisão do usuário.

A tentativa inicial em sandbox falhou ao escrever o log do pcleaner no
cache do usuário. Após autorização para executar fora do sandbox, o smoke
Legado sobre Nível I de `page-156-163` passou: 348.471 pixels alterados,
zero fora da máscara. A repetição na matriz produziu exatamente o mesmo
SHA-256 de imagem e máscara. A tentativa bloqueada foi preservada como
diagnóstico, sem ser contada nas 16 combinações.

Relatório navegável local:
`reports/experimentos/textoff_especiais_v2/review/index.html`.
Cada região mostra as entradas I/II, as quatro combinações e os motivos
das combinações sem proposta. Recortes são ampliáveis e derivados dos
arquivos reais. O relatório não é uma tela da Central nem uma aprovação.

Correção após revisão do usuário: a abertura local exibia imagens quebradas,
embora os PNGs estivessem presentes. O gerador agora incorpora os 23 recortes
como dados PNG no HTML e abre a ampliação em um diálogo da própria página.
O comparativo é um arquivo único de aproximadamente 6,8 MB, sem dependência
de carregamento dos PNGs vizinhos. Os 23 dados incorporados foram decodificados
e validados como imagens; a sintaxe JavaScript do ampliador também foi validada.
Nenhum processamento de imagem foi reexecutado para essa correção.

## Limites e continuidade

O Patch Transparente mantém o gate compartilhado que adia componentes
transparentes. Não contornar esse gate silenciosamente para obter uma
saída. Ausência de componentes é registrada como falha de geração da
proposta, e não como imagem aprovada ou limpeza bem-sucedida.

O Legado pode remover texto que o Nível II manteve, mas também sintetiza
detalhes de cenário dentro da máscara. Zero mudanças fora da máscara não
significa preservação perfeita da arte dentro dela. A avaliação visual é
por região; não promover uma receita para todas as páginas com base num
único resultado favorável.

Para a próxima fatia: conectar seleção de página/ROI, job e comparação à
interface V2 usando o executor validado; apresentar os resultados sem
autorizar promoção. Qualquer mudança no gate ou no algoritmo exige uma
decisão de domínio separada e nova comparação, preservando esta baseline.
