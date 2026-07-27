"""Tests for the deterministic HTML table extraction tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.html_table import HtmlTableTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the html_table tool with the given arguments."""

    result = HtmlTableTool().execute(ToolInvocation(tool_name="html_table", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_html_table_extracts_first_table_as_markdown() -> None:
    """The default path extracts the first table and renders markdown."""

    html = """
    <h1>Leaderboard</h1>
    <table>
      <tr><th>model</th><th>score</th></tr>
      <tr><td>GPT-5.5</td><td>98 &amp; rising</td></tr>
      <tr><td>Claude Sonnet 4.6</td><td>97<br />steady</td></tr>
    </table>
    <table><tr><td>ignored</td></tr></table>
    """

    ok, content, metadata = _run(text=html)

    assert ok is True
    assert content == "\n".join(
        [
            "| model | score |",
            "| --- | --- |",
            "| GPT-5.5 | 98 & rising |",
            "| Claude Sonnet 4.6 | 97<br>steady |",
        ]
    )
    assert metadata["table_index"] == 1
    assert metadata["table_count"] == 2
    assert metadata["row_count"] == 3
    assert metadata["column_count"] == 2
    assert metadata["format"] == "markdown"


def test_html_table_extracts_indexed_table_as_csv_from_sentinel_options() -> None:
    """A 1-based index and CSV format can be supplied in a single text payload."""

    html = "".join(
        [
            "<table><tr><td>first</td></tr></table>",
            "<table>",
            "<tr><th>model</th><th>owner</th></tr>",
            "<tr><td>Gemini 3.x</td><td>Google</td></tr>",
            "<tr><td>Kimi K2</td><td>Moonshot</td></tr>",
            "</table>",
            "<<<HTML_TABLE>>>index=2;format=csv",
        ]
    )

    ok, content, metadata = _run(text=html)

    assert ok is True
    assert content == "\n".join(
        [
            "model,owner",
            "Gemini 3.x,Google",
            "Kimi K2,Moonshot",
        ]
    )
    assert metadata["table_index"] == 2
    assert metadata["table_count"] == 2
    assert metadata["row_count"] == 3
    assert metadata["column_count"] == 2
    assert metadata["format"] == "csv"


def test_html_table_returns_failure_when_no_table_exists() -> None:
    """Missing tables return ``ok=False`` rather than raising."""

    ok, content, metadata = _run(text="<p>No tabular data here.</p>")

    assert ok is False
    assert "no table" in content
    assert metadata == {"table_count": 0}


def test_html_table_returns_failure_for_out_of_bounds_table_index() -> None:
    """A requested 1-based index beyond the table count is structured metadata."""

    ok, content, metadata = _run(text="<table><tr><td>only</td></tr></table>", table_index=2)

    assert ok is False
    assert "out of bounds" in content
    assert metadata == {"table_index": 2, "table_count": 1}


def test_html_table_rejects_oversized_document() -> None:
    """Documents above the character cap are refused before parsing."""

    document = "<table><tr><td>" + ("x" * 20_000) + "</td></tr></table>"

    ok, content, metadata = _run(text=document)

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == len(document)


def test_html_table_rejects_oversized_row_count() -> None:
    """More than the row cap is a structured failure."""

    rows = "".join("<tr><td>x</td></tr>" for _ in range(201))

    ok, content, metadata = _run(text=f"<table>{rows}</table>")

    assert ok is False
    assert "max_rows" in content
    assert metadata["rows"] == 201


def test_html_table_rejects_oversized_column_count() -> None:
    """More than the column cap is a structured failure."""

    cells = "".join(f"<td>c{i}</td>" for i in range(33))

    ok, content, metadata = _run(text=f"<table><tr>{cells}</tr></table>")

    assert ok is False
    assert "max_columns" in content
    assert metadata["columns"] == 33


def test_html_table_is_registered_in_default_tools() -> None:
    """The html_table tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "html_table" in tools
    assert tools["html_table"].name == "html_table"
    assert "html_table" in SafetyPolicy().allowed_tools
