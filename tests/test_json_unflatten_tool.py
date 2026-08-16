"""Tests for the JSON unflatten tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.json_unflatten import JsonUnflattenTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the json_unflatten tool."""

    result = JsonUnflattenTool().execute(ToolInvocation(tool_name="json_unflatten", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_json_unflatten_rebuilds_nested_objects_and_arrays() -> None:
    """Dotted object paths and bracket array indexes become nested JSON."""

    document = json.dumps(
        {
            "model": "GPT-5.5",
            "items[0].name": "Claude Sonnet 4.6",
            "items[1].name": "Gemini 3.x",
            "meta.vendor": "Kimi K2",
        }
    )
    ok, content, metadata = _run(text=document)

    assert ok is True
    assert json.loads(content) == {
        "items": [{"name": "Claude Sonnet 4.6"}, {"name": "Gemini 3.x"}],
        "meta": {"vendor": "Kimi K2"},
        "model": "GPT-5.5",
    }
    assert metadata["keys"] == 4
    assert metadata["separator"] == "."


def test_json_unflatten_supports_custom_separator() -> None:
    """Object nesting uses the requested separator while arrays stay bracketed."""

    ok, content, metadata = _run(text='{"a_b[0]": 1, "a_b[1]": 2}', separator="_")

    assert ok is True
    assert json.loads(content) == {"a": {"b": [1, 2]}}
    assert metadata["separator"] == "_"


def test_json_unflatten_rejects_empty_oversized_invalid_and_non_object_input() -> None:
    """Empty, oversized, malformed, and non-object input fails structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_bad, content_bad, _m3 = _run(text='{"a":')
    ok_root, content_root, _m4 = _run(text='["a"]')
    ok_sep, content_sep, _m5 = _run(text='{"a": 1}', separator="")
    ok_long_sep, content_long_sep, _m6 = _run(text='{"a": 1}', separator="x" * 17)

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_bad is False and "invalid JSON" in content_bad
    assert ok_root is False and "root must be an object" in content_root
    assert ok_sep is False and "separator must be non-empty" in content_sep
    assert ok_long_sep is False and "max length 16" in content_long_sep


def test_json_unflatten_rejects_conflicting_key_paths() -> None:
    """A path cannot be both a leaf and a parent or both an object and array."""

    ok_prefix, content_prefix, _m1 = _run(text='{"a": 1, "a.b": 2}')
    ok_container, content_container, _m2 = _run(text='{"a.b": 1, "a[0]": 2}')

    assert ok_prefix is False and "conflicting key paths" in content_prefix
    assert ok_container is False and "conflicting object/array paths" in content_container


def test_json_unflatten_rejects_more_than_2000_keys() -> None:
    """Flat maps cannot exceed the key cap."""

    document = json.dumps(
        {chr(0x1000 + index): 0 for index in range(2001)},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    ok, content, metadata = _run(text=document)

    assert ok is False
    assert "max_keys=2000" in content
    assert metadata["keys"] == 2001


def test_json_unflatten_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "json_unflatten" in tools
    assert tools["json_unflatten"].name == "json_unflatten"
    SafetyPolicy().validate_tool("json_unflatten")
    assert "json_unflatten" in SafetyPolicy().allowed_tools
