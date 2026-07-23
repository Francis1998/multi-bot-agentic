"""Tests for the deterministic CSV parsing tool."""

from __future__ import annotations

import json
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_parse import CsvParseTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv tool with the given arguments.

    Args:
        **arguments: Tool arguments (``text``, optional ``delimiter``).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = CsvParseTool().execute(ToolInvocation(tool_name="csv", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_csv_parses_header_and_rows() -> None:
    """A simple CSV yields header, rows, and counts as canonical JSON."""

    ok, content, metadata = _run(text="name,age\nAda,36\nGrace,45\n")

    assert ok is True
    payload = json.loads(content)
    assert payload["header"] == ["name", "age"]
    assert payload["rows"] == [["Ada", "36"], ["Grace", "45"]]
    assert payload["row_count"] == 2
    assert metadata["column_count"] == 2


def test_csv_respects_custom_delimiter() -> None:
    """A custom single-character delimiter splits fields."""

    ok, content, metadata = _run(text="a|b\n1|2\n", delimiter="|")

    assert ok is True
    payload = json.loads(content)
    assert payload["header"] == ["a", "b"]
    assert payload["rows"] == [["1", "2"]]
    assert metadata["delimiter"] == "|"


def test_csv_rejects_blank_header_cells() -> None:
    """Blank header cells are ambiguous column names and must fail.

    This previously parsed successfully with ``""`` as a column name, making the
    result hard for downstream agents to reference deterministically.
    """

    ok, content, metadata = _run(text="name,\nAda,36\n")

    assert ok is False
    assert "blank column names" in content
    assert metadata["columns"] == [1]


def test_csv_rejects_oversized_column_count() -> None:
    """More than the column cap is a structured failure."""

    header = ",".join(f"c{i}" for i in range(33))
    ok, content, metadata = _run(text=header + "\n")

    assert ok is False
    assert "max_columns" in content
    assert metadata["columns"] == 33


def test_csv_rejects_empty_document() -> None:
    """Empty or whitespace-only input is a structured failure."""

    ok, content, _metadata = _run(text="   ")

    assert ok is False
    assert "empty" in content


def test_csv_rejects_invalid_delimiter() -> None:
    """A multi-character delimiter is a structured failure."""

    ok, content, metadata = _run(text="a,b\n", delimiter="||")

    assert ok is False
    assert "delimiter" in content
    assert metadata["delimiter"] == "||"


def test_csv_is_registered_in_default_tools() -> None:
    """The csv tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "csv" in tools
    assert tools["csv"].name == "csv"
    assert "csv" in SafetyPolicy().allowed_tools
