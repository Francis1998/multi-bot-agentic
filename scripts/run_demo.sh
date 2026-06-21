#!/usr/bin/env bash
set -euo pipefail

mkdir -p demo-output
rm -f demo-output/demo.sqlite
PYTHONPATH=src python -m multi_bot_agentic.cli run \
  --goal "Create a launch checklist for a multi-provider agent orchestrator" \
  --provider fake \
  --max-steps 6 \
  --event-log demo-output/demo.sqlite

PYTHONPATH=src python -m multi_bot_agentic.cli replay --event-log demo-output/demo.sqlite
PYTHONPATH=src python -m multi_bot_agentic.cli replay --event-log demo-output/demo.sqlite --format text
PYTHONPATH=src python -m multi_bot_agentic.cli report --event-log demo-output/demo.sqlite
