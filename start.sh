#!/bin/bash
set -e

cd "$(dirname "$0")"

fnm use 22

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-5000}"

cd frontend
pnpm build

cd ..
uv run gunicorn -w 4 -b "$HOST:$PORT" main:app