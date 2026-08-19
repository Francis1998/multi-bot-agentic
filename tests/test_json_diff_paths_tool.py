"""Tests for the bounded JSON difference-path tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.json_diff_paths import JsonDiffPathsTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the json_diff_paths tool."""

    result = JsonDiffPathsTool().execute(ToolInvocation(tool_name="json_diff_paths", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_json_diff_paths_reports_sorted_nested_paths() -> None:
    """Changed, added, and removed values use dotted/bracket paths."""

    left = json.dumps(
        {
            "model": "GPT-5.5",
            "agents": [{"name": "Claude Sonnet 4.6", "active": True}],
            "removed": "Kimi K2",
        }
    )
    right = json.dumps(
        {
            "model": "Gemini 3.x",
            "agents": [{"name": "Claude Sonnet 4.6", "active": False}, {"name": "Kimi K2"}],
            "added": 1,
        }
    )

    ok, content, metadata = _run(text=left, other=right)

    assert ok is True
    assert json.loads(content) == [
        "added",
        "agents[0].active",
        "agents[1]",
        "model",
        "removed",
    ]
    assert metadata["paths"] == 5
    assert metadata["text_chars"] == len(left)
    assert metadata["other_chars"] == len(right)


def test_json_diff_paths_accepts_sentinel_and_equal_documents() -> None:
    """A single directive payload can contain both documents."""

    ok, content, metadata = _run(
        text='{"models":["GPT-5.5","Claude Sonnet 4.6"]}<<<JSON_DIFF_PATHS>>>{"models":["GPT-5.5","Claude Sonnet 4.6"]}'
    )

    assert ok is True
    assert json.loads(content) == []
    assert metadata["paths"] == 0


def test_json_diff_paths_reports_root_type_and_scalar_changes() -> None:
    """Root-level scalar or type differences use the dollar path."""

    ok_type, content_type, _metadata_type = _run(text='{"model":"Kimi K2"}', other="[]")
    ok_scalar, content_scalar, _metadata_scalar = _run(text='"GPT-5.5"', other='"Gemini 3.x"')

    assert ok_type is True and json.loads(content_type) == ["$"]
    assert ok_scalar is True and json.loads(content_scalar) == ["$"]


def test_json_diff_paths_rejects_empty_oversized_invalid_and_ambiguous_input() -> None:
    """Missing, over-limit, malformed, and duplicate-sentinel inputs fail."""

    ok_empty, content_empty, _m1 = _run(text="{}", other="")
    ok_big, content_big, metadata_big = _run(text="{}", other="x" * 20_001)
    ok_bad, content_bad, metadata_bad = _run(text="{}", other='{"a":')
    ok_many_sentinels, content_many_sentinels, _m4 = _run(text="{}<<<JSON_DIFF_PATHS>>>{}<<<JSON_DIFF_PATHS>>>{}")

    assert ok_empty is False and "other is empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big == {"chars": 20_001, "document": "other"}
    assert ok_bad is False and "invalid JSON in other" in content_bad
    assert metadata_bad["document"] == "other"
    assert ok_many_sentinels is False and "more than one" in content_many_sentinels


def test_json_diff_paths_rejects_non_finite_numbers_and_too_many_paths() -> None:
    """Strict JSON numbers and the 2000-path cap are enforced."""

    ok_nan, content_nan, _metadata_nan = _run(text='{"value": NaN}', other='{"value": 1}')
    left = json.dumps(list(range(2001)))
    right = json.dumps(list(range(1, 2002)))
    ok_many, content_many, metadata_many = _run(text=left, other=right)

    assert ok_nan is False and "invalid JSON in text" in content_nan
    assert ok_many is False and "max_paths=2000" in content_many
    assert metadata_many["paths"] == 2000


def test_json_diff_paths_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "json_diff_paths" in tools
    assert tools["json_diff_paths"].name == "json_diff_paths"
    SafetyPolicy().validate_tool("json_diff_paths")
    assert "json_diff_paths" in SafetyPolicy().allowed_tools
