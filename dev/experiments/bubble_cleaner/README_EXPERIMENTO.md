# Bubble Cleaner — experimento conservador V1

Objetivo: validar uma estratégia de limpeza de texto de balões sem colocar o acervo original em risco.

## Segurança desta versão

- Não altera nenhuma imagem de origem.
- Não está integrada ao menu principal.
- Não usa OCR ainda.
- Só tenta limpar componentes escuros quando eles estão dentro de uma região grande, clara, pouco texturizada e afastados da borda.
- Qualquer componente duvidoso é preservado e marcado para revisão.
- Depois da limpeza, compara original x resultado e exige que nenhuma alteração tenha ocorrido fora da máscara autorizada.
- Gera máscara, overlay, preview limpo e relatório JSON.

Essa V1 é propositalmente conservadora. Ela deve errar mais por **não limpar** do que por apagar arte.

## Arquivos gerados por imagem

`authorized-mask.png`
: pixels autorizados para alteração.

`overlay.png`
: visualização da máscara e regiões de revisão.

`cleaned-preview.png`
: resultado experimental.

`report.json`
: decisões, confiança e checagem de integridade.

## Instalação no projeto

Execute `apply.py` a partir deste pacote. Ele cria somente:

`experiments/bubble_cleaner/`

Nenhum arquivo existente do projeto é modificado.

## Uso

Na raiz `Fominha_de_Manga`:

```bash
python experiments/bubble_cleaner/bubble_cleaner_experimental.py \
  "caminho/para/page-001.png" \
  --output "bubble_cleaner_output"
```

Também aceita uma pasta inteira:

```bash
python experiments/bubble_cleaner/bubble_cleaner_experimental.py \
  "mangago_downloader/output/comix/OBRA/IMG/1" \
  --output "bubble_cleaner_output/capitulo-1"
```

## Testes

```bash
python -m unittest experiments/bubble_cleaner/test_bubble_cleaner_experimental.py
```

## Próxima fase

Depois da validação visual desta V1, podemos acrescentar uma segunda confirmação sem alterar a política de segurança:

1. detector de balão;
2. detector/OCR de texto independente;
3. concordância entre os dois;
4. classificação diálogo x onomatopeia;
5. limpeza somente com confiança alta.

Não devemos instalar um modelo pesado antes de medir o desempenho da máscara conservadora com páginas reais.
