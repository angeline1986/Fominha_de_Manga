# Análise do TextOff: Correção Assistida e tratamentos especiais

## Objetivo e fontes

Este documento registra a análise do fluxo atual de **TextOff Correção Assistida** e compara suas etapas com os tratamentos especiais disponíveis: Patch Degradê, Patch Estilizado, Transparência, Transparência legada e Degradê Suave. Serve como referência técnica para a implementação inicial de Texto Off — Merged na Central V2 e para mudanças futuras na Correção Assistida.

Fontes consultadas:

- `docs/Refatoracao/03_arquitetura_interface_alvo.md`
- `docs/Refatoracao/mapa_componentes_e_dependencias.md`
- `docs/Refatoracao/catalogo_fluxos_criticos.md`
- `docs/Refatoracao/checkpoints/04b_mapa_metro_auditoria_proveniencia.md`
- `analise_tecnica_textoff_correcao_assistida_tratamentos_especiais.md`, fornecido em Downloads
- Implementações atuais na interface e no domínio TextOff.

## Conclusão principal

Correção Assistida e TextOff Especiais **não usam o mesmo pipeline de correção**. Na Correção Assistida, a análise automática é uma sugestão visual; a geração da prévia depende de uma seleção manual independente e usa processamento regional com OCR e LaMa. Nos tratamentos especiais, cada opção tem uma regra própria para autorizar pixels e reconstruir a região.

Essa distinção afeta a interface, a segurança das alterações, os artefatos de proposta e as regras de promoção. Uma integração não deve presumir que as caixas detectadas pela análise são automaticamente selecionadas, nem que todos os tratamentos especiais têm a mesma autoridade para salvar o resultado.

## Correção Assistida: fluxo atual

### 1. Analisar resíduos

A ação **Analisar resíduos** chama `textoff_level3_analyze` por `/api/action` e acompanha a execução assíncrona. O analisador trabalha sobre a imagem atual do TextOff:

1. converte a imagem para tons de cinza;
2. procura componentes escuros abaixo do limiar configurado, usando conectividade de quatro vizinhos;
3. filtra componentes por tamanho e dimensões;
4. inspeciona um anel em torno dos componentes para exigir fundo claro e relativamente uniforme;
5. agrupa componentes próximos e descarta grupos grandes demais;
6. devolve caixas delimitadoras para a interface desenhar como sugestões.

O algoritmo é identificado como `textoff_level3_uniform_residual_v1`. Não é OCR, não lê o conteúdo, não determina semanticamente que a região é um resíduo e não altera imagem alguma. É uma heurística de componentes e uniformidade local: pode indicar falsos positivos e deixar resíduos sem indicação.

As sugestões são guardadas no estado da análise e desenhadas sobre a prévia. **Elas não são copiadas para a seleção manual** usada pela ação seguinte.

### 2. Selecionar área(s)

A seleção é uma ação manual independente, desenhada sobre a imagem de resultado atual. A interface registra retângulos em coordenadas percentuais relativas à imagem, para que a seleção sobreviva a diferenças de escala de exibição. Retângulos menores que o limite mínimo são ignorados.

As caixas da análise ajudam visualmente, mas não autorizam pixels nem preenchem `level3Selections`. A seleção manual é a entrada efetiva para gerar a prévia.

### 3. Gerar prévia

A ação **Gerar prévia** envia `level3Selections` para `textoff_level3_preview`; não envia `level3Analysis`. No servidor, o fluxo valida o capítulo pendente, os arquivos de origem e limpeza, a associação no `clean-manifest.json` e a integridade dos arquivos por SHA-256.

O worker regional (`level3_regional/regional.py`) executa, em linhas gerais, esta sequência:

