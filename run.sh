#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install -r requirements.txt

if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs)
fi

: "${BOT_TOKEN:?BOT_TOKEN topilmadi. .env ga BOT_TOKEN=... yozing}"
: "${OWNER_ID:?OWNER_ID topilmadi. .env ga OWNER_ID=... yozing}"

exec python main.py
