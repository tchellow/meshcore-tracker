#!/usr/bin/env bash
set -e
# Roda a partir do codigo, sem instalar. O instalador esta em docs/instalacao.md.

PROJETO="$(cd "$(dirname "$0")" && pwd)"
DADOS="${XDG_DATA_HOME:-$HOME/.local/share}/meshcore-tracker"
VENV="$DADOS/.venv"
export PYTHONDONTWRITEBYTECODE=1

if [ ! -x "$VENV/bin/python" ]; then
    echo "Preparando o ambiente Python..."
    mkdir -p "$DADOS"
    if ! python3 -m venv "$VENV"; then
        echo "Nao foi possivel criar o ambiente. Instale com: sudo apt install python3-venv"
        exit 1
    fi
fi

"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r "$PROJETO/requirements.txt"

if ! id -nG | grep -qw dialout; then
    echo "Aviso: para acessar a USB, rode 'sudo usermod -aG dialout $USER' e entre de novo na sessao."
fi

exec "$VENV/bin/python" "$PROJETO/app.py" "$@"
