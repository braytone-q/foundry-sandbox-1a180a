#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo 'Create .venv and install requirements-api.txt; see INSTRUCTIONS.md.' >&2
  exit 1
fi
if [[ -x .venv/azure-cli/bin/az ]]; then
  export PATH="$PWD/.venv/azure-cli/bin:$PATH"
fi
if [[ -d .venv/azure-config ]]; then
  export AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-$PWD/.venv/azure-config}"
fi

# One process owns startup recovery. Bind only to this computer.
exec .venv/bin/python -m uvicorn regen_api.main:create_app --factory \
  --host 127.0.0.1 --port "${REGEN_PORT:-8000}" --workers 1