1. transforma as áreas selecionadas em caixas em pixels;
2. examina com EasyOCR o recorte da **imagem de origem** dentro das caixas;
3. executa OCR com os grupos compatíveis `en+ko`, `ch_sim+en` e `ch_tra+en`; as detecções e os idiomas do modelo aplicado são registrados no relatório da proposta;
4. usa critérios de contraste para construir uma máscara menor que a ROI, restrita aos pixels autorizados;
5. expande/fecha a máscara morfologicamente conforme os parâmetros do algoritmo;
6. fornece a LaMa o recorte da origem com contexto ao redor — atualmente até 120 px — para sintetizar a região;
7. aplica os pixels sintetizados a uma cópia da imagem limpa atual, somente onde a máscara permite;
8. verifica que pixels fora da máscara não foram alterados.

O manifesto `proposal.json` registra `regional.ocr` e `worker.ocr`: engine, idiomas configurados, grupos de modelos usados, contagem de detecções por grupo e por região. Cada detecção registra `reader_languages`, isto é, o grupo de modelos que produziu aquela caixa. Esse campo **não afirma qual idioma foi reconhecido em cada texto**; EasyOCR não fornece essa classificação neste fluxo.

EasyOCR não aceita os três scripts juntos numa única lista. Os leitores são executados separadamente e suas máscaras são unidas. A implementação inclui chinês simplificado e tradicional. Isso implica até três inferências por ROI e pode aumentar o tempo de prévia. Os pares e a compatibilidade foram conferidos no código oficial do EasyOCR; os pesos de coreano/chinês não estão no cache local observado e podem precisar ser baixados antes do primeiro uso.

Portanto, desenhar um retângulo **não significa substituir o retângulo inteiro**. A ROI delimita onde procurar texto; OCR, contraste e máscara determinam o subconjunto efetivamente modificado. A síntese usa contexto da origem e é aplicada à imagem limpa atual.

A proposta, o relatório e os hashes são persistidos em uma área temporária/promovível. A geração da prévia não modifica o resultado oficial nem `02_MERGE`. A aprovação posterior revalida os hashes e a correspondência dos arquivos; quando a origem é MERGE, a aprovação pode atualizar o resultado do TextOff e o MERGE correspondente. Para origem ORIGINAL, a imagem original permanece inalterada.

### O encadeamento visível não é um encadeamento de dados

Na interface, as três ações aparecem como etapas relacionadas, mas os dados não são encadeados automaticamente:

```text
Analisar resíduos ──> caixas de sugestão desenhadas na prévia
                             │
                             └── não preenche a seleção manual

Selecionar área(s) ──> level3Selections ──> Gerar prévia
```

Se a intenção for permitir aceitar sugestões como áreas selecionadas, isso requer uma decisão funcional e uma mudança explícita no contrato da interface. A análise não deve ser tratada como autorização de pixels por acidente.

## Comparação dos tratamentos especiais

Os tratamentos especiais atuam sobre uma imagem escolhida pelo usuário, por upload ou pelo seletor de imagens da obra, e normalmente exigem uma ou mais ROIs manuais. As coordenadas são enviadas em pixels. O processamento gera um resultado de execução separado; a promoção é uma etapa posterior e depende da origem e do tratamento.

### Patch Degradê (`degrade`)

- Algoritmo do adaptador: `textoff_special_roi_degrade_v2`.
- Usa Cleaner e autorização de balões, além de um gate de superfície.
- Detecta componentes conectados e pode autorizar um componente quando ele intersecta uma ROI; a ROI atua como critério de seleção, não necessariamente como recorte rígido do componente.
- Reconstrói com *local heal* usando uma base e parâmetros de contexto/superfície.
- Não é o algoritmo separado `textoff_gradient_patch_v1`; nomes parecidos não indicam implementação compartilhada.

### Patch Estilizado (`estilizado`)

- Acrescenta classificação de região baseada em estatísticas de cor (LAB) e densidade de bordas (Canny), para autorizar ou preservar componentes.
- Combina a classificação, a ROI e o gate de superfície antes da reconstrução local.
- A implementação atual marca o resultado como prova (`proof_phase`) e `promotion_allowed=False`; o promotor bloqueia o algoritmo estilizado identificado.

### Transparência (`transparente`)

