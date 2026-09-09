"""Tests for ObservationRedactor."""

from __future__ import annotations

import pytest

from multi_bot_agentic.observation_redactor import ObservationRedactor


def test_redacts_email_phone_and_token() -> None:
    """Emails, phones, and API tokens are replaced with placeholders."""

    text = (
        "Contact ada@example.com at +1 (415) 555-1234. "
        "Authorization: Bearer abcdEFGH1234567890xyz. "
        "key=sk-abcdefghijklmnopqrstuvwxyz12"
    )
    result = ObservationRedactor().redact(text)
    assert "ada@example.com" not in result.redacted_text
    assert "415" not in result.redacted_text or "[PHONE]" in result.redacted_text
    assert "[EMAIL]" in result.redacted_text
    assert "[PHONE]" in result.redacted_text
    assert "[TOKEN]" in result.redacted_text
    assert "Bearer abcd" not in result.redacted_text
    assert "sk-abcdefghijklmnopqrstuvwxyz12" not in result.redacted_text
    assert "email" in result.categories
    assert "phone" in result.categories
    assert "token" in result.categories


def test_redacts_ssn_like() -> None:
    """SSN-like 3-2-4 digit groups are redacted."""

    result = ObservationRedactor().redact("ssn 123-45-6789 on file")
    assert "[SSN]" in result.redacted_text
    assert "123-45-6789" not in result.redacted_text
    assert "ssn" in result.categories


def test_leaves_safe_text() -> None:
    """Plain operational text is unchanged."""

    text = "Bot observed checklist step complete for launch plan."
    result = ObservationRedactor().redact(text)
    assert result.redacted_text == text
    assert result.redaction_count == 0
    assert result.categories == ()


def test_redaction_count_accurate() -> None:
    """redaction_count equals the number of replacements."""

    text = "a@b.co and c@d.com and 111-22-3333"
    result = ObservationRedactor().redact(text)
    assert result.redaction_count == 3
    assert result.categories == ("email", "ssn")


def test_non_string_raises() -> None:
    """Non-string input raises TypeError."""

    with pytest.raises(TypeError):
        ObservationRedactor().redact(123)  # type: ignore[arg-type]
