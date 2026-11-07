# Configuration

Configuration is read from CLI flags first, then environment variables. Copy `.env.example` when running real providers.

```bash
cp .env.example .env
```

## Providers

- `fake`: deterministic provider used by tests and demos.
- `openai`: calls the OpenAI chat completions API using `OPENAI_API_KEY`.
- `claude_code`: invokes the local Claude Code CLI configured by `CLAUDE_CODE_COMMAND` (default `claude -p`). The
  prompt is written to the command's stdin, so the command must run Claude Code in print mode (`-p`/`--print`, its
  non-interactive mode); plain `claude` starts an interactive session.
- `gemini`: calls the Gemini `generateContent` API using `GEMINI_API_KEY`.
- `kimi`: calls the Moonshot/Kimi chat completions API using `KIMI_API_KEY`.

## Current Model Stack

Defaults were verified against the providers' documentation on 2026-11-06. Override any of them with the
environment variables below. For prices, see each provider's pricing page.

| Provider | Default here | Other current models | Notes |
| --- | --- | --- | --- |
| OpenAI ([models](https://developers.openai.com/api/docs/guides/latest-model)) | `gpt-6.1-sol` | `gpt-6-astra` (highest intelligence), `gpt-6.1-terra` (fast), `gpt-6-luna` (fastest, lowest cost) | Reasoning models: the adapter sends `max_completion_tokens` (default 32768, which covers reasoning and visible output; set it with `OPENAI_MAX_COMPLETION_TOKENS`) and no `temperature`/`top_p` |
| Anthropic via Claude Code CLI ([models](https://platform.claude.com/docs/en/models/overview)) | the CLI's own setting | `claude-opus-5-5` (recommended default), `claude-sonnet-5-5`, `claude-haiku-5-5`, `claude-fable-5-1` | Choose one with `CLAUDE_CODE_COMMAND="claude -p --model claude-opus-5-5"` (keep `-p`, print mode) |
| Google Gemini ([models](https://aistudio.google.com/docs/models)) | `gemini-3.8-flash` | `gemini-4-argon` (flagship reasoning), `gemini-3.6-flash`, `gemini-3.5-flash-lite` | `generateContent` API |
| Kimi / Moonshot ([parameters](https://platform.kimi.ai/docs/api/models-overview.md)) | `kimi-k3.1-pro` | `kimi-k3.1-pro-highspeed`, `kimi-k3` | K3 fixes `temperature`/`top_p`/`n`/penalties and always reasons, so none of those are sent. `KIMI_MAX_COMPLETION_TOKENS` sets the budget (default 32768). K2 is being retired |

If you override `OPENAI_MODEL` with an older model whose output limit is below 32768 tokens, lower
`OPENAI_MAX_COMPLETION_TOKENS` to match. For example, `gpt-4o` documents a 16384-token output limit.

## Provider Parameter Rules

Current models reject or ignore sampling parameters, so no adapter sends `temperature`, `top_p`, `top_k`, `n`,
penalties, or logprobs. `tests/test_adapters.py` guards this for every provider.

| Provider | Rule (official docs, checked 2026-11-07) | What the adapter does |
| --- | --- | --- |
| OpenAI GPT-6 | When reasoning effort is not `none`, remove `temperature`, `top_p`, and `top_logprobs` (and `logprobs` on Chat Completions). `gpt-6.1-sol` and `gpt-6-astra` support only `low`..`max`. `gpt-6.1-terra` and `gpt-6-luna` accept `temperature` only with `reasoning_effort: none` ([GPT-6 guide](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md)) | Sends only `model`, `messages`, and `max_completion_tokens` |
| Anthropic Claude 5.5 | A non-default `temperature`, `top_p`, or `top_k` returns 400. Since API version 2026-10-21, any of them returns 400 on every model. Use `output_config.effort` instead ([thinking](https://platform.claude.com/docs/en/build-with-claude/thinking.md), [effort](https://platform.claude.com/docs/en/build-with-claude/effort.md)) | The Claude Code CLI adapter runs only the configured command (for example `claude -p --model claude-opus-5-5`) and adds no flags of its own |
| Google Gemini 3.x | Remove `temperature`, `top_p`, and `top_k`; if provided, they are ignored ([Gemini 3 guide](https://aistudio.google.com/docs/gemini-3.md)) | Sends only `contents`, with no `generationConfig` |
| Kimi K3 | `temperature` is fixed at 1.0 (any other value errors), as are `top_p`, `n`, and penalties. Use top-level `reasoning_effort` (`low`/`high`/`max`) ([parameters](https://platform.kimi.ai/docs/api/models-overview.md)) | Sends only `model`, `messages`, and `max_completion_tokens` |

## Provider Commands

Fake:

```bash
multi-bot-agentic run --goal "Draft a launch checklist" --provider fake
```

OpenAI GPT:

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-6.1-sol
multi-bot-agentic run --goal "Draft a launch checklist" --provider openai
```

Claude Code CLI:

```bash
export CLAUDE_CODE_COMMAND="claude -p --model claude-opus-5-5"
multi-bot-agentic run --goal "Draft a launch checklist" --provider claude_code
```

Gemini:

```bash
export GEMINI_API_KEY=...
export GEMINI_MODEL=gemini-3.8-flash
multi-bot-agentic run --goal "Draft a launch checklist" --provider gemini
```

Kimi / Moonshot:

```bash
export KIMI_API_KEY=...
export KIMI_MODEL=kimi-k3.1-pro
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

## Trace Export

`multi-bot-agentic trace` reads one run from `--event-log` and exports it. It has no environment variables of
its own. Every setting is a flag:

| Flag | Default | Meaning |
| --- | --- | --- |
| `--run-id` | most recently active run | Run to export |
| `--format` | `otlp-json` | `otlp-json` (OpenTelemetry `ExportTraceServiceRequest`) or `mermaid` (`sequenceDiagram`) |
| `--output` | stdout | Write the output to a file |
| `--include-content` | off | Add the goal, model inputs and outputs, tool arguments and results, and handoff summaries, all redacted |
| `--agent-name` | none | `gen_ai.agent.name` of the root `invoke_agent` span |
| `--otlp-endpoint` | none | Also POST the OTLP/JSON to this `http(s)` URL, for example `http://localhost:4318/v1/traces` (Jaeger, Tempo) or `https://cloud.langfuse.com/api/public/otel/v1/traces` |
| `--otlp-header` | none | Repeatable `KEY=VALUE` request header. `${VAR}` and `${VAR:-default}` are expanded from the environment, so `--otlp-header 'Authorization=Bearer ${OTLP_TOKEN}'` keeps the token out of shell history. Values are never printed |
| `--otlp-timeout` | `10` | OTLP request timeout in seconds |

The standard `OTEL_EXPORTER_OTLP_*` variables are not read: `trace` only pushes when `--otlp-endpoint` is given,
so credentials meant for another collector are never sent by accident. See the
[OpenTelemetry Trace Export Guide](guides/OTEL_TRACE_EXPORT_GUIDE.md) for backends, the span model, and privacy.

## Safety Settings

- `MULTIBOT_MAX_STEPS`: maximum Observe -> Decide -> Act iterations.
- `MULTIBOT_TIMEOUT_SECONDS`: per-provider timeout budget.
- `MULTIBOT_MAX_PROMPT_CHARS`: maximum accepted goal size.
- `MULTIBOT_EVENT_LOG`: sqlite file used for durable events.
- `MULTIBOT_CANCEL_FILE`: optional file path; if the file exists, the next decision cancels the run.

## Notes

The fake provider is the only provider exercised in CI. Live provider calls require credentials and are intentionally operator-triggered.
