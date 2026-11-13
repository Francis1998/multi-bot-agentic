# Problems This Solves

Eleven everyday agent-engineering problems and how multi-bot-agentic addresses each one. Problems 1-10 were
moved verbatim from the former README. For an end-to-end walkthrough with real commands, see
[USE-CASE-mcp-release-readiness.md](USE-CASE-mcp-release-readiness.md).

### 1. "My agent did something, but I cannot explain why."

LLM-first agents often skip straight from prompt to action. When something goes wrong, the transcript may show what the model said, but not which control rule allowed the action.

`multi-bot-agentic` writes every decision as a durable event with a `RationaleTrace`: rule id, observations used, rejected actions, and explanation. You can replay the run later and inspect exactly why the engine chose `call_llm`, `call_tool`, `finish`, or `cancel`.

```bash
multi-bot-agentic replay --event-log data/runs.sqlite --event-type decision --format text
```

### 2. "I want to use AI agents, but I do not want the model directly executing tools."

Many agent frameworks let the model choose and invoke tools directly. That is convenient, but risky for production workflows where tool access should be explicit, bounded, and auditable.

This repo treats model output as an observation. The deterministic decision engine interprets constrained text like `TOOL:checklist:<payload>`, checks the safety policy, and only then executes an allowlisted tool adapter.

### 3. "I need the same agent flow to work with GPT-6, Claude 5.5, Gemini, and Kimi K3.1."

Provider-specific SDKs and response shapes make agent code hard to port. A prototype built around one model often leaks provider details into the orchestration layer.

`multi-bot-agentic` normalizes providers behind one adapter interface:

- `OpenAIAdapter` for GPT-6 (`gpt-6.1-sol` by default) and OpenAI-compatible chat completions.
- `ClaudeCodeCLIAdapter` for local Claude Code CLI workflows with `claude-opus-5-5`, `claude-fable-5-2`, or `claude-sonnet-5-5`.
- `GeminiAdapter` for Gemini `generateContent` (`gemini-3.8-flash` by default; `gemini-4-hydrogen` is Google's recommended upgrade and `gemini-4-carbon` its strongest reasoning model).
- `KimiAdapter` for Moonshot/Kimi K3.1 chat completions (`kimi-k3.1-pro` by default).
- `FakeLLMAdapter` for deterministic CI and demos.

The runner consumes all provider responses as `ModelOutput`, so orchestration logic stays provider-neutral.

### 4. "I need a safe demo path that does not require API keys."

Portfolio and CI demos should not depend on live model credentials, model availability, or network behavior.

The fake provider produces deterministic model-like outputs that the real runtime consumes. It still exercises Observe -> Decide -> Act, tool routing, safety checks, event logging, replay, and reports.

```bash
multi-bot-agentic run --goal "Create a launch checklist for an AI agent platform" --provider fake
```

### 5. "Agent runs fail silently or leave no durable audit trail."

Long-running agent tasks need post-run inspection. Without durable state, crashes and restarts turn into guesswork.

The sqlite event log records lifecycle transitions, observations, decisions, action requests, action results, failures, cancellations, and completion. Replay does not call any provider or tool, so postmortems are safe and deterministic.

```bash
multi-bot-agentic report --event-log data/runs.sqlite
```

### 6. "The agent keeps looping or spending tokens without finishing."

Unbounded agent loops are a common failure mode. They waste time, cost money, and make incident response harder.

`SafetyPolicy` bounds run scope with `max_steps`, provider/tool timeouts, prompt size limits, cancellation files, and tool allowlists. If the run reaches its budget, the decision engine finishes or fails through explicit lifecycle events.

### 7. "I need to compare AI provider behavior without rewriting my orchestration."

Teams often want to compare GPT-6.1 Sol, Gemini 3.8 Flash, Kimi K3.1 Pro, and Claude Opus 5.5, but provider-specific code makes comparisons noisy.

With provider adapters, you can keep the same runner, same decision engine, same event log, and same replay/report UX while swapping the provider:

```bash
multi-bot-agentic run --goal "Draft a migration plan" --provider openai
multi-bot-agentic run --goal "Draft a migration plan" --provider gemini
multi-bot-agentic run --goal "Draft a migration plan" --provider kimi
multi-bot-agentic run --goal "Draft a migration plan" --provider claude_code
```

### 8. "I want agents to produce useful artifacts, not just chat text."

Agent demos often end with prose. Real workflows need structured, repeatable artifacts.

The built-in `checklist` tool turns a goal into a deterministic launch checklist and records the tool result in the event log. It is intentionally simple, but it demonstrates the production pattern: model suggests, policy validates, adapter executes, event log records.

### 9. "I need a clean teaching or interview example for agent architecture."

Agent systems can become hard to explain when planning, tool use, model calls, retries, and state are mixed together.

This repo keeps the boundaries visible:

- `runner.py`: owns Observe -> Decide -> Act.
- `decision.py`: deterministic rules and rationale traces.
- `lifecycle.py`: state-machine transitions.
- `event_log.py`: durable sqlite events.
- `llm/`: provider adapters.
- `tools/`: allowlisted tool adapters.
- `safety.py`: bounds and cancellation.

### 10. "I need CI to prove the agent works without real provider credentials."

Live provider tests are useful, but they should not be required for every pull request.

CI runs lint, format, typecheck, tests, and a fake-provider smoke demo across Python 3.10, 3.11, and 3.12. Live provider calls remain operator-triggered because they require credentials and external systems.

### 11. "I want to see agent runs in our tracing backend, not a terminal."

Teams already watch services in Jaeger, Grafana Tempo, Langfuse, or Datadog, and other agent frameworks feed
those tools through OpenTelemetry. A durable log that can only be printed leaves agent runs outside that view,
and a text timeline makes it hard to see which bot handed off to whom.

`trace` exports any recorded run, even one that ran without tracing, as an OpenTelemetry trace that follows the
GenAI semantic conventions: an `invoke_agent` span per run and per bot, `chat` spans for model calls, and
`execute_tool` spans for built-in and MCP tools, each with the rule that chose it. The same run always exports
the same ids and bytes. Prompts, outputs, and tool payloads stay out unless you pass `--include-content`, and
then they are redacted. `--format mermaid` draws the run as a sequence diagram that GitHub renders inline.

```bash
multi-bot-agentic trace --event-log data/runs.sqlite --format mermaid
multi-bot-agentic trace --event-log data/runs.sqlite --otlp-endpoint http://localhost:4318/v1/traces
```

See the [OpenTelemetry Trace Export Guide](../guides/OTEL_TRACE_EXPORT_GUIDE.md).

### 12. "I want to retry from the middle of a run with another goal, bot, or provider, without re-running the start."

An agent run goes wrong at step 3, or the goal changes after the expensive research steps, or you want to see
how another provider would have continued. Re-running from scratch repeats every provider call and tool side
effect before that point, and `resume` only continues an interrupted run.

`fork` branches any recorded run after any step into a new run. It rebuilds the state after that step from the
event log without calling a provider, keeps the original untouched, and continues with a new goal, provider, bot,
or step budget. Bot scopes are re-checked against the current registry and safety policy. The new run records its
parent, the fork step, and digests of the events it inherited, so `report` shows the lineage and `trace` links
it to the parent's trace.

```bash
multi-bot-agentic history --event-log data/runs.sqlite --run-id demo
multi-bot-agentic fork --event-log data/runs.sqlite --run-id demo --at-step 2 --new-run-id demo-gemini --provider gemini
```

See the [Run Fork Guide](../guides/RUN_FORK_GUIDE.md).
