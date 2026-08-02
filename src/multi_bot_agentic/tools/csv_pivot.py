"""CSV pivot / unpivot tool for agent tabular handoffs.

Agents often need to reshape long CSV snippets into a wide pivot (or back) when
moving observations between tools and prompts. Asking a language model to pivot
tables invents columns and drops rows. This tool uses stdlib :mod:`csv` to
pivot long-form rows into wide columns by an index key and value column, or
unpivot wide columns back to long form. It never executes code and never makes
network requests. Safe for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
"""

from __future__ import annotations

import csv
import io
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_DEFAULT_MODE: Final[str] = "pivot"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"pivot", "unpivot"})


class CsvPivotTool:
    """Pivot or unpivot CSV text."""

    name = "csv_pivot"
    description = (
        "Pivots long CSV to wide (or unpivots) via stdlib csv "
        "(mode pivot|unpivot; index/columns/values or id_vars/value_vars); max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Pivot or unpivot the CSV document.

        Args:
            invocation: Tool invocation whose ``text`` argument holds CSV,
                ``mode`` is ``pivot`` (default) or ``unpivot``, and mode-specific
                column arguments select the reshape keys.

        Returns:
            Tool result with reshaped CSV text, or ``ok=False`` when input is
            empty, oversized, malformed, or arguments are invalid.
        """

        document = str(invocation.arguments.get("text", "")).strip()
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )

        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _ALLOWED_MODES:
            return self._fail(
                f"unsupported mode: {mode!r}; must be pivot or unpivot",
                {"mode": mode},
            )

        try:
            rows = list(csv.reader(io.StringIO(document)))
        except csv.Error as exc:
            return self._fail(f"csv parse error: {exc}", {"mode": mode})

        if not rows or not any(cell.strip() for row in rows for cell in row):
            return self._fail("csv has no data rows", {"mode": mode})
        if len(rows) > _MAX_ROWS + 1:
            return self._fail(
                f"csv exceeds max_rows={_MAX_ROWS}",
                {"rows": len(rows) - 1},
            )
        if any(len(row) > _MAX_COLUMNS for row in rows):
            return self._fail(
                f"csv exceeds max_columns={_MAX_COLUMNS}",
                {"columns": max(len(row) for row in rows)},
            )

        header = [cell.strip() for cell in rows[0]]
        if not header or any(not name for name in header):
            return self._fail("csv header must be non-empty named columns", {"mode": mode})
        if len(set(header)) != len(header):
            return self._fail("csv header columns must be unique", {"mode": mode})

        body = rows[1:]
        if mode == "pivot":
            return self._pivot(header, body, invocation.arguments)
        return self._unpivot(header, body, invocation.arguments)

    def _pivot(
        self,
        header: list[str],
        body: list[list[str]],
        arguments: dict[str, object],
    ) -> ToolResult:
        """Pivot long-form rows into wide columns."""

        index_col = str(arguments.get("index", "")).strip()
        columns_col = str(arguments.get("columns", "")).strip()
        values_col = str(arguments.get("values", "")).strip()
        if not index_col or not columns_col or not values_col:
            return self._fail(
                "pivot requires index, columns, and values column names",
                {"index": index_col, "columns": columns_col, "values": values_col},
            )
        for name in (index_col, columns_col, values_col):
            if name not in header:
                return self._fail(
                    f"unknown column: {name!r}",
                    {"columns": ",".join(header)},
                )
        if len({index_col, columns_col, values_col}) != 3:
            return self._fail(
                "index, columns, and values must be distinct",
                {"index": index_col, "columns": columns_col, "values": values_col},
            )

        index_i = header.index(index_col)
        columns_i = header.index(columns_col)
        values_i = header.index(values_col)

        pivoted: dict[str, dict[str, str]] = {}
        pivot_columns: list[str] = []
        seen_pivot: set[str] = set()
        for row in body:
            if not row or all(not cell.strip() for cell in row):
                continue
            padded = row + [""] * (len(header) - len(row))
            key = padded[index_i]
            col = padded[columns_i]
            val = padded[values_i]
            if col not in seen_pivot:
                seen_pivot.add(col)
                pivot_columns.append(col)
            bucket = pivoted.setdefault(key, {})
            if col in bucket:
                return self._fail(
                    f"duplicate pivot cell for index={key!r} column={col!r}",
                    {"index": key, "column": col},
                )
            bucket[col] = val

        if len(pivot_columns) + 1 > _MAX_COLUMNS:
            return self._fail(
                f"pivot would exceed max_columns={_MAX_COLUMNS}",
                {"columns": len(pivot_columns) + 1},
            )

        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow([index_col, *pivot_columns])
        for key, values in pivoted.items():
            writer.writerow([key, *[values.get(col, "") for col in pivot_columns]])
        content = out.getvalue()
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "mode": "pivot",
                "rows": len(pivoted),
                "columns": len(pivot_columns) + 1,
                "chars": len(content),
            },
        )

    def _unpivot(
        self,
        header: list[str],
        body: list[list[str]],
        arguments: dict[str, object],
    ) -> ToolResult:
        """Unpivot wide columns into long-form rows."""

        id_vars_raw = str(arguments.get("id_vars", "")).strip()
        value_vars_raw = str(arguments.get("value_vars", "")).strip()
        var_name = str(arguments.get("var_name", "variable")).strip() or "variable"
        value_name = str(arguments.get("value_name", "value")).strip() or "value"
        if not id_vars_raw:
            return self._fail("unpivot requires id_vars column name(s)", {})

        id_vars = [part.strip() for part in id_vars_raw.split(",") if part.strip()]
        if not id_vars:
            return self._fail("unpivot requires id_vars column name(s)", {})
        for name in id_vars:
            if name not in header:
                return self._fail(f"unknown column: {name!r}", {"columns": ",".join(header)})

        if value_vars_raw:
            value_vars = [part.strip() for part in value_vars_raw.split(",") if part.strip()]
        else:
            value_vars = [name for name in header if name not in id_vars]
        if not value_vars:
            return self._fail("unpivot requires at least one value column", {"id_vars": id_vars_raw})
        for name in value_vars:
            if name not in header:
                return self._fail(f"unknown column: {name!r}", {"columns": ",".join(header)})
        if var_name in id_vars or value_name in id_vars:
            return self._fail(
                "var_name and value_name must not collide with id_vars",
                {"var_name": var_name, "value_name": value_name},
            )

        id_indices = [header.index(name) for name in id_vars]
        value_indices = [header.index(name) for name in value_vars]

        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow([*id_vars, var_name, value_name])
        row_count = 0
        for row in body:
            if not row or all(not cell.strip() for cell in row):
                continue
            padded = row + [""] * (len(header) - len(row))
            id_values = [padded[i] for i in id_indices]
            for col_name, col_i in zip(value_vars, value_indices, strict=True):
                writer.writerow([*id_values, col_name, padded[col_i]])
                row_count += 1
                if row_count > _MAX_ROWS:
                    return self._fail(
                        f"unpivot would exceed max_rows={_MAX_ROWS}",
                        {"rows": row_count},
                    )

        content = out.getvalue()
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "mode": "unpivot",
                "rows": row_count,
                "columns": len(id_vars) + 2,
                "chars": len(content),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
