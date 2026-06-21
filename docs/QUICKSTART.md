# Quickstart

## Install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Verify

```bash
ruff check .
ruff format --check .
mypy src tests
pytest
```

## Run A Deterministic Demo

```bash
multi-bot-agentic run \
  --goal "Create a launch checklist for an AI agent platform" \
  --provider fake \
  --event-log data/runs.sqlite
```

## Replay The Durable Event Log

```bash
multi-bot-agentic replay --event-log data/runs.sqlite
```
