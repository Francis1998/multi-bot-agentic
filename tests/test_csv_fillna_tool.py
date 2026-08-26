"""Tests for the CSV fillna tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_fillna import CsvFillnaTool

_SAMPLE = "model,region,score\nGPT-5.5,,1\n,eu,\nClaude Sonnet 4.6,us,2\n"


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_fillna tool."""

    result = CsvFillnaTool().execute(ToolInvocation(tool_name="csv_fillna", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_csv_fillna_fills_empty_cells_default() -> None:
    """Empty cells become the fill_value (default empty string keeps blanks)."""

    ok, content, metadata = _run(text=_SAMPLE, fill_value="NA")

    assert ok is True
    assert content == ("model,region,score\nGPT-5.5,NA,1\nNA,eu,NA\nClaude Sonnet 4.6,us,2\n")
    assert metadata["filled"] == 3
    assert metadata["fill_value"] == "NA"
    assert metadata["target_columns"] == "model,region,score"


def test_csv_fillna_supports_column_subset_and_sentinel() -> None:
    """Optional columns limit the fill; sentinel form works."""

    ok, content, metadata = _run(text=_SAMPLE, fill_value="X", columns="region,score")
    assert ok is True
    assert content == ("model,region,score\nGPT-5.5,X,1\n,eu,X\nClaude Sonnet 4.6,us,2\n")
    assert metadata["filled"] == 2
    assert metadata["target_columns"] == "region,score"

    ok2, content2, metadata2 = _run(text=f"{_SAMPLE}<<<CSV_FILLNA>>>NA<<<COLUMNS>>>model,score")
    assert ok2 is True
    assert content2 == ("model,region,score\nGPT-5.5,,1\nNA,eu,NA\nClaude Sonnet 4.6,us,2\n")
    assert metadata2["fill_value"] == "NA"


def test_csv_fillna_rejects_empty_oversized_and_bad_columns() -> None:
    """Empty, oversized, duplicate-header, and unknown-column inputs fail."""

    ok_empty, content_empty, _m1 = _run(text="", fill_value="NA")
    ok_big, content_big, metadata_big = _run(text="name\n" + ("x" * 20_000), fill_value="NA")
    ok_dup, content_dup, _m3 = _run(text="a,a\n1,\n", fill_value="NA")
    ok_column, content_column, _m4 = _run(text=_SAMPLE, fill_value="NA", columns="missing")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars=20000" in content_big
    chars = metadata_big["chars"]
    assert isinstance(chars, int) and chars > 20_000
    assert ok_dup is False and "unique" in content_dup
    assert ok_column is False and "unknown column" in content_column


def test_csv_fillna_rejects_row_and_column_bounds() -> None:
    """CSV input is capped at 500 data rows and 64 columns."""

    too_many_rows = "id\n" + "".join(f"{index}\n" for index in range(501))
    too_many_columns = ",".join(f"c{index}" for index in range(65)) + "\n"
    ok_rows, content_rows, _m1 = _run(text=too_many_rows, fill_value="NA")
    ok_columns, content_columns, _m2 = _run(text=too_many_columns, fill_value="NA")

    assert ok_rows is False and "max_rows=500" in content_rows
    assert ok_columns is False and "max_columns=64" in content_columns


def test_csv_fillna_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_fillna" in tools
    assert tools["csv_fillna"].name == "csv_fillna"
    SafetyPolicy().validate_tool("csv_fillna")
    assert "csv_fillna" in SafetyPolicy().allowed_tools
