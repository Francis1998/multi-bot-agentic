"""Tests for the CSV ↔ TSV bridge tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.csv_tsv import CsvTsvTool


def _run(
    document: str,
    direction: str = "csv_to_tsv",
    *,
    delimiter: str | None = None,
) -> tuple[bool, str]:
    """Execute the csv_tsv tool for a document.

    Args:
        document: Source document text.
        direction: Conversion direction (``csv_to_tsv`` or ``tsv_to_csv``).
        delimiter: Optional single-character input delimiter override.

    Returns:
        Tuple of ``(ok, content)`` from the tool result.
    """

    arguments: dict[str, object] = {"text": document, "direction": direction}
    if delimiter is not None:
        arguments["delimiter"] = delimiter
    result = CsvTsvTool().execute(ToolInvocation(tool_name="csv_tsv", arguments=arguments))
    return result.ok, result.content


def test_csv_tsv_converts_csv_to_tsv() -> None:
    """CSV input is parsed and emitted as tab-delimited TSV."""

    ok, content = _run(
        "model,score\nGPT-5.5,95\nClaude Sonnet 4.6,92\n",
        direction="csv_to_tsv",
    )

    assert ok is True
    assert content == "model\tscore\nGPT-5.5\t95\nClaude Sonnet 4.6\t92"


def test_csv_tsv_converts_tsv_to_csv() -> None:
    """TSV input is parsed and emitted as comma-delimited CSV."""

    ok, content = _run(
        "model\tscore\nGemini 3.x\t90\nKimi K2\t88\n",
        direction="tsv_to_csv",
    )

    assert ok is True
    assert content == "model,score\nGemini 3.x,90\nKimi K2,88"


def test_csv_tsv_quotes_fields_with_commas_when_emitting_csv() -> None:
    """Fields containing commas are quoted in CSV output."""

    ok, content = _run(
        "model\tvendor\nClaude Sonnet 4.6\tAnthropic, Inc.\n",
        direction="tsv_to_csv",
    )

    assert ok is True
    assert content == 'model,vendor\nClaude Sonnet 4.6,"Anthropic, Inc."'


def test_csv_tsv_defaults_to_csv_to_tsv_direction() -> None:
    """Omitting direction converts CSV to TSV."""

    result = CsvTsvTool().execute(ToolInvocation(tool_name="csv_tsv", arguments={"text": "a,b\n1,2\n"}))

    assert result.ok is True
    assert result.content == "a\tb\n1\t2"
    assert result.metadata["direction"] == "csv_to_tsv"


def test_csv_tsv_respects_delimiter_override() -> None:
    """A single-character delimiter override is used when reading input."""

    ok, content = _run("model;score\nGPT-5.5;95\n", direction="csv_to_tsv", delimiter=";")

    assert ok is True
    assert content == "model\tscore\nGPT-5.5\t95"


def test_csv_tsv_rejects_invalid_delimiter() -> None:
    """Multi-character delimiters return a structured failure."""

    ok, content = _run("a,b\n1,2\n", delimiter="||")

    assert ok is False
    assert "delimiter must be a single character" in content


def test_csv_tsv_rejects_uneven_column_counts() -> None:
    """Rows whose width differs from the header are rejected."""

    ok, content = _run("model,score\nGPT-5.5\nGemini 3.x,88", direction="csv_to_tsv")

    assert ok is False
    assert "uneven column counts" in content


def test_csv_tsv_rejects_malformed_csv() -> None:
    """Unterminated quotes return a structured failure."""

    ok, content = _run('model,score\n"GPT-5.5,95\n', direction="csv_to_tsv")

    assert ok is False
    assert "invalid CSV" in content


def test_csv_tsv_rejects_empty_document() -> None:
    """An empty document is reported as a failure."""

    ok, content = _run("   ")

    assert ok is False
    assert "empty" in content


def test_csv_tsv_rejects_oversized_document() -> None:
    """Documents above the fixed character cap are refused before parsing."""

    ok, content = _run("model,score\n" + ("x" * 20_001))

    assert ok is False
    assert "max_chars=20000" in content


def test_csv_tsv_rejects_invalid_direction() -> None:
    """Unknown direction values return a structured failure."""

    ok, content = _run("a,b\n1,2\n", direction="csv_to_json")

    assert ok is False
    assert "invalid direction" in content


def test_csv_tsv_reports_metadata() -> None:
    """Successful results include direction, counts, and delimiter."""

    result = CsvTsvTool().execute(
        ToolInvocation(
            tool_name="csv_tsv",
            arguments={
                "text": "model\tvendor\nKimi K2\tMoonshot\n",
                "direction": "tsv_to_csv",
            },
        )
    )

    assert result.ok is True
    assert result.content == "model,vendor\nKimi K2,Moonshot"
    assert result.metadata == {
        "direction": "tsv_to_csv",
        "row_count": 2,
        "column_count": 2,
        "delimiter": "\t",
    }


def test_csv_tsv_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is available through the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "csv_tsv" in tools
    assert tools["csv_tsv"].name == "csv_tsv"
    SafetyPolicy().validate_tool("csv_tsv")
    assert "csv_tsv" in SafetyPolicy().allowed_tools
