#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

echo "Environment ready. Activate with 'source ${VENV_DIR}/bin/activate'."
