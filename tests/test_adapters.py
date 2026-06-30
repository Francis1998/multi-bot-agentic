"""Tests for provider adapter output parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from multi_bot_agentic.config import build_llm_adapter
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.llm.gemini import GeminiAdapter, _extract_gemini_text
from multi_bot_agentic.llm.kimi import KimiAdapter
from multi_bot_agentic.llm.openai import OpenAIAdapter, _extract_openai_text
from multi_bot_agentic.models import ModelRequest, Observation

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


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
                Observation(source="tool:checklist", content="- demo"),
            ),
        ),
        timeout_seconds=1.0,
    )

    assert first.text.startswith("TOOL:checklist:")
    assert second.text.startswith("DONE:")


def test_openai_parser_consumes_assistant_message() -> None:
    """OpenAI-compatible responses are normalized to assistant text."""

    text = _extract_openai_text({"choices": [{"message": {"content": "DONE: ok"}}]})

    assert text == "DONE: ok"


def test_gemini_parser_consumes_candidate_parts() -> None:
    """Gemini candidate parts are normalized to text."""

    text = _extract_gemini_text({"candidates": [{"content": {"parts": [{"text": "DONE:"}, {"text": " ok"}]}}]})

    assert text == "DONE:\n ok"


def test_openai_adapter_default_uses_latest_gpt_stack(monkeypatch: MonkeyPatch) -> None:
    """OpenAI adapter defaults should stay aligned with the current GPT stack."""

    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    adapter = build_llm_adapter("openai")

    assert isinstance(adapter, OpenAIAdapter)
    assert adapter.model == "gpt-5.5"


def test_required_provider_secret_rejects_blank_value(monkeypatch: MonkeyPatch) -> None:
    """Provider construction should fail fast for blank secret values."""

    monkeypatch.setenv("OPENAI_API_KEY", "   ")

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        build_llm_adapter("openai")


def test_gemini_adapter_default_uses_latest_flash_stack(monkeypatch: MonkeyPatch) -> None:
    """Gemini adapter defaults should stay aligned with the current Flash stack."""

    monkeypatch.setenv("GEMINI_API_KEY", "dummy-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    adapter = build_llm_adapter("gemini")

    assert isinstance(adapter, GeminiAdapter)
    assert adapter.model == "gemini-3.5-flash"


def test_kimi_adapter_default_uses_latest_k2_stack(monkeypatch: MonkeyPatch) -> None:
    """Kimi adapter defaults should stay aligned with the current K2 stack."""

    monkeypatch.setenv("KIMI_API_KEY", "dummy-key")
    monkeypatch.delenv("KIMI_MODEL", raising=False)

    adapter = build_llm_adapter("kimi")

    assert isinstance(adapter, KimiAdapter)
    assert adapter.model == "kimi-k2"
