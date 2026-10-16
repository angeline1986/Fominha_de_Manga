# Consolidação e restauração — Central V2

## Consolidado intermediário I/II

`consolidated.py::rebuild_consolidated()` exige Nível I correspondente ao MERGE e valida os manifestos de Nível I e II, hashes dos manifests, source artifacts, páginas candidatas/analisadas/alteradas, status de integridade e arquivos. Seleciona por página o output Nível II para página válida alterada e mantém o Nível I para o restante; o manifesto intermediário aponta para os artifacts, registra seleções/fontes/hashes e é publicado por staging.

`consolidated_is_current()` repete validações antes do uso. Quando existe manifest legado de Nível II, o leitor contém caminho de compatibilidade específico; isso não autoriza atualizar arquivos legados durante consulta.

## Consolidado Final

O estágio lógico `CONSOLIDADO_FINAL` usa `07_CONSOLIDADO_FINAL/<capítulo>/`; imagens PNG ficam na raiz da pasta de capítulo e o manifesto em `json/final-manifest.json`. Schema `textoff_consolidado_final_manifest_v1`, versão `1`, guarda uma entrada por página, origem/tratamento, hash e histórico de versões substituídas.

`rebuild_final_baseline()` exige consolidado intermediário corrente, copia arquivos para staging, confere hash de cada cópia e do manifesto predecessor e promove. `promote_treatment_pages()` valida que o input e o manifesto continuam os mesmos, verifica a saída declarada no estágio do tratamento, copia a imagem e inclui a versão substituída no histórico antes da promoção transacional. `read_manifest()` confere schema, contexto de obra/capítulo, segurança de nomes, existência de cada página e SHA-256.

## Restauração especial de página

`special_page_restore.py` monta contexto, inspeção e proposta vinculada aos hashes atuais. `special_page_restore_source.py` localiza e snapshotta fonte; `_prepare.py`, `_check.py` e `_backup.py` tratam staging, compatibilidade, backup e validação. A restauração exige que as entradas/manifests usados permaneçam iguais ao preparar e publicar; execuções dependentes podem ser invalidadas. O fluxo se refere à restauração especial de página, não a restauração genérica de toda a obra.

## Diferença de autoridade

O consolidado intermediário é uma composição por referências das saídas automáticas; o final é conjunto independente de PNGs por página, editável por promoção explícita de tratamentos. Ambos guardam contexto/hashes, mas usam schemas e regras diferentes. Não misturar um `clean-manifest.json` com `final-manifest.json` nem copiar nomes de etapa entre V1 e V2 sem mapear origem.
