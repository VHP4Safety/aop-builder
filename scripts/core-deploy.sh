#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Create it from .env.example first." >&2
  exit 1
fi

cd "$ROOT_DIR/apps/ai-core"
exec docker compose --env-file "$ENV_FILE" -f docker-compose-deploy.yml up -d "$@"
