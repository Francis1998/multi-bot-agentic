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

## Export A Run As A Trace

```bash
# Mermaid sequence diagram (GitHub renders it inside a mermaid code block)
multi-bot-agentic trace --event-log data/runs.sqlite --format mermaid

# OpenTelemetry GenAI trace as OTLP/JSON, printed or written to a file
multi-bot-agentic trace --event-log data/runs.sqlite --output demo-output/trace.json

# Push it to an OTLP/HTTP endpoint, for example Jaeger
docker run --rm -p 16686:16686 -p 4318:4318 cr.jaegertracing.io/jaegertracing/jaeger:2.23.0
multi-bot-agentic trace --event-log data/runs.sqlite --otlp-endpoint http://localhost:4318/v1/traces
```

Without `--run-id`, `trace` exports the most recently active run. Prompts, outputs, and tool payloads are only
included with `--include-content`, and are redacted. See
[OpenTelemetry Trace Export Guide](guides/OTEL_TRACE_EXPORT_GUIDE.md).

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

## Regenerate Tool-Guide Demo GIFs

```bash
python scripts/render_guide_demos.py --list   # embedded GIFs that are missing or placeholders
python scripts/render_guide_demos.py          # render them
python scripts/render_guide_demos.py docs/guides/BASE58_TOOL_GUIDE.md  # redraw one guide's GIF
```

Each GIF is a terminal transcript of the guide's first python example, run for real with `PYTHONPATH=src`,
a timeout, and sockets disabled. The script uses only the standard library (no `ffmpeg`). An example that fails
or prints nothing is reported as a docs bug instead of being drawn.

## Try A Live Provider

```bash
export OPENAI_API_KEY=...
multi-bot-agentic run \
  --goal "Return DONE: with a short release checklist" \
  --provider openai \
  --max-steps 4
```

Current defaults: `gpt-6.1-sol` (OpenAI), `gemini-3.8-flash` (Gemini), and `kimi-k3.1-pro` (Kimi). For Claude Code,
choose the model with `CLAUDE_CODE_COMMAND="claude -p --model claude-opus-5-5"` (or `claude-sonnet-5-5`). Keep `-p`
(print mode): plain `claude` starts an interactive session and cannot answer the prompt piped to it. Override
any default with `OPENAI_MODEL`, `GEMINI_MODEL`, or `KIMI_MODEL`. See [Configuration](CONFIGURATION.md#current-model-stack).

Live providers are not required for tests or CI.
