"""Tests for the CSV column predicate filter tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_filter import CsvFilterTool


def _run(
    text: str,
    column: str | None = None,
    value: str | None = None,
    **kwargs: object,
) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_filter tool.

    Args:
        text: CSV document, or combined payload when ``column``/``value`` are omitted.
        column: Optional column name for programmatic invocation.
        value: Optional predicate value for programmatic invocation.
        kwargs: Extra tool arguments such as ``mode`` or ``case_insensitive``.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    arguments: dict[str, object] = {"text": text, **kwargs}
    if column is not None:
        arguments["column"] = column
    if value is not None:
        arguments["value"] = value
    result = CsvFilterTool().execute(ToolInvocation(tool_name="csv_filter", arguments=arguments))
    return result.ok, result.content, result.metadata


def test_csv_filter_equals_case_insensitive_by_default() -> None:
    """Default mode keeps rows whose selected column equals the value case-insensitively."""

    csv_text = "id,status\n1,Open\n2,closed\n3,OPEN\n"
    ok, content, metadata = _run(csv_text, "status", "open")

    assert ok is True
    assert content == "id,status\n1,Open\n3,OPEN\n"
    assert metadata["rows_in"] == 3
    assert metadata["rows_out"] == 2
    assert metadata["column"] == "status"


def test_csv_filter_contains_can_be_case_sensitive() -> None:
    """Contains mode honors case_insensitive=false."""

    csv_text = "id,name\n1,Ada Lovelace\n2,Grace Hopper\n3,ada Byron\n"
    ok, content, metadata = _run(
        csv_text,
        "name",
        "Ada",
        mode="contains",
        case_insensitive=False,
    )

    assert ok is True
    assert content == "id,name\n1,Ada Lovelace\n"
    assert metadata["mode"] == "contains"
    assert metadata["case_insensitive"] is False


def test_csv_filter_sentinel_equals_and_contains_forms() -> None:
    """A single text payload may split on <<<CSV_FILTER>>> with equals or contains operators."""

    equals_payload = "id,status\n1,open\n2,closed\n<<<CSV_FILTER>>>status<<<=>>>open"
    contains_payload = "id,title\n1,urgent bug\n2,feature\n<<<CSV_FILTER>>>title<<<~>>>bug"
    ok_equals, content_equals, _m1 = _run(equals_payload)
    ok_contains, content_contains, _m2 = _run(contains_payload)

    assert ok_equals is True
    assert content_equals == "id,status\n1,open\n"
    assert ok_contains is True
    assert content_contains == "id,title\n1,urgent bug\n"


def test_csv_filter_returns_header_when_no_rows_match() -> None:
    """No matching rows still returns a valid CSV with the original header."""

    ok, content, metadata = _run("id,status\n1,open\n", "status", "closed")

    assert ok is True
    assert content == "id,status\n"
    assert metadata["rows_in"] == 1
    assert metadata["rows_out"] == 0


def test_csv_filter_rejects_unknown_column_and_bad_mode() -> None:
    """Unknown columns and unsupported modes fail structurally."""

    ok_column, content_column, metadata_column = _run("id,status\n1,open\n", "missing", "open")
    ok_mode, content_mode, metadata_mode = _run("id,status\n1,open\n", "status", "open", mode="regex")

    assert ok_column is False
    assert "unknown column" in content_column
    assert metadata_column["columns"] == "id,status"
    assert ok_mode is False
    assert "unsupported mode" in content_mode
    assert metadata_mode["mode"] == "regex"


def test_csv_filter_rejects_empty_and_oversized_text() -> None:
    """Empty and oversized inputs are refused."""

    ok_empty, content_empty, _m1 = _run("   ", "status", "open")
    ok_big, content_big, metadata_big = _run("a\n" + ("x" * 20_001), "a", "x")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    value = metadata_big["chars"]
    assert isinstance(value, int)
    assert value > 20_000


def test_csv_filter_rejects_row_and_column_bounds() -> None:
    """CSV row and column caps match the newer CSV family tools."""

    too_many_rows = "id,status\n" + "".join(f"{index},open\n" for index in range(501))
    too_many_columns = ",".join(f"c{index}" for index in range(65)) + "\n"
    ok_rows, content_rows, metadata_rows = _run(too_many_rows, "status", "open")
    ok_cols, content_cols, metadata_cols = _run(too_many_columns, "c0", "")

    assert ok_rows is False
    assert "max_rows=500" in content_rows
    assert metadata_rows["rows"] == 501
    assert ok_cols is False
    assert "max_columns=64" in content_cols
    assert metadata_cols["columns"] == 65


def test_csv_filter_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_filter" in tools
    assert tools["csv_filter"].name == "csv_filter"
    SafetyPolicy().validate_tool("csv_filter")
    assert "csv_filter" in SafetyPolicy().allowed_tools
