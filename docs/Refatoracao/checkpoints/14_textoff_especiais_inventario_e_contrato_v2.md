# TextOff — Casos Especiais: inventário e contrato inicial V2

Data: 29/09/2026. Base de código inspecionada: `52af0926`.

Status: levantamento concluído para os dois tratamentos iniciais; contrato
proposto para implementação. Nenhum processamento novo ou promoção executado.

## Escopo inicial

Implementar uma fatia vertical de comparação manual de **Patch Balão
Transparente** e **Balão Transparente — Legado** na Central V2. Preservar a
V1, os algoritmos e seus parâmetros. A primeira entrega produz propostas em
staging, sem escrever em IMG, MERGE ou nos resultados Merged I/II.

Entrada proposta: página do TextOff Merged escolhida pelo usuário, com nível
I ou II explícito e vínculo validado pelo manifesto correspondente. A imagem
escolhida é a entrada efetiva dos dois tratamentos e a referência do Antes.
Não alternar silenciosamente para o MERGE original. O vínculo com o original
é proveniência, não autorização para sobrescrevê-lo. Upload e composição
sobre uma segunda imagem ficam fora desta primeira entrega.

Esta escolha permite comparar remoção de resíduos sobre o resultado atual;
não afirma equivalência com testes históricos executados sobre MERGE original.

## Inventário comportamental da V1

| Aspecto | Patch Balão Transparente | Balão Transparente — Legado |
|---|---|---|
| Identificador | `transparente` | `transparente_legacy` |
| Função | `run_transparent_roi` | `run_transparent_legacy_roi` |
| Algoritmo | `textoff_special_roi_transparent_v1` | `textoff_special_roi_transparent_legacy_v1` |
| Sequência | Cleaner → autorização de balões → dilatação 3×3 → seleção de componentes por ROI → dilatação 9×9 → LaMa | Cleaner → seleção de componentes por ROI → dilatação 3×3 → dilatação 9×9 → LaMa |
| Seleção | Caixas dos componentes da máscara-base intersectam uma ROI | Caixas dos componentes da máscara bruta intersectam uma ROI |
| Contexto LaMa | 120 px | 120 px |
| Saída técnica | `04_lama_text_only_roi.png` | `04_lama_text_only_legacy_roi.png` |
| Composição opcional V1 | Alterações efetivas aplicadas sobre `base_snapshot`, em arquivo separado | Não possui composição sobre segunda base |
| Invariante | Zero pixels alterados fora da máscara autorizada | Zero pixels alterados fora da máscara autorizada |
| Metadados | `proof_phase=True`, `promotion_allowed=False` | Mesmos campos |

As ROIs são coordenadas em pixels, arredondadas e limitadas às dimensões da
imagem pelo domínio. A interseção usa a **caixa delimitadora** do componente:
não exige interseção dos pixels do componente com a ROI. O componente inteiro
é selecionado e as dilatações podem ultrapassar a ROI. Ausência de componentes
e máscara vazia geram erro; não significam limpeza concluída.

Cada tratamento escreve máscaras, overlay, imagem técnica, metadados LaMa e
`roi_report.json`. O atual também escreve o relatório de autorização de balões.

### Divergências que a V2 deve apresentar corretamente

1. A autorização compartilhada atual é
   `textoff_level1_balloon_transparency_gate_v3`: preserva componentes com
   sobreposição a balões classificados como transparentes, com motivo
   `transparent_balloon_deferred`. O Patch Transparente chama essa autorização.
   Portanto, seu nome não garante que ele processe precisamente os componentes
   transparentes pretendidos. O Legado não chama essa etapa. Não mudar o gate
   para viabilizar a migração; registrar a diferença e medir os casos reais.
2. A interface V1 omite a autorização de balões na descrição resumida do Patch
   Transparente. Ambos os tratamentos mostram os mesmos assets
   `transparente_antes.png` e `transparente_depois.png`. Esses exemplos não são
   evidência independente de cada pipeline.
3. A promoção genérica V1 não respeita `promotion_allowed=False` do Transparente;
   o Legado é bloqueado explicitamente. A V2 não reutilizará esse promotor para
   esta entrega e não oferecerá promoção de nenhum dos dois tratamentos.

### Interação existente

