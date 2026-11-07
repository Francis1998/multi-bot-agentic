"""Tests for the advertised tool catalog in provider prompts."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from multi_bot_agentic.config import build_llm_adapter
from multi_bot_agentic.llm.base import render_tool_catalog
from multi_bot_agentic.llm.claude_code_cli import _render_prompt as claude_prompt
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.llm.gemini import _render_prompt as gemini_prompt
from multi_bot_agentic.llm.openai import _render_prompt as openai_prompt
from multi_bot_agentic.models import ModelRequest, Observation, ToolSpec

SEARCH = ToolSpec(
    name="mcp__notes__search_notes",
    description="[MCP notes] Search notes.",
    input_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": ["integer", "null"]}},
        "required": ["query"],
    },
)


def test_tool_spec_signature_summarizes_arguments() -> None:
    """Signatures mark required arguments and union types; empty schemas render nothing."""

    assert SEARCH.signature() == "query: string (required), limit: integer|null"
    assert ToolSpec(name="t", description="d").signature() == ""
    assert ToolSpec(name="t", description="d", input_schema={"properties": {"x": True}}).signature() == "x: any"


def test_tool_spec_signature_tolerates_hostile_schemas() -> None:
    """Untrusted MCP schemas with odd ``required`` entries or huge property lists stay safe and bounded."""

    odd = ToolSpec(name="t", description="d", input_schema={"properties": {"a": {}}, "required": [{"x": 1}, "a"]})
    assert odd.signature() == "a: any (required)"
    huge = ToolSpec(name="t", description="d", input_schema={"properties": {f"p{i}": {} for i in range(500)}})
    assert len(huge.signature()) == 400
    assert huge.signature().endswith("…")


def test_render_tool_catalog_is_empty_without_tools() -> None:
    """No catalog means no prompt change at all."""

    assert render_tool_catalog(()) == ""
    rendered = render_tool_catalog((SEARCH,))
    assert rendered.startswith("\n\nAvailable tools (request one with TOOL:<name>:")
    assert rendered.endswith(
        "- mcp__notes__search_notes: [MCP notes] Search notes. Arguments: query: string (required), "
        "limit: integer|null."
    )


@pytest.mark.parametrize("render", [openai_prompt, gemini_prompt, claude_prompt])
def test_provider_prompts_append_catalog_only_when_tools_are_advertised(render: Callable[[ModelRequest], str]) -> None:
    """Every real provider renders the catalog; prompts without tools are unchanged."""

    observations = (Observation(source="user", content="find the release notes"),)
    plain = render(ModelRequest(goal="find notes", observations=observations))
    with_tools = render(ModelRequest(goal="find notes", observations=observations, tools=(SEARCH,)))

    assert "Available tools" not in plain
    assert "- mcp__notes__search_notes: [MCP notes] Search notes." in with_tools
    assert with_tools.replace(render_tool_catalog((SEARCH,)), "") == plain


def test_fake_provider_tool_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    """``MULTIBOT_FAKE_TOOL`` lets demos drive any tool; the default stays ``checklist``."""

    request = ModelRequest(goal="release checklist", observations=(Observation(source="user", content="g"),))
    default = FakeLLMAdapter().complete(request, timeout_seconds=1.0)
    assert default.text == "TOOL:checklist:release checklist"
    assert default.raw["mode"] == "deterministic-checklist-request"

    monkeypatch.setenv("MULTIBOT_FAKE_TOOL", "mcp__notes__search_notes")
    adapter = build_llm_adapter("fake")
    output = adapter.complete(request, timeout_seconds=1.0)
    assert output.text == "TOOL:mcp__notes__search_notes:release checklist"
    assert output.raw["mode"] == "deterministic-tool-request"
