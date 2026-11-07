# Quickstart

## Install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Verify

```bash
scripts/check.sh
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
multi-bot-agentic replay --event-log data/runs.sqlite --format text
multi-bot-agentic replay --event-log data/runs.sqlite --event-type decision --format text
multi-bot-agentic report --event-log data/runs.sqlite
```

## Run The Scripted Demo

```bash
scripts/run_demo.sh
```

The demo uses the fake provider and writes a replayable sqlite event log under `demo-output/`.

## Regenerate The README GIF

```bash
python scripts/render_demo_gif.py
```

The renderer uses stdlib Python for pixel frames and `ffmpeg` to stitch them into `docs/demo.gif`.

## Try A Live Provider

```bash
export OPENAI_API_KEY=...
multi-bot-agentic run \
  --goal "Return DONE: with a short release checklist" \
  --provider openai \
  --max-steps 4
```

Current defaults: `gpt-6.1-sol` (OpenAI), `gemini-3.8-flash` (Gemini), and `kimi-k3.1-pro` (Kimi). For Claude Code,
choose the model with `CLAUDE_CODE_COMMAND="claude --model claude-opus-5-5"` (or `claude-sonnet-5-5`). Override
any default with `OPENAI_MODEL`, `GEMINI_MODEL`, or `KIMI_MODEL`. See [Configuration](CONFIGURATION.md#current-model-stack).

Live providers are not required for tests or CI.
