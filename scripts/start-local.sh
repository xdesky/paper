#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  echo 'Thiếu .venv: xem README.md để cài dependencies.' >&2
  exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
  echo 'Thiếu frontend/dist: chạy scripts/build-frontend.sh trước.' >&2
  exit 1
fi
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
exec .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8005
