# Configuration

Configuration is read from CLI flags first, then environment variables. Copy `.env.example` when running real providers.

```bash
cp .env.example .env
```

## Providers

- `fake`: deterministic provider used by tests and demos.
- `openai`: calls the OpenAI chat completions API using `OPENAI_API_KEY`.
- `claude_code`: invokes the local Claude Code CLI configured by `CLAUDE_CODE_COMMAND`.
- `gemini`: calls the Gemini `generateContent` API using `GEMINI_API_KEY`.
- `kimi`: calls the Moonshot/Kimi chat completions API using `KIMI_API_KEY`.

## Provider Commands

Fake:

```bash
multi-bot-agentic run --goal "Draft a launch checklist" --provider fake
```

OpenAI GPT:

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-5.5
multi-bot-agentic run --goal "Draft a launch checklist" --provider openai
```

Claude Code CLI:

```bash
export CLAUDE_CODE_COMMAND="claude"
multi-bot-agentic run --goal "Draft a launch checklist" --provider claude_code
```

Gemini:

```bash
export GEMINI_API_KEY=...
export GEMINI_MODEL=gemini-2.5-flash
multi-bot-agentic run --goal "Draft a launch checklist" --provider gemini
```

Kimi / Moonshot:

```bash
export KIMI_API_KEY=...
multi-bot-agentic run --goal "Draft a launch checklist" --provider kimi
```

## Safety Settings

- `MULTIBOT_MAX_STEPS`: maximum Observe -> Decide -> Act iterations.
- `MULTIBOT_TIMEOUT_SECONDS`: per-provider timeout budget.
- `MULTIBOT_MAX_PROMPT_CHARS`: maximum accepted goal size.
- `MULTIBOT_EVENT_LOG`: sqlite file used for durable events.

## Notes

The fake provider is the only provider exercised in CI. Live provider calls require credentials and are intentionally operator-triggered.
