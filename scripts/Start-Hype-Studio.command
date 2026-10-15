#!/bin/bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ ! -x .venv/bin/python ]] || [[ ! -d node_modules/electron ]]; then
  bash scripts/setup.sh
fi
exec npm start
