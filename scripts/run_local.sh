#!/usr/bin/env bash
# Run from project root. Loads .env if present, then runs: seed | fetch | assign [--dry-run]

set -e
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -z "$1" ]; then
  echo "Usage: $0 <seed|fetch|assign> [--dry-run]"
  echo "  seed   — generate companies via Claude, append to CSV"
  echo "  fetch  — fetch eligible accounts from Attio to CSV"
  echo "  assign — score & assign (use --dry-run to preview)"
  exit 1
fi

python -m src.main "$@"
