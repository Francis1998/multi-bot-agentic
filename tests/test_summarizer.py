"""Tests for ConversationSummarizer."""

from __future__ import annotations

import pytest

from multi_bot_agentic.summarizer import ConversationSummarizer


def test_empty_conversation() -> None:
    """Empty input yields empty summary marker."""

    summary = ConversationSummarizer().summarize([])
    assert summary.message_count == 0
    assert "empty" in summary.summary_text


def test_head_tail_and_keywords() -> None:
    """Long transcripts keep head/tail and extract keywords from middle."""

    messages = [
        "User goal: launch checklist",
        "Bot observes requirements",
        "Discuss kubernetes FastAPI deployment",
        "Discuss kubernetes Redis caching",
        "Discuss FastAPI Redis again",
        "Final decision: ship MVP",
        "Done",
    ]
    summary = ConversationSummarizer(keep_head=2, keep_tail=2, max_keywords=5).summarize(messages)
    assert summary.message_count == 7
    assert len(summary.kept_head) == 2
    assert len(summary.kept_tail) == 2
    assert "fastapi" in summary.keywords or "redis" in summary.keywords
    assert "HEAD:" in summary.summary_text
    assert "TAIL:" in summary.summary_text


def test_max_summary_chars_enforced() -> None:
    """Summary text is truncated to max_summary_chars."""

    messages = ["x" * 200 for _ in range(10)]
    summary = ConversationSummarizer(max_summary_chars=80, keep_head=1, keep_tail=1).summarize(messages)
    assert len(summary.summary_text) <= 80


def test_invalid_config_raises() -> None:
    """Invalid constructor args raise ValueError."""

    with pytest.raises(ValueError):
        ConversationSummarizer(max_summary_chars=1)
    with pytest.raises(ValueError):
        ConversationSummarizer(max_keywords=0)


def test_non_string_messages_raise() -> None:
    """Non-string message entries raise TypeError."""

    with pytest.raises(TypeError):
        ConversationSummarizer().summarize(["ok", 1])  # type: ignore[list-item]


def test_deterministic() -> None:
    """Repeated summarize calls match."""

    msgs = ["alpha beta", "beta gamma", "gamma delta", "delta epsilon"]
    s = ConversationSummarizer()
    assert s.summarize(msgs) == s.summarize(msgs)
