"""Tests for the CSV join / lookup tool."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_join import CsvJoinTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_join tool with the given arguments."""

    result = CsvJoinTool().execute(ToolInvocation(tool_name="csv_join", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


_LEFT = "id,name\n1,alice\n2,bob\n3,cara\n"
_RIGHT = "id,score\n1,10\n3,30\n4,40\n"


def test_csv_join_inner_on_shared_key() -> None:
    """Inner join keeps only matching keys."""

    ok, content, metadata = _run(left=_LEFT, right=_RIGHT, on="id", how="inner")

    assert ok is True
    assert content.splitlines()[0] == "id,name,score"
    assert "1,alice,10" in content
    assert "3,cara,30" in content
    assert "bob" not in content
    assert cast(int, metadata["rows"]) == 2
    assert metadata["how"] == "inner"


def test_csv_join_left_keeps_unmatched() -> None:
    """Left join keeps left rows without a right match."""

    ok, content, metadata = _run(text=_LEFT, right=_RIGHT, on="id", how="left")

    assert ok is True
    assert "2,bob," in content
    assert cast(int, metadata["rows"]) == 3
    assert metadata["how"] == "left"


def test_csv_join_left_on_right_on() -> None:
    """Differing key names are supported via left_on/right_on."""

    right = "user_id,score\n1,10\n2,20\n"
    ok, content, metadata = _run(
        left=_LEFT,
        right=right,
        left_on="id",
        right_on="user_id",
        how="inner",
    )

    assert ok is True
    assert "1,alice,10" in content
    assert metadata["left_on"] == "id"
    assert metadata["right_on"] == "user_id"


def test_csv_join_rejects_empty_right() -> None:
    """Empty right CSV is a structured failure."""

    ok, content, _metadata = _run(left=_LEFT, right="", on="id")

    assert ok is False
    assert "right" in content and "empty" in content


def test_csv_join_rejects_unknown_column() -> None:
    """Unknown join keys are refused."""

    ok, content, _metadata = _run(left=_LEFT, right=_RIGHT, on="missing")

    assert ok is False
    assert "unknown" in content


def test_csv_join_rejects_unsupported_how() -> None:
    """Unsupported join types are refused."""

    ok, content, metadata = _run(left=_LEFT, right=_RIGHT, on="id", how="outer")

    assert ok is False
    assert "unsupported how" in content
    assert metadata["how"] == "outer"


def test_csv_join_is_registered_in_default_tools(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_join" in tools
    assert tools["csv_join"].name == "csv_join"
    SafetyPolicy().validate_tool("csv_join")
    assert "csv_join" in SafetyPolicy().allowed_tools
