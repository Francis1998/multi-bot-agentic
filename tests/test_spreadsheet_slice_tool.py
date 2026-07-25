"""Tests for the deterministic spreadsheet slice tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.spreadsheet_slice import SpreadsheetSliceTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the spreadsheet_slice tool with the given arguments.

    Args:
        **arguments: Tool arguments (``text``, optional rows/columns/delimiter).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = SpreadsheetSliceTool().execute(ToolInvocation(tool_name="spreadsheet_slice", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_spreadsheet_slice_slices_body_rows() -> None:
    """A zero-based, end-exclusive row range selects body rows, not the header."""

    ok, content, metadata = _run(text="name,age\nAda,36\nGrace,45\nKatherine,40\n", rows="1:3")

    assert ok is True
    payload = json.loads(content)
    assert payload["header"] == ["name", "age"]
    assert payload["rows"] == [["Grace", "45"], ["Katherine", "40"]]
    assert payload["row_start"] == 1
    assert payload["row_end"] == 3
    assert metadata["row_count"] == 2
    assert metadata["source_row_count"] == 3


def test_spreadsheet_slice_slices_columns_by_name_and_index() -> None:
    """Mixed header-name and zero-based index selection preserves request order."""

    ok, content, metadata = _run(
        text="name,age,city\nAda,36,London\nGrace,45,New York\n",
        columns=["city", 0],
    )

    assert ok is True
    payload = json.loads(content)
    assert payload["header"] == ["city", "name"]
    assert payload["rows"] == [["London", "Ada"], ["New York", "Grace"]]
    assert payload["column_indexes"] == [2, 0]
    assert metadata["column_count"] == 2


def test_spreadsheet_slice_accepts_start_end_arguments() -> None:
    """Programmatic callers may use row_start/row_end instead of rows."""

    ok, content, metadata = _run(text="name,age\nAda,36\nGrace,45\n", row_start=0, row_end=1)

    assert ok is True
    payload = json.loads(content)
    assert payload["rows"] == [["Ada", "36"]]
    assert metadata["row_start"] == 0
    assert metadata["row_end"] == 1


def test_spreadsheet_slice_accepts_custom_delimiter_and_sentinel_options() -> None:
    """A single sentinel payload can supply CSV text plus rows/columns/delimiter."""

    text = (
        "name|age|city\nAda|36|London\nGrace|45|New York\n"
        "<<<SPREADSHEET_SLICE>>>\nrows=0:1\ncolumns=name,2\ndelimiter=|"
    )

    ok, content, metadata = _run(text=text)

    assert ok is True
    payload = json.loads(content)
    assert payload["header"] == ["name", "city"]
    assert payload["rows"] == [["Ada", "London"]]
    assert metadata["delimiter"] == "|"
    assert metadata["column_indexes"] == [0, 2]


def test_spreadsheet_slice_rejects_empty_document() -> None:
    """Empty or whitespace-only input is a structured failure."""

    ok, content, _metadata = _run(text="   ")

    assert ok is False
    assert "empty" in content


def test_spreadsheet_slice_rejects_oversized_document() -> None:
    """Documents above the shared CSV cap are rejected before parsing."""

    ok, content, metadata = _run(text="x" * 20_001)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_001


def test_spreadsheet_slice_rejects_invalid_delimiter() -> None:
    """A multi-character delimiter is a structured failure."""

    ok, content, metadata = _run(text="a,b\n1,2\n", delimiter="||")

    assert ok is False
    assert "delimiter" in content
    assert metadata["delimiter"] == "||"


def test_spreadsheet_slice_rejects_invalid_row_range() -> None:
    """Out-of-bounds row ranges fail rather than silently clipping."""

    ok, content, metadata = _run(text="name,age\nAda,36\n", rows="0:2")

    assert ok is False
    assert "out of bounds" in content
    assert metadata["source_row_count"] == 1


def test_spreadsheet_slice_rejects_missing_column_name() -> None:
    """Unknown header names fail with structured metadata."""

    ok, content, metadata = _run(text="name,age\nAda,36\n", column_names="city")

    assert ok is False
    assert "column name not found" in content
    assert metadata["column_name"] == "city"


def test_spreadsheet_slice_rejects_ambiguous_column_name() -> None:
    """Duplicate requested header names are ambiguous."""

    ok, content, metadata = _run(text="name,name\nAda,Lovelace\n", column_names="name")

    assert ok is False
    assert "ambiguous" in content
    assert metadata["matches"] == [0, 1]


def test_spreadsheet_slice_is_registered_in_default_tools() -> None:
    """The spreadsheet_slice tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "spreadsheet_slice" in tools
    assert tools["spreadsheet_slice"].name == "spreadsheet_slice"
    assert "spreadsheet_slice" in SafetyPolicy().allowed_tools
