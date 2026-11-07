"""Tests for provider adapter output parsing."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from multi_bot_agentic.config import build_llm_adapter
from multi_bot_agentic.llm.claude_code_cli import ClaudeCodeCLIAdapter
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


def test_openai_parser_consumes_structured_content_parts() -> None:
    """Assistant content delivered as a parts list must be joined, not rejected.

    The base Chat Completions contract returns ``message.content`` as a string,
    but several OpenAI-compatible gateways (LiteLLM, vLLM, OpenRouter) return it
    as a list of ``{"type": "text", "text": ...}`` parts. The adapter previously
    only accepted a string and raised ``ValueError`` for the list shape, which
    the runner records as a failed run. Structured text parts must be joined into
    the assistant text.
    """

    text = _extract_openai_text(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "DONE:"},
                            {"type": "text", "text": " ok"},
                        ]
                    }
                }
            ]
        }
    )

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
    assert adapter.model == "gpt-6.1-sol"


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
    assert adapter.model == "gemini-3.8-flash"


def test_claude_code_adapter_maps_timeout_to_runtime_error(monkeypatch: MonkeyPatch) -> None:
    """A Claude Code CLI timeout must surface as a RuntimeError the runner handles.

    ``subprocess.run`` raises ``subprocess.TimeoutExpired`` when the CLI exceeds
    its timeout budget. That exception is a ``SubprocessError``, not an
    ``OSError``/``RuntimeError``/``ValueError``, so it previously escaped the
    ``AgentRunner`` loop's ``except`` clause and crashed the process instead of
    being recorded as a failed run. The adapter must translate it into a
    ``RuntimeError`` (its documented provider-failure contract).
    """

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1.0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = ClaudeCodeCLIAdapter(command="claude")
    request = ModelRequest(
        goal="demo",
        observations=(Observation(source="user", content="demo"),),
    )

    with pytest.raises(RuntimeError, match="timed out"):
        adapter.complete(request, timeout_seconds=1.0)


def test_kimi_adapter_default_uses_latest_k3_stack(monkeypatch: MonkeyPatch) -> None:
    """Kimi adapter defaults should stay aligned with the current K3 stack (K2 is being retired)."""

    monkeypatch.setenv("KIMI_API_KEY", "dummy-key")
    monkeypatch.delenv("KIMI_MODEL", raising=False)

    adapter = build_llm_adapter("kimi")

    assert isinstance(adapter, KimiAdapter)
    assert adapter.model == "kimi-k3.1-pro"


# Sampling parameters that reasoning models reject: GPT-6 (reasoning effort above "none") does not accept
# temperature/top_p/logprobs, and Kimi K3 fixes temperature/top_p/n/penalties ("omit them from requests").
_FIXED_OR_UNSUPPORTED = {
    "temperature",
    "top_p",
    "top_k",
    "n",
    "presence_penalty",
    "frequency_penalty",
    "logprobs",
    "top_logprobs",
}


def _captured_payload(monkeypatch: MonkeyPatch, adapter: OpenAIAdapter) -> dict[str, object]:
    captured: dict[str, object] = {}

    def fake_post_json(
        url: str, payload: dict[str, object], headers: dict[str, str], timeout_seconds: float
    ) -> dict[str, object]:
        del url, headers, timeout_seconds
        captured.update(payload)
        return {"choices": [{"message": {"content": "DONE: ok"}, "finish_reason": "stop"}]}

    monkeypatch.setattr("multi_bot_agentic.llm.openai.post_json", fake_post_json)
    request = ModelRequest(goal="demo", observations=(Observation(source="user", content="demo"),))
    assert adapter.complete(request, timeout_seconds=1.0).text == "DONE: ok"
    return captured


@pytest.mark.parametrize(
    ("adapter_cls", "model"),
    [(OpenAIAdapter, "gpt-6.1-sol"), (KimiAdapter, "kimi-k3.1-pro")],
)
def test_reasoning_model_payload_uses_max_completion_tokens(
    monkeypatch: MonkeyPatch, adapter_cls: type[OpenAIAdapter], model: str
) -> None:
    """Current GPT-6 and Kimi K3 models are reasoning models with fixed or unsupported sampling knobs.

    ``max_tokens`` is deprecated in favor of ``max_completion_tokens`` (which counts reasoning
    tokens), so a 500-token ``max_tokens`` cap could be spent entirely on reasoning before any
    visible answer. The payload must use a reasoning-sized ``max_completion_tokens`` and never
    send temperature-style sampling parameters.
    """

    payload = _captured_payload(monkeypatch, adapter_cls(api_key="k", model=model, base_url="https://example.test"))

    assert payload["model"] == model
    assert "max_tokens" not in payload
    max_completion_tokens = payload["max_completion_tokens"]
    assert isinstance(max_completion_tokens, int)
    assert max_completion_tokens >= 25_000
    assert _FIXED_OR_UNSUPPORTED.isdisjoint(payload)


@pytest.mark.parametrize(
    ("provider", "prefix", "model"),
    [("openai", "OPENAI", "gpt-4o"), ("kimi", "KIMI", "kimi-k3.1-pro-highspeed")],
)
def test_completion_budget_is_configurable_per_provider(
    monkeypatch: MonkeyPatch, provider: str, prefix: str, model: str
) -> None:
    """``*_MAX_COMPLETION_TOKENS`` lowers the budget for overrides with smaller output limits."""

    monkeypatch.setenv(f"{prefix}_API_KEY", "dummy-key")
    monkeypatch.setenv(f"{prefix}_MODEL", model)
    monkeypatch.setenv(f"{prefix}_MAX_COMPLETION_TOKENS", "16384")

    adapter = build_llm_adapter(provider)

    assert isinstance(adapter, OpenAIAdapter)
    assert _captured_payload(monkeypatch, adapter)["max_completion_tokens"] == 16384


@pytest.mark.parametrize("value", ["0", "-5", "lots", "1.5"])
def test_completion_budget_rejects_invalid_values(monkeypatch: MonkeyPatch, value: str) -> None:
    """Invalid budgets fail fast with the variable name instead of reaching the provider."""

    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
    monkeypatch.setenv("OPENAI_MAX_COMPLETION_TOKENS", value)

    with pytest.raises(ValueError, match="OPENAI_MAX_COMPLETION_TOKENS must be a positive integer"):
        build_llm_adapter("openai")


def test_gemini_payload_sends_no_sampling_parameters(monkeypatch: MonkeyPatch) -> None:
    """Gemini 3.x ignores temperature/topP/topK, so the adapter sends no ``generationConfig`` at all."""

    captured: dict[str, object] = {}

    def fake_post_json(
        url: str, payload: dict[str, object], headers: dict[str, str], timeout_seconds: float
    ) -> dict[str, object]:
        del headers, timeout_seconds
        captured.update(payload, url=url)
        return {"candidates": [{"content": {"parts": [{"text": "DONE: ok"}]}}]}

    monkeypatch.setattr("multi_bot_agentic.llm.gemini.post_json", fake_post_json)
    adapter = GeminiAdapter(api_key="k", model="gemini-3.8-flash")
    request = ModelRequest(goal="demo", observations=(Observation(source="user", content="demo"),))

    assert adapter.complete(request, timeout_seconds=1.0).text == "DONE: ok"
    assert "gemini-3.8-flash:generateContent" in str(captured.pop("url"))
    assert set(captured) == {"contents"}


def test_claude_code_adapter_adds_no_sampling_flags(monkeypatch: MonkeyPatch) -> None:
    """Claude 5.5 rejects temperature/top_p/top_k, so the CLI adapter only runs the configured command."""

    seen: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="DONE: ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = ClaudeCodeCLIAdapter(command="claude --model claude-opus-5-5")
    request = ModelRequest(goal="demo", observations=(Observation(source="user", content="demo"),))

    assert adapter.complete(request, timeout_seconds=1.0).text == "DONE: ok"
    assert seen == [["claude", "--model", "claude-opus-5-5"]]
