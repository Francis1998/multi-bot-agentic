"""Tests for the deterministic JSON path extraction tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.json_path import JsonPathTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the json_path tool with the given arguments.

    Args:
        **arguments: Tool arguments (``text``, optional ``path``).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = JsonPathTool().execute(ToolInvocation(tool_name="json_path", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_json_path_extracts_nested_array_value() -> None:
    """Dot keys and array indexes select a nested JSON value."""

    ok, content, metadata = _run(text='{"items":[{"name":"Ada"},{"name":"Grace"}]}', path=".items[1].name")

    assert ok is True
    assert json.loads(content) == "Grace"
    assert metadata["path"] == ".items[1].name"
    assert metadata["result_type"] == "str"


def test_json_path_accepts_sentinel_split_in_text() -> None:
    """A single ``text`` split on ``<<<JSON_PATH>>>`` supplies document and path."""

    ok, content, metadata = _run(text='{"items":[{"id":7}]}<<<JSON_PATH>>>items[0].id')

    assert ok is True
    assert json.loads(content) == 7
    assert metadata["path"] == "items[0].id"


def test_json_path_empty_path_returns_whole_document() -> None:
    """An empty path canonicalizes and returns the whole JSON document."""

    ok, content, metadata = _run(text='{"b":1,"a":[true]}', path="")

    assert ok is True
    assert content == '{\n  "a": [\n    true\n  ],\n  "b": 1\n}'
    assert metadata["result_type"] == "dict"


def test_json_path_dollar_path_returns_whole_document() -> None:
    """The special ``$`` path returns the whole JSON document."""

    ok, content, _metadata = _run(text='["alpha", "beta"]', path="$")

    assert ok is True
    assert json.loads(content) == ["alpha", "beta"]


def test_json_path_rejects_unsupported_recursive_descent() -> None:
    """Recursive descent is outside the simple path dialect."""

    ok, content, metadata = _run(text='{"a":{"b":1}}', path="a..b")

    assert ok is False
    assert "unsupported JSON path syntax" in content
    assert metadata["path"] == "a..b"


def test_json_path_rejects_filters_scripts_and_pipes() -> None:
    """Filter/script/pipe syntax is outside the deterministic path dialect."""

    for path in ("items[?(@.id==1)]", "items[(@.length-1)]", "items | length"):
        ok, content, metadata = _run(text='{"items":[{"id":1}]}', path=path)

        assert ok is False
        assert "unsupported" in content
        assert metadata["path"] == path


def test_json_path_rejects_missing_key() -> None:
    """A missing object key is a structured traversal failure."""

    ok, content, metadata = _run(text='{"item":{"id":1}}', path="item.name")

    assert ok is False
    assert "key not found" in content
    assert metadata["segment"] == "name"


def test_json_path_rejects_out_of_bounds_index() -> None:
    """An array index outside the selected list is a structured failure."""

    ok, content, metadata = _run(text='{"items":[]}', path="items[0]")

    assert ok is False
    assert "out of bounds" in content
    assert metadata["index"] == 0
    assert metadata["length"] == 0


def test_json_path_rejects_invalid_json() -> None:
    """Malformed JSON returns ``ok=False`` rather than raising."""

    ok, content, metadata = _run(text='{"items": [}', path="items")

    assert ok is False
    assert "invalid JSON" in content
    assert metadata["chars"] == 12


def test_json_path_rejects_non_finite_json_constants() -> None:
    """Python's non-standard NaN/Infinity constants are refused."""

    ok, content, _metadata = _run(text='{"value": NaN}', path="value")

    assert ok is False
    assert "invalid JSON" in content
    assert "NaN" in content


def test_json_path_rejects_oversized_document_path_and_result() -> None:
    """Document, path, and serialized result caps return structured failures."""

    ok, content, metadata = _run(text="x" * 20_001, path="$")
    assert ok is False
    assert "document exceeds" in content
    assert metadata["chars"] == 20_001

    ok, content, metadata = _run(text="{}", path="a" * 257)
    assert ok is False
    assert "path exceeds" in content
    assert metadata["chars"] == 257

    compact_large_array = json.dumps({"value": [0] * 4000}, separators=(",", ":"))
    ok, content, metadata = _run(text=compact_large_array, path="value")
    assert ok is False
    assert "result exceeds" in content
    chars = metadata["chars"]
    assert isinstance(chars, int)
    assert chars > 20_000


def test_json_path_requires_path_or_sentinel() -> None:
    """A bare ``text`` argument without a sentinel is ambiguous and rejected."""

    ok, content, _metadata = _run(text='{"a":1}')

    assert ok is False
    assert "requires text+path" in content


def test_json_path_is_registered_in_default_tools() -> None:
    """The json_path tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "json_path" in tools
    assert tools["json_path"].name == "json_path"
    assert "json_path" in SafetyPolicy().allowed_tools
