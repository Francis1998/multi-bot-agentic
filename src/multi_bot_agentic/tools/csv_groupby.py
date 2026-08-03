"""CSV group-by / aggregate tool for agent tabular handoffs.

Agents often need to aggregate long CSV snippets (sum, count, min, max, mean)
by a key column before the next LLM turn. Asking a language model to aggregate
tables invents totals and drops groups. This tool uses stdlib :mod:`csv` to
group rows by one or more key columns and emit aggregated numeric columns. It
never executes code and never makes network requests. Safe for GPT-5.5 /
Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.
"""

from __future__ import annotations

import csv
import io
import statistics
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_ROWS: Final[int] = 500
_MAX_COLUMNS: Final[int] = 64
_ALLOWED_AGGS: Final[frozenset[str]] = frozenset({"sum", "count", "min", "max", "mean"})
_DEFAULT_AGG: Final[str] = "sum"


class CsvGroupbyTool:
    """Group CSV rows and aggregate numeric columns."""

    name = "csv_groupby"
    description = (
        "Groups CSV rows by key columns and aggregates numeric value columns "
        "(agg sum|count|min|max|mean); max 20_000 chars."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Group and aggregate the CSV document.

        Args:
            invocation: Tool invocation whose ``text`` argument holds CSV,
                ``by`` is a comma-separated list of group key columns, ``values``
                is a comma-separated list of numeric columns to aggregate, and
                ``agg`` is one of sum/count/min/max/mean (default sum).

        Returns:
            Tool result with aggregated CSV text, or ``ok=False`` when input is
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

        by_raw = str(invocation.arguments.get("by", "")).strip()
        values_raw = str(invocation.arguments.get("values", "")).strip()
        agg = str(invocation.arguments.get("agg", _DEFAULT_AGG)).strip().lower()
        if not by_raw:
            return self._fail("by key column name(s) required", {})
        if not values_raw:
            return self._fail("values column name(s) required", {})
        if agg not in _ALLOWED_AGGS:
            return self._fail(
                f"unsupported agg: {agg!r}; must be sum, count, min, max, or mean",
                {"agg": agg},
            )

        by_cols = [part.strip() for part in by_raw.split(",") if part.strip()]
        value_cols = [part.strip() for part in values_raw.split(",") if part.strip()]
        if not by_cols or not value_cols:
            return self._fail("by and values must name at least one column each", {})
        if set(by_cols) & set(value_cols):
            return self._fail(
                "by and values columns must be disjoint",
                {"by": by_raw, "values": values_raw},
            )

        try:
            rows = list(csv.reader(io.StringIO(document)))
        except csv.Error as exc:
            return self._fail(f"csv parse error: {exc}", {"agg": agg})

        if not rows or not any(cell.strip() for row in rows for cell in row):
            return self._fail("csv has no data rows", {"agg": agg})
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
            return self._fail("csv header must be non-empty named columns", {"agg": agg})
        if len(set(header)) != len(header):
            return self._fail("csv header columns must be unique", {"agg": agg})

        for name in [*by_cols, *value_cols]:
            if name not in header:
                return self._fail(
                    f"unknown column: {name!r}",
                    {"columns": ",".join(header)},
                )

        by_indices = [header.index(name) for name in by_cols]
        value_indices = [header.index(name) for name in value_cols]

        groups: dict[tuple[str, ...], list[list[float]]] = {}
        group_order: list[tuple[str, ...]] = []
        for row in rows[1:]:
            if not row or all(not cell.strip() for cell in row):
                continue
            padded = row + [""] * (len(header) - len(row))
            key = tuple(padded[i] for i in by_indices)
            numeric_values: list[float] = []
            for col_i in value_indices:
                cell = padded[col_i].strip()
                if not cell:
                    return self._fail(
                        "empty numeric value in values column",
                        {"agg": agg},
                    )
                try:
                    numeric_values.append(float(cell))
                except ValueError:
                    return self._fail(
                        f"non-numeric value in values column: {cell!r}",
                        {"agg": agg, "value": cell},
                    )
            if key not in groups:
                groups[key] = []
                group_order.append(key)
            groups[key].append(numeric_values)

        if not groups:
            return self._fail("csv has no data rows", {"agg": agg})

        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        out_header = [*by_cols, *[f"{col}_{agg}" for col in value_cols]]
        writer.writerow(out_header)
        for key in group_order:
            series_by_col = list(zip(*groups[key], strict=True))
            aggregated: list[str] = []
            for series in series_by_col:
                values = list(series)
                if agg == "sum":
                    result = sum(values)
                elif agg == "count":
                    result = float(len(values))
                elif agg == "min":
                    result = min(values)
                elif agg == "max":
                    result = max(values)
                else:
                    result = statistics.fmean(values)
                aggregated.append(self._format_number(result))
            writer.writerow([*key, *aggregated])

        content = out.getvalue()
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=content,
            metadata={
                "agg": agg,
                "groups": len(groups),
                "columns": len(out_header),
                "chars": len(content),
            },
        )

    @staticmethod
    def _format_number(value: float) -> str:
        """Format aggregated numbers without trailing .0 when integral."""

        if value.is_integer():
            return str(int(value))
        return repr(value)

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)
