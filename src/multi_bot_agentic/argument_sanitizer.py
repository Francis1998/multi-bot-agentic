"""Tool argument sanitizer for multi-bot agent loops.

Scrubs secrets from tool **args dicts** before execute. Distinct from
``ObservationRedactor`` (observation/log text) and ``RedactionTool`` (callable
PII tool). Fills a gap vs AutoGen/CrewAI, which often pass raw tool args
verbatim — this is a thin, stdlib-only guard suitable for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 loops.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final

_PLACEHOLDER: Final[str] = "[REDACTED]"

# Substring fragments matched against key.casefold().
_SENSITIVE_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "passwd",
    "credential",
    "access_key",
    "private_key",
)

_VALUE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:"
    r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"
    r"|sk-[A-Za-z0-9]{16,}"
    r")"
)


@dataclass(frozen=True)
class SanitizeResult:
    """Outcome of sanitizing a tool arguments dict.

    Attributes:
        arguments: Deep-copied args with secrets replaced by ``[REDACTED]``.
        redaction_count: Total number of redactions performed.
        redacted_keys: Dotted paths of keys/values that were redacted.
    """

    arguments: dict[str, Any]
    redaction_count: int
    redacted_keys: tuple[str, ...]


class ToolArgumentSanitizer:
    """Strip secrets from tool argument dicts before execute.

    Caller-driven v1: wrap ``ToolInvocation.arguments`` before
    ``tool.execute(...)``. Does not wire into the runner automatically.
    """

    def sanitize(self, arguments: dict[str, Any]) -> SanitizeResult:
        """Sanitize sensitive keys and token-like string values.

        Args:
            arguments: Tool args mapping to scrub (not mutated).

        Returns:
            SanitizeResult with a deep-copied sanitized dict, count, and paths.

        Raises:
            TypeError: When ``arguments`` is not a dict.
        """

        if not isinstance(arguments, dict):
            raise TypeError("arguments must be a dict")

        cleaned, count, redacted_keys = self._sanitize_mapping(
            arguments,
            prefix="",
            count=0,
            redacted_keys=[],
        )
        return SanitizeResult(
            arguments=cleaned,
            redaction_count=count,
            redacted_keys=tuple(redacted_keys),
        )

    def _sanitize_mapping(
        self,
        mapping: dict[str, Any],
        *,
        prefix: str,
        count: int,
        redacted_keys: list[str],
    ) -> tuple[dict[str, Any], int, list[str]]:
        out: dict[str, Any] = {}
        for key, value in mapping.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if _is_sensitive_key(str(key)):
                out[key] = _PLACEHOLDER
                count += 1
                redacted_keys.append(path)
                continue
            cleaned, count, redacted_keys = self._sanitize_value(
                value,
                path=path,
                count=count,
                redacted_keys=redacted_keys,
            )
            out[key] = cleaned
        return out, count, redacted_keys

    def _sanitize_value(
        self,
        value: Any,
        *,
        path: str,
        count: int,
        redacted_keys: list[str],
    ) -> tuple[Any, int, list[str]]:
        if isinstance(value, dict):
            return self._sanitize_mapping(
                value,
                prefix=path,
                count=count,
                redacted_keys=redacted_keys,
            )
        if isinstance(value, list):
            items: list[Any] = []
            for index, item in enumerate(value):
                item_path = f"{path}[{index}]"
                cleaned, count, redacted_keys = self._sanitize_value(
                    item,
                    path=item_path,
                    count=count,
                    redacted_keys=redacted_keys,
                )
                items.append(cleaned)
            return items, count, redacted_keys
        if isinstance(value, str):
            cleaned, n = _VALUE_PATTERN.subn(_PLACEHOLDER, value)
            if n:
                count += n
                redacted_keys.append(path)
            return cleaned, count, redacted_keys
        return value, count, redacted_keys


def _is_sensitive_key(key: str) -> bool:
    folded = key.casefold()
    return any(fragment in folded for fragment in _SENSITIVE_KEY_FRAGMENTS)