A V1 recebe upload ou imagem selecionada da obra, permite múltiplas seleções,
converte coordenadas exibidas para pixels naturais e descarta arrastos menores
que 3 pixels de exibição. A comparação possui zoom sincronizado. A V2 deve
reutilizar seus próprios componentes de viewer/zoom e limpar assinaturas ao
sair da página, sem copiar a interface V1.

## Runtimes e dependências

Hoje `_run_cleaner` e `_run_lama_worker` usam `base.CLEANER_PY`, definido em
`patch_degrade_experimento.py`, apontando para
`processamento/limpeza_baloes/cleaner_v2/.venv/bin/python`. OpenCV/NumPy e a
autorização também executam no processo que chama os adaptadores. O ambiente
Level 3 Regional é referência documental, não o Python chamado pelo LaMa
destes tratamentos.

Destinos separados, ainda não provisionados:

- `central_v2/runtime/textoff/especiais/balao_transparente/.venv`
- `central_v2/runtime/textoff/especiais/balao_transparente_legado/.venv`

Dependências a fechar em locks próprios: `pcleaner`, OpenCV, NumPy, Pillow,
Torch e `simple-lama-inpainting`; o atual requer também `ultralytics` e
`huggingface_hub` para autorização. A lista é de dependências relevantes,
não substitui o inventário transitivo nem um lock reproduzível.

Preservar o perfil `cleaner_v2/preserve-colors.ini`, o código Cleaner e os
modelos externos. Registrar hashes do perfil, modelos e módulos usados. O
lock do Merged I é candidato de comparação por reunir Cleaner e autorização;
não presumir equivalência entre bibliotecas instaladas e qualidade visual.

**Lacuna de integração:** os adaptadores não recebem o interpretador como
parâmetro, e os subprocessos usam um caminho global da V1. Criar venvs não
resolve esse vínculo. A implementação precisa de configuração restrita ao
worker V2: executar cada proposta em processo exclusivo e configurar nesse
processo o interpretador dos subprocessos para o mesmo Python da feature.
Não alterar globais do servidor nem os arquivos V1. Validar por teste que
Cleaner e LaMa não retornam à venv antiga. Não copiar os algoritmos para V2.

## Contrato de aplicação proposto

Fronteira: rota V2 → orquestração da feature → worker isolado → domínio
existente → artefatos da proposta. Arquivos V2 com até 200 linhas e uma
responsabilidade coesa. Nenhum import de `interface_web`.

Rotas propostas, ainda não implementadas:

- `GET /api/textoff/especiais`: tratamentos, disponibilidade dos runtimes e
  páginas elegíveis do contexto selecionado.
- `POST /api/textoff/especiais/preview`: cria job com obra/capítulo/página,
  nível Merged explícito, hash esperado, tratamento e lista de ROIs.
- `GET /api/textoff/especiais/runs/<run_id>`: estado e manifesto da proposta.
- Mídia da proposta por identificador de artefato validado no backend; nunca
  aceitar caminho arbitrário do cliente.

Reutilizar acompanhamento de jobs da V2. Troca de contexto invalida seleções
e respostas pendentes. Desabilitar execução durante o job correspondente.
Executar A e B separadamente sobre o mesmo snapshot e mesmas ROIs para uma
comparação controlada; registrar qualquer diferença de entrada.

Antes de executar: resolver página via manifesto do nível indicado, validar
pertencimento à obra, associação e integridade, dimensões e ROIs finitas;
copiar a entrada para snapshot e confirmar hash. Mudança concorrente da
entrada gera erro de proposta obsoleta, sem sobrescrever artefatos.

Staging proposto:

```text
reports/experimentos/textoff_especiais_v2/<run_id>/
  input/source.png
  treatment/              artefatos nativos do domínio, sem renomeá-los
  logs/worker.log
  manifest.json
```

O manifesto é um registro de experimento, sem autoridade para declarar um
capítulo concluído. Campos mínimos: versão do schema, run/job, tratamento e
algoritmo, timestamps/estado/erro, origem e predecessor, hashes da entrada e
manifesto predecessor, dimensões, ROIs solicitadas e efetivas, parâmetros,
interpretador/versão/lock, commit e hashes do código/configuração/modelos,
duração total e por fase quando instrumentada, artefatos com caminhos
relativos e hashes, pixels alterados e alterações fora da máscara.

