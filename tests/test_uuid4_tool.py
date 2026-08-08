"""Tests for the random UUID (version 4) generation tool."""

from __future__ import annotations

import uuid
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.uuid4 import Uuid4Tool


def _run(count: object | None = None) -> tuple[bool, str, dict[str, object]]:
    """Execute the uuid4 tool with an optional count.

    Args:
        count: Optional number of UUIDs to generate.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    arguments: dict[str, object] = {}
    if count is not None:
        arguments["count"] = count
    result = Uuid4Tool().execute(ToolInvocation(tool_name="uuid4", arguments=arguments))
    return result.ok, result.content, result.metadata


def test_uuid4_generates_valid_version_4() -> None:
    """Default invocation returns one version-4 UUID string."""

    ok, content, metadata = _run()

    assert ok is True
    parsed = uuid.UUID(content)
    assert parsed.version == 4
    assert metadata["count"] == 1
    assert metadata["version"] == 4
    assert metadata["uuids"] == [content]


def test_uuid4_count_returns_newline_joined_unique_values() -> None:
    """Count greater than one returns newline-joined unique UUIDs."""

    ok, content, metadata = _run(count=3)

    assert ok is True
    lines = content.split("\n")
    assert len(lines) == 3
    assert len(set(lines)) == 3
    for line in lines:
        assert uuid.UUID(line).version == 4
    assert metadata["count"] == 3
    assert metadata["uuids"] == lines


def test_uuid4_rejects_count_below_minimum() -> None:
    """Count below 1 is a structured failure."""

    ok, content, metadata = _run(count=0)

    assert ok is False
    assert "count must be an integer 1..16" in content
    assert metadata["count"] == 0


def test_uuid4_rejects_count_above_maximum() -> None:
    """Count above 16 is a structured failure."""

    ok, content, metadata = _run(count=17)

    assert ok is False
    assert "count must be an integer 1..16" in content
    assert metadata["count"] == 17


def test_uuid4_rejects_non_integer_count() -> None:
    """Non-integer count values are refused."""

    ok, content, _metadata = _run(count="many")

    assert ok is False
    assert "count must be an integer 1..16" in content


def test_uuid4_rejects_boolean_count() -> None:
    """Boolean counts are refused (bool is a subclass of int)."""

    ok, content, _metadata = _run(count=True)

    assert ok is False
    assert "count must be an integer 1..16" in content


def test_uuid4_accepts_string_digit_count() -> None:
    """Digit strings within bounds are accepted."""

    ok, content, metadata = _run(count="2")

    assert ok is True
    assert len(content.split("\n")) == 2
    assert metadata["count"] == 2


def test_uuid4_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "uuid4" in tools
    assert tools["uuid4"].name == "uuid4"
    SafetyPolicy().validate_tool("uuid4")
    assert "uuid4" in SafetyPolicy().allowed_tools
