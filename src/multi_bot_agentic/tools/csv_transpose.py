"""Deterministic CSV transpose tool.

Agents routinely need to flip spreadsheet-shaped CSV so columns become rows
(or vice versa) before the next model turn. Asking GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 to transpose tables is error-prone for wide inputs. This
tool validates a bounded CSV document and emits its transpose. It never
executes code or makes network requests.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64


class CsvTransposeTool:
    """Transpose a CSV document (rows become columns)."""

    name = "csv_transpose"
    description = (
        "Transposes a CSV document so rows become columns "
        "(max 20_000 chars, 500 rows, 64 columns); rejects malformed input."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Validate CSV input and return its transpose."""

        text = str(invocation.arguments.get("text", ""))
        if not text.strip():
            return self._fail("CSV input is empty", {})
        if len(text) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"CSV input exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(text)},
            )

        try:
            rows = list(csv.reader(io.StringIO(text), strict=True))
        except csv.Error as exc:
            return self._fail(f"csv parse error: {exc}", {})

        if not rows:
            return self._fail("csv document is empty", {})

        width = max(len(row) for row in rows)
        if width == 0:
            return self._fail("csv document has no columns", {})
        if width > _MAX_COLUMNS:
            return self._fail(
                f"csv exceeds max_columns={_MAX_COLUMNS}",
                {"columns": width},
            )
        if len(rows) > _MAX_ROWS:
            return self._fail(
                f"csv exceeds max_rows={_MAX_ROWS}",
                {"rows": len(rows)},
            )

        normalized: list[list[str]] = []
        for row_index, row in enumerate(rows, start=1):
            if len(row) > width:
                return self._fail(
                    f"csv row {row_index} has {len(row)} columns; expected <= {width}",
                    {"columns": len(row), "row": row_index},
                )
            padded = list(row) + [""] * (width - len(row))
            normalized.append(padded)

        transposed = [list(column) for column in zip(*normalized, strict=True)]
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerows(transposed)
        content = buffer.getvalue()
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"transposed CSV exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "input_chars": len(text)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "input_chars": len(text),
                "input_rows": len(normalized),
                "input_columns": width,
                "output_rows": len(transposed),
                "output_columns": len(transposed[0]) if transposed else 0,
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
