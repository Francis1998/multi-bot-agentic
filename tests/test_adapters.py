"""Tests for provider adapter output parsing."""

from __future__ import annotations

from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.llm.gemini import _extract_gemini_text
from multi_bot_agentic.llm.openai import _extract_openai_text
from multi_bot_agentic.models import ModelRequest, Observation


def test_fake_adapter_emits_tool_then_done() -> None:
    """The fake adapter emits deterministic text consumed by the runner."""

    adapter = FakeLLMAdapter()
    first = adapter.complete(
        ModelRequest(goal="demo", observations=(Observation(source="user", content="demo"),)),
        timeout_seconds=1.0,
    )
    second = adapter.complete(
        ModelRequest(
            goal="demo",
            observations=(
                Observation(source="user", content="demo"),
                Observation(source="tool:echo", content="demo"),
            ),
        ),
        timeout_seconds=1.0,
    )

    assert first.text.startswith("TOOL:echo:")
    assert second.text.startswith("DONE:")


def test_openai_parser_consumes_assistant_message() -> None:
    """OpenAI-compatible responses are normalized to assistant text."""

    text = _extract_openai_text({"choices": [{"message": {"content": "DONE: ok"}}]})

    assert text == "DONE: ok"


def test_gemini_parser_consumes_candidate_parts() -> None:
    """Gemini candidate parts are normalized to text."""

    text = _extract_gemini_text({"candidates": [{"content": {"parts": [{"text": "DONE:"}, {"text": " ok"}]}}]})

    assert text == "DONE:\n ok"
