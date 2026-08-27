"""Tests for the jsonl_parse tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.jsonl_parse import JsonlParseTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the jsonl_parse tool."""

    result = JsonlParseTool().execute(ToolInvocation(tool_name="jsonl_parse", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_jsonl_parse_objects_default() -> None:
    """Default mode returns a pretty JSON array of objects with sorted keys."""

    text = '{"b": 2, "a": 1}\n{"z": true}\n'
    ok, content, metadata = _run(text=text)
    assert ok is True
    assert metadata["mode"] == "objects"
    assert metadata["lines"] == 2
    assert json.loads(content) == [{"a": 1, "b": 2}, {"z": True}]
    assert content.index('"a"') < content.index('"b"')


def test_jsonl_parse_any_mode_allows_scalars() -> None:
    """mode=any accepts non-object JSON values per line."""

    text = '1\n"x"\n[true]\n{"k": null}\n'
    ok, content, metadata = _run(text=text, mode="any")
    assert ok is True
    assert metadata["mode"] == "any"
    assert json.loads(content) == [1, "x", [True], {"k": None}]


def test_jsonl_parse_rejects_non_object_blank_and_bounds() -> None:
    """Non-object lines (objects mode), blanks, and oversize input fail."""

    ok_scalar, content_scalar, meta_scalar = _run(text="1\n")
    ok_blank, content_blank, meta_blank = _run(text='{"a":1}\n\n{"b":2}\n')
    ok_bad, content_bad, meta_bad = _run(text='{"a":1}\n{bad}\n')
    ok_mode, content_mode, _m4 = _run(text='{"a":1}\n', mode="rows")
    ok_empty, content_empty, _m5 = _run(text="   ")
    ok_lines, content_lines, meta_lines = _run(text="\n".join(f'{{"i":{i}}}' for i in range(501)))

    assert ok_scalar is False and "not a JSON object" in content_scalar
    assert meta_scalar["line"] == 1
    assert ok_blank is False and "blank line" in content_blank
    assert meta_blank["line"] == 2
    assert ok_bad is False and "invalid JSON" in content_bad
    assert meta_bad["line"] == 2
    assert ok_mode is False and "unsupported mode" in content_mode
    assert ok_empty is False and "empty" in content_empty
    assert ok_lines is False and "max_lines" in content_lines
    assert meta_lines["lines"] == 501


def test_jsonl_parse_mentions_model_versions_as_examples() -> None:
    """Dataset tooling docs cover GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."""

    text = '{"model":"GPT-5.5"}\n{"model":"Claude Sonnet 4.6"}\n{"model":"Gemini 3.x"}\n{"model":"Kimi K2"}\n'
    ok, content, metadata = _run(text=text)
    assert ok is True
    assert metadata["lines"] == 4
    payload = json.loads(content)
    assert [row["model"] for row in payload] == [
        "GPT-5.5",
        "Claude Sonnet 4.6",
        "Gemini 3.x",
        "Kimi K2",
    ]


def test_jsonl_parse_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "jsonl_parse" in tools
    assert tools["jsonl_parse"].name == "jsonl_parse"
    SafetyPolicy().validate_tool("jsonl_parse")
    assert "jsonl_parse" in SafetyPolicy().allowed_tools
