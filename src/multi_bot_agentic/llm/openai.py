"""OpenAI GPT chat-completions adapter."""

from __future__ import annotations

from typing import Any

from multi_bot_agentic.llm.http import post_json
from multi_bot_agentic.models import ModelOutput, ModelRequest


class OpenAIAdapter:
    """Adapter for OpenAI-compatible GPT chat completions."""

    provider_name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        """Initialize the adapter.

        Args:
            api_key: OpenAI API key.
            model: Model name.
            base_url: Chat completions endpoint.
        """

        self.api_key = api_key
        self.model = model
        self.base_url = base_url

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
            "max_tokens": max(64, min(request.max_output_chars // 4, 1024)),
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
    return f"Goal: {request.goal}\n\nObservations:\n{observations}"


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
    if not isinstance(content, str):
        raise ValueError("OpenAI message content was not text")
    return content


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
