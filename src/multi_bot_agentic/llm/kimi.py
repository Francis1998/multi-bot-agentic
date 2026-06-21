"""Kimi / Moonshot OpenAI-compatible adapter."""

from __future__ import annotations

from multi_bot_agentic.llm.openai import OpenAIAdapter


class KimiAdapter(OpenAIAdapter):
    """Adapter for Moonshot/Kimi chat completions."""

    provider_name = "kimi"