- Usa Cleaner, autorização de balões, dilatações e uma máscara autorizada.
- Executa LaMa com contexto e verifica que não houve alterações fora da máscara.
- O adaptador declara `proof_phase=True` e `promotion_allowed=False`.
- **Divergência encontrada:** a rota genérica de promoção não consulta esses dois campos para esse tratamento e não bloqueia `transparente`; a interface também pode habilitar “Salvar resultado” quando há caminho de origem. A Transparência segura pode, assim, ter uma regra declarada de não promoção que não é aplicada pelo caminho genérico. Isso deve ser resolvido antes de ampliar seu uso.

### Transparência legada (`transparente_legacy`)

- Seleciona componentes inteiros da máscara do Cleaner cujas caixas delimitadoras intersectam a ROI e depois dilata a máscara. Não recorta rigidamente a máscara na ROI.
- Não passa pelo mesmo estágio de autorização de balões da Transparência atual.
- Usa LaMa e valida a região externa à máscara.
- A promoção está explicitamente bloqueada.

### Degradê Suave (`gradiente_suave`)

- Não usa Cleaner, OCR ou LaMa.
- Expande verticalmente a ROI — pelo menos 12 px ou uma fração da altura selecionada — e considera uma borda de contexto.
- Calcula cores de superfície em faixas acima e abaixo, converte para LAB, suaviza horizontalmente as amostras e interpola entre as bordas.
- Reescreve a área retangular expandida, e não apenas os pixels da ROI original. Áreas expandidas sobrepostas são rejeitadas.

## Diferenças operacionais e de autoridade

| Aspecto | Correção Assistida | TextOff Especiais |
|---|---|---|
| Entrada | Par associado a capítulo pendente e resultado atual do TextOff | Imagem escolhida ou enviada pelo usuário |
| Análise automática | Heurística de componentes e fundo; apenas sugestão | Varia por tratamento; gates e máscaras são próprios de cada algoritmo |
| ROI efetiva | Manual; separada das caixas analisadas; coordenadas percentuais | Manual; enviada em pixels |
| Reconstrução | OCR regional + máscara + LaMa aplicada sobre a imagem limpa atual | Varia: local heal, LaMa com outras máscaras ou interpolação matemática |
| Execução | Ações assíncronas por `/api/action` e jobs | Rotas próprias de processar/promover, fora do mesmo contrato de job |
| Resultado inicial | Proposta; não altera o oficial até aprovação | Resultado de execução; promoção separada quando permitida |
| Promoção | Revalida hashes e par; aprovação de origem MERGE pode atualizar TextOff e MERGE | Atualiza saída oficial do TextOff; não altera diretamente `02_MERGE` |
| Proteção espacial | Máscara regional e verificação fora da máscara | Varia por tratamento; gates, máscaras e invariantes específicos |

## Riscos e divergências a considerar antes da implementação

### Validação OCR multilíngue

A configuração agora usa leitores separados `en+ko`, `ch_sim+en` e `ch_tra+en`, porque EasyOCR restringe cada modelo não latino a uma combinação com inglês. Os modelos precisam ser obtidos no ambiente regional se ainda não estiverem em cache. A integração e a observabilidade do manifesto têm testes unitários; falta validar qualidade de reconhecimento e tempo em páginas representativas da obra, especialmente conteúdo misto, letras pequenas e balões estilizados.

### Promoção da Transparência

Os metadados `promotion_allowed=False` e `proof_phase=True` não são respeitados pela rota genérica da mesma forma que o bloqueio explícito por nome de algoritmo em Estilizado e Transparência legada. A regra deve ser centralizada e testada para todos os tratamentos, em vez de depender de condições especiais dispersas.

### Worker/documentação obsoletos

O módulo de Correção Assistida contém referências e docstring legadas ao worker do Cleaner V2. O caminho usado por `generate_preview()` chama o worker regional dedicado e seu ambiente virtual próprio. A documentação de implementação deve descrever o caminho realmente executado, preservando a referência histórica apenas quando necessária.

### Proveniência

