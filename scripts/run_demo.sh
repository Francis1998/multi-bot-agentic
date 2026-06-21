#!/usr/bin/env bash
set -euo pipefail

mkdir -p demo-output
multi-bot-agentic run \
  --goal "Create a launch checklist for a multi-provider agent orchestrator" \
  --provider fake \
  --max-steps 6 \
  --event-log demo-output/demo.sqlite

multi-bot-agentic replay --event-log demo-output/demo.sqlite
