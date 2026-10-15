# CV2-OBS-03 — Instrumentar autorização automática do Degradê para diagnóstico de falhas de detecção de balão

- **Prioridade:** P1 (alta)
- **Status:** TODO
- **Categoria:** Saúde Arquitetural · Observabilidade · Processamento
- **Escopo:** Central V2 — Laboratório · Degradê
- **Responsável:** A definir

## Contexto

Na investigação da execução Degradê do Laboratório para `page-099.png`, capítulo 3, a ROI salva (`x=436, y=286, largura=408, altura=158`) continha o componente encontrado pelo Cleaner. A autorização automática registrou:

- `balloons_detected = 0`
- `authorized_pixels = 0`
- `best_balloon = null`
- `decision = preserve`
- `reason = outside_or_ambiguous`

O fluxo encerrou com a mensagem “Nenhum componente autorizado intersecta as seleções”, embora a causa imediata registrada tenha sido ausência de detecção/autorização, e não falha de coordenadas ou interseção com a ROI. Os artefatos atuais não permitem inspecionar as propostas brutas e confidências do segmentador nem separar com precisão os tempos da detecção e autorização.

## Adendo: tipo de imagem de entrada

Foi observado que a falha ocorre quando a execução usa a imagem fatiada e não ocorre quando usa a imagem mergeada. Esse comportamento amplia a investigação: ela deve abranger a entrada usada pelo pipeline, além do tratamento Degradê e do autorizador.

**Hipótese a verificar:** o detector/autorizador pode ser sensível à perda de contexto da imagem fatiada, enquanto a mergeada preserva contexto visual suficiente para detectar e autorizar o balão. Essa hipótese não está confirmada.

A comparação deve avaliar, com parâmetros equivalentes, a mesma área na imagem mergeada e na imagem fatiada. Registrar possíveis diferenças de contexto visual, recorte do balão, bordas artificiais da fatia, escala/resolução efetiva, posição do balão e pré-processamento aplicado em cada fluxo. Essas diferenças devem ser medidas/documentadas como evidência, sem presumir que alguma delas seja a causa.

## Justificativa

A falta de observabilidade dificulta o diagnóstico de falsos negativos, gera retrabalho investigativo e aumenta o tempo de resposta a incidentes semelhantes. Cada falha exige nova análise manual dos artefatos disponíveis, que não registram evidências suficientes para distinguir a ausência de proposta de uma proposta rejeitada.

## Objetivo

Tornar explícita, persistente e rastreável a decisão da autorização automática no fluxo Degradê, identificando inequivocamente:

1. `no_detection` — nenhuma proposta/candidato detectado;
2. `candidate_rejected` — candidato detectado e rejeitado, com motivo objetivo;
3. `deferred` — candidato diferido pela regra vigente;
4. `authorized_but_no_roi_intersection` — candidato autorizado sem interseção com a ROI;
5. `execution_error` — falha operacional durante execução ou instrumentação.

## Escopo esperado

- Persistir evidências técnicas da etapa de autorização em artefato associado à execução.
- Registrar propostas brutas relevantes do segmentador/detector, incluindo quantidade, caixas/máscaras disponíveis, confidências, versão/modelo e parâmetros de detecção usados.
- Registrar decisão e motivo de rejeição por componente/candidato, sem confundir ausência de detecção com rejeição ou falta de interseção.
- Registrar durações das etapas críticas, incluindo Cleaner, detecção, autorização, interseção com ROI e tratamento, inclusive quando uma etapa falhar.
- Ajustar os códigos/status técnicos e a mensagem pública/diagnóstica para representar a causa real sem induzir que toda falha é de interseção com ROI.
- Documentar o fluxo, parâmetros, formato e localização dos artefatos, estados possíveis e interpretação dos diagnósticos.
- Manter instrumentação separada da regra de negócio e da apresentação; preferir módulos pequenos e coesos e evitar arquivos acima de 200 linhas sem necessidade.

## Critérios de aceite

- [ ] Uma execução com falha semelhante é reproduzida e rastreada de ponta a ponta com os novos artefatos.
- [ ] O diagnóstico distingue inequivocamente `no_detection`, `candidate_rejected`, `deferred`, `authorized_but_no_roi_intersection` e `execution_error`.
- [ ] O artefato informa quantidade de propostas/candidatos avaliados, versão/modelo, parâmetros relevantes, motivo objetivo por candidato e tempos das principais etapas.
- [ ] A mensagem diagnóstica não atribui a falha apenas à interseção com ROI quando não houve autorização.
- [ ] Uma comparação controlada da mesma área na imagem mergeada e na fatiada, com os mesmos parâmetros, registra lado a lado detecções, decisões/motivos de autorização e tempos por etapa.
- [ ] A evidência da comparação permite identificar se a divergência está associada ao tipo de entrada, incluindo contexto, recorte/bordas, escala/resolução, posicionamento do balão e pré-processamento; qualquer causa permanece descrita como hipótese até ser demonstrada.
- [ ] A ROI manual continua sendo apenas uma restrição espacial e não substitui a autorização automática.
- [ ] Nenhuma remoção ocorre sem validação automática vigente; falhas de detecção ou autorização continuam falhando de forma fechada.
- [ ] Documentação descreve o fluxo, o contrato dos artefatos, os parâmetros e como interpretar cada estado/motivo.

## Fora de escopo e restrições

- Não trocar o modelo detector neste item.
- Não reduzir thresholds nem recalibrar funcionalmente o Degradê.
- Não permitir que a ROI autorize remoção.
- Não alterar regra de autorização sem evidência posterior produzida pela instrumentação.
- Preservar a autorização automática como barreira obrigatória de segurança.
- Preservar a Central V1 e os demais contratos de processamento não necessários para este diagnóstico.

## Evidência de referência

Investigação consolidada da execução `61fb9ac5fe854f88827e0ca2990b06df`, com a imagem-fonte `page-099.png`, capítulo 3, ROI `408×158`, hash SHA-256 `6256d17f9eb0ce4e115963d950adf7de0210ce653590ca31051b3de18213bce7`. O componente encontrado pelo Cleaner estava contido na ROI; o relatório registrou zero balões detectados e zero pixels autorizados. A execução Artístico com a mesma fonte e ROI registrou interseção do componente, corroborando que a causa do Degradê não foi a coordenada da seleção.

**Referência de fluxo:** `processamento/limpeza_baloes/textoff_special_roi.py`, `processamento/limpeza_baloes/cleaner_v2/balloon_authorization.py`, `central_v2/backend/routes/laboratorio_degrade.py` e `central_v2/backend/routes/laboratorio_degrade_jobs.py`.

**Comparação adicional solicitada:** mesma área em entrada mergeada versus fatiada, mantendo os mesmos parâmetros e registrando diferenças de entrada/pré-processamento, propostas de detecção, autorização, motivos e tempos.
