"""Tests for the CSV pivot / unpivot tool."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_pivot import CsvPivotTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_pivot tool with the given arguments."""

    result = CsvPivotTool().execute(ToolInvocation(tool_name="csv_pivot", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


_LONG_CSV = "id,metric,value\na,x,1\na,y,2\nb,x,3\nb,y,4\n"
_WIDE_CSV = "id,x,y\na,1,2\nb,3,4\n"


def test_csv_pivot_pivots_long_to_wide() -> None:
    """Pivot mode reshapes long CSV into wide columns."""

    ok, content, metadata = _run(
        text=_LONG_CSV,
        mode="pivot",
        index="id",
        columns="metric",
        values="value",
    )

    assert ok is True
    assert "id,x,y" in content.splitlines()[0]
    assert "a,1,2" in content
    assert "b,3,4" in content
    assert metadata["mode"] == "pivot"
    assert cast(int, metadata["rows"]) == 2


def test_csv_pivot_unpivots_wide_to_long() -> None:
    """Unpivot mode reshapes wide CSV into long rows."""

    ok, content, metadata = _run(
        text=_WIDE_CSV,
        mode="unpivot",
        id_vars="id",
        value_vars="x,y",
        var_name="metric",
        value_name="value",
    )

    assert ok is True
    assert content.splitlines()[0] == "id,metric,value"
    assert "a,x,1" in content
    assert "a,y,2" in content
    assert metadata["mode"] == "unpivot"
    assert cast(int, metadata["rows"]) == 4


def test_csv_pivot_defaults_to_pivot_mode() -> None:
    """Mode defaults to pivot when omitted."""

    ok, _content, metadata = _run(
        text=_LONG_CSV,
        index="id",
        columns="metric",
        values="value",
    )

    assert ok is True
    assert metadata["mode"] == "pivot"


def test_csv_pivot_rejects_empty_text() -> None:
    """Empty input is a structured failure."""

    ok, content, _metadata = _run(text="")

    assert ok is False
    assert "empty" in content


def test_csv_pivot_rejects_oversized_text() -> None:
    """Documents above the char cap are refused."""

    ok, content, metadata = _run(text="x" * 20_001)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_csv_pivot_rejects_unknown_column() -> None:
    """Unknown pivot columns are refused."""

    ok, content, _metadata = _run(
        text=_LONG_CSV,
        mode="pivot",
        index="missing",
        columns="metric",
        values="value",
    )

    assert ok is False
    assert "unknown column" in content


def test_csv_pivot_rejects_duplicate_pivot_cell() -> None:
    """Duplicate index/column pairs are refused."""

    dup = "id,metric,value\na,x,1\na,x,9\n"
    ok, content, metadata = _run(
        text=dup,
        mode="pivot",
        index="id",
        columns="metric",
        values="value",
    )

    assert ok is False
    assert "duplicate pivot cell" in content
    assert metadata["column"] == "x"


def test_csv_pivot_rejects_unsupported_mode() -> None:
    """Unknown modes are refused."""

    ok, content, metadata = _run(text=_LONG_CSV, mode="melt")

    assert ok is False
    assert "unsupported mode" in content
    assert metadata["mode"] == "melt"


def test_csv_pivot_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_pivot" in tools
    assert tools["csv_pivot"].name == "csv_pivot"
    SafetyPolicy().validate_tool("csv_pivot")
    assert "csv_pivot" in SafetyPolicy().allowed_tools
