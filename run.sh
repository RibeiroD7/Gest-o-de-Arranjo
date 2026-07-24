#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ -f "venv-linux/bin/activate" ]; then
    source venv-linux/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "ERRO: Ambiente virtual não encontrado."
    echo "Execute: python3 -m venv venv-linux && venv-linux/bin/pip install -r src/requirements.txt"
    exit 1
fi

python src/main.py
