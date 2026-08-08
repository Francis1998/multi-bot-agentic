"""CSV row filter tool for deterministic tabular handoffs.

Agents often need to keep only CSV rows where a named column equals or contains
a value before the next LLM turn. Asking a model to filter pasted tables can
drop quoted cells or shift columns. This tool uses stdlib :mod:`csv` only,
preserves the header, and emits filtered CSV with bounded input size, rows, and
columns. It never executes code and never makes network requests.

Because the decision engine only forwards a single ``text`` payload from
``TOOL:csv_filter:<payload>``, the CSV document and predicate may be supplied
either as separate ``text`` / ``column`` / ``value`` arguments or as a single
``text`` value split on ``<<<CSV_FILTER>>>`` followed by
``column<<<=>>>value`` (equals) or ``column<<<~>>>value`` (contains).
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_DEFAULT_MODE: Final[str] = "equals"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"equals", "contains"})
_SPLIT_SENTINEL: Final[str] = "<<<CSV_FILTER>>>"
_EQUALS_TOKEN: Final[str] = "<<<=>>>"
_CONTAINS_TOKEN: Final[str] = "<<<~>>>"


class CsvFilterTool:
    """Filter CSV rows by an equals or contains predicate on one named column."""

    name = "csv_filter"
    description = (
        "Filters CSV rows where a named column equals or contains a value "
        "(mode equals|contains, case_insensitive default true); max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Filter a CSV document by one column predicate.

        Args:
            invocation: Tool invocation whose arguments hold ``text``, ``column``,
                ``value``, optional ``mode`` (``equals`` or ``contains``), and
                optional ``case_insensitive`` (default true). A single ``text``
                payload may instead split CSV from the predicate with
                ``<<<CSV_FILTER>>>``.

        Returns:
            Tool result with filtered CSV preserving the header, or ``ok=False``
            when input is empty, oversized, malformed, over bounds, or names a
            missing/invalid column or mode.
        """

        document, column, value, sentinel_mode, resolve_error = self._resolve_arguments(invocation.arguments)
        if resolve_error is not None:
            return self._fail(resolve_error, {})
        assert document is not None and column is not None and value is not None

        if not document.strip():
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        mode = sentinel_mode
        if mode is None:
            mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _ALLOWED_MODES:
            return self._fail(
                f"unsupported mode: {mode!r}; must be equals or contains",
                {"mode": mode},
            )

        case_insensitive, bool_error = self._resolve_case_insensitive(
            invocation.arguments.get("case_insensitive", True)
        )
        if bool_error is not None:
            return self._fail(bool_error, {"case_insensitive": invocation.arguments.get("case_insensitive")})

        try:
            rows = list(csv.reader(io.StringIO(document)))
        except csv.Error as exc:
            return self._fail(f"csv parse error: {exc}", {"mode": mode})

        while rows and self._is_blank_row(rows[-1]):
            rows.pop()

        if not rows or not any(cell.strip() for row in rows for cell in row):
            return self._fail("csv has no rows", {"mode": mode})
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
            return self._fail("csv header must be non-empty named columns", {"mode": mode})
        if len(set(header_names)) != len(header_names):
            return self._fail("csv header columns must be unique", {"mode": mode})
        if column not in header_names:
            return self._fail(
                f"unknown column: {column!r}",
                {"columns": ",".join(header_names)},
            )

        column_index = header_names.index(column)
        needle = value.casefold() if case_insensitive else value
        out_rows: list[list[str]] = [header]

        for row in rows[1:]:
            padded = list(row) + [""] * (width - len(row))
            haystack = padded[column_index].casefold() if case_insensitive else padded[column_index]
            if self._matches(haystack, needle, mode):
                out_rows.append(padded)

        content = self._dump_csv(out_rows)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "rows_in": len(rows) - 1,
                "rows_out": len(out_rows) - 1,
                "column": column,
                "mode": mode,
                "case_insensitive": case_insensitive,
                "chars": len(content),
            },
        )

    @classmethod
    def _resolve_arguments(
        cls,
        arguments: dict[str, object],
    ) -> tuple[str | None, str | None, str | None, str | None, str | None]:
        """Resolve CSV document, column, value, and optional mode from args."""

        text = str(arguments.get("text", ""))
        if "column" in arguments or "value" in arguments:
            column = str(arguments.get("column", "")).strip()
            if not column:
                return None, None, None, None, "column name required"
            if "value" not in arguments:
                return None, None, None, None, "value required"
            return text, column, str(arguments["value"]), None, None

        if _SPLIT_SENTINEL not in text:
            return (
                None,
                None,
                None,
                None,
                (f"csv_filter requires text+column+value arguments, or a single text split on {_SPLIT_SENTINEL!r}"),
            )

        document, predicate = text.split(_SPLIT_SENTINEL, maxsplit=1)
        if _SPLIT_SENTINEL in predicate:
            return None, None, None, None, "text contains more than one <<<CSV_FILTER>>> sentinel"

        predicate = predicate.strip("\n")
        equals_count = predicate.count(_EQUALS_TOKEN)
        contains_count = predicate.count(_CONTAINS_TOKEN)
        if equals_count + contains_count != 1:
            return (
                None,
                None,
                None,
                None,
                "csv_filter predicate must contain exactly one <<<=>>> or <<<~>>> operator",
            )

        if equals_count:
            column, value = predicate.split(_EQUALS_TOKEN, maxsplit=1)
            mode = "equals"
        else:
            column, value = predicate.split(_CONTAINS_TOKEN, maxsplit=1)
            mode = "contains"

        column = column.strip()
        if not column:
            return None, None, None, None, "column name required"
        return document.strip("\n"), column, value.strip("\n"), mode, None

    @staticmethod
    def _resolve_case_insensitive(raw: object) -> tuple[bool, str | None]:
        """Parse a permissive boolean argument for case sensitivity."""

        if isinstance(raw, bool):
            return raw, None
        text = str(raw).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True, None
        if text in {"0", "false", "no", "n", "off"}:
            return False, None
        return False, "case_insensitive must be a boolean"

    @staticmethod
    def _matches(haystack: str, needle: str, mode: str) -> bool:
        """Return whether the candidate cell satisfies the selected mode."""

        if mode == "equals":
            return haystack == needle
        return needle in haystack

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
