#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

echo "Delegating to scripts/start_server.py (centralized starter)."

# Prefer the system 'python3' or 'python' command to run the central starter.
if command -v python3 >/dev/null 2>&1; then
    python3 "$ROOT/scripts/start_server.py"
elif command -v python >/dev/null 2>&1; then
    python "$ROOT/scripts/start_server.py"
else
    echo "No Python interpreter found on PATH. Please install Python 3 and ensure 'python' or 'python3' is available." >&2
    exit 1
fi
