"""JWT header+payload decode tool (no signature verification).

Agent runs often need to inspect claims inside a JWT relayed by an upstream
step — issuer, subject, expiry — without treating the token as authenticated.
This tool base64url-decodes the header and payload segments only and returns
canonical JSON. It never verifies signatures, never trusts claims, never
executes code, and never makes a network request. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers that need opaque claim
inspection before the next turn.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_TOKEN_CHARS: Final[int] = 20_000
_MAX_RESULT_CHARS: Final[int] = 20_000


class JwtDecodeTool:
    """Decode a JWT header and payload without verifying the signature."""

    name = "jwt_decode"
    description = (
        "Decodes JWT header+payload via base64url to JSON claims; "
        "NO signature verification — never trust output; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Decode the JWT token in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the JWT
                (``header.payload.signature``). Only the first two segments are
                decoded; the signature is ignored and never verified.

        Returns:
            Tool result whose ``content`` is pretty JSON with ``header`` and
            ``payload`` objects, or ``ok=False`` when the token is empty,
            oversized, malformed, or not valid base64url/JSON. Output must not
            be treated as authenticated.
        """

        token = str(invocation.arguments.get("text", "")).strip()
        if not token:
            return self._fail("token is empty", {})
        if len(token) > _MAX_TOKEN_CHARS:
            return self._fail(
                f"token exceeds max_chars={_MAX_TOKEN_CHARS}",
                {"chars": len(token)},
            )

        parts = token.split(".")
        if len(parts) != 3:
            return self._fail(
                f"token must have exactly 3 dot-separated segments, got {len(parts)}",
                {"segments": len(parts)},
            )

        header_raw, payload_raw, _signature = parts
        if not header_raw or not payload_raw:
            return self._fail("header and payload segments must be non-empty", {})

        header, header_error = self._decode_segment(header_raw, "header")
        if header_error is not None:
            return self._fail(header_error, {"segment": "header"})

        payload, payload_error = self._decode_segment(payload_raw, "payload")
        if payload_error is not None:
            return self._fail(payload_error, {"segment": "payload"})

        try:
            content = json.dumps(
                {"header": header, "payload": payload},
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            return self._fail(f"claims are not serializable JSON: {exc}", {})

        if len(content) > _MAX_RESULT_CHARS:
            return self._fail(
                f"result exceeds max_chars={_MAX_RESULT_CHARS}",
                {"chars": len(content)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "verified": False,
                "trusted": False,
                "chars": len(content),
            },
        )

    @staticmethod
    def _decode_segment(segment: str, label: str) -> tuple[object, str | None]:
        """Base64url-decode a JWT segment and parse it as a JSON object.

        Args:
            segment: Raw base64url segment text (no padding required).
            label: Human-readable segment name for error messages.

        Returns:
            ``(parsed, error)`` — exactly one of a JSON object or an error.
        """

        padded = segment + ("=" * (-len(segment) % 4))
        try:
            # validate=True rejects non-alphabet characters (stdlib urlsafe helper
            # is permissive by default, which would blur malformed tokens).
            raw = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
        except (binascii.Error, ValueError) as exc:
            return None, f"invalid base64url {label}: {exc}"

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            return None, f"{label} is not valid UTF-8: {exc}"

        try:
            parsed: object = json.loads(text)
        except json.JSONDecodeError as exc:
            return None, f"invalid JSON {label}: {exc}"

        if not isinstance(parsed, dict):
            return None, f"{label} must be a JSON object"
        return parsed, None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
