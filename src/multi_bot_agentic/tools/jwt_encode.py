"""JWT HS256 encode tool (stdlib only, companion to jwt_decode).

Agent runs often need to mint HS256 JWTs for webhook handoffs or test fixtures
next to the existing decode-only inspector. Asking a model to assemble
base64url segments and HMAC signatures is error-prone. This tool builds
``header.payload.signature`` tokens with stdlib ``hmac``, ``hashlib``, and
``base64`` only — no PyJWT dependency. It never makes network requests.
Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_PAYLOAD_BYTES: Final[int] = 8_192
_MAX_SECRET_CHARS: Final[int] = 1_024
_ALGORITHM: Final[str] = "HS256"


class JwtEncodeTool:
    """Encode a JSON payload into an HS256 JWT."""

    name = "jwt_encode"
    description = (
        "Encodes payload+secret into an HS256 JWT (stdlib hmac/hashlib/base64); "
        "payload max 8KB, secret max 1KB; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Build an HS256 JWT from ``payload`` and ``secret``.

        Args:
            invocation: Tool invocation with required ``payload`` (JSON object
                string or dict) and ``secret`` string, plus optional ``headers``
                dict merged into the JWT header (``alg`` is always ``HS256``).

        Returns:
            Tool result whose ``content`` is the compact JWT string, or
            ``ok=False`` on validation failure. The secret is never included in
            content or metadata.
        """

        raw_payload = invocation.arguments.get("payload")
        if raw_payload is None:
            return self._fail("missing required argument: payload", {})

        raw_secret = invocation.arguments.get("secret")
        if raw_secret is None:
            return self._fail("missing required argument: secret", {})
        secret = str(raw_secret)
        if not secret:
            return self._fail("secret is empty", {})
        if len(secret) > _MAX_SECRET_CHARS:
            return self._fail(
                f"secret exceeds max_chars={_MAX_SECRET_CHARS}",
                {"secret_chars": len(secret)},
            )

        payload, payload_error = self._parse_payload(raw_payload)
        if payload_error is not None:
            return self._fail(payload_error, {})

        payload_bytes = self._canonical_json(payload)
        if len(payload_bytes) > _MAX_PAYLOAD_BYTES:
            return self._fail(
                f"payload exceeds max_bytes={_MAX_PAYLOAD_BYTES}",
                {"payload_bytes": len(payload_bytes)},
            )

        raw_headers = invocation.arguments.get("headers")
        header = self._build_header(raw_headers)

        header_segment = self._b64url(self._canonical_json(header))
        payload_segment = self._b64url(payload_bytes)
        signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
        signature = hmac.new(
            secret.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        token = f"{header_segment}.{payload_segment}.{self._b64url(signature)}"

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=token,
            metadata={
                "algorithm": _ALGORITHM,
                "payload_bytes": len(payload_bytes),
                "token_chars": len(token),
            },
        )

    @staticmethod
    def _parse_payload(raw_payload: object) -> tuple[dict[str, object], str | None]:
        """Parse ``payload`` into a JSON object."""

        if isinstance(raw_payload, dict):
            parsed: object = raw_payload
        else:
            text = str(raw_payload).strip()
            if not text:
                return {}, "payload is empty"
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                return {}, f"invalid JSON payload: {exc}"

        if not isinstance(parsed, dict):
            return {}, "payload must be a JSON object"
        return parsed, None

    @staticmethod
    def _build_header(raw_headers: object) -> dict[str, object]:
        """Merge optional headers with required HS256 JWT fields."""

        header: dict[str, object] = {"alg": _ALGORITHM, "typ": "JWT"}
        if raw_headers is None:
            return header
        if not isinstance(raw_headers, dict):
            return header
        merged = dict(raw_headers)
        merged["alg"] = _ALGORITHM
        if "typ" not in merged:
            merged["typ"] = "JWT"
        return merged

    @staticmethod
    def _canonical_json(value: dict[str, object]) -> bytes:
        """Serialize a JSON object to compact UTF-8 bytes."""

        return json.dumps(
            value,
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    @staticmethod
    def _b64url(data: bytes) -> str:
        """Encode bytes as unpadded base64url."""

        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
