#!/usr/bin/env bash
# Portfolio verification — lint + tests (no Docker)
set -euo pipefail
cd "$(dirname "$0")/.."
echo "==> ruff"
ruff check .
echo "==> pytest"
pytest tests/ -q --tb=line
echo "==> import multi_bot_agentic"
python -c "import multi_bot_agentic"
echo "Portfolio checks passed."
