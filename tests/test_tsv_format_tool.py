"""Tests for the TSV validation and canonicalization tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.tsv_format import TsvFormatTool


def _run(document: str) -> tuple[bool, str]:
    """Execute the tsv_format tool for a document.

    Args:
        document: TSV document text to validate.

    Returns:
        Tuple of ``(ok, content)`` from the tool result.
    """

    result = TsvFormatTool().execute(ToolInvocation(tool_name="tsv_format", arguments={"text": document}))
    return result.ok, result.content


def test_tsv_format_canonicalizes_document() -> None:
    """A valid document is re-serialized with tab delimiters and stable rows."""

    ok, content = _run("model\tscore\nGPT-5.5\t95\nClaude Sonnet 4.6\t92\n")

    assert ok is True
    assert content == "model\tscore\nGPT-5.5\t95\nClaude Sonnet 4.6\t92"


def test_tsv_format_strips_trailing_blank_rows() -> None:
    """Trailing blank rows are removed during canonicalization."""

    ok, content = _run("name\tvalue\nalpha\t1\n\n")

    assert ok is True
    assert content == "name\tvalue\nalpha\t1"


def test_tsv_format_rejects_uneven_column_counts() -> None:
    """Rows whose width differs from the header are rejected."""

    ok, content = _run("model\tscore\nGPT-5.5\nGemini 3.x\t88")

    assert ok is False
    assert "uneven column counts" in content


def test_tsv_format_rejects_empty_document() -> None:
    """An empty document is reported as a failure."""

    ok, content = _run("   ")

    assert ok is False
    assert "empty" in content


def test_tsv_format_rejects_oversized_document() -> None:
    """Documents above the fixed character cap are refused before parsing."""

    ok, content = _run("model\tscore\n" + ("x" * 20_001))

    assert ok is False
    assert "max_chars=20000" in content


def test_tsv_format_reports_metadata() -> None:
    """Successful results include row and column counts."""

    result = TsvFormatTool().execute(
        ToolInvocation(
            tool_name="tsv_format",
            arguments={"text": "model\tvendor\nKimi K2\tMoonshot\n"},
        )
    )

    assert result.ok is True
    assert "Kimi K2\tMoonshot" in result.content
    assert result.metadata == {"row_count": 2, "column_count": 2}


def test_tsv_format_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is available through the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "tsv_format" in tools
    assert tools["tsv_format"].name == "tsv_format"
    SafetyPolicy().validate_tool("tsv_format")
    assert "tsv_format" in SafetyPolicy().allowed_tools
