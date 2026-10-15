#!/usr/bin/env bash
set -euo pipefail
if [[ "$(uname -s)" == 'Darwin' ]]; then
  export PATH="/opt/homebrew/bin:/usr/local/bin:/opt/homebrew/opt/node/bin:/usr/local/opt/node/bin:${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ ! -x .venv/bin/python ]]; then
  echo 'Önce ./scripts/setup.sh komutunu çalıştırın.'
  exit 1
fi
exec .venv/bin/python -m app.server
