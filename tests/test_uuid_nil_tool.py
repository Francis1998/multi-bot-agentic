"""Tests for the uuid_nil tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.uuid_nil import UuidNilTool

_NIL = "00000000-0000-0000-0000-000000000000"
_MAX = "ffffffff-ffff-ffff-ffff-ffffffffffff"


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the uuid_nil tool."""

    result = UuidNilTool().execute(ToolInvocation(tool_name="uuid_nil", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_uuid_nil_returns_rfc4122_nil_by_default() -> None:
    """Default mode returns the all-zero nil UUID."""

    ok, content, metadata = _run()

    assert ok is True
    assert content == _NIL
    assert metadata["mode"] == "nil"
    assert metadata["chars"] == 36


def test_uuid_nil_mode_max_returns_all_ones() -> None:
    """mode=max returns the RFC-style max UUID."""

    ok, content, metadata = _run(mode="max")

    assert ok is True
    assert content == _MAX
    assert metadata["mode"] == "max"


def test_uuid_nil_rejects_unsupported_mode() -> None:
    """Unknown modes fail structurally."""

    ok, content, metadata = _run(mode="uuid4")

    assert ok is False
    assert "unsupported mode" in content
    assert metadata["mode"] == "uuid4"


def test_uuid_nil_mentions_model_versions_as_examples() -> None:
    """Placeholder ids stay stable for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."""

    ok, content, metadata = _run(mode="nil")

    assert ok is True
    assert content == _NIL
    assert metadata["mode"] == "nil"


def test_uuid_nil_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "uuid_nil" in tools
    assert tools["uuid_nil"].name == "uuid_nil"
    SafetyPolicy().validate_tool("uuid_nil")
    assert "uuid_nil" in SafetyPolicy().allowed_tools
