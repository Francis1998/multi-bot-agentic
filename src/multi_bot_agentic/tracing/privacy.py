"""Redaction helpers for exported traces.

Every free-text value a trace exports (error messages by default; prompts, outputs, tool
arguments, and results only with ``--include-content``) passes through the repository's
existing scrubbers first: :class:`ObservationRedactor` replaces emails, phone numbers,
SSN-like numbers, and ``Bearer``/``sk-`` tokens, and :class:`ToolArgumentSanitizer` decides
which keys are sensitive (``api_key``, ``authorization``, ``password``, ``token``, ...). Values
of sensitive keys are replaced both in structured objects and in ``key: value``,
``key=value``, and ``"key": "value"`` pairs inside text, such as JSON a model wrote.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, Final

from multi_bot_agentic.argument_sanitizer import ToolArgumentSanitizer
from multi_bot_agentic.observation_redactor import ObservationRedactor

# Longest content string (characters) exported per message part, argument, or result value.
MAX_CONTENT_CHARS: Final[int] = 4096
# Longest error message (characters) exported as a span status description.
MAX_ERROR_CHARS: Final[int] = 256
# The redaction regexes are superlinear on long tokens, so only text that can survive the cut
# is scanned, plus a margin so a secret straddling the cut is still recognized.
_SCAN_MARGIN_CHARS: Final[int] = 256
_TRUNCATION_MARKER: Final[str] = "...[truncated]"
_REDACTED: Final[str] = "[REDACTED]"
_MAX_DEPTH: Final[int] = 32

# ``key: value``, ``key=value``, and ``"key": "value"`` pairs inside free text.
_KEY_VALUE: Final[re.Pattern[str]] = re.compile(
    r"""(?P<key>["']?[A-Za-z][A-Za-z0-9_.-]{0,63}["']?)(?P<separator>\s*[:=]\s*)(?!//)"""
    r"""(?P<value>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|\[[A-Z_]+\]|[^\s"',;&}\])]+)"""
)

_REDACTOR = ObservationRedactor()
_SANITIZER = ToolArgumentSanitizer()


def redact_text(text: str, limit: int = MAX_CONTENT_CHARS) -> str:
    """Redact secrets and PII from ``text`` and cap its length.

    Args:
        text: Text to scrub.
        limit: Maximum characters kept before the truncation marker.

    Returns:
        Redacted, possibly truncated text.
    """

    scanned = text[: limit + _SCAN_MARGIN_CHARS]
    redacted = _KEY_VALUE.sub(_redact_pair, _REDACTOR.redact(scanned).redacted_text)
    if len(redacted) > limit or len(text) > len(scanned):
        return redacted[:limit] + _TRUNCATION_MARKER
    return redacted


def redact_value(value: Any, limit: int = MAX_CONTENT_CHARS) -> Any:
    """Redact a JSON-like value: sensitive keys are replaced, strings are scrubbed.

    Args:
        value: JSON-like value (object, array, string, number, boolean, or null).
        limit: Maximum characters kept per string.

    Returns:
        A redacted deep copy.
    """

    return _redact(value, limit, depth=0)


def to_json_object(text: str, key: str) -> dict[str, Any]:
    """Deserialize ``text`` when it is a JSON object, otherwise wrap it as ``{key: text}``.

    The GenAI semantic conventions record tool arguments and results as objects and ask
    instrumentations to deserialize serialized strings on a best-effort basis.

    Args:
        text: Possibly serialized JSON object.
        key: Key used when ``text`` is not a JSON object.

    Returns:
        A JSON object.
    """

    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except (ValueError, RecursionError):
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    return {key: text}


def is_sensitive_key(key: str) -> bool:
    """Return whether :class:`ToolArgumentSanitizer` treats ``key`` as holding a secret.

    Args:
        key: Object key or parameter name.

    Returns:
        True for keys such as ``api_key``, ``Authorization``, or ``password``.
    """

    return _SANITIZER.sanitize({key: ""}).redaction_count > 0


def _redact_pair(match: re.Match[str]) -> str:
    """Replace the value of a sensitive ``key: value`` pair found in text."""

    if not is_sensitive_key(match.group("key").strip("\"'")):
        return match.group(0)
    value = match.group("value")
    quote = value[0] if value[0] in "\"'" else ""
    return f"{match.group('key')}{match.group('separator')}{quote}{_REDACTED}{quote}"


def _redact(value: Any, limit: int, *, depth: int) -> Any:
    """Recursive worker for :func:`redact_value`, bounded so hostile nesting cannot recurse forever."""

    if depth > _MAX_DEPTH:
        return _TRUNCATION_MARKER
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            # A sensitive key hides its whole subtree, not just string leaves.
            if is_sensitive_key(name):
                redacted[name] = _REDACTED
            else:
                redacted[name] = _redact(item, limit, depth=depth + 1)
        return redacted
    if isinstance(value, (list, tuple)):
        return [_redact(item, limit, depth=depth + 1) for item in value]
    if isinstance(value, str):
        return redact_text(value, limit)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(str(value), limit)
