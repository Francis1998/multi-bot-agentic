"""URL normalization tool for agent pipelines.

Agent runs routinely reconcile URLs that differ only by default ports, trailing
slashes, or fragment noise. Asking a model to canonicalize those forms is
unreliable. This tool normalizes a URL via stdlib ``urllib.parse``: lowercases
the scheme/host, drops default ``:80``/``:443`` ports, strips fragments, and
optionally collapses a trailing slash on the path. It never executes code and
never makes network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x /
Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final
from urllib.parse import urlsplit, urlunsplit

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_CHARS: Final[int] = 8_000
_DEFAULT_PORTS: Final[dict[str, int]] = {"http": 80, "https": 443}


class UrlNormalizeTool:
    """Normalize a URL to a canonical string form."""

    name = "url_normalize"
    description = (
        "Normalizes a URL (lowercase scheme/host, drop default ports/fragments; "
        "optional strip_trailing_slash); no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Return a normalized URL string.

        Args:
            invocation: Tool invocation with required ``url`` and optional
                ``strip_trailing_slash`` (default true).

        Returns:
            Tool result whose ``content`` is the normalized URL, or
            ``ok=False`` on validation failure.
        """

        raw = invocation.arguments.get("url")
        if raw is None:
            return self._fail("missing required argument: url", {})
        url = str(raw).strip()
        if not url:
            return self._fail("url must be non-empty", {"chars": 0})
        if len(url) > _MAX_CHARS:
            return self._fail(
                f"url exceeds max {_MAX_CHARS} chars",
                {"chars": len(url)},
            )

        strip_slash = self._as_bool(invocation.arguments.get("strip_trailing_slash", True))
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return self._fail("url must include scheme and host", {"chars": len(url)})

        scheme = parts.scheme.lower()
        hostname = (parts.hostname or "").lower()
        if not hostname:
            return self._fail("url host is empty", {"chars": len(url)})

        port = parts.port
        default_port = _DEFAULT_PORTS.get(scheme)
        if port is not None and default_port is not None and port == default_port:
            netloc = hostname
        elif port is not None:
            netloc = f"{hostname}:{port}"
        else:
            # Preserve userinfo if present without port.
            netloc = hostname
            if parts.username:
                auth = parts.username
                if parts.password is not None:
                    auth = f"{auth}:{parts.password}"
                netloc = f"{auth}@{hostname}"

        path = parts.path or ""
        if strip_slash and len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        normalized = urlunsplit((scheme, netloc, path, parts.query, ""))
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=normalized,
            metadata={
                "chars": len(normalized),
                "scheme": scheme,
                "strip_trailing_slash": strip_slash,
            },
        )

    @staticmethod
    def _as_bool(value: object) -> bool:
        """Interpret common truthy/falsy argument forms."""

        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return bool(value)

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
