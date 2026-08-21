"""Deterministic MIME attachment-filename disambiguation tool.

Agents sometimes need safe destination names for repeated MIME attachment
filenames without reading or writing payloads. This tool parses a bounded raw
message, groups decoded original filenames, and assigns collision-free names by
adding ``-2``, ``-3``, and so on before the final extension. It never returns
payloads, writes files, executes code, or makes network requests. Safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import json
import os
from email import policy
from email.parser import Parser
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000


class MimeAttachmentFilenamesUniqueTool:
    """Map original attachment filenames to unique names for each occurrence."""

    name = "mime_attachment_filenames_unique"
    description = (
        "Parses bounded raw MIME and returns a JSON mapping from each decoded "
        "attachment filename to collision-free names, adding -2/-3 before the "
        "extension for repeats; never returns payloads; max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse raw MIME and return only original-to-unique filename mappings."""

        raw = str(invocation.arguments.get("raw", ""))
        if not raw.strip():
            return self._fail("raw is empty", {})
        if len(raw) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"raw exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(raw)},
            )

        try:
            message = Parser(policy=policy.default).parsestr(raw)
        except (TypeError, ValueError) as exc:
            return self._fail(f"unable to parse MIME message: {exc}", {})

        parts = list(message.walk())
        defects = [str(defect) or type(defect).__name__ for part in parts for defect in part.defects]
        if defects:
            return self._fail(
                f"unable to parse MIME message: {defects[0]}",
                {"defects": defects},
            )

        filenames = [str(filename) for part in parts if (filename := part.get_filename()) is not None]
        mapping, renamed_count = self._build_unique_mapping(filenames)
        content = json.dumps(mapping, indent=2, ensure_ascii=False) + "\n"
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"filename mapping exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "input_chars": len(raw)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "attachment_count": len(filenames),
                "chars": len(raw),
                "original_name_count": len(mapping),
                "part_count": len(parts) - 1,
                "renamed_count": renamed_count,
            },
        )

    @classmethod
    def _build_unique_mapping(cls, filenames: list[str]) -> tuple[dict[str, list[str]], int]:
        """Assign globally unique names while preserving first occurrences."""

        reserved_originals = set(filenames)
        used: set[str] = set()
        mapping: dict[str, list[str]] = {}
        renamed_count = 0

        for filename in filenames:
            assigned = mapping.setdefault(filename, [])
            occurrence = len(assigned) + 1
            if occurrence == 1:
                candidate = filename
            else:
                suffix = occurrence
                candidate = cls._add_suffix(filename, suffix)
                while candidate in used or candidate in reserved_originals:
                    suffix += 1
                    candidate = cls._add_suffix(filename, suffix)

            assigned.append(candidate)
            used.add(candidate)
            if candidate != filename:
                renamed_count += 1

        return mapping, renamed_count

    @staticmethod
    def _add_suffix(filename: str, suffix: int) -> str:
        """Insert a numeric suffix immediately before the final extension."""

        stem, extension = os.path.splitext(filename)
        return f"{stem}-{suffix}{extension}"

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
