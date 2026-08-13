"""Deterministic URL percent-encoding tool.

Agents often need a stable percent-encoded form of a path segment, query value,
or free-form token before composing a URL or comparing opaque strings. Asking a
model to apply RFC 3986 encoding can drop characters or invent escapes. This
tool wraps stdlib :func:`urllib.parse.quote` (or :func:`urllib.parse.quote_plus`
when spaces should become ``+``) with an optional ``safe`` character set and a
hard input cap. It never executes code or makes network requests. Safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

The document and options may be supplied as separate ``text`` / ``safe`` /
``plus`` arguments or as a single ``text`` value split on ``<<<URL_ENCODE>>>``.
"""

from __future__ import annotations

from typing import Final
from urllib.parse import quote, quote_plus

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_DEFAULT_SAFE: Final[str] = "/"
_DEFAULT_PLUS: Final[bool] = False
_SPLIT_SENTINEL: Final[str] = "<<<URL_ENCODE>>>"
_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
_FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off"})


class UrlEncodeTool:
    """Percent-encode text for use in URLs."""

    name = "url_encode"
    description = (
        "Percent-encodes text via urllib.parse.quote (optional safe chars, plus-for-space); "
        "accepts text+safe+plus or <<<URL_ENCODE>>>; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Percent-encode the invocation text."""

        document, safe, plus, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and safe is not None and plus is not None

        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        encoded = quote_plus(document, safe=safe) if plus else quote(document, safe=safe)

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=encoded,
            metadata={
                "chars": len(encoded),
                "input_chars": len(document),
                "safe": safe,
                "plus": plus,
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, str | None, bool | None, str | None]:
        """Resolve text, safe chars, and plus mode from args or sentinel syntax."""

        text = str(arguments.get("text", ""))
        has_safe = "safe" in arguments
        has_plus = "plus" in arguments

        if has_safe or has_plus:
            safe = str(arguments.get("safe", _DEFAULT_SAFE))
            if has_plus:
                plus = cls._parse_bool(arguments["plus"])
                if plus is None:
                    return None, None, None, f"plus must be a boolean, got {arguments['plus']!r}"
            else:
                plus = _DEFAULT_PLUS
            return text, safe, plus, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_SAFE, _DEFAULT_PLUS, None

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in remainder:
            return None, None, None, "text contains more than one <<<URL_ENCODE>>> sentinel"

        parsed_safe, parsed_plus, parse_error = cls._parse_sentinel_remainder(remainder)
        if parse_error is not None:
            return None, None, None, parse_error
        return document, parsed_safe, parsed_plus, None

    @classmethod
    def _parse_sentinel_remainder(
        cls,
        remainder: str,
    ) -> tuple[str | None, bool | None, str | None]:
        """Parse optional safe/plus settings from a sentinel suffix."""

        stripped = remainder.strip()
        if not stripped:
            return _DEFAULT_SAFE, _DEFAULT_PLUS, None

        as_bool = cls._parse_bool(stripped)
        if as_bool is not None:
            return _DEFAULT_SAFE, as_bool, None

        safe = _DEFAULT_SAFE
        plus = _DEFAULT_PLUS
        saw_safe = False
        saw_plus = False
        for part in stripped.split(":"):
            chunk = part.strip()
            if not chunk:
                continue
            if "=" not in chunk:
                return None, None, f"url_encode sentinel options must be key=value, got {chunk!r}"
            key, value = chunk.split("=", maxsplit=1)
            key = key.strip().lower()
            value = value.strip()
            if key == "safe":
                safe = value
                saw_safe = True
            elif key == "plus":
                parsed = cls._parse_bool(value)
                if parsed is None:
                    return None, None, f"plus must be a boolean, got {value!r}"
                plus = parsed
                saw_plus = True
            else:
                return None, None, f"unknown url_encode option: {key!r}"

        if not saw_safe and not saw_plus:
            return None, None, f"url_encode sentinel options must be key=value, got {stripped!r}"
        return safe, plus, None

    @staticmethod
    def _parse_bool(value: object) -> bool | None:
        """Coerce a boolean-like plus argument."""

        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in _TRUTHY:
                return True
            if normalized in _FALSY:
                return False
        return None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
