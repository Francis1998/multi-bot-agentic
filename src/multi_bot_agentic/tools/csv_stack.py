"""Deterministic bounded CSV vertical stacking tool.

Agents often need to concatenate tabular observations from several workers
without asking a model to copy headers or align rows. This tool validates that
all CSV documents share the same header, emits the header once, and appends data
rows in document order. It never executes code or makes network requests. Safe
for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Documents may be supplied as a ``csvs`` list or in one ``text`` value separated
by ``<<<CSV_STACK>>>``.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_SPLIT_SENTINEL: Final[str] = "<<<CSV_STACK>>>"


class CsvStackTool:
    """Vertically concatenate CSV documents with identical headers."""

    name = "csv_stack"
    description = (
        "Vertically stacks CSV documents with identical headers from a csvs "
        "list or text split by <<<CSV_STACK>>>; max 20_000 total chars, "
        "500 output rows, and 64 columns."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Validate and stack CSV documents in their supplied order."""

        documents, input_chars, resolve_error = self._resolve_documents(invocation.arguments)
        if resolve_error is not None:
            metadata: dict[str, object] = {"chars": input_chars} if input_chars is not None else {}
            return self._fail(resolve_error, metadata)
        assert documents is not None and input_chars is not None

        expected_header: list[str] | None = None
        output_rows: list[list[str]] = []
        for document_index, document in enumerate(documents, start=1):
            try:
                rows = list(csv.reader(io.StringIO(document), strict=True))
            except csv.Error as exc:
                return self._fail(
                    f"csv parse error in document {document_index}: {exc}",
                    {"document": document_index},
                )

            if not rows:
                return self._fail(
                    f"csv document {document_index} is empty",
                    {"document": document_index},
                )

            header = [cell.strip() for cell in rows[0]]
            if not header or any(not name for name in header):
                return self._fail(
                    f"csv document {document_index} header must contain non-empty named columns",
                    {"document": document_index},
                )
            if len(set(header)) != len(header):
                return self._fail(
                    f"csv document {document_index} header columns must be unique",
                    {"document": document_index},
                )
            if len(header) > _MAX_COLUMNS:
                return self._fail(
                    f"csv exceeds max_columns={_MAX_COLUMNS}",
                    {"columns": len(header), "document": document_index},
                )

            if expected_header is None:
                expected_header = header
            elif header != expected_header:
                return self._fail(
                    f"csv document {document_index} header does not match document 1",
                    {
                        "actual_header": header,
                        "document": document_index,
                        "expected_header": expected_header,
                    },
                )

            for row_index, row in enumerate(rows[1:], start=2):
                if not row or all(not cell.strip() for cell in row):
                    continue
                if len(row) != len(header):
                    return self._fail(
                        f"csv document {document_index} row {row_index} has {len(row)} columns; expected {len(header)}",
                        {
                            "columns": len(row),
                            "document": document_index,
                            "expected_columns": len(header),
                            "row": row_index,
                        },
                    )
                output_rows.append(row)
                if len(output_rows) > _MAX_ROWS:
                    return self._fail(
                        f"stacked csv exceeds max_rows={_MAX_ROWS}",
                        {"rows": len(output_rows)},
                    )

        assert expected_header is not None
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(expected_header)
        writer.writerows(output_rows)
        content = out.getvalue()
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"stacked csv exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content), "input_chars": input_chars},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "chars": len(content),
                "columns": len(expected_header),
                "documents": len(documents),
                "input_chars": input_chars,
                "rows": len(output_rows),
            },
        )

    @staticmethod
    def _resolve_documents(
        arguments: dict[str, object],
    ) -> tuple[list[str] | None, int | None, str | None]:
        """Resolve a document list from ``csvs`` or sentinel-separated text."""

        has_csvs = "csvs" in arguments
        has_text = "text" in arguments
        if has_csvs and has_text:
            return None, None, "provide csvs or text, not both"

        if has_csvs:
            raw_csvs = arguments["csvs"]
            if not isinstance(raw_csvs, list):
                return None, None, "csvs must be a list of CSV strings"
            documents = []
            for document in raw_csvs:
                if not isinstance(document, str):
                    return None, None, "every csvs item must be a string"
                documents.append(document)
            input_chars = sum(len(document) for document in documents)
        else:
            text = str(arguments.get("text", ""))
            if not text.strip():
                return None, len(text), "CSV input is empty"
            documents = text.split(_SPLIT_SENTINEL)
            input_chars = len(text)

        if input_chars > _MAX_DOCUMENT_CHARS:
            return (
                None,
                input_chars,
                f"CSV input exceeds max_chars={_MAX_DOCUMENT_CHARS}",
            )
        if len(documents) < 2:
            return None, input_chars, "csv_stack requires at least two CSV documents"
        for index, document in enumerate(documents, start=1):
            if not document.strip():
                return None, input_chars, f"csv document {index} is empty"
        return documents, input_chars, None

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
