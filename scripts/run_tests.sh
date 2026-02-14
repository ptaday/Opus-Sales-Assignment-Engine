#!/usr/bin/env bash
# Run tests from project root. Usage: ./scripts/run_tests.sh [unit|api|all] [--coverage]
# - unit   — unit tests only (default; no live APIs)
# - api    — API tests only (requires ATTIO_API_TOKEN / ANTHROPIC_API_KEY)
# - all    — unit + API (API tests skip if credentials missing)
# - --coverage — with unit, show coverage (only applies to unit/all)

set -e
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

MODE="${1:-unit}"
COVERAGE=""
[ "${2:-}" = "--coverage" ] && COVERAGE="--cov=src --cov-report=term-missing"

case "$MODE" in
  unit)
    echo "Running unit tests..."
    pytest tests/unit/ -v $COVERAGE
    ;;
  api)
    echo "Running API tests (credentials required)..."
    pytest tests/api/ -v -m api
    ;;
  all)
    echo "Running all tests..."
    pytest tests/ -v $COVERAGE
    ;;
  *)
    echo "Usage: $0 <unit|api|all> [--coverage]"
    echo "  unit       — unit tests only (default)"
    echo "  api        — live API tests only"
    echo "  all        — unit + API"
    echo "  --coverage — show coverage (with unit or all)"
    exit 1
    ;;
esac
