"""HMAC signing tool for webhook-style agent workflows.

LangChain / n8n-style agent stacks frequently need a deterministic HMAC digest
to sign outbound webhook payloads before the next LLM turn. Asking a model to
compute HMAC is unreliable. This tool signs UTF-8 text with a secret key using
an allowlisted hash algorithm and returns hex or Base64. It never logs the
secret, never executes code, and never makes network requests. Safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_TEXT_CHARS: Final[int] = 20_000
_MAX_KEY_CHARS: Final[int] = 1_024
_DEFAULT_ALGORITHM: Final[str] = "sha256"
_DEFAULT_OUTPUT: Final[str] = "hex"
_ALGORITHMS: Final[frozenset[str]] = frozenset({"sha1", "sha256", "sha512"})
_OUTPUTS: Final[frozenset[str]] = frozenset({"hex", "base64"})


class HmacSignTool:
    """Compute an HMAC digest of text with a secret key."""

    name = "hmac_sign"
    description = (
        "Computes an HMAC digest of text with a secret key (sha256 default, sha1, sha512; output hex or base64)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Sign the document with HMAC.

        Args:
            invocation: Tool invocation with ``text``, ``key``, optional
                ``algorithm`` (default ``sha256``), and optional ``output``
                (``hex`` or ``base64``, default ``hex``).

        Returns:
            Tool result with the digest string, or ``ok=False`` for invalid
            input. The secret key is never included in content or metadata.
        """

        document = str(invocation.arguments.get("text", ""))
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_TEXT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_TEXT_CHARS}",
                {"chars": len(document)},
            )

        key = str(invocation.arguments.get("key", ""))
        if not key:
            return self._fail("key is empty", {})
        if len(key) > _MAX_KEY_CHARS:
            return self._fail(
                f"key exceeds max_chars={_MAX_KEY_CHARS}",
                {"key_chars": len(key)},
            )

        algorithm = str(invocation.arguments.get("algorithm", _DEFAULT_ALGORITHM)).strip().lower()
        if algorithm not in _ALGORITHMS:
            supported = ", ".join(sorted(_ALGORITHMS))
            return self._fail(
                f"unsupported algorithm: {algorithm!r}; supported: {supported}",
                {"algorithm": algorithm},
            )

        output = str(invocation.arguments.get("output", _DEFAULT_OUTPUT)).strip().lower()
        if output not in _OUTPUTS:
            supported = ", ".join(sorted(_OUTPUTS))
            return self._fail(
                f"unsupported output: {output!r}; supported: {supported}",
                {"output": output},
            )

        encoded_text = document.encode("utf-8")
        encoded_key = key.encode("utf-8")
        digest = hmac.new(encoded_key, encoded_text, getattr(hashlib, algorithm)).digest()
        content = digest.hex() if output == "hex" else base64.b64encode(digest).decode("ascii")

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "algorithm": algorithm,
                "output": output,
                "chars": len(document),
                "bytes": len(encoded_text),
                "key_chars": len(key),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result without exposing the secret."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
