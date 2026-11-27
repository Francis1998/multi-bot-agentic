"""Usage parsing from recorded provider payloads, and pricing (offline)."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from multi_bot_agentic.llm.claude_code_cli import ClaudeCodeCLIAdapter
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.llm.gemini import GeminiAdapter
from multi_bot_agentic.llm.kimi import KimiAdapter
from multi_bot_agentic.llm.openai import OpenAIAdapter
from multi_bot_agentic.models import ModelRequest, Observation, Usage
from multi_bot_agentic.pricing import PriceTable, PriceTableError, price_call
from multi_bot_agentic.usage import parse_openai_usage

REQUEST = ModelRequest(goal="Ship v2", observations=(Observation(source="user", content="Ship v2"),))
DAY = date(2026, 11, 27)

# Recorded Chat Completions response (GPT-6.2 Sol): cached prompt tokens and reasoning tokens.
OPENAI_CHAT = {
    "id": "chatcmpl-1",
    "model": "gpt-6.2-sol",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "DONE: shipped"}, "finish_reason": "stop"}],
    "usage": {
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "total_tokens": 1500,
        "prompt_tokens_details": {"cached_tokens": 1000, "audio_tokens": 0},
        "completion_tokens_details": {"reasoning_tokens": 200, "audio_tokens": 0},
    },
}
# Recorded Gemini generateContent response: thinking and implicit-cache counts.
GEMINI_RESPONSE = {
    "candidates": [{"content": {"role": "model", "parts": [{"text": "DONE: shipped"}]}, "finishReason": "STOP"}],
    "usageMetadata": {
        "promptTokenCount": 900,
        "candidatesTokenCount": 40,
        "thoughtsTokenCount": 160,
        "cachedContentTokenCount": 512,
        "totalTokenCount": 1100,
    },
}
# Recorded `claude -p --output-format json` result.
CLAUDE_RESULT = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "num_turns": 1,
    "result": "DONE: shipped",
    "session_id": "4f2c",
    "total_cost_usd": 0.0123,
    "usage": {
        "input_tokens": 12,
        "cache_creation_input_tokens": 300,
        "cache_read_input_tokens": 2000,
        "output_tokens": 80,
    },
    "modelUsage": {
        "claude-opus-5-5": {
            "inputTokens": 12,
            "outputTokens": 80,
            "cacheReadInputTokens": 2000,
            "cacheCreationInputTokens": 300,
            "costUSD": 0.0123,
        }
    },
}


def _post(monkeypatch: MonkeyPatch, module: str, response: dict[str, Any]) -> None:
    def fake_post_json(*_args: object, **_kwargs: object) -> dict[str, Any]:
        return response

    monkeypatch.setattr(f"multi_bot_agentic.llm.{module}.post_json", fake_post_json)


def _claude(monkeypatch: MonkeyPatch, stdout: str) -> ClaudeCodeCLIAdapter:
    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return ClaudeCodeCLIAdapter(command="claude -p --output-format json")


@pytest.mark.parametrize("adapter_cls", [OpenAIAdapter, KimiAdapter])
def test_openai_compatible_adapters_record_chat_completions_usage(
    monkeypatch: MonkeyPatch, adapter_cls: type[OpenAIAdapter]
) -> None:
    _post(monkeypatch, "openai", OPENAI_CHAT)
    output = adapter_cls(api_key="k", model="gpt-6.2-sol", base_url="https://example.test").complete(REQUEST, 5)

    assert output.model == "gpt-6.2-sol"
    assert output.usage == Usage(
        input_tokens=1200, output_tokens=300, cached_input_tokens=1000, reasoning_tokens=200, total_tokens=1500
    )


def test_responses_api_usage_shape_is_parsed() -> None:
    usage = {
        "input_tokens": 50,
        "input_tokens_details": {"cached_tokens": 10},
        "output_tokens": 20,
        "output_tokens_details": {"reasoning_tokens": 5},
        "total_tokens": 70,
    }

    assert parse_openai_usage(usage) == Usage(
        input_tokens=50, output_tokens=20, cached_input_tokens=10, reasoning_tokens=5, total_tokens=70
    )


def test_missing_or_partial_openai_usage_stays_unknown(monkeypatch: MonkeyPatch) -> None:
    """No usage block means unknown usage, and missing details stay None instead of 0."""

    _post(monkeypatch, "openai", {key: value for key, value in OPENAI_CHAT.items() if key != "usage"})
    assert OpenAIAdapter(api_key="k", model="gpt-6.2-sol", base_url="https://x.test").complete(REQUEST, 5).usage is None
    assert parse_openai_usage({"prompt_tokens": 7, "completion_tokens": 3}) == Usage(
        input_tokens=7, output_tokens=3, total_tokens=10
    )


def test_gemini_usage_counts_thoughts_as_output_and_cache_as_input(monkeypatch: MonkeyPatch) -> None:
    _post(monkeypatch, "gemini", GEMINI_RESPONSE)
    output = GeminiAdapter(api_key="k", model="gemini-4-neon").complete(REQUEST, 5)

    assert output.model == "gemini-4-neon"
    assert output.usage == Usage(
        input_tokens=900, output_tokens=200, cached_input_tokens=512, reasoning_tokens=160, total_tokens=1100
    )


def test_gemini_omitted_zero_counts_are_zero_and_missing_metadata_is_unknown(monkeypatch: MonkeyPatch) -> None:
    """proto3 JSON drops zero counts, so only a missing usageMetadata means unknown usage."""

    _post(monkeypatch, "gemini", {**GEMINI_RESPONSE, "usageMetadata": {"promptTokenCount": 9, "totalTokenCount": 9}})
    sparse = GeminiAdapter(api_key="k", model="gemini-4-hydrogen").complete(REQUEST, 5).usage
    _post(monkeypatch, "gemini", {"candidates": GEMINI_RESPONSE["candidates"]})
    missing = GeminiAdapter(api_key="k", model="gemini-4-hydrogen").complete(REQUEST, 5).usage

    assert sparse == Usage(input_tokens=9, output_tokens=0, cached_input_tokens=0, reasoning_tokens=0, total_tokens=9)
    assert missing is None


def test_claude_code_json_output_reports_usage_and_its_own_cost(monkeypatch: MonkeyPatch) -> None:
    output = _claude(monkeypatch, json.dumps(CLAUDE_RESULT)).complete(REQUEST, 5)

    assert output.text == "DONE: shipped"
    assert (output.model, output.cost_usd) == ("claude-opus-5-5", 0.0123)
    assert output.usage == Usage(input_tokens=2312, output_tokens=80, cached_input_tokens=2000, total_tokens=2392)


def test_claude_code_text_output_reports_no_usage_and_error_results_raise(monkeypatch: MonkeyPatch) -> None:
    text = _claude(monkeypatch, "DONE: ok\n").complete(REQUEST, 5)
    assert (text.text, text.usage, text.cost_usd) == ("DONE: ok", None, None)

    failed = {**CLAUDE_RESULT, "is_error": True, "subtype": "error_max_turns"}
    with pytest.raises(RuntimeError, match="error_max_turns"):
        _claude(monkeypatch, json.dumps(failed)).complete(REQUEST, 5)


def test_fake_usage_is_deterministic_and_priced_as_free() -> None:
    first = FakeLLMAdapter().complete(REQUEST, 5)
    second = FakeLLMAdapter().complete(REQUEST, 5)

    # 40 overhead + ceil(18 prompt chars / 4); the reply "TOOL:checklist:Ship v2" is 22 chars.
    assert (
        first.usage
        == second.usage
        == Usage(input_tokens=45, output_tokens=6, cached_input_tokens=0, reasoning_tokens=0, total_tokens=51)
    )
    cost = price_call(first.usage, model=first.model, provider_cost=None, table=PriceTable(), on=DAY)
    assert (cost.usd, cost.source) == (0.0, "price_table")


def test_price_table_prices_cached_input_and_long_context() -> None:
    table = PriceTable()
    usage = Usage(input_tokens=1200, output_tokens=300, cached_input_tokens=1000, total_tokens=1500)
    short = price_call(usage, model="gpt-6.2-sol", provider_cost=None, table=table, on=DAY)
    long = price_call(
        Usage(input_tokens=300_000, output_tokens=1000), model="gpt-6.2-astra", provider_cost=None, table=table, on=DAY
    )

    # 200 x $2 + 1000 x $0.10 + 300 x $10 per 1M tokens.
    assert short.usd == pytest.approx(0.0035)
    assert short.rate["verified"] == "2026-11-26"
    # More than 272K input tokens: 2x input ($16) and 1.5x output ($60).
    assert long.usd == pytest.approx(300_000 * 16e-6 + 1000 * 60e-6)
    assert long.notes == ("long-context rates: more than 272,000 input tokens",)


def test_gemini_4_carbon_price_is_effective_dated() -> None:
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    before = price_call(usage, model="gemini-4-carbon", provider_cost=None, table=PriceTable(), on=date(2026, 11, 30))
    after = price_call(usage, model="gemini-4-carbon", provider_cost=None, table=PriceTable(), on=date(2026, 12, 1))

    assert (before.usd, after.usd) == (12.0, 24.0)
    assert after.rate["effective_from"] == "2026-12-01"


def test_unpriced_model_has_no_cost_and_says_why() -> None:
    usage = Usage(input_tokens=10, output_tokens=5)
    cost = price_call(usage, model="gemini-3.8-flash", provider_cost=None, table=PriceTable(), on=DAY)

    assert (cost.usd, cost.source) == (None, "unpriced")
    assert cost.notes == ("no price for model 'gemini-3.8-flash' in the price table",)
    unknown = price_call(None, model="gpt-6.2-sol", provider_cost=None, table=PriceTable(), on=DAY)
    assert (unknown.usd, unknown.notes) == (None, ("the provider reported no token usage",))


def test_provider_reported_cost_wins_over_the_table() -> None:
    usage = Usage(input_tokens=1_000_000, output_tokens=0)
    cost = price_call(usage, model="gpt-6.2-sol", provider_cost=0.25, table=PriceTable(), on=DAY)

    assert (cost.usd, cost.source, cost.rate) == (0.25, "provider", {})


def test_missing_cached_rate_prices_cache_hits_at_the_input_rate() -> None:
    usage = Usage(input_tokens=1000, output_tokens=0, cached_input_tokens=400)
    cost = price_call(usage, model="kimi-k3.1-pro", provider_cost=None, table=PriceTable(), on=DAY)

    assert cost.usd == pytest.approx(1000 * 2e-6)
    assert "upper bound" in cost.notes[0]


def test_price_file_adds_and_replaces_entries(tmp_path: Path) -> None:
    path = tmp_path / "prices.json"
    path.write_text(json.dumps({"models": {"gemini-3.8-flash": {"input": 0.5, "output": 3, "source": "contract"}}}))
    table = PriceTable.load(path)
    cost = price_call(
        Usage(input_tokens=1_000_000, output_tokens=1_000_000),
        model="gemini-3.8-flash",
        provider_cost=None,
        table=table,
        on=DAY,
    )

    assert cost.usd == 3.5
    assert (cost.rate["source"], cost.rate["verified"]) == ("contract", None)
    assert table.get("gpt-6.2-sol") is not None


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ("[]", 'must be a JSON object with a "models" object'),
        ('{"models": {"x": {"input": -1, "output": 1}}}', "x.input must be a number >= 0"),
        ('{"models": {"x": {"input": 1}}}', "x.output must be a number >= 0"),
        ("{", "cannot read price file"),
    ],
)
def test_invalid_price_files_are_rejected(tmp_path: Path, document: str, message: str) -> None:
    path = tmp_path / "prices.json"
    path.write_text(document)

    with pytest.raises(PriceTableError, match=message):
        PriceTable.load(path)
