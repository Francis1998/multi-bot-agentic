"""Tests for the JSON Merge Patch tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.json_merge_patch import JsonMergePatchTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the json_merge_patch tool with the given arguments."""

    result = JsonMergePatchTool().execute(ToolInvocation(tool_name="json_merge_patch", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_json_merge_patch_merges_objects() -> None:
    """Object patches merge recursively and preserve siblings."""

    ok, content, metadata = _run(
        base='{"a":1,"b":{"c":2,"d":3}}',
        patch='{"b":{"c":9},"e":4}',
    )

    assert ok is True
    payload = json.loads(content)
    assert payload == {"a": 1, "b": {"c": 9, "d": 3}, "e": 4}
    assert metadata["base_type"] == "dict"


def test_json_merge_patch_null_deletes_key() -> None:
    """Null patch values delete keys per RFC 7396."""

    ok, content, _metadata = _run(base='{"a":1,"b":2}', patch='{"b":null}')

    assert ok is True
    assert json.loads(content) == {"a": 1}


def test_json_merge_patch_accepts_combined_text() -> None:
    """Combined text with <<<PATCH>>> delimiter is accepted."""

    ok, content, _metadata = _run(text='{"a":1}<<<PATCH>>>{"b":2}')

    assert ok is True
    assert json.loads(content) == {"a": 1, "b": 2}


def test_json_merge_patch_rejects_empty_base() -> None:
    """Empty base is a structured failure."""

    ok, content, _metadata = _run(base="", patch="{}")

    assert ok is False
    assert "base JSON is empty" in content


def test_json_merge_patch_rejects_invalid_json() -> None:
    """Malformed patch JSON is refused."""

    ok, content, metadata = _run(base="{}", patch="{")

    assert ok is False
    assert "patch JSON parse error" in content
    assert "pos" in metadata


def test_json_merge_patch_replaces_non_object_target() -> None:
    """Non-object targets are replaced by object patches."""

    ok, content, _metadata = _run(base="[1,2]", patch='{"a":1}')

    assert ok is True
    assert json.loads(content) == {"a": 1}


def test_json_merge_patch_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "json_merge_patch" in tools
    assert tools["json_merge_patch"].name == "json_merge_patch"
    SafetyPolicy().validate_tool("json_merge_patch")
    assert "json_merge_patch" in SafetyPolicy().allowed_tools
    assert cast(object, tools["json_merge_patch"]) is not None
