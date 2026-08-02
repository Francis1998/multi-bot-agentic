"""Tests for the JSON query select/pluck tool."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.json_query import JsonQueryTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the json_query tool with the given arguments."""

    result = JsonQueryTool().execute(ToolInvocation(tool_name="json_query", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


_ARRAY = '[{"name":"Ada","active":true},{"name":"Bob","active":false},{"name":"Cyd","active":true}]'


def test_json_query_where_filters_objects() -> None:
    """Where mode keeps objects whose field equals the value."""

    ok, content, metadata = _run(text=_ARRAY, mode="where", field="active", equals=True)

    assert ok is True
    assert content == '[{"name":"Ada","active":true},{"name":"Cyd","active":true}]'
    assert metadata["mode"] == "where"
    assert cast(int, metadata["items"]) == 2


def test_json_query_pluck_collects_field() -> None:
    """Pluck mode collects one field from each object."""

    ok, content, metadata = _run(text=_ARRAY, mode="pluck", field="name")

    assert ok is True
    assert content == '["Ada","Bob","Cyd"]'
    assert metadata["mode"] == "pluck"
    assert cast(int, metadata["items"]) == 3


def test_json_query_sentinel_payload() -> None:
    """Sentinel form supplies args after <<<JSON_QUERY>>>."""

    text = _ARRAY + '<<<JSON_QUERY>>>{"mode":"where","field":"name","equals":"Bob"}'
    ok, content, metadata = _run(text=text)

    assert ok is True
    assert content == '[{"name":"Bob","active":false}]'
    assert metadata["field"] == "name"


def test_json_query_rejects_empty_text() -> None:
    """Empty input is a structured failure."""

    ok, content, _metadata = _run(text="", mode="pluck", field="name")

    assert ok is False
    assert "empty" in content


def test_json_query_rejects_non_array() -> None:
    """Non-array JSON roots are refused."""

    ok, content, _metadata = _run(text='{"a":1}', mode="pluck", field="a")

    assert ok is False
    assert "array" in content


def test_json_query_where_requires_equals() -> None:
    """Where mode without equals is refused."""

    ok, content, _metadata = _run(text=_ARRAY, mode="where", field="active")

    assert ok is False
    assert "equals" in content


def test_json_query_rejects_unsupported_mode() -> None:
    """Unknown modes are refused."""

    ok, content, metadata = _run(text=_ARRAY, mode="map", field="name")

    assert ok is False
    assert "unsupported mode" in content
    assert metadata["mode"] == "map"


def test_json_query_rejects_oversized_text() -> None:
    """Documents above the char cap are refused."""

    ok, content, metadata = _run(text="[" + "x" * 20_000 + "]", mode="pluck", field="a")

    assert ok is False
    assert "max_chars" in content
    assert cast(int, metadata["chars"]) > 20_000


def test_json_query_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "json_query" in tools
    assert tools["json_query"].name == "json_query"
    SafetyPolicy().validate_tool("json_query")
    assert "json_query" in SafetyPolicy().allowed_tools
