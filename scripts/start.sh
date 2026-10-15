#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ ! -x .venv/bin/python ]]; then
  echo 'Önce ./scripts/setup.sh komutunu çalıştırın.'
  exit 1
fi
exec .venv/bin/python -m app.server
