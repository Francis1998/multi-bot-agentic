"""Tests for the bounded CSV vertical stacking tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_stack import CsvStackTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_stack tool."""

    result = CsvStackTool().execute(ToolInvocation(tool_name="csv_stack", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_csv_stack_stacks_a_list_with_one_header() -> None:
    """List input appends rows in document order and emits one header."""

    ok, content, metadata = _run(
        csvs=[
            "model,score\nGPT-5.5,95\nClaude Sonnet 4.6,94\n",
            "model,score\nGemini 3.x,93\nKimi K2,92\n",
        ]
    )

    assert ok is True
    assert content == ("model,score\nGPT-5.5,95\nClaude Sonnet 4.6,94\nGemini 3.x,93\nKimi K2,92\n")
    assert metadata["documents"] == 2
    assert metadata["rows"] == 4
    assert metadata["columns"] == 2


def test_csv_stack_accepts_sentinel_text_and_quoted_cells() -> None:
    """Directive input is split on the sentinel and parsed with stdlib CSV."""

    ok, content, metadata = _run(
        text='model,note\nGPT-5.5,"fast, safe"\n<<<CSV_STACK>>>model,note\nKimi K2,"open, capable"\n'
    )

    assert ok is True
    assert content == 'model,note\nGPT-5.5,"fast, safe"\nKimi K2,"open, capable"\n'
    assert metadata["documents"] == 2
    assert metadata["rows"] == 2


def test_csv_stack_rejects_mismatched_headers() -> None:
    """All headers must have the same names in the same order."""

    ok_order, content_order, metadata_order = _run(
        csvs=["model,score\nGPT-5.5,95\n", "score,model\n94,Claude Sonnet 4.6\n"]
    )
    ok_name, content_name, _metadata_name = _run(csvs=["model,score\nGPT-5.5,95\n", "model,rating\nGemini 3.x,93\n"])

    assert ok_order is False and "header does not match" in content_order
    assert metadata_order["document"] == 2
    assert ok_name is False and "header does not match" in content_name


def test_csv_stack_rejects_empty_ambiguous_and_single_inputs() -> None:
    """Input must contain at least two non-empty documents in one form."""

    invalid_arguments: list[dict[str, object]] = [
        {},
        {"csvs": []},
        {"csvs": ["a\n"]},
        {"csvs": ["a\n", "   "]},
        {"csvs": "a\n<<<CSV_STACK>>>a\n"},
        {"csvs": ["a\n", 3]},
        {"csvs": ["a\n", "a\n"], "text": "a\n<<<CSV_STACK>>>a\n"},
        {"text": "a\n<<<CSV_STACK>>>"},
    ]
    for arguments in invalid_arguments:
        ok, _content, _metadata = _run(**arguments)
        assert ok is False


def test_csv_stack_rejects_malformed_headers_and_rows() -> None:
    """Duplicate headers, uneven rows, and malformed quoting fail safely."""

    ok_duplicate, content_duplicate, _m1 = _run(csvs=["a,a\n1,2\n", "a,a\n3,4\n"])
    ok_uneven, content_uneven, metadata_uneven = _run(csvs=["a,b\n1\n", "a,b\n2,3\n"])
    ok_malformed, content_malformed, metadata_malformed = _run(csvs=['a,b\n"unterminated,1', "a,b\n2,3\n"])

    assert ok_duplicate is False and "unique" in content_duplicate
    assert ok_uneven is False and "expected 2" in content_uneven
    assert metadata_uneven["row"] == 2
    assert ok_malformed is False and "parse error" in content_malformed
    assert metadata_malformed["document"] == 1


def test_csv_stack_enforces_character_row_and_column_bounds() -> None:
    """Total input, output rows, and header columns are bounded."""

    rows_a = "".join(f"{index},a\n" for index in range(251))
    rows_b = "".join(f"{index},b\n" for index in range(251))
    too_many_columns = ",".join(f"c{index}" for index in range(65))

    ok_chars, content_chars, metadata_chars = _run(csvs=["a\n" + ("x" * 20_000), "a\n"])
    ok_rows, content_rows, metadata_rows = _run(csvs=[f"id,value\n{rows_a}", f"id,value\n{rows_b}"])
    ok_columns, content_columns, metadata_columns = _run(csvs=[f"{too_many_columns}\n", f"{too_many_columns}\n"])

    assert ok_chars is False and "max_chars" in content_chars
    chars = metadata_chars["chars"]
    assert isinstance(chars, int) and chars > 20_000
    assert ok_rows is False and "max_rows" in content_rows
    assert metadata_rows["rows"] == 501
    assert ok_columns is False and "max_columns" in content_columns
    assert metadata_columns["columns"] == 65


def test_csv_stack_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_stack" in tools
    assert tools["csv_stack"].name == "csv_stack"
    SafetyPolicy().validate_tool("csv_stack")
    assert "csv_stack" in SafetyPolicy().allowed_tools
