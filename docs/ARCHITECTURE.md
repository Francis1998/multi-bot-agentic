# Architecture

The runtime is a deterministic control plane around LLM and tool adapters. The LLM can propose text such as `TOOL:echo:<payload>` or `DONE:<answer>`, but it never directly executes tools.

## Runtime Loop

The core loop lives in `AgentRunner.run()`:

```text
Observe -> Decide -> Act -> Observe -> ...
```

## Observe

The runner gathers observations from the initial goal, provider outputs, and tool results. Observations are durable events.

Observation examples:

- user goal
- normalized provider output
- tool result
- cancellation signal

## Decide

The deterministic decision engine evaluates observations and safety policy. It emits a `Decision` with a `RationaleTrace` that records why an action was chosen and which alternatives were rejected.

Current deterministic rules:

- `safety.cancel-file`: cancel if the configured cancellation file exists.
- `observe.no-model-output`: call the selected provider first.
- `model.requested-tool`: call an allowlisted tool for `TOOL:<name>:<payload>`.
- `tool.result-needs-synthesis`: send tool results back to the provider.
- `model.done-or-budget`: finish on `DONE:<answer>` or final budget step.
- `model.needs-followup`: call the provider again for non-final text.

## Act

Actions are limited to provider calls, allowlisted tools, finish, fail, or cancel. The LLM never directly invokes tools.

## Durable Event Log

The sqlite event log stores every lifecycle transition, observation, decision, action request, action result, and failure with a per-run sequence number. A run can be replayed without calling a provider.

## Provider Adapters

All providers implement one interface:

```text
ModelRequest -> ModelOutput
```

Adapters normalize GPT/OpenAI, Claude Code CLI, Gemini, Kimi/Moonshot, and the deterministic fake provider.

## State Machine

```text
created
  -> observing
  -> deciding
  -> acting
  -> observing
  -> deciding
  -> succeeded | failed | cancelled
```

Invalid transitions raise `InvalidTransitionError` and are covered by tests.

## Replay

Replay reads sqlite events and prints them in sequence. Replay never calls providers or tools, so it is safe to run in CI and postmortems.

## Bot Handoff

Optional `BotSpec` registries let the decision engine accept `HANDOFF:bot_id:summary`. The runner swaps `active_bot_id` and `SafetyPolicy.allowed_tools` for the rest of that run without changing the ODA loop shape. Every `run()` starts again from the constructor's `active_bot_id`, and `resume()` restores the bot recorded in the checkpoint.

## MCP Tool Bridge

`multi_bot_agentic.mcp` lets bots use tools from any Model Context Protocol server without new dependencies:

- `StdioMcpClient` launches a server in its own process group and speaks newline-delimited JSON-RPC over stdio.
  It is dual-era: a `server/discover` probe selects the stateless MCP 2026-07-28 protocol (per-request `_meta`,
  `-32022` version retry), and any other answer or a probe timeout falls back to the legacy
  `initialize` + `notifications/initialized` handshake. The era is cached per server process.
- `McpToolset` starts every server in a Claude-Desktop-style `mcpServers` config, follows `tools/list`
  pagination, applies `allowedTools`/`deniedTools`, and wraps each tool as `McpToolAdapter` named
  `mcp__<server>__<tool>`.
- The CLI (`run`/`resume --mcp-config`) merges these adapters into the tool registry, adds them to
  `SafetyPolicy.allowed_tools`, and passes their `ToolSpec` catalog to the runner. The runner advertises only
  the currently allowed specs in `ModelRequest.tools`, and provider prompts render them as an
  `Available tools` section.

Execution still flows through the unchanged decision engine (`TOOL:<name>:<payload>`) and event log, so MCP
calls get rationale traces, replay, and resume like any other tool. See
[MCP Tool Bridge Guide](guides/MCP_TOOLS_GUIDE.md).

## HITL Approval Gate

`HitlApprovalGate` optionally pauses sensitive tool calls behind file-backed JSON approvals (`pending`/`approved`/`rejected`). v1 is caller-driven and does not require runner rewiring.

## Parallel Fan-Out

`ParallelFanOut` optionally fans capped tasks across a thread pool with caller-supplied workers. Results preserve input order; worker exceptions map to `ok=False` without a graph runtime.

## Checkpoint resume

Durable checkpoint resume for ODA runs is available via `resume`. Only interrupted runs (no
`run_completed`/`run_failed`/`run_cancelled` event) continue; a finished run returns its recorded
outcome without executing anything. See `docs/guides/CHECKPOINT_RESUME_GUIDE.md`.

## SharedBlackboard

In-process typed scratchpad for multi-bot coordination with revision counters and size caps. See `docs/guides/SHARED_BLACKBOARD_GUIDE.md`.
