#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

python_binary="${HYPE_PYTHON:-python3}"
if ! command -v "$python_binary" >/dev/null 2>&1; then
  echo 'Python 3.11 veya üzeri gerekli. Mac: brew install python@3.12'
  exit 1
fi
"$python_binary" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 veya üzeri gerekli."'
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo 'Node.js 22.12 veya üzeri gerekli. Mac: brew install node'
  exit 1
fi
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 12)) { console.error("Node.js 22.12 veya üzeri gerekli."); process.exit(1); }'
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo 'FFmpeg gerekli. Mac: brew install ffmpeg; Ubuntu/Debian: sudo apt install ffmpeg'
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
  "$python_binary" -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
npm ci --no-audit --no-fund
if [[ -n "${HTTPS_PROXY:-${HTTP_PROXY:-}}" ]]; then
  ELECTRON_GET_USE_PROXY=1 node node_modules/electron/install.js
else
  node node_modules/electron/install.js
fi
if [[ ! -e .env ]]; then
  (umask 077; cp .env.example .env)
fi

if [[ "$(uname -s)" != 'Darwin' ]] && ! command -v espeak-ng >/dev/null 2>&1 && ! command -v espeak >/dev/null 2>&1 && [[ ! -x "${LOCAL_TTS_ROOT:-/workspace/.tools/espeak}/usr/bin/espeak-ng" ]]; then
  echo 'Seslendirme için espeak-ng kurulmalı: sudo apt install espeak-ng'
fi
echo 'Hazır. Mac masaüstü: npm start | Tarayıcı: npm run dev'
echo 'Testler: npm test'
