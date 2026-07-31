"""Tests for the HTML table-to-CSV conversion tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.html_table_csv import HtmlTableCsvTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the html_table_csv tool with the given arguments."""

    result = HtmlTableCsvTool().execute(ToolInvocation(tool_name="html_table_csv", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_html_table_csv_converts_first_table() -> None:
    """The default path converts only the first table to CSV."""

    html = """
    <table>
      <tr><th>model</th><th>score</th></tr>
      <tr><td>GPT-5.5</td><td>98</td></tr>
      <tr><td>Claude Sonnet 4.6</td><td>97</td></tr>
    </table>
    <table><tr><td>ignored</td></tr></table>
    """

    ok, content, metadata = _run(text=html)

    assert ok is True
    assert content == "model,score\nGPT-5.5,98\nClaude Sonnet 4.6,97"
    assert metadata["all"] is False
    assert metadata["table_count"] == 2
    assert metadata["tables_rendered"] == 1


def test_html_table_csv_converts_all_tables() -> None:
    """When all=true every table is emitted as a separate CSV block."""

    html = """
    <table><tr><th>a</th></tr><tr><td>1</td></tr></table>
    <table><tr><th>b</th></tr><tr><td>Gemini 3.x</td></tr></table>
    """

    ok, content, metadata = _run(text=html, all=True)

    assert ok is True
    assert content == "a\n1\n\nb\nGemini 3.x"
    assert metadata["all"] is True
    assert metadata["tables_rendered"] == 2


def test_html_table_csv_rejects_script_content() -> None:
    """Documents containing script elements fail."""

    ok, content, metadata = _run(text="<p>ok</p><script>alert(1)</script>")

    assert ok is False
    assert "script" in content
    assert metadata["rejected_tag"] == "script"


def test_html_table_csv_rejects_empty_document() -> None:
    """Whitespace-only input is a structured failure."""

    ok, content, _metadata = _run(text="   ")

    assert ok is False
    assert "empty" in content


def test_html_table_csv_rejects_oversized_document() -> None:
    """Documents above the char cap are refused."""

    ok, content, metadata = _run(text="<p>" + ("x" * 20_001) + "</p>")

    assert ok is False
    assert "max_chars" in content
    assert metadata["chars"] == 20_008


def test_html_table_csv_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "html_table_csv" in tools
    assert tools["html_table_csv"].name == "html_table_csv"
    SafetyPolicy().validate_tool("html_table_csv")
    assert "html_table_csv" in SafetyPolicy().allowed_tools
