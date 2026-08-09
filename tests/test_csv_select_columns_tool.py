"""Tests for the CSV column select/reorder tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_select_columns import CsvSelectColumnsTool


def _run(
    text: str,
    columns: object | None = None,
) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_select_columns tool.

    Args:
        text: CSV document, or combined payload when ``columns`` is omitted.
        columns: Optional column names (list or comma-separated string).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    arguments: dict[str, object] = {"text": text}
    if columns is not None:
        arguments["columns"] = columns
    result = CsvSelectColumnsTool().execute(ToolInvocation(tool_name="csv_select_columns", arguments=arguments))
    return result.ok, result.content, result.metadata


def test_csv_select_columns_reorders_and_projects() -> None:
    """Named columns are selected and emitted in the requested order."""

    csv_text = "id,name,status\n1,Ada,open\n2,Grace,closed\n"
    ok, content, metadata = _run(csv_text, ["status", "id"])

    assert ok is True
    assert content == "status,id\nopen,1\nclosed,2\n"
    assert metadata["rows"] == 2
    assert metadata["columns"] == "status,id"
    assert metadata["column_count"] == 2


def test_csv_select_columns_accepts_comma_string_and_sentinel() -> None:
    """Columns may be a comma string or embedded after <<<CSV_SELECT>>>."""

    csv_text = "a,b,c\n1,2,3\n"
    ok_str, content_str, _m1 = _run(csv_text, "c,a")
    ok_sentinel, content_sentinel, _m2 = _run("a,b,c\n1,2,3\n<<<CSV_SELECT>>>b,a")

    assert ok_str is True
    assert content_str == "c,a\n3,1\n"
    assert ok_sentinel is True
    assert content_sentinel == "b,a\n2,1\n"


def test_csv_select_columns_rejects_unknown_and_duplicate_columns() -> None:
    """Unknown and duplicate requested columns fail structurally."""

    csv_text = "id,name\n1,Ada\n"
    ok_missing, content_missing, metadata_missing = _run(csv_text, ["id", "missing"])
    ok_dup, content_dup, _m2 = _run(csv_text, ["id", "id"])

    assert ok_missing is False
    assert "unknown column" in content_missing
    assert metadata_missing["columns"] == "id,name"
    assert ok_dup is False
    assert "unique" in content_dup


def test_csv_select_columns_rejects_empty_and_oversized_text() -> None:
    """Empty and oversized inputs are refused."""

    ok_empty, content_empty, _m1 = _run("   ", ["id"])
    ok_big, content_big, metadata_big = _run("a\n" + ("x" * 20_001), ["a"])

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    value = metadata_big["chars"]
    assert isinstance(value, int)
    assert value > 20_000


def test_csv_select_columns_rejects_row_and_column_bounds() -> None:
    """CSV row and column caps match the CSV family tools."""

    too_many_rows = "id,status\n" + "".join(f"{index},open\n" for index in range(501))
    too_many_columns = ",".join(f"c{index}" for index in range(65)) + "\n"
    ok_rows, content_rows, metadata_rows = _run(too_many_rows, ["status"])
    ok_cols, content_cols, metadata_cols = _run(too_many_columns, ["c0"])

    assert ok_rows is False
    assert "max_rows=500" in content_rows
    assert metadata_rows["rows"] == 501
    assert ok_cols is False
    assert "max_columns=64" in content_cols
    assert metadata_cols["columns"] == 65


def test_csv_select_columns_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_select_columns" in tools
    assert tools["csv_select_columns"].name == "csv_select_columns"
    SafetyPolicy().validate_tool("csv_select_columns")
    assert "csv_select_columns" in SafetyPolicy().allowed_tools
