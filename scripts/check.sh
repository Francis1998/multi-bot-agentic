#!/usr/bin/env bash
set -euo pipefail

ruff check .
ruff format --check .
mypy src tests
pytest
rm -f /tmp/multi-bot-agentic-check.sqlite
PYTHONPATH=src python -m multi_bot_agentic.cli run \
  --goal "Create a launch checklist for an AI agent platform" \
  --provider fake \
  --max-steps 5 \
  --event-log /tmp/multi-bot-agentic-check.sqlite
PYTHONPATH=src python -m multi_bot_agentic.cli replay \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --event-type decision \
  --format text
PYTHONPATH=src python -m multi_bot_agentic.cli report \
  --event-log /tmp/multi-bot-agentic-check.sqlite
