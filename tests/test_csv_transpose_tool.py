"""Tests for the CSV transpose tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_transpose import CsvTransposeTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_transpose tool."""

    result = CsvTransposeTool().execute(ToolInvocation(tool_name="csv_transpose", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_csv_transpose_flips_rows_and_columns() -> None:
    """A rectangular CSV becomes its transpose."""

    ok, content, metadata = _run(text="model,provider\nGPT-5.5,openai\nClaude Sonnet 4.6,anthropic\n")

    assert ok is True
    assert content == "model,GPT-5.5,Claude Sonnet 4.6\nprovider,openai,anthropic\n"
    assert metadata["input_rows"] == 3
    assert metadata["input_columns"] == 2
    assert metadata["output_rows"] == 2
    assert metadata["output_columns"] == 3


def test_csv_transpose_pads_short_rows() -> None:
    """Short rows are right-padded with empty cells before transpose."""

    ok, content, metadata = _run(text="a,b,c\n1,2\n")

    assert ok is True
    assert content == "a,1\nb,2\nc,\n"
    assert metadata["input_columns"] == 3
    assert metadata["output_rows"] == 3


def test_csv_transpose_rejects_empty_and_malformed() -> None:
    """Empty and malformed CSV documents fail safely."""

    ok_empty, content_empty, _m1 = _run(text="   ")
    ok_bad, content_bad, _m2 = _run(text='a,b\n"unclosed')

    assert ok_empty is False and "empty" in content_empty
    assert ok_bad is False and "csv parse error" in content_bad


def test_csv_transpose_enforces_bounds() -> None:
    """Oversized documents and column counts are rejected."""

    ok_chars, content_chars, meta = _run(text="x" * 20_001)
    wide = ",".join(f"c{i}" for i in range(65)) + "\n"
    ok_cols, content_cols, _m2 = _run(text=wide)

    assert ok_chars is False and "max_chars" in content_chars and meta["chars"] == 20_001
    assert ok_cols is False and "max_columns" in content_cols


def test_csv_transpose_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_transpose" in tools
    assert tools["csv_transpose"].name == "csv_transpose"
    SafetyPolicy().validate_tool("csv_transpose")
    assert "csv_transpose" in SafetyPolicy().allowed_tools
