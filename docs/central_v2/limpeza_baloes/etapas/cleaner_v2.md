# Cleaner V2 e preservação de balões transparentes

**Escopo:** motor compartilhado chamado pelos caminhos V1 e V2; esta página documenta o contrato do motor e assinala diferenças de orquestração.\
**Fonte:** `processamento/limpeza_baloes/cleaner_v2/`; defaults conferidos no código atual.

## Objetivo e entrada

Executar Panel Cleaner em lote offline, aplicar autorização conservadora de máscara relativa a balões e, para candidatos autorizados à segunda fase, refinar a imagem com processamento local. A integração recebe uma lista de imagens, diretório-alvo, `source_stage`, timeout, callbacks/progresso e nome de capítulo opcional.

## Execução

```text
imagens de uma etapa
  → Panel Cleaner (--offline, perfil outlined-text.ini)
  → validar outputs/mascaras
  → gate de balões transparentes e relatório de autorização
  → Nível II sobre fontes/candidatos elegíveis
  → validar saídas e integridade
  → promover diretório completo e clean-manifest.json
```

`integration.clean_chapter()` fixa timeout de integração em 900 s e rejeita outro valor. O runtime é a `.venv` do pacote e o perfil de produção é `outlined-text.ini`; requirements estão em `requirements.txt`. A configuração chamada `preserve-colors.ini` também existe, mas não é o perfil padrão da execução oficial documentada.

## Algoritmo e parâmetros confirmados

### Cleaner / autorização

`balloon_authorization.py` segmenta/detecta componentes de balão a partir de modelo fixado no código e compara máscara Cleaner com interiores de balão. A política preserva componentes que intersectam balões classificados como transparentes, registrando o adiamento para etapa posterior.

O classificador usa somente pixels do interior com cinza `>= 200`; abaixo de `500` amostras, o resultado é inconclusivo e não classificado como transparente. Caso contrário, classifica como transparente se desvio-padrão do cinza `>= 9.0` **ou** proporção de saturação HSV `> 5` igual ou superior a `0.05`.

Se o sinal primário não indicar transparência e a máscara bruta do Cleaner estiver disponível, o gate de segurança secundário exclui da análise a máscara dilatada com elipse de raio `5 px`, erode o interior com elipse de raio `3 px` e compara pixels restantes no espaço Lab com branco `[255,128,128]`. A distância Lab `>= 8.0` é não branca; uma razão `>= 0.01` suspeita transparência. Também exige `500` pixels de análise. Parâmetros e motivos são escritos no relatório.

No gate de componentes, confiança do modelo é `0.25`, IoU é `0.45`; segmento de balão é erodido por margem baseada em `2.5%` do menor lado, limitada de `2` a `8 px`. Componentes de máscara menores que `20 px` são preservados. Componentes com sobreposição a qualquer balão transparente são preservados/adiados; os demais só são autorizados quando `>= 90%` de sua área está dentro de um único interior. Fora ou ambíguo é preservado. Modelo: `huyvux3005/manga109-segmentation-bubble`, arquivo `best.pt`, revision fixada no código (`f9a4108c4955136a810e5e92207972f3fb3a65fd`). O código falha fechado se não carregar um modelo de segmentação com classe `balloon`.

### Nível II

O Nível II só detecta componentes conectados na máscara autorizada do Nível I; a máscara é interpretada como pixels `> 8`. Exige um único `*_clean` e `*_mask` por fonte e dimensões compatíveis. Componentes com área `< 20,000 px` ou retangularidade `< 0.85` não são candidatos. As métricas são calculadas em cinza sobre a imagem limpa, com bandas de contexto de `12 px` nas quatro bordas disponíveis:

- `TYPE_A`: desvio-padrão interno `>= 2.5`.
- `TYPE_B`: desvio-padrão `<= 1.5`, faixa entre médias das bandas `>= 25`, média interna `<= 245` e pelo menos três lados de contexto.

Para candidatos, LaMa recebe um recorte da imagem original ampliado em `160 px` ao redor da caixa; o resultado é aplicado **somente aos pixels do componente** sobre uma cópia do Nível I já limpo. Isso evita reintroduzir texto removido em componentes não suspeitos. Usa `anime-manga-big-lama.pt` e MPS quando disponível, caso contrário CPU. `level2.py` grava o clean atualizado por substituição atômica e relatório `textoff_level2_v3_lama_local_v1`.

## Saídas e validação

`integration.py` registra `schema_version: 3`, algoritmo e separação de metadados por nível. O Cleaner exige artefato limpo para cada entrada concluída; máscaras podem ser incompletas apenas conforme os sinalizadores explícitos (`masks_total` / `mask_complete`). O manifesto de lote só é promovido quando o lote completo passa validação. A publicação usa staging/promoção do diretório.

O Nível II executa em subprocesso com timeout de 900 s. Timeout gera erro preservando a saída oficial anterior. Não tratar um resultado de subprocesso parcial como oficial.

## Diferenças V1/V2

O motor e autorização são compartilhados. V1 os alcança via `orquestracao/textoff/merged.py` e/ou ações do `processing_web.py`; V2 envolve o motor em `central_v2/backend/orchestration/textoff_merged/`. Os clientes, rotas, estados e projeções das duas Centrais são diferentes.

## Validação para equivalência

Registrar runtime Python e locks usados, hashes dos perfis/modelos/código, hashes das fontes/saídas, algoritmo dos manifests, páginas candidatos, máscaras autorizadas, área alterada e diferença fora da máscara. Comparar pixels e inspeção visual; sucesso computacional sozinho não comprova qualidade ou equivalência.

## Lacunas

- Thresholds completos de cada classificador Nível II precisam ser copiados para especificação com rastreio a linhas atuais.
- Hashes/versões dos pesos externos são específicos do modelo disponível e não devem ser inferidos de um nome de modelo.
- Reprodutibilidade por SO/GPU e qualidade visual para classes raras não estão demonstradas apenas pelo baseline de dependências histórico.
