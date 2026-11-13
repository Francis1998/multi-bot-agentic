"""OpenAI GPT chat-completions adapter."""

from __future__ import annotations

from typing import Any

from multi_bot_agentic.llm.base import render_tool_catalog
from multi_bot_agentic.llm.http import post_json
from multi_bot_agentic.models import ModelOutput, ModelRequest

# Reasoning models (GPT-6, Kimi K3.1) count hidden reasoning tokens against
# max_completion_tokens; OpenAI recommends reserving at least 25,000 tokens.
DEFAULT_MAX_COMPLETION_TOKENS = 32_768


class OpenAIAdapter:
    """Adapter for OpenAI-compatible GPT chat completions."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
    ) -> None:
        """Initialize the adapter.

        Args:
            api_key: OpenAI API key.
            model: Model name.
            base_url: Chat completions endpoint.
            max_completion_tokens: Upper bound for reasoning plus visible output tokens.
        """

        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_completion_tokens = max_completion_tokens

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        """Call the provider and normalize text output.

        Args:
            request: Normalized model request.
            timeout_seconds: Provider timeout budget.

        Returns:
            Normalized model output.
        """

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an agent worker. Return concise text. Use TOOL:echo:<text> "
                    "when a safe echo tool is useful. Use DONE:<answer> when finished.",
                },
                {"role": "user", "content": _render_prompt(request)},
            ],
            # max_tokens is deprecated and rejected by reasoning models; sampling knobs such as
            # temperature are unsupported (GPT-6) or fixed (Kimi K3.1), so none are sent.
            "max_completion_tokens": self.max_completion_tokens,
        }
        decoded = post_json(
            self.base_url,
            payload,
            {"authorization": f"Bearer {self.api_key}"},
            timeout_seconds,
        )
        text = _extract_openai_text(decoded)
        return ModelOutput(
            provider=self.provider_name,
            text=text[: request.max_output_chars],
            raw={"model": self.model, "finish_reason": _finish_reason(decoded)},
        )


def _render_prompt(request: ModelRequest) -> str:
    """Render request context for a chat model.

    Args:
        request: Normalized model request.

    Returns:
        Prompt string.
    """

    observations = "\n".join(f"- {observation.source}: {observation.content}" for observation in request.observations)
    return f"Goal: {request.goal}\n\nObservations:\n{observations}{render_tool_catalog(request.tools)}"


def _extract_openai_text(decoded: dict[str, Any]) -> str:
    """Extract assistant text from an OpenAI-compatible response.

    Args:
        decoded: Provider JSON response.

    Returns:
        Assistant text.

    Raises:
        ValueError: If the response shape is not recognized.
    """

    choices = decoded.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenAI response did not include choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("OpenAI choice was not an object")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("OpenAI choice did not include message")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        joined = _join_content_parts(content)
        if joined:
            return joined
    raise ValueError("OpenAI message content was not text")


def _join_content_parts(parts: list[Any]) -> str:
    """Join OpenAI structured-content parts into a single text string.

    Args:
        parts: Content list from an OpenAI-compatible message.

    Returns:
        Concatenated text of string and ``{"text": ...}`` parts.
    """

    segments: list[str] = []
    for part in parts:
        if isinstance(part, str) and part:
            segments.append(part)
        elif isinstance(part, dict):
            value = part.get("text")
            if isinstance(value, str) and value:
                segments.append(value)
    return "".join(segments)


def _finish_reason(decoded: dict[str, Any]) -> str | None:
    """Extract a finish reason when present.

    Args:
        decoded: Provider JSON response.

    Returns:
        Finish reason or None.
    """

    choices = decoded.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        reason = choices[0].get("finish_reason")
        return reason if isinstance(reason, str) else None
    return None
