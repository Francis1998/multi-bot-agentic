"""English pluralize / singularize tool.

Agents frequently need deterministic English plural forms for labels and
counts. Models invent irregular forms. This tool applies a small, explicit
rule set (including common irregulars) with no network access. Safe for
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 workers.
"""

from __future__ import annotations

from typing import Final

from multi_bot_agentic.models import ToolInvocation, ToolResult

_MAX_DOCUMENT_CHARS: Final[int] = 2_000
_DEFAULT_MODE: Final[str] = "pluralize"
_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"pluralize", "singularize"})
_IRREGULAR_PLURAL: Final[dict[str, str]] = {
    "child": "children",
    "person": "people",
    "man": "men",
    "woman": "women",
    "mouse": "mice",
    "goose": "geese",
    "tooth": "teeth",
    "foot": "feet",
    "ox": "oxen",
    "leaf": "leaves",
    "life": "lives",
    "knife": "knives",
    "wife": "wives",
    "analysis": "analyses",
    "index": "indices",
    "matrix": "matrices",
    "vertex": "vertices",
    "quota": "quotas",
    "data": "data",
    "sheep": "sheep",
    "deer": "deer",
    "series": "series",
    "species": "species",
}
_IRREGULAR_SINGULAR: Final[dict[str, str]] = {plural: singular for singular, plural in _IRREGULAR_PLURAL.items()}


class PluralizeTool:
    """Pluralize or singularize a single English word."""

    name = "pluralize"
    description = (
        "Pluralizes or singularizes an English word (mode pluralize|singularize); "
        "max 2000 chars; common irregulars; no network."
    )

    def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Pluralize or singularize the word in the invocation arguments.

        Args:
            invocation: Tool invocation whose ``text`` or ``word`` argument
                holds the word and whose optional ``mode`` argument selects
                ``pluralize`` (default) or ``singularize``.

        Returns:
            Tool result with the transformed word, or ``ok=False`` when the
            word is empty/too long or the mode is unsupported.
        """

        raw = invocation.arguments.get("text")
        if raw is None:
            raw = invocation.arguments.get("word")
        if raw is None:
            return self._fail("missing required argument: text or word", {})
        document = str(raw).strip()
        if not document:
            return self._fail("text is empty", {})
        if len(document) > _MAX_DOCUMENT_CHARS:
            return self._fail(
                f"text exceeds max_chars={_MAX_DOCUMENT_CHARS}",
                {"chars": len(document)},
            )
        if any(ch.isspace() for ch in document):
            return self._fail("text must be a single word", {"chars": len(document)})

        mode = str(invocation.arguments.get("mode", _DEFAULT_MODE)).strip().lower()
        if mode not in _ALLOWED_MODES:
            supported = ", ".join(sorted(_ALLOWED_MODES))
            return self._fail(
                f"unsupported mode: {mode!r}; supported: {supported}",
                {"mode": mode},
            )

        result = _pluralize(document) if mode == "pluralize" else _singularize(document)
        return ToolResult(
            tool_name=self.name,
            ok=True,
            content=result,
            metadata={
                "mode": mode,
                "input": document,
                "chars": len(result),
            },
        )

    def _fail(self, message: str, metadata: dict[str, object]) -> ToolResult:
        """Build a failing tool result."""

        return ToolResult(tool_name=self.name, ok=False, content=message, metadata=metadata)


def _preserve_case(source: str, transformed: str) -> str:
    """Preserve capitalization style of ``source`` on ``transformed``."""

    if source.isupper():
        return transformed.upper()
    if source[:1].isupper():
        return transformed[:1].upper() + transformed[1:]
    return transformed


def _pluralize(word: str) -> str:
    """Return the plural form of ``word``."""

    lower = word.lower()
    if lower in _IRREGULAR_PLURAL:
        return _preserve_case(word, _IRREGULAR_PLURAL[lower])
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return _preserve_case(word, lower + "es")
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return _preserve_case(word, lower[:-1] + "ies")
    if lower.endswith("f"):
        return _preserve_case(word, lower[:-1] + "ves")
    if lower.endswith("fe"):
        return _preserve_case(word, lower[:-2] + "ves")
    return _preserve_case(word, lower + "s")


def _singularize(word: str) -> str:
    """Return the singular form of ``word``."""

    lower = word.lower()
    if lower in _IRREGULAR_SINGULAR:
        return _preserve_case(word, _IRREGULAR_SINGULAR[lower])
    if lower.endswith("ies") and len(lower) > 3:
        return _preserve_case(word, lower[:-3] + "y")
    if lower.endswith("ves") and len(lower) > 3:
        # knives -> knife; leaves -> leaf (prefer f when not known)
        stem = lower[:-3]
        if stem.endswith("i"):
            return _preserve_case(word, stem + "fe")
        return _preserve_case(word, stem + "f")
    if lower.endswith("es") and len(lower) > 2:
        stem = lower[:-2]
        if stem.endswith(("s", "x", "z", "ch", "sh")) or lower.endswith(("ches", "shes", "xes", "zes", "sses")):
            return _preserve_case(word, stem if not lower.endswith("sses") else lower[:-2])
        # boxes -> box already handled; for plain "es" after sibilant
        if any(lower.endswith(suffix + "es") for suffix in ("s", "x", "z", "ch", "sh")):
            return _preserve_case(word, lower[:-2])
    if lower.endswith("s") and len(lower) > 1 and not lower.endswith("ss"):
        return _preserve_case(word, lower[:-1])
    return word
