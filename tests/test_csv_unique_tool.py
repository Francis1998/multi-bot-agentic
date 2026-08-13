"""Tests for the CSV unique tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_unique import CsvUniqueTool

_SAMPLE = "name,team,score\nAda,A,2\nGrace,B,10\nAda,A,9\nKimi,B,2\n"


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_unique tool."""

    result = CsvUniqueTool().execute(ToolInvocation(tool_name="csv_unique", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_csv_unique_keeps_first_row_per_key_and_header() -> None:
    """Duplicate keys drop later rows; the header stays first."""

    ok, content, metadata = _run(text=_SAMPLE, columns="name")

    assert ok is True
    assert content == "name,team,score\nAda,A,2\nGrace,B,10\nKimi,B,2\n"
    assert metadata["rows"] == 3
    assert metadata["columns"] == 3
    assert metadata["key_columns"] == "name"
    assert metadata["dropped"] == 1


def test_csv_unique_supports_multi_column_keys() -> None:
    """Composite keys keep rows unique on the full key tuple."""

    document = "model,region,rank\nGPT-5.5,us,1\nClaude Sonnet 4.6,eu,2\nGPT-5.5,us,9\nGemini 3.x,us,3\nKimi K2,eu,4\n"
    ok, content, metadata = _run(text=document, columns=["model", "region"])

    assert ok is True
    assert content == ("model,region,rank\nGPT-5.5,us,1\nClaude Sonnet 4.6,eu,2\nGemini 3.x,us,3\nKimi K2,eu,4\n")
    assert metadata["key_columns"] == "model,region"
    assert metadata["dropped"] == 1


def test_csv_unique_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies the dedupe column list."""

    ok, content, metadata = _run(text=f"{_SAMPLE}<<<CSV_UNIQUE>>>team")

    assert ok is True
    assert content == "name,team,score\nAda,A,2\nGrace,B,10\n"
    assert metadata["key_columns"] == "team"
    assert metadata["dropped"] == 2


def test_csv_unique_rejects_empty_oversized_and_missing_column() -> None:
    """Empty, oversized, and missing-column inputs fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="", columns="name")
    ok_big, content_big, metadata_big = _run(text="name\n" + ("x" * 20_000), columns="name")
    ok_arg, content_arg, _m3 = _run(text=_SAMPLE)
    ok_column, content_column, _m4 = _run(text=_SAMPLE, columns="missing")
    ok_dup, content_dup, _m5 = _run(text="a,a\n1,2\n", columns="a")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars=20000" in content_big
    chars = metadata_big["chars"]
    assert isinstance(chars, int) and chars > 20_000
    assert ok_arg is False and "text+columns" in content_arg
    assert ok_column is False and "unknown column" in content_column
    assert ok_dup is False and "unique" in content_dup


def test_csv_unique_rejects_row_and_column_bounds() -> None:
    """CSV input is capped at 500 data rows and 64 columns."""

    too_many_rows = "id\n" + "".join(f"{index}\n" for index in range(501))
    too_many_columns = ",".join(f"c{index}" for index in range(65)) + "\n"
    ok_rows, content_rows, _m1 = _run(text=too_many_rows, columns="id")
    ok_columns, content_columns, _m2 = _run(text=too_many_columns, columns="c0")

    assert ok_rows is False and "max_rows=500" in content_rows
    assert ok_columns is False and "max_columns=64" in content_columns


def test_csv_unique_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_unique" in tools
    assert tools["csv_unique"].name == "csv_unique"
    SafetyPolicy().validate_tool("csv_unique")
    assert "csv_unique" in SafetyPolicy().allowed_tools
