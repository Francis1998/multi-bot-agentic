# Configuration

Configuration is read from CLI flags first, then environment variables. Copy `.env.example` when running real providers.

## Providers

- `fake`: deterministic provider used by tests and demos.
- `openai`: calls the OpenAI chat completions API using `OPENAI_API_KEY`.
- `claude_code`: invokes the local Claude Code CLI configured by `CLAUDE_CODE_COMMAND`.
- `gemini`: calls the Gemini `generateContent` API using `GEMINI_API_KEY`.
- `kimi`: calls the Moonshot/Kimi chat completions API using `KIMI_API_KEY`.

## Safety Settings

- `MULTIBOT_MAX_STEPS`: maximum Observe -> Decide -> Act iterations.
- `MULTIBOT_TIMEOUT_SECONDS`: per-provider timeout budget.
- `MULTIBOT_MAX_PROMPT_CHARS`: maximum accepted goal size.
- `MULTIBOT_EVENT_LOG`: sqlite file used for durable events.
