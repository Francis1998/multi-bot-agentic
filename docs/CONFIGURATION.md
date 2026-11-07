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
export GEMINI_MODEL=gemini-3.5-flash
multi-bot-agentic run --goal "Draft a launch checklist" --provider gemini
```

Kimi / Moonshot:

```bash
export KIMI_API_KEY=...
multi-bot-agentic run --goal "Draft a launch checklist" --provider kimi
```

## MCP Servers

Pass a Claude-Desktop-style `mcpServers` JSON file to expose MCP tools to a run:

```bash
multi-bot-agentic mcp-tools --mcp-config examples/mcp/mcp.json
multi-bot-agentic run --goal "Find the release checklist" --provider openai --mcp-config examples/mcp/mcp.json
```

Per-server keys: `command`, `args`, `env`, `cwd`, `allowedTools`, `deniedTools`, `callTimeoutSeconds`
(default 30), `startupTimeoutSeconds` (default 30), `maxResultBytes` (default 16384), `redactResults`
(default false), and `disabled`. `${VAR}` and `${VAR:-default}` placeholders are expanded from the
environment. Servers inherit only `HOME`, `LOGNAME`, `PATH`, `SHELL`, `TERM`, and `USER`. Pass anything else
through `env`. Full reference: [MCP Tool Bridge Guide](guides/MCP_TOOLS_GUIDE.md#configuration).

- `MULTIBOT_FAKE_TOOL`: tool the fake provider requests on its first turn (default `checklist`). Set it to an
  MCP tool such as `mcp__notes__search_notes` for offline MCP demos.

## Safety Settings

- `MULTIBOT_MAX_STEPS`: maximum Observe -> Decide -> Act iterations.
- `MULTIBOT_TIMEOUT_SECONDS`: per-provider timeout budget.
- `MULTIBOT_MAX_PROMPT_CHARS`: maximum accepted goal size.
- `MULTIBOT_EVENT_LOG`: sqlite file used for durable events.
- `MULTIBOT_CANCEL_FILE`: optional file path; if the file exists, the next decision cancels the run.

## Notes

The fake provider is the only provider exercised in CI. Live provider calls require credentials and are intentionally operator-triggered.
