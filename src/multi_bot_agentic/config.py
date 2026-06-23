"""Configuration loading and adapter construction."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from multi_bot_agentic.llm.base import LLMAdapter
from multi_bot_agentic.llm.claude_code_cli import ClaudeCodeCLIAdapter
from multi_bot_agentic.llm.fake import FakeLLMAdapter
from multi_bot_agentic.llm.gemini import GeminiAdapter
from multi_bot_agentic.llm.kimi import KimiAdapter
from multi_bot_agentic.llm.openai import OpenAIAdapter
from multi_bot_agentic.safety import SafetyPolicy


@dataclass(frozen=True)
class AppConfig:
    """Application configuration."""

    provider: str
    event_log: Path
    safety: SafetyPolicy

    @classmethod
    def from_env(
        cls,
        provider: str | None = None,
        event_log: Path | None = None,
        max_steps: int | None = None,
    ) -> AppConfig:
        """Load configuration from environment with optional CLI overrides.

        Args:
            provider: Optional provider override.
            event_log: Optional event-log path override.
            max_steps: Optional max-step override.

        Returns:
            Application configuration.
        """

        selected_provider: str = provider if provider is not None else os.getenv("MULTIBOT_PROVIDER", "fake")
        selected_event_log = event_log or Path(os.getenv("MULTIBOT_EVENT_LOG", "data/runs.sqlite"))
        safety = SafetyPolicy(
            max_steps=max_steps or int(os.getenv("MULTIBOT_MAX_STEPS", "6")),
            timeout_seconds=float(os.getenv("MULTIBOT_TIMEOUT_SECONDS", "30")),
            max_prompt_chars=int(os.getenv("MULTIBOT_MAX_PROMPT_CHARS", "4000")),
            cancellation_file=_optional_path(os.getenv("MULTIBOT_CANCEL_FILE")),
        )
        return cls(provider=selected_provider, event_log=selected_event_log, safety=safety)


def build_llm_adapter(provider: str) -> LLMAdapter:
    """Build an LLM adapter from environment configuration.

    Args:
        provider: Provider name.

    Returns:
        LLM adapter.

    Raises:
        ValueError: If provider config is missing or unsupported.
    """

    if provider == "fake":
        return FakeLLMAdapter()
    if provider == "openai":
        api_key = _required_env("OPENAI_API_KEY")
        return OpenAIAdapter(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
        )
    if provider == "claude_code":
        return ClaudeCodeCLIAdapter(command=os.getenv("CLAUDE_CODE_COMMAND", "claude"))
    if provider == "gemini":
        return GeminiAdapter(
            api_key=_required_env("GEMINI_API_KEY"),
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        )
    if provider == "kimi":
        return KimiAdapter(
            api_key=_required_env("KIMI_API_KEY"),
            model=os.getenv("KIMI_MODEL", "moonshot-v1-8k"),
            base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.ai/v1/chat/completions"),
        )
    raise ValueError(f"unsupported provider: {provider}")


def _required_env(name: str) -> str:
    """Read a required environment variable.

    Args:
        name: Environment variable name.

    Returns:
        Environment variable value.

    Raises:
        ValueError: If the value is missing.
    """

    value = os.getenv(name)
    if not value:
        raise ValueError(f"missing required environment variable: {name}")
    return value


def _optional_path(value: str | None) -> Path | None:
    """Convert an optional string into a path.

    Args:
        value: Optional path string.

    Returns:
        Path when supplied, otherwise None.
    """

    return Path(value) if value else None
