"""Tests for the JSON flatten tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.json_flatten import JsonFlattenTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the json_flatten tool."""

    result = JsonFlattenTool().execute(ToolInvocation(tool_name="json_flatten", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_json_flatten_flattens_nested_objects_and_arrays() -> None:
    """Nested objects and arrays become dotted/bracket keys."""

    document = json.dumps(
        {
            "model": "GPT-5.5",
            "items": [{"name": "Claude Sonnet 4.6"}, {"name": "Gemini 3.x"}],
            "meta": {"vendor": "Kimi K2"},
        }
    )
    ok, content, metadata = _run(text=document)

    assert ok is True
    assert json.loads(content) == {
        "items[0].name": "Claude Sonnet 4.6",
        "items[1].name": "Gemini 3.x",
        "meta.vendor": "Kimi K2",
        "model": "GPT-5.5",
    }
    assert metadata["keys"] == 4
    assert metadata["separator"] == "."


def test_json_flatten_supports_custom_separator() -> None:
    """Object nesting uses the requested separator while arrays stay bracketed."""

    document = json.dumps({"a": {"b": [1]}})
    ok, content, metadata = _run(text=document, separator="_")

    assert ok is True
    assert json.loads(content) == {"a_b[0]": 1}
    assert metadata["separator"] == "_"


def test_json_flatten_preserves_scalar_root_values() -> None:
    """A scalar JSON document flattens to an empty map."""

    ok, content, metadata = _run(text='"GPT-5.5"')

    assert ok is True
    assert json.loads(content) == {}
    assert metadata["keys"] == 0


def test_json_flatten_rejects_empty_oversized_invalid_and_too_many_keys() -> None:
    """Empty, oversized, malformed, and over-expanded input fails structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_bad, content_bad, _m3 = _run(text='{"a":')
    ok_sep, content_sep, _m4 = _run(text='{"a":1}', separator="")
    too_many = json.dumps({"items": list(range(2001))})

    ok_many, content_many, metadata_many = _run(text=too_many)

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_bad is False and "invalid JSON" in content_bad
    assert ok_sep is False and "separator must be non-empty" in content_sep
    assert ok_many is False and "max_keys=2000" in content_many
    assert metadata_many["keys"] == 2000


def test_json_flatten_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "json_flatten" in tools
    assert tools["json_flatten"].name == "json_flatten"
    SafetyPolicy().validate_tool("json_flatten")
    assert "json_flatten" in SafetyPolicy().allowed_tools
