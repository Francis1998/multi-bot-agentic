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
  --run-id check-smoke \
  --event-log /tmp/multi-bot-agentic-check.sqlite
PYTHONPATH=src python -m multi_bot_agentic.cli replay \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --event-type decision \
  --format text
PYTHONPATH=src python -m multi_bot_agentic.cli report \
  --event-log /tmp/multi-bot-agentic-check.sqlite
PYTHONPATH=src python -m multi_bot_agentic.cli trace \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --format otlp-json
PYTHONPATH=src python -m multi_bot_agentic.cli trace \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --format mermaid
PYTHONPATH=src python -m multi_bot_agentic.cli history \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-smoke
PYTHONPATH=src python -m multi_bot_agentic.cli fork \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-smoke \
  --at-step 1 \
  --new-run-id check-smoke-fork \
  --goal "Create a rollback checklist for an AI agent platform" \
  --provider fake \
  --max-steps 6
PYTHONPATH=src python -m multi_bot_agentic.cli report \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-smoke-fork
PYTHONPATH=src python -m multi_bot_agentic.cli trace \
  --event-log /tmp/multi-bot-agentic-check.sqlite \
  --run-id check-smoke-fork \
  --format mermaid
