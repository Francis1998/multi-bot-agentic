"""Tests for the CSV sort tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_sort import CsvSortTool

_SAMPLE = "name,score\nGrace,10\nAda,2\nKimi,2\n"


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_sort tool."""

    result = CsvSortTool().execute(ToolInvocation(tool_name="csv_sort", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_csv_sort_orders_rows_by_column_keeping_header() -> None:
    """Rows sort lexicographically by the named column; header stays first."""

    ok, content, metadata = _run(text=_SAMPLE, column="name")

    assert ok is True
    assert content == "name,score\nAda,2\nGrace,10\nKimi,2\n"
    assert metadata["rows"] == 3
    assert metadata["columns"] == 2
    assert metadata["column"] == "name"
    assert metadata["descending"] is False
    assert metadata["numeric"] is False


def test_csv_sort_supports_descending_and_numeric_modes() -> None:
    """Numeric descending keeps non-numeric values after parsed numbers."""

    document = "model,rank\nGPT-5.5,2\nClaude Sonnet 4.6,10\nGemini 3.x,n/a\nKimi K2,3\n"
    ok, content, metadata = _run(text=document, column="rank", descending=True, numeric=True)

    assert ok is True
    assert content == ("model,rank\nClaude Sonnet 4.6,10\nKimi K2,3\nGPT-5.5,2\nGemini 3.x,n/a\n")
    assert metadata["descending"] is True
    assert metadata["numeric"] is True


def test_csv_sort_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies the sort column name."""

    ok, content, metadata = _run(text=f"{_SAMPLE}<<<CSV_SORT>>>score")

    assert ok is True
    assert content == "name,score\nGrace,10\nAda,2\nKimi,2\n"
    assert metadata["column"] == "score"


def test_csv_sort_rejects_empty_oversized_and_missing_column() -> None:
    """Empty, oversized, and missing-column inputs fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="", column="name")
    ok_big, content_big, metadata_big = _run(text="name\n" + ("x" * 20_000), column="name")
    ok_arg, content_arg, _m3 = _run(text=_SAMPLE)
    ok_column, content_column, _m4 = _run(text=_SAMPLE, column="missing")
    ok_dup, content_dup, _m5 = _run(text="a,a\n1,2\n", column="a")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars=20000" in content_big
    chars = metadata_big["chars"]
    assert isinstance(chars, int) and chars > 20_000
    assert ok_arg is False and "text+column" in content_arg
    assert ok_column is False and "unknown column" in content_column
    assert ok_dup is False and "unique" in content_dup


def test_csv_sort_rejects_row_and_column_bounds() -> None:
    """CSV input is capped at 500 data rows and 64 columns."""

    too_many_rows = "id\n" + "".join(f"{index}\n" for index in range(501))
    too_many_columns = ",".join(f"c{index}" for index in range(65)) + "\n"
    ok_rows, content_rows, _m1 = _run(text=too_many_rows, column="id")
    ok_columns, content_columns, _m2 = _run(text=too_many_columns, column="c0")

    assert ok_rows is False and "max_rows=500" in content_rows
    assert ok_columns is False and "max_columns=64" in content_columns


def test_csv_sort_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_sort" in tools
    assert tools["csv_sort"].name == "csv_sort"
    SafetyPolicy().validate_tool("csv_sort")
    assert "csv_sort" in SafetyPolicy().allowed_tools
