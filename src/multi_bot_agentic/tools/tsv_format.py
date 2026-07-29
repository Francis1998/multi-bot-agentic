"""TSV validation and canonicalization tool.

Agent toolkits (LangChain tools, CrewAI helpers, OpenAI/Anthropic agent demos)
routinely exchange tab-separated spreadsheets for handoffs between workers.
This tool parses TSV text with the stdlib ``csv`` module (``excel-tab`` dialect),
validates rectangular tables, and re-serializes them with consistent newlines
without executing code. Output stays portable across GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000


class TsvFormatTool:
    """Validate and canonicalize a TSV document."""

    name = "tsv_format"
    description = "Validates TSV and returns it canonicalized (tab-delimited rows, consistent newlines)."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Validate and canonicalize the TSV document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the TSV
                document to validate.

        Returns:
            Tool result with the canonicalized document, or ``ok=False`` and an
            explanation when the document is empty, too long, unparsable, or has
            uneven column counts across rows.
        """

        document = str(invocation.arguments.get("text", "")).strip()
        if not document:
            return ToolResult(tool_name=self.name, ok=False, content="document is empty", metadata={})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )

        try:
            reader = csv.reader(io.StringIO(document), dialect="excel-tab")
            rows = [list(row) for row in reader]
        except csv.Error as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid TSV: {error}",
                metadata={"chars": len(document)},
            )

        while rows and _is_blank_row(rows[-1]):
            rows.pop()

        if not rows:
            return ToolResult(tool_name=self.name, ok=False, content="document is empty", metadata={})

        width = len(rows[0])
        if width == 0:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="invalid TSV: header row has no columns",
                metadata={"chars": len(document)},
            )

        for index, row in enumerate(rows):
            if len(row) != width:
                return ToolResult(
                    tool_name=self.name,
                    ok=False,
                    content=(
                        f"invalid TSV: uneven column counts (header defines {width} columns; "
                        f"row {index + 1} has {len(row)})"
                    ),
                    metadata={"chars": len(document), "expected_columns": width, "row": index + 1},
                )

        canonical = _dump_tsv(rows)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=canonical,
            metadata={"row_count": len(rows), "column_count": width},
        )


def _is_blank_row(row: list[str]) -> bool:
    """Return whether a parsed row is empty or all blank cells."""

    return not row or all(cell == "" for cell in row)


def _dump_tsv(rows: list[list[str]]) -> str:
    """Serialize rows as canonical TSV with ``\\n`` line endings."""

    buffer = io.StringIO()
    writer = csv.writer(buffer, dialect="excel-tab", lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue().rstrip("\n")
