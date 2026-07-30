"""CSV ↔ TSV bridge tool for agent handoffs.

Agents often need to convert tabular snippets between comma-separated and
tab-separated forms when moving data between tools, spreadsheets, and prompt
payloads. This tool parses one format with the stdlib ``csv`` module and emits
the other deterministically, without executing code. Output stays portable
across GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_VALID_DIRECTIONS: Final[frozenset[str]] = frozenset({"csv_to_tsv", "tsv_to_csv"})
_DEFAULT_CSV_DELIMITER: Final[str] = ","
_DEFAULT_TSV_DELIMITER: Final[str] = "\t"


class CsvTsvTool:
    """Convert between CSV and TSV text."""

    name = "csv_tsv"
    description = (
        "Converts between CSV and TSV text for agent handoffs "
        "(direction: csv_to_tsv or tsv_to_csv; optional single-character delimiter override)."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Convert the document between CSV and TSV.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the source
                document, ``direction`` is ``csv_to_tsv`` (default) or
                ``tsv_to_csv``, and optional ``delimiter`` overrides the input
                field separator (must be a single character).

        Returns:
            Tool result with converted text, or ``ok=False`` and an explanation
            when the document is empty, too long, the direction/delimiter is
            invalid, or the table is malformed.
        """

        document = str(invocation.arguments.get("text", "")).strip()
        direction = str(invocation.arguments.get("direction", "csv_to_tsv")).strip().lower()
        if not document:
            return ToolResult(tool_name=self.name, ok=False, content="document is empty", metadata={})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"document exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                metadata={"chars": len(document)},
            )
        if direction not in _VALID_DIRECTIONS:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content="invalid direction: must be csv_to_tsv or tsv_to_csv",
                metadata={"direction": direction},
            )

        default_input = _DEFAULT_CSV_DELIMITER if direction == "csv_to_tsv" else _DEFAULT_TSV_DELIMITER
        delimiter = str(invocation.arguments.get("delimiter")) if "delimiter" in invocation.arguments else default_input
        if len(delimiter) != 1:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"delimiter must be a single character, got {delimiter!r}",
                metadata={"delimiter": delimiter},
            )

        output_delimiter = _DEFAULT_TSV_DELIMITER if direction == "csv_to_tsv" else _DEFAULT_CSV_DELIMITER

        try:
            reader = csv.reader(io.StringIO(document), delimiter=delimiter)
            rows = [list(row) for row in reader]
        except csv.Error as error:
            label = "CSV" if direction == "csv_to_tsv" else "TSV"
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid {label}: {error}",
                metadata={"direction": direction, "chars": len(document), "delimiter": delimiter},
            )

        while rows and _is_blank_row(rows[-1]):
            rows.pop()

        if not rows:
            return ToolResult(tool_name=self.name, ok=False, content="document is empty", metadata={})

        width = len(rows[0])
        if width == 0:
            label = "CSV" if direction == "csv_to_tsv" else "TSV"
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid {label}: header row has no columns",
                metadata={"direction": direction, "chars": len(document)},
            )

        for index, row in enumerate(rows):
            if len(row) != width:
                label = "CSV" if direction == "csv_to_tsv" else "TSV"
                return ToolResult(
                    tool_name=self.name,
                    ok=False,
                    content=(
                        f"invalid {label}: uneven column counts (header defines {width} columns; "
                        f"row {index + 1} has {len(row)})"
                    ),
                    metadata={
                        "direction": direction,
                        "chars": len(document),
                        "expected_columns": width,
                        "row": index + 1,
                    },
                )

        content = _dump_delimited(rows, output_delimiter)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "direction": direction,
                "row_count": len(rows),
                "column_count": width,
                "delimiter": delimiter,
            },
        )


def _is_blank_row(row: list[str]) -> bool:
    """Return whether a parsed row is empty or all blank cells."""

    return not row or all(cell == "" for cell in row)


def _dump_delimited(rows: list[list[str]], delimiter: str) -> str:
    """Serialize rows with the given delimiter and ``\\n`` line endings."""

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue().rstrip("\n")
