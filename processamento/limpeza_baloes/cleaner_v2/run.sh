#!/usr/bin/env bash
set -euo pipefail

# Uso: bash run.sh --timeout 900

cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
    echo 'Ambiente .venv não encontrado. Siga a instalação no README.md.' >&2
    exit 1
fi

exec .venv/bin/python main.py "$@"
