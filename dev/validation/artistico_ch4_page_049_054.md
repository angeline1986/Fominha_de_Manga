# Validação visual isolada: Candy YumYum (Yaoi), Ch. 4, page-049-054.png

## Estado observado em leitura em 08/10/2026

- Obra operacional: `/Users/alinesouza/Documents/FominhaData/output/mangago/Candy YumYum (Yaoi)`.
- A entrada anterior ao Artístico consta no histórico do Consolidado Final com SHA-256
  `5b9492d0b7de07bad4dc2d9b039b7ce2c3c24b1ce4b5e4fbfb0ff5d64b3de76c`;
  o arquivo da etapa Transparência possui exatamente esse hash.
- O histórico registra a saída Artística `6bb36a8f1fb4f82058307181e98d6a40847ef41fecd5720bb4688f30726b4441`
  e depois um Degradê. A página final atual tem SHA-256
  `573dabb2f7bcac06865a8c29de1587938c8eb9330d6091d063f7794f92ef2ef3`.
- Há quatro ocorrências Artísticas na página, todas com status `failed` no Manifesto Especial.
  Não há manifesto `06_PINCEL/ARTISTICO/Ch. 4/json/artistico-manifest.json` nem manifesto
  `06_PINCEL/DEGRADE/Ch. 4/json/degrade-manifest.json`.
- Uma busca pelos arquivos `page-049-054*.png` da obra, excluindo recortes, não encontrou
  a saída Artística com o hash `6bb36a8...`. Não há máscaras de autoria por ocorrência.
  **A reexecução individual deve continuar bloqueada.** A ROI retangular e diferenças
  de pixels não bastam para reconstruir autoria.

## Procedimento quando houver evidência histórica verificável

1. Registrar SHA-256 do Check, Manifesto Especial, Consolidado Final e página operacional.
   Copiar a obra para um diretório temporário isolado, com `FOMINHA_DATA_ROOT` apontando
   somente para essa cópia. Confirmar que os hashes da cópia coincidem com os originais.
   Não chamar funções de estágio sobre a obra operacional: a resolução de estágio pode
   migrar pastas legadas.
2. Na cópia, verificar e registrar para **cada ocorrência** o ID, ROI aprovada, entrada
   pré-filtro, saída antiga, máscara de autorização, máscara de escrita efetiva, SHA de
   cada artefato e dependências posteriores. Para o Degradê posterior, exigir máscara de
   autoria verificável. Se qualquer prova faltar ou divergir, manter o bloqueio e encerrar.
3. Usar a consulta da Central V2 apontada para a cópia. Selecionar somente a ocorrência
   desejada na coluna **OCORRÊNCIA**; conferir página, ID, ROI, filtro atual e solicitado.
   Abrir **Revisar** para observar o antes/depois da página e registrar recortes da ROI.
4. Na cópia, gerar a prévia técnica e a composição em staging, sem chamar `publish`.
   Conferir essas imagens e guardar entrada pré-filtro, saída técnica, máscara antiga,
   máscara nova e composição proposta antes de autorizar a publicação na própria cópia.
   Comparar pixel a pixel: pixels antigos exclusivos voltam à entrada histórica; os novos
   são aplicados a partir dessa entrada; fora da união das duas máscaras, a imagem final
   permanece igual. Verificar separadamente todas as outras ROIs e seus registros.
5. Após aprovação visual, exercer o fluxo transacional somente na cópia. Simular nela
   uma mudança de SHA e uma sobreposição com tratamento posterior.
   Ambos os casos devem falhar sem publicação parcial. Inspecionar o journal transacional
   e repetir as comparações de SHA dos artefatos não selecionados.
6. Recalcular os hashes operacionais registrados no passo 1 para confirmar que nenhum
   artefato da obra real mudou. Submeter as imagens antes/depois e o relatório de pixels
   para revisão visual antes de liberar a funcionalidade naquela página.

Este procedimento prepara a validação; nenhum tratamento operacional foi executado.