O fluxo de correção calcula hashes na geração e volta a validá-los na aprovação, mas o catálogo de fluxos aponta lacuna na proveniência do vínculo entre bytes de MERGE e manifesto Cleaner. A migração deve preservar as validações existentes e não criar uma segunda autoridade ou inventar um contrato paralelo.

### Cobertura de testes

As referências de baseline registram falta de testes automatizados específicos para os fluxos TextOff e tratamentos especiais. Antes ou junto da implementação, é necessário cobrir contratos que podem causar dano silencioso:

- associação entre capítulo, origem e imagem limpa;
- análise apenas como sugestão e eventual aceite explícito de caixas;
- ROI percentual convertida corretamente para pixels;
- idioma OCR e geração de máscara em conteúdo representativo;
- zero mudanças fora da máscara nos métodos que prometem essa invariância;
- rejeição de propostas obsoletas após mudança de origem/resultado;
- regras de promoção de cada tratamento, especialmente Transparência;
- diferença de autoridade entre aprovar Correção Assistida originada em MERGE e promover um Especial.

## Orientação arquitetural para a próxima etapa

Atualização de 29/09/2026: o inventário dos dois tratamentos transparentes e
o contrato inicial proposto para Casos Especiais V2 estão em
[`checkpoints/14_textoff_especiais_inventario_e_contrato_v2.md`](checkpoints/14_textoff_especiais_inventario_e_contrato_v2.md).
Esse levantamento também registra o efeito do gate atual de adiamento de
balões transparentes, os runtimes efetivamente chamados e a integridade de
34 resultados históricos. Não representa validação visual nem implementação
da feature V2.

`docs/Refatoracao/03_arquitetura_interface_alvo.md` define a Central V2 como camada isolada de interface/orquestração, reutilizando a lógica de domínio existente. O mapa de dependências documenta as ações da Correção Assistida e as rotas próprias dos Especiais. A interface atual da Correção Assistida ainda está em `interface_web`; a tela V2 não deve duplicar limiares, algoritmos, validações de manifesto, hashes ou regras de autorização.

Para a implementação, manter separadas as responsabilidades abaixo:

1. **detecção/sugestão** de regiões;
2. **seleção/consentimento** de ROIs pelo usuário;
3. **autorização** dos pixels que podem mudar;
4. **reconstrução** específica do algoritmo escolhido;
5. **prévia e auditoria** sem alteração oficial;
6. **aprovação/promoção** com autoridade e validação de proveniência próprias.

O contrato de idiomas para esta fase está definido como inglês, coreano, chinês simplificado e chinês tradicional, com leitores EasyOCR separados e metadados no manifesto. A implementação inicial da tela Texto Off — Merged na V2 foi iniciada sobre o executor existente `clean_chapter(source_stage="MERGE")`. Permanecem decisões futuras sobre aceitar sugestões de análise como seleção manual e alinhar as permissões de promoção dos tratamentos especiais. Esses contratos devem ser explícitos na interface, no backend e nos testes.

## Referências de implementação

- Interface Correção Assistida: `interface_web/textoff_compare.js`
- Analisador heurístico: `processamento/limpeza_baloes/textoff_level3_analyzer.py`
- Orquestração de prévia e aprovação: `processamento/limpeza_baloes/textoff_level3_correction.py`
- Worker regional: `processamento/limpeza_baloes/level3_regional/regional.py`
- Tratamentos especiais e promoção: `processamento/limpeza_baloes/textoff_special_web.py`
- Patch Degradê: `processamento/limpeza_baloes/textoff_special_roi.py`
- Patch Estilizado: `processamento/limpeza_baloes/textoff_special_styled_roi.py`
- Transparência: `processamento/limpeza_baloes/textoff_special_transparent_roi.py`
- Transparência legada: `processamento/limpeza_baloes/textoff_special_transparent_legacy_roi.py`
- Degradê Suave: `processamento/limpeza_baloes/gradiente_suave/gradiente_suave.py`
- Especificação técnica detalhada consultada: `analise_tecnica_textoff_correcao_assistida_tratamentos_especiais.md` (Downloads, 1407 linhas).
