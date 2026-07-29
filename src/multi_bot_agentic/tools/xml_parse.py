"""Deterministic XML parsing tool.

Agent toolkits (LangChain tools, CrewAI helpers, OpenAI/Anthropic agent demos)
often ship XML helpers so workers can exchange structured handoffs without
inventing element trees. This tool parses XML with the stdlib
``xml.etree.ElementTree`` module, rejects DOCTYPE/ENTITY declarations before
parse (XXE hardening), and returns a compact indented text summary (tag names,
``@attr=value`` pairs, and text nodes) with depth and element caps. Output stays
portable across GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 20_000
_MAX_DEPTH: Final[int] = 12
_MAX_ELEMENTS: Final[int] = 500
_DANGEROUS_MARKERS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"<!DOCTYPE", re.IGNORECASE),
    re.compile(r"<!ENTITY", re.IGNORECASE),
)


class XmlParseTool:
    """Parse XML into a compact text tree for agent handoffs."""

    name = "xml_parse"
    description = (
        "Parses XML into a compact indented text tree (tags, @attrs, text); "
        "rejects DOCTYPE/ENTITY; depth- and element-capped."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Parse the XML document in the invocation text.

        Args:
            invocation: Tool invocation whose ``text`` argument holds the XML
                document to parse.

        Returns:
            Tool result with the compact tree summary, or ``ok=False`` and an
            explanation when the document is empty, too long, contains disallowed
            declarations, is malformed, or exceeds render caps.
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

        for pattern in _DANGEROUS_MARKERS:
            if pattern.search(document):
                return ToolResult(
                    tool_name=self.name,
                    ok=False,
                    content="document contains disallowed DOCTYPE or ENTITY declaration",
                    metadata={"chars": len(document)},
                )

        try:
            root = ET.fromstring(document)
        except ET.ParseError as error:
            return ToolResult(
                tool_name=self.name,
                ok=False,
                content=f"invalid XML: {error}",
                metadata={"chars": len(document)},
            )

        summary, render_meta = _render_tree(root)
        path_counts = _count_tag_paths(root)
        metadata: dict[str, object] = {
            "element_count": render_meta["element_count"],
            "path_count": len(path_counts),
            "truncated_depth": render_meta["truncated_depth"],
            "truncated_elements": render_meta["truncated_elements"],
        }
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=summary,
            metadata=metadata,
        )


def _local_name(tag: str) -> str:
    """Return the local part of an XML tag, stripping any namespace URI."""

    if tag.startswith("{"):
        return tag.rpartition("}")[2] or tag
    return tag


def _format_attr(value: str) -> str:
    """Quote an attribute value when it contains whitespace or quotes."""

    if not value:
        return '""'
    if any(character in value for character in ('"', "'", " ", "\n", "\t")):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _quote_text(value: str) -> str:
    """Quote element text for the compact tree output."""

    if "\n" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _render_tree(root: ET.Element) -> tuple[str, dict[str, object]]:
    """Render an element tree as indented text with depth and element caps.

    Args:
        root: Parsed XML root element.

    Returns:
        Tuple of the rendered summary text and render metadata.
    """

    lines: list[str] = []
    element_count = 0
    truncated_elements = False
    truncated_depth = False

    def walk(element: ET.Element, depth: int) -> None:
        nonlocal element_count, truncated_elements, truncated_depth
        if truncated_elements:
            return

        element_count += 1
        if element_count > _MAX_ELEMENTS:
            truncated_elements = True
            lines.append(f"{'  ' * min(depth, _MAX_DEPTH)}... [element limit]")
            return

        if depth > _MAX_DEPTH:
            if not truncated_depth:
                truncated_depth = True
                lines.append(f"{'  ' * _MAX_DEPTH}... [depth limit]")
            return

        indent = "  " * (depth - 1)
        name = _local_name(element.tag)
        attribute_parts = [
            f"@{_local_name(key)}={_format_attr(value)}" for key, value in sorted(element.attrib.items())
        ]
        header = name if not attribute_parts else f"{name} {' '.join(attribute_parts)}"
        lines.append(f"{indent}{header}")

        direct_text = (element.text or "").strip()
        if direct_text:
            lines.append(f"{indent}  {_quote_text(direct_text)}")

        for child in list(element):
            walk(child, depth + 1)
            if truncated_elements:
                return

    walk(root, 1)
    return "\n".join(lines), {
        "element_count": min(element_count, _MAX_ELEMENTS),
        "truncated_depth": truncated_depth,
        "truncated_elements": truncated_elements,
    }


def _count_tag_paths(root: ET.Element) -> dict[str, int]:
    """Count occurrences of slash-separated tag paths in the document.

    Args:
        root: Parsed XML root element.

    Returns:
        Mapping of tag paths (for example ``root/child``) to occurrence counts.
    """

    counts: Counter[str] = Counter()

    def walk(element: ET.Element, prefix: str) -> None:
        name = _local_name(element.tag)
        path = f"{prefix}/{name}" if prefix else name
        counts[path] += 1
        for child in element:
            walk(child, path)

    walk(root, "")
    return dict(sorted(counts.items()))
