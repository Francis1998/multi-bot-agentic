"""Gemini generateContent adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from multi_bot_agentic.llm.http import post_json
from multi_bot_agentic.models import ModelOutput, ModelRequest


class GeminiAdapter:
    """Adapter for Google's Gemini generateContent API."""

    provider_name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        """Initialize the adapter.

        Args:
            api_key: Gemini API key.
            model: Gemini model name.
        """

        self.api_key = api_key
        self.model = model

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        """Call Gemini and normalize text output.

        Args:
            request: Normalized model request.
            timeout_seconds: Provider timeout budget.

        Returns:
            Normalized model output.
        """

        prompt = _render_prompt(request)
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(self.model, safe='')}:generateContent?key={quote(self.api_key, safe='')}"
        )
        decoded = post_json(
            url,
            {"contents": [{"role": "user", "parts": [{"text": prompt}]}]},
            {},
            timeout_seconds,
        )
        return ModelOutput(
            provider=self.provider_name,
            text=_extract_gemini_text(decoded)[: request.max_output_chars],
            raw={"model": self.model},
        )


def _render_prompt(request: ModelRequest) -> str:
    """Render a Gemini prompt.

    Args:
        request: Normalized model request.

    Returns:
        Prompt string.
    """

    observations = "\n".join(f"- {observation.source}: {observation.content}" for observation in request.observations)
    return (
        "You are an agent worker. Return concise text. Use TOOL:echo:<text> for safe tool use "
        "or DONE:<answer> when finished.\n\n"
        f"Goal: {request.goal}\n\nObservations:\n{observations}"
    )


def _extract_gemini_text(decoded: dict[str, Any]) -> str:
    """Extract text from a Gemini response.

    Args:
        decoded: Provider JSON response.

    Returns:
        Generated text.

    Raises:
        ValueError: If the response shape is not recognized.
    """

    candidates = decoded.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Gemini response did not include candidates")
    first_candidate = candidates[0]
    if not isinstance(first_candidate, dict):
        raise ValueError("Gemini candidate was not an object")
    content = first_candidate.get("content")
    if not isinstance(content, dict):
        raise ValueError("Gemini candidate did not include content")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise ValueError("Gemini content did not include parts")
    text_parts = [part.get("text") for part in parts if isinstance(part, dict)]
    return "\n".join(part for part in text_parts if isinstance(part, str))
