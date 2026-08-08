"""Tests for the RFC 6901 JSON Pointer extraction tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.json_pointer import JsonPointerTool


def _run(text: str, pointer: str | None = None) -> tuple[bool, str, dict[str, object]]:
    """Execute the json_pointer tool.

    Args:
        text: JSON document, or combined payload when ``pointer`` is omitted and
            the sentinel is embedded.
        pointer: Optional RFC 6901 pointer.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    arguments: dict[str, object] = {"text": text}
    if pointer is not None:
        arguments["pointer"] = pointer
    result = JsonPointerTool().execute(ToolInvocation(tool_name="json_pointer", arguments=arguments))
    return result.ok, result.content, result.metadata


def test_json_pointer_extracts_nested_value() -> None:
    """Pointer /foo/0/bar selects the nested value."""

    document = json.dumps({"foo": [{"bar": "Ada"}, {"bar": "Grace"}]})
    ok, content, metadata = _run(document, "/foo/0/bar")

    assert ok is True
    assert json.loads(content) == "Ada"
    assert metadata["pointer"] == "/foo/0/bar"


def test_json_pointer_empty_returns_whole_document() -> None:
    """Empty pointer returns the whole document as pretty JSON."""

    document = '{"b": 1, "a": 2}'
    ok, content, metadata = _run(document, "")

    assert ok is True
    assert json.loads(content) == {"a": 2, "b": 1}
    assert metadata["pointer"] == ""


def test_json_pointer_unescapes_tilde_and_slash() -> None:
    """~0 and ~1 escapes decode to ~ and / respectively."""

    document = json.dumps({"a/b": 1, "c~d": 2, "e": {"f/g": True}})
    ok_slash, content_slash, _m1 = _run(document, "/a~1b")
    ok_tilde, content_tilde, _m2 = _run(document, "/c~0d")
    ok_nested, content_nested, _m3 = _run(document, "/e/f~1g")

    assert ok_slash is True and json.loads(content_slash) == 1
    assert ok_tilde is True and json.loads(content_tilde) == 2
    assert ok_nested is True and json.loads(content_nested) is True


def test_json_pointer_sentinel_split() -> None:
    """A single text payload may split on <<<JSON_POINTER>>>."""

    ok, content, _metadata = _run('{"items":[9]}<<<JSON_POINTER>>>/items/0')

    assert ok is True
    assert json.loads(content) == 9


def test_json_pointer_rejects_missing_key_and_bad_index() -> None:
    """Missing keys and invalid array indexes fail structurally."""

    ok_key, content_key, _m1 = _run('{"a":1}', "/missing")
    ok_index, content_index, _m2 = _run('{"a":[1]}', "/a/01")
    ok_oob, content_oob, _m3 = _run('{"a":[1]}', "/a/3")

    assert ok_key is False and "key not found" in content_key
    assert ok_index is False and "invalid array index" in content_index
    assert ok_oob is False and "index out of bounds" in content_oob


def test_json_pointer_rejects_invalid_pointer_syntax() -> None:
    """Pointers that do not start with / (unless empty) fail."""

    ok, content, _metadata = _run('{"a":1}', "a")

    assert ok is False
    assert "must be empty or start with '/'" in content


def test_json_pointer_rejects_empty_and_oversized_document() -> None:
    """Empty and oversized documents are refused."""

    ok_empty, content_empty, _m1 = _run("   ", "/")
    ok_big, content_big, metadata = _run("{" + ("a" * 20_001) + "}", "")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    value = metadata["chars"]
    assert isinstance(value, int)
    assert value > 20_000


def test_json_pointer_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "json_pointer" in tools
    assert tools["json_pointer"].name == "json_pointer"
    SafetyPolicy().validate_tool("json_pointer")
    assert "json_pointer" in SafetyPolicy().allowed_tools
