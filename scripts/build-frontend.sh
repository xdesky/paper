#!/bin/sh
set -eu
cd "$(dirname "$0")/../frontend"
if command -v node >/dev/null 2>&1; then
  NODE_EXE=node
elif [ -x /Users/datnv/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node ]; then
  NODE_EXE=/Users/datnv/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node
else
  echo 'Cần Node.js 22 trở lên.' >&2
  exit 1
fi
"$NODE_EXE" node_modules/typescript/bin/tsc -b
"$NODE_EXE" node_modules/vite/bin/vite.js build
