#!/usr/bin/env bash
set -euo pipefail

ruff check .
ruff format --check .
mypy src tests
pytest
multi-bot-agentic run \
  --goal "Create a launch checklist for an AI agent platform" \
  --provider fake \
  --max-steps 5 \
  --event-log /tmp/multi-bot-agentic-check.sqlite
