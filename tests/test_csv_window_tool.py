"""Tests for the bounded CSV sliding-window tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_window import CsvWindowTool

_SAMPLE = "model,score\nGPT-5.5,95\nClaude Sonnet 4.6,94\nGemini 3.x,93\nKimi K2,92\n"


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the csv_window tool."""

    result = CsvWindowTool().execute(ToolInvocation(tool_name="csv_window", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_csv_window_emits_overlapping_blocks_with_header() -> None:
    """Default step=1 emits consecutive windows separated by a blank line."""

    ok, content, metadata = _run(text=_SAMPLE, window_size=2)

    assert ok is True
    assert content == (
        "model,score\nGPT-5.5,95\nClaude Sonnet 4.6,94\n"
        "\n"
        "model,score\nClaude Sonnet 4.6,94\nGemini 3.x,93\n"
        "\n"
        "model,score\nGemini 3.x,93\nKimi K2,92\n"
    )
    assert metadata["windows"] == 3
    assert metadata["window_rows"] == 2
    assert metadata["step"] == 1
    assert metadata["rows"] == 4


def test_csv_window_supports_step_start_row_and_index() -> None:
    """step/start_row slice the sequence; index returns one window."""

    ok_step, content_step, metadata_step = _run(text=_SAMPLE, window_size=2, step=2)
    ok_start, content_start, metadata_start = _run(text=_SAMPLE, window_size=2, start_row=1)
    ok_index, content_index, metadata_index = _run(text=_SAMPLE, window_size=2, index=1)

    assert ok_step is True
    assert content_step == ("model,score\nGPT-5.5,95\nClaude Sonnet 4.6,94\n\nmodel,score\nGemini 3.x,93\nKimi K2,92\n")
    assert metadata_step["windows"] == 2

    assert ok_start is True
    assert content_start.startswith("model,score\nClaude Sonnet 4.6,94\nGemini 3.x,93\n")
    assert metadata_start["start_row"] == 1
    assert metadata_start["windows"] == 2

    assert ok_index is True
    assert content_index == "model,score\nClaude Sonnet 4.6,94\nGemini 3.x,93\n"
    assert metadata_index["windows"] == 1
    assert metadata_index["windows_available"] == 3
    assert metadata_index["index"] == 1


def test_csv_window_rejects_bad_options_and_bounds() -> None:
    """Missing/invalid options and out-of-range index/start fail clearly."""

    ok_missing, content_missing, _m1 = _run(text=_SAMPLE)
    ok_window, content_window, _m2 = _run(text=_SAMPLE, window_size=0)
    ok_step, content_step, _m3 = _run(text=_SAMPLE, window_size=2, step=-1)
    ok_index, content_index, metadata_index = _run(text=_SAMPLE, window_size=2, index=99)
    ok_fit, content_fit, metadata_fit = _run(text=_SAMPLE, window_size=5)

    assert ok_missing is False and "window_size is required" in content_missing
    assert ok_window is False and "positive integer" in content_window
    assert ok_step is False and "positive integer" in content_step
    assert ok_index is False and "out of range" in content_index
    assert metadata_index["windows"] == 3
    assert ok_fit is False and "no complete windows" in content_fit
    assert metadata_fit["window_size"] == 5


def test_csv_window_rejects_malformed_headers_and_rows() -> None:
    """Duplicate headers, uneven rows, and malformed quoting fail safely."""

    ok_duplicate, content_duplicate, _m1 = _run(text="a,a\n1,2\n", window_size=1)
    ok_uneven, content_uneven, metadata_uneven = _run(text="a,b\n1\n", window_size=1)
    ok_malformed, content_malformed, _m3 = _run(text='a,b\n"unterminated,1', window_size=1)

    assert ok_duplicate is False and "unique" in content_duplicate
    assert ok_uneven is False and "expected 2" in content_uneven
    assert metadata_uneven["row"] == 2
    assert ok_malformed is False and "parse error" in content_malformed


def test_csv_window_enforces_character_row_and_column_bounds() -> None:
    """Total input, data rows, and header columns are bounded."""

    too_many_rows = "id,value\n" + "".join(f"{index},x\n" for index in range(501))
    too_many_columns = ",".join(f"c{index}" for index in range(65)) + "\n"

    ok_chars, content_chars, metadata_chars = _run(text="a\n" + ("x" * 20_000), window_size=1)
    ok_rows, content_rows, metadata_rows = _run(text=too_many_rows, window_size=1)
    ok_columns, content_columns, metadata_columns = _run(text=too_many_columns, window_size=1)

    assert ok_chars is False and "max_chars" in content_chars
    chars = metadata_chars["chars"]
    assert isinstance(chars, int) and chars > 20_000
    assert ok_rows is False and "max_rows" in content_rows
    assert metadata_rows["rows"] == 501
    assert ok_columns is False and "max_columns" in content_columns
    assert metadata_columns["columns"] == 65


def test_csv_window_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_window" in tools
    assert tools["csv_window"].name == "csv_window"
    SafetyPolicy().validate_tool("csv_window")
    assert "csv_window" in SafetyPolicy().allowed_tools
