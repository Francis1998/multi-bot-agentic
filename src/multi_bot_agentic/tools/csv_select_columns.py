"""CSV column select/reorder tool for deterministic tabular handoffs.

Agents often need only a subset of CSV columns — or a stable column order —
before the next LLM turn. Asking a model to project pasted tables can drop
quoted cells or scramble headers. This tool uses stdlib :mod:`csv` only,
preserves row order, and emits CSV with the requested columns in the given
order. It never executes code and never makes network requests.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:csv_select_columns:<payload>``, the CSV document and column list may
be supplied either as separate ``text`` / ``columns`` arguments or as a
single ``text`` value split on ``<<<CSV_SELECT>>>`` followed by a
comma-separated column name list.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_SPLIT_SENTINEL: Final[str] = "<<<CSV_SELECT>>>"


class CsvSelectColumnsTool:
    """Select and reorder CSV columns by name."""

    name = "csv_select_columns"
    description = "Selects/reorders CSV columns by name (text+columns or <<<CSV_SELECT>>>); max 500 rows, 64 columns."

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Project a CSV document onto named columns in caller order.

        Args:
            invocation: Tool invocation whose arguments hold ``text`` and
                ``columns`` (list of names, or a comma-separated string), or a
                single ``text`` payload split on ``<<<CSV_SELECT>>>``.

        Returns:
            Tool result with projected CSV preserving row order, or
            ``ok=False`` when input is empty, oversized, malformed, over
            bounds, or names a missing/duplicate/empty column.
        """

        document, columns, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and columns is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )
        if not columns:
            return self._fail("columns list is empty", {})
        if any(not name for name in columns):
            return self._fail("column names must be non-empty", {"columns": ",".join(columns)})
        if len(set(columns)) != len(columns):
            return self._fail("requested columns must be unique", {"columns": ",".join(columns)})
        if len(columns) > _MAX_COLUMNS:
            return self._fail(
                f"requested columns exceed max_columns={_MAX_COLUMNS}",
                {"columns": len(columns)},
            )

        try:
            rows = list(csv.reader(io.StringIO(document)))
        except csv.Error as exc:
            return self._fail(f"csv parse error: {exc}", {})

        while rows and self._is_blank_row(rows[-1]):
            rows.pop()

        if not rows or not any(cell.strip() for row in rows for cell in row):
            return self._fail("csv has no rows", {})
        if len(rows) > _MAX_ROWS + 1:
            return self._fail(
                f"csv exceeds max_rows={_MAX_ROWS}",
                {"rows": len(rows) - 1},
            )

        width = max(len(row) for row in rows)
        if width > _MAX_COLUMNS:
            return self._fail(
                f"csv exceeds max_columns={_MAX_COLUMNS}",
                {"columns": width},
            )

        header = list(rows[0]) + [""] * (width - len(rows[0]))
        header_names = [cell.strip() for cell in header]
        if not header_names or any(not name for name in header_names):
            return self._fail("csv header must be non-empty named columns", {})
        if len(set(header_names)) != len(header_names):
            return self._fail("csv header columns must be unique", {})

        missing = [name for name in columns if name not in header_names]
        if missing:
            return self._fail(
                f"unknown column: {missing[0]!r}",
                {"columns": ",".join(header_names), "missing": ",".join(missing)},
            )

        indexes = [header_names.index(name) for name in columns]
        out_rows: list[list[str]] = [list(columns)]
        for row in rows[1:]:
            padded = list(row) + [""] * (width - len(row))
            out_rows.append([padded[index] for index in indexes])

        content = self._dump_csv(out_rows)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "rows": len(out_rows) - 1,
                "columns": ",".join(columns),
                "column_count": len(columns),
                "chars": len(content),
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, list[str] | None, str | None]:
        """Resolve CSV document and column names from args or a sentinel payload."""

        text = str(arguments.get("text", ""))
        if "columns" in arguments:
            columns, error = cls._parse_columns(arguments["columns"])
            if error is not None:
                return None, None, error
            return text, columns, None

        if _SPLIT_SENTINEL not in text:
            return (
                None,
                None,
                (f"csv_select_columns requires text+columns arguments, or a single text split on {_SPLIT_SENTINEL!r}"),
            )

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in remainder:
            return None, None, "text contains more than one <<<CSV_SELECT>>> sentinel"
        columns, error = cls._parse_columns(remainder.strip("\n"))
        if error is not None:
            return None, None, error
        return document.strip("\n"), columns, None

    @staticmethod
    def _parse_columns(raw: object) -> tuple[list[str] | None, str | None]:
        """Parse a columns argument into a list of stripped names."""

        if isinstance(raw, (list, tuple)):
            names = [str(item).strip() for item in raw]
            return names, None
        text = str(raw).strip()
        if not text:
            return None, "columns list is empty"
        # Prefer commas; also accept newlines for multi-line sentinel payloads.
        if "\n" in text and "," not in text:
            names = [line.strip() for line in text.splitlines() if line.strip()]
        else:
            names = [part.strip() for part in text.split(",")]
        return names, None

    @staticmethod
    def _is_blank_row(row: list[str]) -> bool:
        """Return whether a parsed row is empty or all blank cells."""

        return not row or all(cell == "" for cell in row)

    @staticmethod
    def _dump_csv(rows: list[list[str]]) -> str:
        """Serialize rows as canonical CSV with ``\\n`` line endings."""

        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerows(rows)
        return out.getvalue()

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
