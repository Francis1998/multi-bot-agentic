"""Tests for the CSV group-by / aggregate tool."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_groupby import CsvGroupbyTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_groupby tool with the given arguments."""

    result = CsvGroupbyTool().execute(ToolInvocation(tool_name="csv_groupby", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


_CSV = "team,metric,value\na,x,1\na,x,3\nb,x,2\na,y,4\n"


def test_csv_groupby_sums_by_key() -> None:
    """Sum aggregation groups numeric values by key columns."""

    ok, content, metadata = _run(text=_CSV, by="team,metric", values="value", agg="sum")

    assert ok is True
    assert content.splitlines()[0] == "team,metric,value_sum"
    assert "a,x,4" in content
    assert "b,x,2" in content
    assert "a,y,4" in content
    assert metadata["agg"] == "sum"
    assert cast(int, metadata["groups"]) == 3


def test_csv_groupby_counts_rows() -> None:
    """Count aggregation returns row counts per group."""

    ok, content, metadata = _run(text=_CSV, by="team", values="value", agg="count")

    assert ok is True
    assert "a,3" in content
    assert "b,1" in content
    assert metadata["agg"] == "count"


def test_csv_groupby_defaults_to_sum() -> None:
    """Agg defaults to sum when omitted."""

    ok, _content, metadata = _run(text=_CSV, by="team", values="value")

    assert ok is True
    assert metadata["agg"] == "sum"


def test_csv_groupby_rejects_empty_text() -> None:
    """Empty input is a structured failure."""

    ok, content, _metadata = _run(text="", by="team", values="value")

    assert ok is False
    assert "empty" in content


def test_csv_groupby_rejects_non_numeric() -> None:
    """Non-numeric value cells are refused."""

    ok, content, metadata = _run(
        text="team,value\na,x\n",
        by="team",
        values="value",
    )

    assert ok is False
    assert "non-numeric" in content
    assert metadata["value"] == "x"


def test_csv_groupby_rejects_unknown_column() -> None:
    """Unknown group columns are refused."""

    ok, content, _metadata = _run(text=_CSV, by="missing", values="value")

    assert ok is False
    assert "unknown column" in content


def test_csv_groupby_rejects_unsupported_agg() -> None:
    """Unknown aggregations are refused."""

    ok, content, metadata = _run(text=_CSV, by="team", values="value", agg="median")

    assert ok is False
    assert "unsupported agg" in content
    assert metadata["agg"] == "median"


def test_csv_groupby_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_groupby" in tools
    assert tools["csv_groupby"].name == "csv_groupby"
    SafetyPolicy().validate_tool("csv_groupby")
    assert "csv_groupby" in SafetyPolicy().allowed_tools
