#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT/docker-compose.dev.yml"

echo "Building and starting containers..."
docker compose -f "$COMPOSE_FILE" up --build -d

echo "Waiting for server to become available at http://localhost:8000 ..."
for i in {1..30}; do
  if curl -sSf http://localhost:8000/ >/dev/null 2>&1; then
    echo "Server is up"
    break
  fi
  sleep 1
done

if [[ "$OSTYPE" == "darwin"* ]]; then
  open http://localhost:8000
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  xdg-open http://localhost:8000 || true
else
  # fallback for Windows via start
  cmd.exe /C start http://localhost:8000 || true
fi

echo "To stop: docker compose -f $COMPOSE_FILE down"
