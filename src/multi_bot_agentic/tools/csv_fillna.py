"""CSV empty-cell fill tool for deterministic tabular handoffs.

Agents often receive sparse CSV exports with blank cells and need a constant
fill (pandas-style ``fillna``) before the next LLM turn. Asking a model to
rewrite pasted tables can drop quoted cells or shift columns. This tool uses
stdlib :mod:`csv` only, preserves the header, fills empty cells with a constant
value (default ``""``), and optionally limits the fill to named columns. It
never executes code and never makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:csv_fillna:<payload>``, the CSV document and fill settings may be
supplied either as separate ``text`` / ``fill_value`` / optional ``columns``
arguments or as a single ``text`` value split on ``<<<CSV_FILLNA>>>`` followed
by the fill value and an optional ``<<<COLUMNS>>>col1,col2`` suffix.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_DEFAULT_FILL: Final[str] = ""
_SPLIT_SENTINEL: Final[str] = "<<<CSV_FILLNA>>>"
_COLUMNS_SENTINEL: Final[str] = "<<<COLUMNS>>>"


class CsvFillnaTool:
    """Fill empty CSV cells with a constant value."""

    name = "csv_fillna"
    description = (
        "Fills empty CSV cells with a constant (fill_value default empty string; "
        "optional columns subset; accepts <<<CSV_FILLNA>>>); max 20_000 chars, 500 rows, 64 columns."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Fill empty cells in a CSV document.

        Args:
            invocation: Tool invocation whose arguments hold ``text``, optional
                ``fill_value`` (default ``""``), and optional ``columns`` (list
                or comma-separated names). A single ``text`` payload may instead
                split CSV from the fill settings with ``<<<CSV_FILLNA>>>``.

        Returns:
            Tool result with filled CSV preserving the header, or ``ok=False``
            when input is empty, oversized, malformed, over bounds, or names a
            missing/invalid column.
        """

        document, fill_value, columns, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and fill_value is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
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

        target_indexes: list[int]
        if columns is None:
            target_indexes = list(range(len(header_names)))
            target_names = header_names
        else:
            if not columns:
                return self._fail("columns list is empty", {})
            if any(not name for name in columns):
                return self._fail("column names must be non-empty", {"columns": ",".join(columns)})
            if len(set(columns)) != len(columns):
                return self._fail("requested columns must be unique", {"columns": ",".join(columns)})
            missing = [name for name in columns if name not in header_names]
            if missing:
                return self._fail(
                    f"unknown column: {missing[0]!r}",
                    {"columns": ",".join(header_names)},
                )
            target_indexes = [header_names.index(name) for name in columns]
            target_names = columns

        filled = 0
        out_rows: list[list[str]] = [header_names]
        for row in rows[1:]:
            padded = list(row) + [""] * (width - len(row))
            for index in target_indexes:
                if padded[index].strip() == "":
                    padded[index] = fill_value
                    filled += 1
            out_rows.append(padded)

        content = self._dump_csv(out_rows)
        if len(content) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"csv output exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(content)},
            )

        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "rows": len(out_rows) - 1,
                "columns": len(header_names),
                "filled": filled,
                "fill_value": fill_value,
                "target_columns": ",".join(target_names),
                "chars": len(content),
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, str | None, list[str] | None, str | None]:
        """Resolve CSV document, fill value, and optional columns from args."""

        text = str(arguments.get("text", ""))
        if "fill_value" in arguments or "columns" in arguments:
            fill_value = str(arguments.get("fill_value", _DEFAULT_FILL))
            columns: list[str] | None = None
            if "columns" in arguments:
                columns, error = cls._parse_columns(arguments["columns"])
                if error is not None:
                    return None, None, None, error
            return text, fill_value, columns, None

        if _SPLIT_SENTINEL not in text:
            return text, _DEFAULT_FILL, None, None

        if text.count(_SPLIT_SENTINEL) != 1:
            return None, None, None, "text contains more than one <<<CSV_FILLNA>>> sentinel"

        document, remainder = text.split(_SPLIT_SENTINEL, maxsplit=1)
        remainder = remainder.strip("\n")
        columns = None
        fill_part = remainder
        if _COLUMNS_SENTINEL in remainder:
            if remainder.count(_COLUMNS_SENTINEL) != 1:
                return None, None, None, "text contains more than one <<<COLUMNS>>> sentinel"
            fill_part, columns_raw = remainder.split(_COLUMNS_SENTINEL, maxsplit=1)
            columns, error = cls._parse_columns(columns_raw.strip("\n"))
            if error is not None:
                return None, None, None, error
        return document, fill_part, columns, None

    @staticmethod
    def _parse_columns(raw: object) -> tuple[list[str] | None, str | None]:
        """Parse a columns argument into a list of stripped names."""

        if isinstance(raw, (list, tuple)):
            names = [str(item).strip() for item in raw]
            return names, None
        text = str(raw).strip()
        if not text:
            return None, "columns list is empty"
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
