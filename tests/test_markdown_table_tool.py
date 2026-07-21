"""Tests for the deterministic markdown table tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.markdown_table import MarkdownTableTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the markdown_table tool with the given arguments.

    Args:
        **arguments: Tool arguments (``text`` or ``rows``, optional ``delimiter``).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = MarkdownTableTool().execute(ToolInvocation(tool_name="markdown_table", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_markdown_table_renders_csv_text() -> None:
    """A simple CSV document becomes a GitHub-flavored markdown table."""

    ok, content, metadata = _run(text="name,age\nAda,36\nGrace,45\n")

    assert ok is True
    assert content == "\n".join(
        [
            "| name | age |",
            "| --- | --- |",
            "| Ada | 36 |",
            "| Grace | 45 |",
        ]
    )
    assert metadata == {
        "row_count": 2,
        "column_count": 2,
        "input_type": "csv",
        "delimiter": ",",
    }


def test_markdown_table_accepts_rows_argument() -> None:
    """Programmatic callers can pass explicit rows without CSV parsing."""

    ok, content, metadata = _run(rows=[["model", "score"], ["GPT-5.5", 98], ["Kimi K2", None]])

    assert ok is True
    assert content == "\n".join(
        [
            "| model | score |",
            "| --- | --- |",
            "| GPT-5.5 | 98 |",
            "| Kimi K2 |  |",
        ]
    )
    assert metadata["input_type"] == "rows"
    assert metadata["row_count"] == 2


def test_markdown_table_accepts_json_rows_text() -> None:
    """The single decision-engine text payload can also carry JSON rows."""

    ok, content, metadata = _run(text='[["name","role"],["Ada","engineer"]]')

    assert ok is True
    assert content == "\n".join(
        [
            "| name | role |",
            "| --- | --- |",
            "| Ada | engineer |",
        ]
    )
    assert metadata["input_type"] == "json_rows"


def test_markdown_table_respects_custom_delimiter() -> None:
    """A custom single-character delimiter splits CSV-like text fields."""

    ok, content, metadata = _run(text="name|score\nGemini 2.5|96\n", delimiter="|")

    assert ok is True
    assert content == "\n".join(
        [
            "| name | score |",
            "| --- | --- |",
            "| Gemini 2.5 | 96 |",
        ]
    )
    assert metadata["delimiter"] == "|"


def test_markdown_table_escapes_pipe_and_newline_regression() -> None:
    """Cell content with pipes/newlines must not corrupt the table structure.

    This is a regression guard for the markdown-table-specific edge case where
    raw cells containing ``|`` or line breaks created extra columns or broken
    table rows.
    """

    ok, content, metadata = _run(rows=[["name", "notes"], ["Ada|Grace", "first\nsecond"]])

    assert ok is True
    assert content == "\n".join(
        [
            "| name | notes |",
            "| --- | --- |",
            "| Ada\\|Grace | first<br>second |",
        ]
    )
    assert metadata["column_count"] == 2


def test_markdown_table_pads_short_rows() -> None:
    """Ragged CSV rows are padded so the markdown table stays rectangular."""

    ok, content, metadata = _run(text="a,b,c\n1,2\n")

    assert ok is True
    assert content.splitlines()[-1] == "| 1 | 2 |  |"
    assert metadata["column_count"] == 3


def test_markdown_table_rejects_oversized_column_count() -> None:
    """More than the column cap is a structured failure."""

    header = ",".join(f"c{i}" for i in range(33))
    ok, content, metadata = _run(text=header + "\n")

    assert ok is False
    assert "max_columns" in content
    assert metadata["columns"] == 33


def test_markdown_table_rejects_oversized_row_count() -> None:
    """More than the data-row cap is a structured failure."""

    rows = [["name"], *[[f"row{i}"] for i in range(201)]]
    ok, content, metadata = _run(rows=rows)

    assert ok is False
    assert "max_rows" in content
    assert metadata["rows"] == 201


def test_markdown_table_rejects_invalid_rows_argument() -> None:
    """Explicit rows must be a list of row lists."""

    ok, content, metadata = _run(rows=["not", "nested"])

    assert ok is False
    assert "row 0" in content
    assert metadata["input_type"] == "rows"


def test_markdown_table_rejects_empty_document() -> None:
    """Empty or whitespace-only text input is a structured failure."""

    ok, content, _metadata = _run(text="   ")

    assert ok is False
    assert "empty" in content


def test_markdown_table_is_registered_in_default_tools() -> None:
    """The markdown_table tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "markdown_table" in tools
    assert tools["markdown_table"].name == "markdown_table"
    assert "markdown_table" in SafetyPolicy().allowed_tools
