"""INI / ConfigParser parse tool for agent pipelines.

Agent runs often ingest legacy ``.ini`` / ``.cfg`` snippets from ops repos.
Asking a model to reconstruct section/key structure is brittle. This tool
parses INI text via stdlib ``configparser.ConfigParser`` and returns a pretty
JSON object of sections→keys. It never executes code and never makes network
requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_CHARS: Final[int] = 20_000
_MAX_SECTIONS: Final[int] = 200
_MAX_KEYS: Final[int] = 2_000


class IniParseTool:
    """Parse INI text into a JSON object of sections and keys."""

    name = "ini_parse"
    description = (
        "Parses INI/CFG text into pretty JSON sections→keys via stdlib configparser (max 20_000 chars); no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Return pretty JSON for the parsed INI document.

        Args:
            invocation: Tool invocation with required ``text`` argument.

        Returns:
            Tool result whose ``content`` is pretty JSON, or ``ok=False`` on
            validation / parse failure.
        """

        raw = invocation.arguments.get("text")
        if raw is None:
            return self._fail("missing required argument: text", {})
        text = str(raw)
        if not text.strip():
            return self._fail("text must be non-empty", {"chars": len(text)})
        if len(text) > _MAX_CHARS:
            return self._fail(
                f"text exceeds max {_MAX_CHARS} chars",
                {"chars": len(text)},
            )

        parser = ConfigParser()
        try:
            parser.read_string(text)
        except ConfigParserError as exc:
            return self._fail(f"ini parse error: {exc}", {"chars": len(text)})

        payload: dict[str, dict[str, str]] = {}
        key_count = 0
        try:
            for section in parser.sections():
                if len(payload) >= _MAX_SECTIONS:
                    return self._fail(
                        f"too many sections (max {_MAX_SECTIONS})",
                        {"chars": len(text)},
                    )
                items = dict(parser.items(section))
                key_count += len(items)
                if key_count > _MAX_KEYS:
                    return self._fail(
                        f"too many keys (max {_MAX_KEYS})",
                        {"chars": len(text)},
                    )
                payload[section] = items
        except ConfigParserError as exc:
            return self._fail(f"ini parse error: {exc}", {"chars": len(text)})

        content = json.dumps(payload, indent=2, sort_keys=True)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(text),
                "sections": len(payload),
                "keys": key_count,
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
