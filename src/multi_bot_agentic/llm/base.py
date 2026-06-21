"""Base provider interface for LLM adapters."""

from __future__ import annotations

from typing import Protocol

from multi_bot_agentic.models import ModelOutput, ModelRequest


class LLMAdapter(Protocol):
    """Protocol implemented by all LLM providers."""

    provider_name: str

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        """Return normalized model output.

        Args:
            request: Normalized model request.
            timeout_seconds: Provider timeout budget.

        Returns:
            Normalized model output.
        """
