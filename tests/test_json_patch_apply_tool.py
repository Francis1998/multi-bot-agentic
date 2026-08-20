"""Tests for the bounded RFC 6902 JSON Patch tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.json_patch_apply import JsonPatchApplyTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the json_patch_apply tool."""

    result = JsonPatchApplyTool().execute(ToolInvocation(tool_name="json_patch_apply", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_json_patch_apply_supports_all_rfc_operations() -> None:
    """All six RFC 6902 operations apply sequentially."""

    document = {"items": ["first", "second"], "config": {"active": False}, "old": "remove"}
    patch = [
        {"op": "add", "path": "/items/1", "value": "inserted"},
        {"op": "remove", "path": "/old"},
        {"op": "replace", "path": "/config/active", "value": True},
        {"op": "copy", "from": "/config", "path": "/config_copy"},
        {"op": "move", "from": "/items/0", "path": "/moved"},
        {"op": "test", "path": "/config_copy/active", "value": True},
    ]

    ok, content, metadata = _run(text=json.dumps(document), patch=patch)

    assert ok is True
    assert json.loads(content) == {
        "items": ["inserted", "second"],
        "config": {"active": True},
        "config_copy": {"active": True},
        "moved": "first",
    }
    assert metadata["operations"] == 6


def test_json_patch_apply_accepts_sentinel_append_and_escaped_paths() -> None:
    """Sentinel input supports array append and RFC 6901 token escapes."""

    combined = (
        '{"models":["GPT-5.5"],"a/b":{"~name":"Claude Sonnet 4.6"}}'
        "<<<JSON_PATCH>>>"
        '[{"op":"add","path":"/models/-","value":"Gemini 3.x"},'
        '{"op":"replace","path":"/a~1b/~0name","value":"Kimi K2"}]'
    )

    ok, content, metadata = _run(text=combined)

    assert ok is True
    assert json.loads(content) == {
        "models": ["GPT-5.5", "Gemini 3.x"],
        "a/b": {"~name": "Kimi K2"},
    }
    assert metadata["operations"] == 2


def test_json_patch_apply_copy_is_deep_and_root_paths_work() -> None:
    """Copied containers do not alias, and the empty pointer targets the root."""

    patch = [
        {"op": "copy", "from": "/source", "path": "/copy"},
        {"op": "replace", "path": "/copy/value", "value": 2},
        {"op": "test", "path": "/source/value", "value": 1},
    ]
    ok_copy, content_copy, _metadata_copy = _run(text='{"source":{"value":1}}', patch=patch)
    ok_root, content_root, _metadata_root = _run(
        text='{"old":true}',
        patch='[{"op":"replace","path":"","value":{"new":true}}]',
    )

    assert ok_copy is True
    assert json.loads(content_copy) == {"source": {"value": 1}, "copy": {"value": 2}}
    assert ok_root is True
    assert json.loads(content_root) == {"new": True}


def test_json_patch_apply_reports_failed_tests_and_invalid_operations() -> None:
    """Failed tests, unknown operations, and malformed members fail structurally."""

    ok_test, content_test, metadata_test = _run(
        text='{"value":1}',
        patch='[{"op":"test","path":"/value","value":2}]',
    )
    ok_op, content_op, metadata_op = _run(
        text="{}",
        patch='[{"op":"merge","path":"","value":{}}]',
    )
    ok_member, content_member, _metadata_member = _run(
        text="{}",
        patch='[{"op":"add","path":"/missing"}]',
    )

    assert ok_test is False and "test did not match" in content_test
    assert metadata_test["operation_index"] == 0
    assert ok_op is False and "op must be one of" in content_op
    assert metadata_op["operation_index"] == 0
    assert ok_member is False and "missing required member 'value'" in content_member


def test_json_patch_apply_rejects_bad_pointers_and_array_bounds() -> None:
    """Pointer syntax, parent existence, and array bounds are enforced."""

    cases = [
        ('[{"op":"add","path":"items/0","value":1}]', "start with '/'"),
        ('[{"op":"add","path":"/items/01","value":1}]', "invalid array index"),
        ('[{"op":"remove","path":"/items/1"}]', "out of bounds"),
        ('[{"op":"add","path":"/missing/child","value":1}]', "member not found"),
        ('[{"op":"move","from":"/obj","path":"/obj/child"}]', "cannot be a child"),
    ]
    for patch, expected in cases:
        ok, content, _metadata = _run(text='{"items":[0],"obj":{}}', patch=patch)
        assert ok is False
        assert expected in content


def test_json_patch_apply_rejects_empty_malformed_nonfinite_and_ambiguous_input() -> None:
    """Empty, invalid, non-finite, and duplicate-sentinel input fails."""

    ok_empty, content_empty, _m1 = _run(text="{}", patch="")
    ok_bad, content_bad, metadata_bad = _run(text="{}", patch="[")
    ok_nan, content_nan, _m3 = _run(text='{"value":NaN}', patch="[]")
    ok_duplicate, content_duplicate, _m4 = _run(text="{}<<<JSON_PATCH>>>[]<<<JSON_PATCH>>>[]")

    assert ok_empty is False and "patch JSON array is empty" in content_empty
    assert ok_bad is False and "invalid JSON in patch" in content_bad
    assert metadata_bad["document"] == "patch"
    assert ok_nan is False and "invalid JSON in text" in content_nan
    assert ok_duplicate is False and "more than one" in content_duplicate


def test_json_patch_apply_enforces_character_operation_and_output_bounds() -> None:
    """Documents, patch arrays, operation counts, and output stay bounded."""

    ok_text, content_text, metadata_text = _run(text=" " * 20_001, patch="[]")
    ok_patch, content_patch, metadata_patch = _run(text="{}", patch=" " * 20_001)
    too_many = [{"op": "test", "path": "", "value": {}}] * 201
    ok_many, content_many, metadata_many = _run(text="{}", patch=too_many)
    ok_output, content_output, metadata_output = _run(
        text=json.dumps({"value": "x" * 10_000}),
        patch=[{"op": "copy", "from": "/value", "path": "/copy"}],
    )

    assert ok_text is False and "text exceeds" in content_text
    assert metadata_text["chars"] == 20_001
    assert ok_patch is False and "patch exceeds" in content_patch
    assert metadata_patch["chars"] == 20_001
    assert ok_many is False and "max_operations=200" in content_many
    assert metadata_many["operations"] == 201
    assert ok_output is False and "output exceeds" in content_output
    assert metadata_output["chars"] > 20_000


def test_json_patch_apply_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "json_patch_apply" in tools
    assert tools["json_patch_apply"].name == "json_patch_apply"
    SafetyPolicy().validate_tool("json_patch_apply")
    assert "json_patch_apply" in SafetyPolicy().allowed_tools
