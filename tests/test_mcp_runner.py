"""End-to-end tests: the ODA runner calls MCP tools and records them durably."""

from __future__ import annotations

import sys
from pathlib import Path

from multi_bot_agentic.bots import BotSpec
from multi_bot_agentic.cli import build_runtime_tools
from multi_bot_agentic.eval.harness import ScriptedLLMAdapter
from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.mcp import McpToolset
from multi_bot_agentic.mcp.config import McpConfig, McpServerConfig
from multi_bot_agentic.models import ModelOutput, ModelRequest, RunState, ToolSpec
from multi_bot_agentic.runner import AgentRunner
from multi_bot_agentic.safety import SafetyPolicy

FIXTURES = Path(__file__).parent / "fixtures" / "mcp"


def _toolset() -> McpToolset:
    servers = (
        McpServerConfig(name="modern", command=sys.executable, args=(str(FIXTURES / "modern_server.py"),)),
        McpServerConfig(name="legacy", command=sys.executable, args=(str(FIXTURES / "legacy_server.py"),)),
    )
    toolset = McpToolset(McpConfig(servers=servers))
    toolset.start()
    return toolset


def test_run_calls_mcp_tool_and_records_it_in_the_event_log(tmp_path: Path) -> None:
    """The fake provider requests an MCP tool; decision, call, and result are all durable."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    with _toolset() as toolset:
        tools, policy, specs = build_runtime_tools(SafetyPolicy(max_steps=5), toolset)
        runner = AgentRunner(
            provider=FakeLLMAdapter(tool_name="mcp__legacy__shout"),
            event_log=log,
            tools=tools,
            safety_policy=policy,
            tool_specs=specs,
        )
        result = runner.run("ship the mcp bridge", run_id="mcp-run")
    events = log.list_events("mcp-run")
    log.close()

    assert result.state == RunState.SUCCEEDED
    decisions = [event.payload for event in events if event.event_type == "decision"]
    assert [item["rationale"]["rule_id"] for item in decisions] == [
        "observe.no-model-output",
        "model.requested-tool",
        "tool.result-needs-synthesis",
        "model.done-or-budget",
    ]
    assert decisions[1]["target"] == "mcp__legacy__shout"
    requested = [event.payload for event in events if event.event_type == "action_requested"]
    assert requested[1]["payload"] == {"text": "ship the mcp bridge"}
    (tool_result,) = [
        event.payload for event in events if event.event_type == "action_result" and event.payload.get("kind") == "tool"
    ]
    assert tool_result["tool"] == "mcp__legacy__shout"
    assert tool_result["ok"] is True
    assert tool_result["content"] == "SHIP THE MCP BRIDGE"
    assert tool_result["metadata"]["mcp_server"] == "legacy"
    assert tool_result["metadata"]["mcp_era"] == "legacy"
    assert tool_result["metadata"]["mcp_protocol_version"] == "2025-11-25"


def test_failed_mcp_tool_is_observed_and_the_model_recovers(tmp_path: Path) -> None:
    """An ``isError`` result is fed back to the model instead of failing the run."""

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    with _toolset() as toolset:
        tools, policy, specs = build_runtime_tools(SafetyPolicy(max_steps=6), toolset)
        runner = AgentRunner(
            provider=ScriptedLLMAdapter(
                ('TOOL:mcp__modern__fail:{"reason": "rate limited"}', 'TOOL:mcp__modern__add:{"a": 2, "b": 40}')
            ),
            event_log=log,
            tools=tools,
            safety_policy=policy,
            tool_specs=specs,
        )
        result = runner.run("add numbers after a failure", run_id="mcp-recover")
    tool_results = [
        (event.payload["tool"], event.payload["ok"], event.payload["content"])
        for event in log.list_events("mcp-recover")
        if event.event_type == "action_result" and event.payload.get("kind") == "tool"
    ]
    log.close()

    assert result.state == RunState.SUCCEEDED
    assert tool_results == [
        ("mcp__modern__fail", False, "tool failed: rate limited"),
        ("mcp__modern__add", True, "42"),
    ]


def test_provider_sees_only_mcp_tools_allowed_for_the_active_bot(tmp_path: Path) -> None:
    """The advertised catalog follows the live allowlist, including bot scoping."""

    seen: list[tuple[ToolSpec, ...]] = []

    class CapturingProvider:
        provider_name = "fake"

        def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
            del timeout_seconds
            seen.append(request.tools)
            return ModelOutput(provider=self.provider_name, text="DONE: catalog captured", raw={})

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    with _toolset() as toolset:
        tools, policy, specs = build_runtime_tools(SafetyPolicy(max_steps=4), toolset)
        unscoped = AgentRunner(
            provider=CapturingProvider(), event_log=log, tools=tools, safety_policy=policy, tool_specs=specs
        )
        unscoped.run("list catalog", run_id="catalog-all")
        bots = {"reader": BotSpec("reader", "Reader", frozenset({"mcp__legacy__echo", "echo"}))}
        scoped = AgentRunner(
            provider=CapturingProvider(),
            event_log=log,
            tools=tools,
            safety_policy=policy,
            bots=bots,
            active_bot_id="reader",
            tool_specs=specs,
        )
        scoped.run("list catalog", run_id="catalog-scoped")
    log.close()

    all_names = [spec.name for spec in seen[0]]
    assert "mcp__modern__echo" in all_names
    assert "mcp__legacy__shout" in all_names
    assert all(name.startswith("mcp__") for name in all_names)
    assert [spec.name for spec in seen[1]] == ["mcp__legacy__echo"]
