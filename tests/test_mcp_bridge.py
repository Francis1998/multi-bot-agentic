"""Tests for MCP tool adapters, argument mapping, and the toolset."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import pytest

from multi_bot_agentic.mcp import McpToolset
from multi_bot_agentic.mcp.bridge import (
    McpArgumentError,
    McpToolAdapter,
    coerce_arguments,
    namespaced_tool_name,
    render_content,
    truncate_utf8,
)
from multi_bot_agentic.mcp.client import McpCallResult, McpToolInfo
from multi_bot_agentic.mcp.config import McpConfig, McpServerConfig
from multi_bot_agentic.models import ToolInvocation

FIXTURES = Path(__file__).parent / "fixtures" / "mcp"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "mcp"
SEARCH_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
    "required": ["query"],
}


def _server(name: str, script: str, *extra: str, **options: Any) -> McpServerConfig:
    return McpServerConfig(name=name, command=sys.executable, args=(str(FIXTURES / script), *extra), **options)


def _invoke(adapter: McpToolAdapter, text: str) -> Any:
    return adapter.execute(ToolInvocation(tool_name=adapter.name, arguments={"text": text}))


@pytest.mark.parametrize(
    ("arguments", "schema", "expected"),
    [
        ({"text": '{"query": "mcp", "limit": 2}'}, SEARCH_SCHEMA, {"query": "mcp", "limit": 2}),
        ({"text": "  release checklist "}, SEARCH_SCHEMA, {"query": "release checklist"}),
        ({"text": "7"}, {"type": "object", "properties": {"n": {"type": "integer"}}}, {"n": 7}),
        ({"text": "anything"}, {"type": "object", "additionalProperties": False}, {}),
        ({"query": "structured", "limit": 1}, SEARCH_SCHEMA, {"query": "structured", "limit": 1}),
        ({"text": "raw"}, {"type": "object", "properties": {"x": {"type": [{}]}}}, {"x": "raw"}),
    ],
)
def test_coerce_arguments_maps_payloads(arguments: dict[str, Any], schema: dict[str, Any], expected: Any) -> None:
    """JSON payloads, single-argument text, scalars, no-arg tools, and structured calls are supported."""

    assert coerce_arguments(arguments, schema) == expected


@pytest.mark.parametrize(
    ("text", "schema", "message"),
    [
        ("2 3", {"type": "object", "properties": {"a": {}, "b": {}}}, "pass a JSON object"),
        ('{"query": ', SEARCH_SCHEMA, "look like JSON but are invalid"),
        ('{"limit": 1}', SEARCH_SCHEMA, "missing required argument"),
        ("many", {"type": "object", "properties": {"n": {"type": "integer"}}}, "expects integer"),
    ],
)
def test_coerce_arguments_explains_the_expected_schema(text: str, schema: dict[str, Any], message: str) -> None:
    """Errors name the problem so the model can correct its next ``TOOL:`` request."""

    with pytest.raises(McpArgumentError, match=message):
        coerce_arguments({"text": text}, schema)


def test_render_content_summarizes_binary_and_resource_blocks() -> None:
    """Binary payloads are never inlined; resources and structured content are rendered."""

    result = McpCallResult(
        content=(
            {"type": "text", "text": "summary"},
            {"type": "image", "data": "aGVsbG8=", "mimeType": "image/png"},
            {"type": "resource_link", "uri": "file:///notes.md", "name": "notes.md"},
            {"type": "resource", "resource": {"uri": "file:///a.txt", "text": "embedded"}},
            {"type": "resource", "resource": {"uri": "file:///b.bin", "blob": "AAAA"}},
            {"type": "mystery"},
        ),
        is_error=False,
    )

    assert render_content(result).splitlines() == [
        "summary",
        "[image image/png: 8 base64 chars omitted]",
        "[resource_link notes.md: file:///notes.md]",
        "embedded",
        "[resource file:///b.bin: binary omitted]",
        "[mystery content omitted]",
    ]
    assert render_content(McpCallResult(content=(), is_error=False, structured_content={"b": 1, "a": 2})) == (
        '{"a": 2, "b": 1}'
    )


def test_render_content_tolerates_malformed_block_types() -> None:
    """Unhashable ``type`` values from a buggy server are omitted instead of raising ``TypeError``."""

    result = McpCallResult(content=({"type": []}, {"type": {}}, {"type": "text", "text": "ok"}), is_error=False)

    assert render_content(result).splitlines() == ["[[] content omitted]", "[{} content omitted]", "ok"]


def test_truncate_utf8_never_splits_a_character() -> None:
    """Byte truncation keeps whole UTF-8 characters and reports the original size."""

    text, original = truncate_utf8("ééé", 5)
    assert original == 6
    assert text.startswith("éé\n…[truncated: kept 4 of 6 bytes")
    assert truncate_utf8("short", 10) == ("short", 5)


def test_toolset_namespaces_tools_from_both_eras() -> None:
    """Both eras load side by side; identical tool names stay distinct per server."""

    config = McpConfig(servers=(_server("modern", "modern_server.py"), _server("legacy", "legacy_server.py")))
    with McpToolset(config) as toolset:
        statuses = toolset.start()
        tools = toolset.tools
        specs = toolset.specs()

    modern, legacy = statuses
    assert (modern.era, modern.protocol_version) == ("modern", "2026-07-28")
    assert (legacy.era, legacy.protocol_version) == ("legacy", "2025-11-25")
    assert modern.skipped_tools == ("bad name:x",)
    assert "mcp__modern__echo" in tools
    assert "mcp__legacy__echo" in tools
    assert tools["mcp__legacy__echo"].description == "[MCP legacy] Echo the text back (legacy)."
    assert [spec.name for spec in specs] == list(tools)
    assert namespaced_tool_name("legacy", "echo") == "mcp__legacy__echo"


def test_toolset_applies_allow_and_deny_lists() -> None:
    """Hidden tools are never wrapped, so the runner cannot call them."""

    server = _server("modern", "modern_server.py", allowed_tools=("e*", "add", "big"), denied_tools=("big",))
    with McpToolset(McpConfig(servers=(server,))) as toolset:
        (status,) = toolset.start()
        names = list(toolset.tools)

    assert names == ["mcp__modern__echo", "mcp__modern__add"]
    assert "big" in status.hidden_tools
    assert "crash" in status.hidden_tools


def test_toolset_reports_disabled_and_failing_servers() -> None:
    """A broken server is reported without hiding healthy servers."""

    broken = McpServerConfig(name="broken", command=str(FIXTURES / "does-not-exist"))
    disabled = _server("off", "modern_server.py", disabled=True)
    with McpToolset(McpConfig(servers=(broken, disabled, _server("ok", "legacy_server.py")))) as toolset:
        statuses = toolset.start()
        failed = toolset.failed
        tools = toolset.tools

    assert [status.name for status in failed] == ["broken"]
    assert "cannot start MCP server 'broken'" in str(failed[0].error)
    assert statuses[1].disabled
    assert all(name.startswith("mcp__ok__") for name in tools)


def test_adapter_maps_results_to_tool_failure_semantics() -> None:
    """Success, ``isError``, and JSON-RPC errors become ``ToolResult`` values, never exceptions."""

    with McpToolset(McpConfig(servers=(_server("modern", "modern_server.py"),))) as toolset:
        toolset.start()
        tools = toolset.tools
        echoed = _invoke(tools["mcp__modern__echo"], "hello mcp")
        failed = _invoke(tools["mcp__modern__fail"], '{"reason": "quota"}')
        client = tools["mcp__modern__echo"]._client
        ghost = McpToolAdapter(
            server=_server("modern", "modern_server.py"),
            tool=McpToolInfo(name="ghost", description="", input_schema={"type": "object"}),
            client=client,
        )
        protocol = _invoke(ghost, "{}")

    assert echoed.ok
    assert echoed.tool_name == "mcp__modern__echo"
    assert echoed.content == "hello mcp"
    assert echoed.metadata["mcp_era"] == "modern"
    assert echoed.metadata["mcp_protocol_version"] == "2026-07-28"
    assert echoed.metadata["mcp_arguments"] == {"text": "hello mcp"}
    assert not failed.ok
    assert failed.metadata["error_kind"] == "tool_error"
    assert failed.content == "tool failed: quota"
    assert not protocol.ok
    assert protocol.metadata["error_kind"] == "protocol_error"
    assert protocol.metadata["error_code"] == -32602


def test_adapter_rejects_bad_arguments_without_calling_the_server() -> None:
    """Ambiguous text for a multi-argument tool is reported with the expected signature."""

    with McpToolset(McpConfig(servers=(_server("modern", "modern_server.py"),))) as toolset:
        toolset.start()
        result = _invoke(toolset.tools["mcp__modern__add"], "two and three")

    assert not result.ok
    assert result.metadata["error_kind"] == "invalid_arguments"
    assert "a: number (required), b: number (required)" in result.content
    assert "mcp_arguments" not in result.metadata


def test_adapter_times_out_and_survives_dead_servers() -> None:
    """Slow and crashed servers produce failed results within the configured timeout."""

    slow_server = _server("slow", "modern_server.py", call_timeout_seconds=0.2)
    crashy_server = _server("crashy", "modern_server.py")
    with McpToolset(McpConfig(servers=(slow_server, crashy_server))) as toolset:
        toolset.start()
        tools = toolset.tools
        started = time.monotonic()
        slow = _invoke(tools["mcp__slow__sleep"], "1")
        elapsed = time.monotonic() - started
        crashed = _invoke(tools["mcp__crashy__crash"], "{}")

    assert not slow.ok
    assert slow.metadata["error_kind"] == "timeout"
    assert elapsed < 0.8
    assert not crashed.ok
    assert crashed.metadata["error_kind"] == "transport_error"


def test_adapter_caps_bytes_and_redacts_results() -> None:
    """``maxResultBytes`` and ``redactResults`` bound and scrub what reaches the event log."""

    server = _server("modern", "modern_server.py", max_result_bytes=64, redact_results=True)
    with McpToolset(McpConfig(servers=(server,))) as toolset:
        toolset.start()
        tools = toolset.tools
        big = _invoke(tools["mcp__modern__big"], "5000")
        contact = _invoke(tools["mcp__modern__contact"], "{}")
        image = _invoke(tools["mcp__modern__image"], "{}")

    assert big.ok
    assert big.metadata["truncated"] is True
    assert big.metadata["result_bytes"] == 10_000
    assert len(big.content.split("\n…[truncated")[0].encode("utf-8")) <= 64
    assert contact.content == "mail [EMAIL], key [TOKEN]"
    assert contact.metadata["redactions"] == 2
    assert image.content == "[image image/png: 12 base64 chars omitted]\na dot"
    assert image.metadata["content_types"] == ["image", "text"]


def test_adapter_call_passes_structured_arguments_verbatim() -> None:
    """Library callers can send literal text that looks like JSON without double-encoding it."""

    with McpToolset(McpConfig(servers=(_server("modern", "modern_server.py"),))) as toolset:
        toolset.start()
        result = toolset.tools["mcp__modern__echo"].call({"text": '{"a": 1}'})

    assert result.ok
    assert result.content == '{"a": 1}'
    assert result.metadata["mcp_arguments"] == {"text": '{"a": 1}'}


def test_adapter_survives_invalid_unicode_and_hostile_content_types() -> None:
    """Lone surrogates and hostile block types become safe text and normalized metadata."""

    with McpToolset(McpConfig(servers=(_server("modern", "modern_server.py", redact_results=True),))) as toolset:
        toolset.start()
        surrogate = _invoke(toolset.tools["mcp__modern__surrogate"], "{}")
        weird = _invoke(toolset.tools["mcp__modern__weird_type"], "{}")

    assert surrogate.ok
    assert surrogate.content == "bad ? text"
    assert weird.ok
    assert weird.metadata["content_types"] == ["unknown", "unknown"]
    assert "sk-abcdefghijklmnopqrstuv" not in str(weird.metadata)


def test_example_notes_server_rejects_bad_arguments_without_crashing() -> None:
    """The shipped demo server answers invalid arguments with -32602 and keeps serving."""

    server = McpServerConfig(name="notes", command=sys.executable, args=(str(EXAMPLES / "notes_server.py"),))
    with McpToolset(McpConfig(servers=(server,))) as toolset:
        toolset.start()
        search = toolset.tools["mcp__notes__search_notes"]
        bad = _invoke(search, '{"query": "release", "limit": "many"}')
        good = _invoke(search, "release")

    assert not bad.ok
    assert bad.metadata["error_kind"] == "protocol_error"
    assert bad.metadata["error_code"] == -32602
    assert good.ok
    assert good.content.startswith("release-checklist:")
