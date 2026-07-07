"""Tests for the PII redaction tool."""

from __future__ import annotations

from multi_bot_agentic.models import ToolInvocation, ToolResult
from multi_bot_agentic.tools.redaction import RedactionTool


def _run(document: str) -> ToolResult:
    """Execute the redact tool for a document.

    Args:
        document: Text to scrub.

    Returns:
        The tool result.
    """

    return RedactionTool().execute(ToolInvocation(tool_name="redact", arguments={"text": document}))


def test_redact_scrubs_email_phone_ssn_and_ip() -> None:
    """Each supported PII category is replaced with its typed placeholder."""

    result = _run("Contact jane.doe@example.com or 415-555-0142, SSN 123-45-6789, host 10.0.0.1")

    assert result.ok is True
    assert result.content == "Contact [EMAIL] or [PHONE], SSN [SSN], host [IP]"
    assert result.metadata["email"] == 1
    assert result.metadata["phone"] == 1
    assert result.metadata["ssn"] == 1
    assert result.metadata["ipv4"] == 1
    assert result.metadata["total"] == 4


def test_redact_counts_multiple_matches() -> None:
    """Repeated values of one category are all redacted and counted."""

    result = _run("a@b.com and c@d.org both work")

    assert result.ok is True
    assert result.content == "[EMAIL] and [EMAIL] both work"
    assert result.metadata["email"] == 2
    assert result.metadata["total"] == 2


def test_redact_leaves_clean_text_unchanged() -> None:
    """Text with no PII is returned verbatim with a zero total."""

    result = _run("no personal data here")

    assert result.ok is True
    assert result.content == "no personal data here"
    assert result.metadata["total"] == 0


def test_redact_rejects_empty_document() -> None:
    """An empty or whitespace-only document is a structured failure."""

    result = _run("   ")

    assert result.ok is False
    assert "empty" in result.content
