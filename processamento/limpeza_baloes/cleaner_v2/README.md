# Cleaner V2

Limpeza em lote com Panel Cleaner, preservação de cores, logs por etapa e OCR
local opcional. Está disponível na opção **7 — Cleaner V2** do menu principal.
A limpeza anterior continua disponível na opção 4. Esta integração é de terminal;
as ações da interface web continuam utilizando a implementação anterior.

## Instalação

Na raiz do Fominha de Manga:

```bash
cd processamento/limpeza_baloes/cleaner_v2
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

O ambiente validado localmente foi Python 3.10 em Mac Apple Silicon. O Panel
Cleaner seleciona o dispositivo disponível. A primeira execução pode baixar
modelos; o cache fica fora do repositório. As dependências de IA são isoladas
no ambiente deste módulo.

## Executar

Pelo menu principal, selecione Cleaner V2 e informe pastas separadas de entrada
e saída. Podem ser imagens originais ou merges já exportados.

Também é possível executar diretamente, dentro da pasta deste módulo:

```bash
bash run.sh -i /caminho/entrada -o /caminho/output-cleaner-v2 --profile outlined-text.ini --timeout 900
```

Depois que os modelos estiverem baixados, acrescente `--offline` para evitar
consultas do OCR ao Hugging Face. Não bloqueia downloads de outros modelos.
O timeout limita o lote inteiro. Ctrl+C interrompe o processamento.

## Perfis e resultados

- `preserve-colors.ini`: preserva tons claros e aplica redução de ruído em cores.
- `outlined-text.ini`: amplia a máscara para texto com contorno branco; usado
  pelo menu. Máscaras maiores podem atingir detalhes próximos, exigindo revisão.

Os resultados incluem `_clean` e `_mask`. PNG mantém as dimensões e usa
compressão sem perdas; as regiões de limpeza são modificadas intencionalmente.
O programa mantém o paralelismo de CPU do Panel Cleaner; a detecção MPS usa
um processo. Uma execução concluída não garante que todas as regiões tenham
máscaras aprovadas: confira os relatórios e revise visualmente a saída.

O módulo não gera o manifesto de integridade do cleaner anterior, pois não
implementa as mesmas garantias. Resultados não são promovidos automaticamente
para as etapas oficiais do hub.

Ambientes, entradas locais e pastas `output*` não devem ser versionados.
