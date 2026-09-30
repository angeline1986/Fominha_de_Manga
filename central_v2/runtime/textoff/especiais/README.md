# Ambientes de Casos Especiais

Dois ambientes independentes, Python 3.12.7/macOS arm64:

| Tratamento | Ambiente | Lock |
|---|---|---|
| Patch Balão Transparente | `balao_transparente/.venv` | `balao_transparente/requirements.lock.txt` |
| Balão Transparente — Legado | `balao_transparente_legado/.venv` | `balao_transparente_legado/requirements.lock.txt` |

Os locks partem da baseline já instalada do Merged I: 86 pacotes fixados,
incluindo Cleaner, LaMa e autorização YOLO. O Legado usa inicialmente o mesmo
conjunto para reduzir variáveis na comparação, embora não chame a autorização.
Os ambientes foram criados separadamente; não compartilham `site-packages`
nem dependem da venv de outra feature. `pip check` passou nos dois.

Snapshots instalados estão em
`docs/Refatoracao/evidencias/textoff_especiais/2026-09-29/*_runtime.json`.
Não atualizar versões como efeito colateral da migração.

## Reconstrução

A partir da raiz do repositório, para cada diretório de tratamento:

```sh
python3.12 -m venv central_v2/runtime/textoff/especiais/balao_transparente/.venv
central_v2/runtime/textoff/especiais/balao_transparente/.venv/bin/python -m pip install -r central_v2/runtime/textoff/especiais/balao_transparente/requirements.lock.txt

python3.12 -m venv central_v2/runtime/textoff/especiais/balao_transparente_legado/.venv
central_v2/runtime/textoff/especiais/balao_transparente_legado/.venv/bin/python -m pip install -r central_v2/runtime/textoff/especiais/balao_transparente_legado/requirements.lock.txt
```

Os modelos permanecem externos, nos caches existentes. O worker configura
Hugging Face/Transformers offline. Ausência de dependência, lock divergente
ou modelo não é motivo para recorrer à venv V1.

## Fronteira do domínio

`central_v2/backend/orchestration/textoff_special/domain.py` chama os módulos
de imagem existentes em `processamento/limpeza_baloes`. Não importa
`interface_web`, não chama suas rotas e não usa o promotor genérico V1.

O domínio ainda usa `base.CLEANER_PY` para dois subprocessos. A ligação é
configurada e restaurada exclusivamente dentro do processo descartável do
tratamento, usando `sys.executable`. Assim Cleaner e LaMa usam a mesma venv
da feature sem editar a V1 ou duplicar algoritmos. O perfil continua sendo
`preserve-colors.ini`; não substituí-lo pelo perfil Merged.

## Prévia por linha de comando

```sh
python3 -m central_v2.backend.orchestration.textoff_special.cli \
  --manga '/caminho/da/obra' --request '/caminho/request.json'
```

O JSON exige `treatment`, `level`, `chapter`, `filename`, `expected_sha256`
e `selections` (`x`, `y`, `width`, `height`, em pixels). A imagem precisa
constar no manifesto Merged selecionado. Staging e logs ficam sob
`reports/experimentos/textoff_especiais_v2/<run_id>/`.

Não existe operação de promoção. `succeeded` significa execução validada;
qualidade visual permanece pendente. Falhas preservam diagnóstico e duração.

## Comparação reproduzível

```sh
python3 dev/tools/textoff_special_matrix.py \
  --inventory docs/Refatoracao/evidencias/textoff_especiais/2026-09-29/entradas_autorizadas.json \
  --report reports/experimentos/textoff_especiais_v2/matrix.json
```

O runner retoma apenas itens ainda não registrados. Para repetir uma matriz,
use outro caminho de relatório; ele não reaproveita silenciosamente falhas.
O Cleaner pode precisar escrever seu log no cache do sistema. Isso é
independente do staging e não autoriza alterações nas imagens oficiais.
