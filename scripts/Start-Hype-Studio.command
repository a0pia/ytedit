#!/bin/bash
set -euo pipefail
if [[ "$(uname -s)" == 'Darwin' ]]; then
  export PATH="/opt/homebrew/bin:/usr/local/bin:/opt/homebrew/opt/node/bin:/usr/local/opt/node/bin:${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ ! -x .venv/bin/python ]] || [[ ! -f node_modules/electron/path.txt ]] || ! command -v npm >/dev/null 2>&1; then
  bash scripts/setup.sh
fi
exec npm start