Registrar separadamente `execution_status` e `visual_review_status`:
sucesso computacional não equivale a aprovação visual. Inicialmente,
`visual_review_status=pending` e `promotion_allowed=false`. A revisão visual
não habilita promoção automaticamente. Falhas mantêm logs e estado de falha;
não apresentar arquivos parciais como resultado válido.

## Evidências históricas recuperadas

Inventário em
`../evidencias/textoff_especiais/2026-09-29/execucoes_v1.json`:

- 34 execuções: 23 Transparente e 11 Legado.
- 34 arquivos de resultado encontrados e SHA-256 iguais aos manifestos.
- Metadados antigos incompletos são preservados como tal; não inferir ROIs,
  parâmetros ou versão de código ausentes.
- A execução `e98258db7bd94f158c6ff60f6daa70fe` é Legado sobre
  `Things that deserve to die`, capítulo 3, `page-179-187.png` em MERGE,
  com duas ROIs e duração registrada de 41,995 s. É candidata de referência,
  não confirmação de que seja o “melhor resultado” citado na cápsula.

Os hashes confirmam integridade dos resultados históricos, não qualidade
visual nem reprodutibilidade com as dependências e o gate atuais. Não foi
feita revisão visual nesta etapa.

## Validação necessária para a implementação

1. Contratos: origem pertencente ao manifesto, hash obsoleto, ROI inválida,
   runtime ausente, tratamento desconhecido e isolamento de subprocessos.
2. Processamento: dimensões preservadas, máscaras registradas e zero mudanças
   fora da máscara; máscara vazia deve ter mensagem clara.
3. Interface: coordenadas corretas em diferentes zooms, troca de contexto,
   descarte de respostas antigas, limpeza da página e comparação sincronizada.
4. Casos reais: `page-156-163`, `page-051-059`, `page-078-083` e `page-179-187`.
   Fixar obra/capítulo/nível/hash e ROIs antes de comparar A/B. Nome de página
   sozinho não identifica uma entrada. Registrar aparência, resíduos e danos
   à arte, além das métricas de pixels e duração.
5. Executar checks Python/frontend/arquitetura da V2 após implementar. Só
   propor produção depois de resultados reais revisados e contrato de
   promoção definido separadamente.

## Próxima unidade de implementação

### Matriz de testes confirmada pelo usuário

Obra: **Things that deserve to die**, provedor RIDI, capítulo 3. Usar
`page-156-163_clean.png`, `page-051-059_clean.png`,
`page-078-083_clean.png` e `page-179-187_clean.png`, **nos Níveis I e II**.
Os caminhos, dimensões e hashes estão em
`../evidencias/textoff_especiais/2026-09-29/entradas_autorizadas.json`.

São oito entradas e dezesseis execuções previstas: dois tratamentos para
cada entrada. Para cada página, fixar as mesmas ROIs nos dois níveis e nos
dois tratamentos. As ROIs ainda devem ser estabelecidas antes de executar.

Comparar as quatro propostas por página com o Nível II atual preservado e
com suas respectivas entradas. O objetivo inclui verificar se aplicar um
Especial diretamente ao Nível I produz resultado visual melhor que o Nível
II atual. Avaliar resíduos, preservação da arte, artefatos de reconstrução,
invariância fora da máscara e duração. Contagem de pixels alterados sozinha
não determina qualidade. Esta autorização não promove resultados.

Preparar os dois runtimes com locks e um executor de prévia isolado, cobrindo
a seleção de interpretadores e a persistência em staging. Depois conectar
rota/job e interface ao executor validado. Não iniciar processamento em lote
nem promoção implícita nesta primeira fatia.

## Fontes inspecionadas

- `interface_web/textoff_special.js`
- `processamento/limpeza_baloes/textoff_special_web.py`
- `processamento/limpeza_baloes/textoff_special_transparent_roi.py`
- `processamento/limpeza_baloes/textoff_special_transparent_legacy_roi.py`
- `processamento/limpeza_baloes/patch_balao_transparente_experimento.py`
- `processamento/limpeza_baloes/patch_degrade_experimento.py`
- `processamento/limpeza_baloes/cleaner_v2/balloon_authorization.py`
- `processamento/limpeza_baloes/cleaner_v2/level2.py`
- `central_v2/AGENTS.md` e contratos em `docs/Refatoracao/`.
