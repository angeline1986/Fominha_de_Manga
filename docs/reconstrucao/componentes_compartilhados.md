# Manual de reconstrucao - componentes compartilhados

## 1. O que e compartilhado

Compartilhamento e confirmado por import/call site, nao apenas por semelhanca de nome. A matriz em `docs/arquitetura/modulos_compartilhados_limpeza_baloes.md` deve ser lida junto ao codigo. Principais casos:

| Componente | Consumidores comprovados | Limite |
|---|---|---|
| `processamento/limpeza_baloes/cleaner_v2/integration.py` | `interface_web/processing_web.py` e orquestracoes V2 TextOff | Mesmo motor chamado sob destinos/workflows distintos. |
| `cleaner_v2/balloon_authorization.py`, `transparency_classifier.py` | integracao Cleaner comum e adaptador V2 N1 | Regra de autorizacao e gate sao dominios comuns; N1 V2 separa persistencia/etapa. |
| `cleaner_v2/level2.py` | integracao V1 combinada e pipeline V2 N2 | Algoritmo comum, envoltorios, entrada elegivel e manifests diferem. |
| `cleaner_v2/launcher.py`, `main.py`, `ocr_manifest.py` | integracao/CLI Cleaner | Perfil/configuracao efetiva deve acompanhar runtime. |
| adapters especiais em `processamento/limpeza_baloes/` | `central_v2/backend/orchestration/textoff_special/` e consumidores legados identificados por import | Algoritmos individuais tem seus proprios contratos e nem todos tem os mesmos consumidores. |

`bubble_cleaner.py` nao foi confirmado como consumidor ativo no fluxo V2 TextOff principal; permanece no projeto para outros usos. Antes de classificacao de compartilhado, verificar import e chamada ativa, inclusive imports dinamicos/adapters.

## 2. Contrato do Cleaner compartilhado

`clean_chapter(source_images, target, source_stage, timeout=900, ...)` valida fontes e nomes, usa links simbolicos em workspace temporario, executa Panel Cleaner offline com `outlined-text.ini`, exige saida clean e mask por entrada, aplica N1, roda N2, monta manifest e promove diretorio staged. Identificadores relevantes: algoritmo `cleaner_v2_panel_cleaner_2_11_11`, engine Panel Cleaner 2.11.11, schema raiz 3. Timeout diferente de 900 e rejeitado.

O perfil e OCR efetivo sao descritos por `ocr_manifest_metadata()`. A documentacao do proprio motor confirma que o perfil desativa Tesseract e resulta no MangaOCR japones, embora `ocr_language=detect_box` reporte `ja`/`eng`; isso nao habilita OCR coreano/chines. A reproducao exige registrar arquivo INI, versao de dependencias, modelo e pesos reais.

## 3. Regras e parametros de N1

Fontes: `cleaner_v2/balloon_authorization.py`, `transparency_classifier.py`.

- Modelo de segmentacao de balao Manga109: repositorio `huyvux3005/manga109-segmentation-bubble`, arquivo `best.pt`, revisao fixada `f9a4108c4955136a810e5e92207972f3fb3a65fd`, task `segment`, classe `balloon`, confidence 0.25 e IoU 0.45.
- Componentes Cleaner abaixo de 20 px sao preservados. A autorizacao exige pelo menos 0.90 de seus pixels dentro de um unico balao.
- Interior de balao e erodido pela razao 0.025 do menor lado, limitado entre 2 e 8 px.
- Fail-closed: componente ambiguo/fora do balao e preservado; interseccao com interior transparente adia o componente inteiro.
- Transparencia primaria: amostra `gray >= 200`, ao menos 500 pixels; desvio-padrao >=9 ou razao de saturacao HSV acima de 5 >=0.05.
- Gate secundario: erosao de borda 3 px, dilatacao de mascara Cleaner 5 px; distancia Lab do branco >=8 e razao nao-branca >=0.01. Amostras insuficientes nao classificam como transparentes.

O relatorio e versionado e declara algoritmo, politica, fail_closed, modelo, limiares, decisoes por componente e totais. Nao substituir esses valores por thresholds aproximados.

## 4. Regras e parametros de N2

Fonte de parametros: `cleaner_v2/level2.py`. Area minima 20,000 px; retangularidade minima 0.85; classificador A: desvio-padrao interno >=2.5; classificador B: desvio-padrao interno <=1.5, range do contexto >=25.0 e media interna <=245.0; ROI/padding 160 px. `level2_vision.py` tem parametros de outro limite: mascara base 3x3, autorizada 9x9; contexto LaMa 120 px; ate 3 paginas MPS por modelo. Reconstrucao deve separar detector/classificador, geometria da mascara e contexto do inpainter.

## 5. Tratamentos especiais e consumidores

`docs/arquitetura/algoritmos_especiais_compartilhados.md` registra parametros concretos de Degrade, Transparente, Suave e Estilizado. A V2 consome esses algoritmos por adapters e envolve execucao em propostas, autorizacao, artifacts e manifests proprios. A matriz de imports define cada call site; nao presumir que todos os modulos listados sejam efetivamente usados por V1 e V2, nem que parametros tenham sido aplicados se uma rota possui um caminho alternativo.

Auto-Merge, Balanceamento e modulos de dominio que nao participam de chamadas de Limpeza de Baloes permanecem fora desta definicao de compartilhado.

## 6. Regra de equivalencia entre wrappers

Para comparar dois consumidores do mesmo dominio, fixar codigo, perfil, modelos e imagens fonte. Comparar em separado:

1. argumento efetivo e lista/ordem das paginas;
2. mascaras brutas, N1 autorizado/adiado e relatorio de decisao;
3. imagens N1 e N2, mudancas por pagina e status de zero alteracoes;
4. campos semanticos dos manifests: algoritmo, fonte, predecessor, contagens, artefatos e hashes;
5. destino, atomicidade, rollback, retry e politica de invalidacao;
6. comportamento API/job/UI de cada wrapper.

Hashes integrais iguais sao esperados somente para os mesmos bytes/arquivos; campos de timestamp, id de execucao ou caminhos de destino podem diferir. Igualdade visual de uma etapa nao comprova equivalencia de promocao/persistencia.

## 7. Testes e limites

Testes de dominio e adaptadores identificados: `test_cleaner_v2_transparency_classifier.py`, `test_cleaner_v2_ocr_manifest.py`, `test_textoff_merged_level1_adapter.py`, `test_textoff_merged_level2.py`, `test_textoff_consolidated.py` e testes `test_special_*`. Os testes nao foram executados como parte desta tarefa.

Lacunas: inventario conclusivo de todos os imports dinamicos fora dos call sites documentados; versoes verificadas do ambiente atual; checksum dos pesos atualmente baixados; casos-limite de transparencia nao cobertos por fixture; resultados referenciais de qualidade visual autorizados para equivalencia.

## Fontes

`processamento/limpeza_baloes/cleaner_v2/`; `central_v2/backend/orchestration/textoff_merged/`; `central_v2/backend/orchestration/textoff_special/`; `interface_web/processing_web.py`; `orquestracao/textoff/`; `docs/arquitetura/modulos_compartilhados_limpeza_baloes.md`; `docs/arquitetura/algoritmos_especiais_compartilhados.md`.
