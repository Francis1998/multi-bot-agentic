"""Deterministic content-type sniffing tool.

Agent runs often receive opaque text blobs — pasted API responses, scraped page
snippets, or relayed tool payloads — and need a quick hint about how to parse
them next. Asking a language model to guess the format is unreliable. This tool
sniffs likely content types (``json``, ``xml``, ``html``, ``csv``, ``tsv``,
``markdown``, ``plain``) from a bounded text or bytes prefix without network
access. It never executes code and returns a detected type plus a confidence
score. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
import re
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_XML_DECL: Final[re.Pattern[str]] = re.compile(r"<\?xml\b", re.IGNORECASE)
_DOCTYPE_HTML: Final[re.Pattern[str]] = re.compile(r"<!DOCTYPE\s+html\b", re.IGNORECASE)
_HTML_TAG: Final[re.Pattern[str]] = re.compile(
    r"<\s*(html|head|body|div|span|table|p|ul|ol|li|a|h[1-6]|script|style)\b",
    re.IGNORECASE,
)
_MARKDOWN_HEADING: Final[re.Pattern[str]] = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_MARKDOWN_LIST: Final[re.Pattern[str]] = re.compile(r"^[\*\-\+]\s+\S", re.MULTILINE)
_MARKDOWN_LINK: Final[re.Pattern[str]] = re.compile(r"\[[^\]]+\]\([^)]+\)")
_MARKDOWN_FENCE: Final[re.Pattern[str]] = re.compile(r"^```", re.MULTILINE)


class ContentTypeSniffTool:
    """Sniff likely content type from a text or bytes prefix."""

    name = "content_type_sniff"
    description = (
        "Sniffs likely content type from text/bytes prefix "
        "(json/xml/html/csv/tsv/markdown/plain) with confidence; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Sniff the likely content type of the invocation payload.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the sample
                to sniff. Optional ``bytes_base64`` may supply a base64-encoded
                byte prefix instead (decoded before sniffing).

        Returns:
            Tool result whose ``content`` names the detected type and whose
            metadata includes ``content_type`` and ``confidence``, or
            ``ok=False`` when the sample is empty or too large.
        """

        sample, error = self._resolve_sample(invocation.arguments)
        if error is not None:
            return self._fail(error, {})

        assert sample is not None
        if not sample.strip():
            return self._fail("document is empty", {})
        if len(sample) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(sample)},
            )

        content_type, confidence = _sniff_content_type(sample)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content_type,
            metadata={
                "content_type": content_type,
                "confidence": confidence,
                "chars": len(sample),
            },
        )

    @classmethod
    def _resolve_sample(cls, arguments: dict[str, object]) -> tuple[str | None, str | None]:
        """Resolve sniff input from text or optional base64 bytes."""

        if "bytes_base64" in arguments:
            import base64
            import binascii

            encoded = str(arguments.get("bytes_base64", "")).strip()
            if not encoded:
                return None, "bytes_base64 is empty"
            try:
                decoded = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                return None, "bytes_base64 is not valid base64"
            if len(decoded) > _MAX_DOCUMENT_CHARS:
                return None, f"decoded bytes exceed max_chars={_MAX_DOCUMENT_CHARS}"
            return decoded.decode("utf-8", errors="replace"), None

        return str(arguments.get("text", "")), None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _sniff_content_type(sample: str) -> tuple[str, float]:
    """Return the best-effort content type and confidence for a sample."""

    stripped = sample.lstrip("\ufeff \t\r\n")
    if not stripped:
        return "plain", 0.5

    json_type, json_conf = _sniff_json(stripped)
    if json_type is not None:
        return json_type, json_conf

    if (
        _XML_DECL.search(stripped)
        or (stripped.startswith("<") and re.match(r"<\?xml\b|<[A-Za-z_][\w\-.:]*", stripped))
    ) and _looks_like_xml(stripped):
        return "xml", 0.95

    if _DOCTYPE_HTML.search(stripped) or _HTML_TAG.search(stripped):
        return "html", 0.9

    tsv_type, tsv_conf = _sniff_delimited(stripped, delimiter="\t")
    if tsv_type is not None:
        return tsv_type, tsv_conf

    csv_type, csv_conf = _sniff_delimited(stripped, delimiter=",")
    if csv_type is not None:
        return csv_type, csv_conf

    markdown_score = _markdown_score(stripped)
    if markdown_score >= 2:
        return "markdown", min(0.55 + 0.1 * markdown_score, 0.92)

    return "plain", 0.55


def _sniff_json(stripped: str) -> tuple[str | None, float]:
    """Detect JSON objects and arrays."""

    if stripped[0] not in {"{", "["}:
        return None, 0.0
    try:
        json.loads(stripped)
    except json.JSONDecodeError:
        return None, 0.0
    return "json", 0.98


def _looks_like_xml(stripped: str) -> bool:
    """Return whether the sample resembles XML markup."""

    if _XML_DECL.search(stripped):
        return True
    return bool(re.search(r"<\/?[A-Za-z_][\w\-.:]*(?:\s[^>]*)?>", stripped))


def _sniff_delimited(stripped: str, *, delimiter: str) -> tuple[str | None, float]:
    """Detect CSV or TSV when multiple lines share a stable column width."""

    lines = [line for line in stripped.splitlines() if line.strip()]
    if len(lines) < 2:
        return None, 0.0

    counts = [line.count(delimiter) + 1 for line in lines[:20]]
    if min(counts) < 2:
        return None, 0.0
    if len(set(counts)) != 1:
        return None, 0.0

    label = "tsv" if delimiter == "\t" else "csv"
    confidence = 0.82 if len(lines) >= 3 else 0.72
    return label, confidence


def _markdown_score(stripped: str) -> int:
    """Count lightweight Markdown signals in a sample."""

    score = 0
    if _MARKDOWN_HEADING.search(stripped):
        score += 1
    if _MARKDOWN_LIST.search(stripped):
        score += 1
    if _MARKDOWN_LINK.search(stripped):
        score += 1
    if _MARKDOWN_FENCE.search(stripped):
        score += 1
    if re.search(r"\*\*[^*]+\*\*", stripped) or re.search(r"__[^_]+__", stripped):
        score += 1
    return score
