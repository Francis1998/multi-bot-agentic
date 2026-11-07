# Use Case: An Auditable Release-Readiness Bot That Uses MCP Tools

**Scenario.** Before each release, a team wants a bot that pulls their release notes from an internal
knowledge source and drafts a readiness checklist. Every step must be explainable afterwards: which rule chose
each action, which tool ran, with what arguments, and what came back. The knowledge source is exposed as an
[MCP](https://modelcontextprotocol.io) server, so the same server can serve Claude Desktop or Cursor too.

**What this shows:**
- MCP tool discovery.
- A deterministic Observe → Decide → Act run that calls an MCP tool.
- The durable audit trail (`replay`/`report`).
- A tool denylist, enforced by the decision engine.
- An offline regression gate (`eval`).

Steps 1–5 were executed from the repository root on 2026-11-07, and the output shown is the real output. They
use the deterministic `fake` provider, so they work offline and in CI. Step 6 needs your own API key, so it is
shown without output.

## 1. Discover the tools the MCP server exposes

The bundled demo server (`examples/mcp/notes_server.py`) speaks the stateless MCP 2026-07-28 protocol.
`examples/mcp/mcp.json` uses the Claude Desktop `mcpServers` format, plus an allowlist and limits:

```json
{"mcpServers": {"notes": {"command": "python3", "args": ["notes_server.py"], "cwd": ".",
  "allowedTools": ["search_notes", "word_count"], "callTimeoutSeconds": 10, "maxResultBytes": 4096}}}
```

```text
$ multi-bot-agentic mcp-tools --mcp-config examples/mcp/mcp.json
server notes: modern 2026-07-28 (notes-demo/1.0.0), 2 tools
  - mcp__notes__search_notes(query: string (required), limit: integer)
      [MCP notes] Search the demo team notes by keyword and return matching note titles and t…
  - mcp__notes__word_count(text: string (required))
      [MCP notes] Count the words in a text.
```

The client detected the protocol era with a `server/discover` probe. A legacy server would have been handled
through the `initialize` handshake instead; see the [MCP guide](../guides/MCP_TOOLS_GUIDE.md#protocol-era-compatibility).

## 2. Run the bot

With `--provider fake`, the deterministic fake model requests the tool named in `MULTIBOT_FAKE_TOOL`, passing
the goal as its payload. A real model picks tools from the catalog in its prompt instead.

```text
$ MULTIBOT_FAKE_TOOL=mcp__notes__search_notes multi-bot-agentic run --provider fake --mcp-config examples/mcp/mcp.json --goal "release checklist" --event-log demo-output/release.sqlite --run-id release-1
mcp: notes modern 2026-07-28 (2 tools)
{
  "run_id": "release-1",
  "state": "succeeded",
  "answer": "synthesized plan from 3 observations",
  "steps": 4,
  "event_log": "demo-output/release.sqlite"
}
```

## 3. Explain every decision afterwards

`replay` reads the SQLite event log and never calls a model or a tool:

```text
$ multi-bot-agentic replay --event-log demo-output/release.sqlite --run-id release-1 --format text | grep -E "decision|action_result"
005 deciding   decision action=call_llm rule=observe.no-model-output
008 acting     action_result kind=llm
014 deciding   decision action=call_tool rule=model.requested-tool
017 acting     action_result kind=tool target=mcp__notes__search_notes ok=true mcp=notes/search_notes era=modern
024 deciding   decision action=call_llm rule=tool.result-needs-synthesis
027 acting     action_result kind=llm
035 deciding   decision action=finish rule=model.done-or-budget
```

`report` summarizes the same run as JSON (abridged):

```text
$ multi-bot-agentic report --event-log demo-output/release.sqlite --run-id release-1
{
  "runs": [
    {
      "run_id": "release-1",
      "final_state": "succeeded",
      "event_count": 37,
      ...
      "tool_calls": [
        {
          "tool": "mcp__notes__search_notes",
          "ok": true
        }
      ],
      "answer": "synthesized plan from 3 observations"
    }
  ]
}
```

`replay --format json` includes the full `action_result` payload: the tool output, `mcp_arguments`, `mcp_era`,
`mcp_protocol_version`, `duration_ms`, and whether the result was truncated.

## 4. Lock the server down

Hide a tool with `deniedTools`. Hidden tools are never wrapped, so even a model that asks for one by name can't
call it. Save this as `demo-output/mcp-locked.json` (`cwd` is resolved relative to the config file):

```json
{"mcpServers": {"notes": {"command": "python3", "args": ["../examples/mcp/notes_server.py"], "cwd": ".",
  "deniedTools": ["word_count"]}}}
```

```text
$ multi-bot-agentic mcp-tools --mcp-config demo-output/mcp-locked.json
server notes: modern 2026-07-28 (notes-demo/1.0.0), 1 tool, 1 hidden by allow/deny lists
  - mcp__notes__search_notes(query: string (required), limit: integer)
      [MCP notes] Search the demo team notes by keyword and return matching note titles and t…
$ MULTIBOT_FAKE_TOOL=mcp__notes__word_count multi-bot-agentic run --provider fake --mcp-config demo-output/mcp-locked.json --goal "count these words" --max-steps 3 --event-log demo-output/locked.sqlite --run-id locked-1
mcp: notes modern 2026-07-28 (1 tool)
{
  "run_id": "locked-1",
  "state": "succeeded",
  "answer": "TOOL:mcp__notes__word_count:count these words",
  "steps": 3,
  "event_log": "demo-output/locked.sqlite"
}
$ multi-bot-agentic replay --event-log demo-output/locked.sqlite --run-id locked-1 --event-type decision --format text
005 deciding   decision action=call_llm rule=observe.no-model-output
014 deciding   decision action=call_llm rule=model.disallowed-tool-request
024 deciding   decision action=finish rule=model.done-or-budget
```

The denied tool never ran. The engine recorded `model.disallowed-tool-request` and asked the model for another
action. The fake model keeps asking for the same tool, so the step budget ends the run with the last model text
as the answer. A real model would pick an allowed tool or answer directly.

## 5. Gate releases on an offline evaluation

The golden-path evaluation replays scripted scenarios through the real runtime and scores tool sequences and
answers. It needs no network or API keys, so it can block a release in CI. `eval` exits with `2` when any
scenario fails, so gate on the command's own exit status. Don't pipe it straight into `head`, because a plain
pipeline reports `head`'s status instead:

```text
$ multi-bot-agentic eval --event-log-dir demo-output/eval-logs > demo-output/eval.json; echo "exit=$?"
exit=0
$ head -5 demo-output/eval.json
{
  "pass_rate": 1.0,
  "mean_tool_sequence_score": 1.0,
  "mean_answer_score": 1.0,
  "scenarios": [
```

## 6. Switch to a real model

The same command works with a live provider. Adapters send only parameters the current models accept: no
`temperature`/`top_p`/`top_k` (see [Configuration](../CONFIGURATION.md#provider-parameter-rules)).

```bash
export OPENAI_API_KEY=...               # default model: gpt-6.1-sol
multi-bot-agentic run --provider openai --mcp-config examples/mcp/mcp.json \
  --goal "Find our release checklist notes and turn them into a go/no-go list" \
  --event-log demo-output/release.sqlite --run-id release-live
```

To use the official reference servers (via `npx`/`uvx`) instead of the demo server, see
`examples/mcp/mcp.official.json` and the [MCP Tool Bridge Guide](../guides/MCP_TOOLS_GUIDE.md).

## Why this is safe to run

- The model never executes anything itself. It emits `TOOL:<name>:<payload>`, and the deterministic engine checks
  the allowlist before any call.
- MCP servers start with a least-privilege environment (provider API keys aren't inherited), per-call timeouts,
  a result byte cap, and process-group cleanup.
- Every decision and tool call is recorded with its rule ID, so the audit trail doesn't depend on model
  transcripts.
