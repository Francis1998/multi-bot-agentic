"""Tests for the deterministic slugify tool."""

from __future__ import annotations

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.slugify import SlugifyTool


def _run(text: str, **arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the slugify tool for a text and optional arguments.

    Args:
        text: Text to slugify.
        **arguments: Optional ``separator`` and ``max_length`` overrides.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    payload: dict[str, object] = {"text": text, **arguments}
    result = SlugifyTool().execute(ToolInvocation(tool_name="slugify", arguments=payload))
    return result.ok, result.content, result.metadata


def test_slugify_normalizes_case_punctuation_and_whitespace() -> None:
    """Mixed case, punctuation, and whitespace collapse into a clean slug."""

    ok, content, metadata = _run("  Hello, World!  Multiple   spaces\tand\ntabs ")

    assert ok is True
    assert content == "hello-world-multiple-spaces-and-tabs"
    assert metadata == {"separator": "-", "length": len(content)}


def test_slugify_strips_diacritics_to_ascii() -> None:
    """Accented characters are transliterated to their ASCII base forms."""

    ok, content, _ = _run("Crème Brûlée à la Française")

    assert ok is True
    assert content == "creme-brulee-a-la-francaise"


def test_slugify_is_deterministic() -> None:
    """The same input always yields the same slug."""

    first = _run("Repeatable Observation #42")[1]
    second = _run("Repeatable Observation #42")[1]

    assert first == second == "repeatable-observation-42"


def test_slugify_honors_custom_separator() -> None:
    """A custom separator replaces and trims the default hyphen."""

    ok, content, metadata = _run("Deploy to prod!", separator="_")

    assert ok is True
    assert content == "deploy_to_prod"
    assert metadata["separator"] == "_"


def test_slugify_alphanumeric_separator_does_not_eat_edge_letters() -> None:
    """An alphanumeric separator must trim whole runs, not character-set strip.

    ``str.strip(separator)`` treats the separator as a character set, so
    ``text=\"test\", separator=\"t\"`` previously collapsed to ``\"es\"``. The
    slug must keep its edge letters when they are part of the content, not the
    separator run.
    """

    ok, content, metadata = _run("test", separator="t")

    assert ok is True
    assert content == "test"
    assert metadata["separator"] == "t"


def test_slugify_truncates_on_word_boundary() -> None:
    """``max_length`` truncates back to the last whole word, not mid-word."""

    ok, content, _ = _run("the quick brown fox jumps", max_length=15)

    assert ok is True
    # "the-quick-brown" is 15 chars; the next word would overflow, and the
    # truncation must not leave a trailing separator or a partial word.
    assert content == "the-quick-brown"


def test_slugify_hard_cuts_a_single_oversized_word() -> None:
    """A first word longer than max_length is hard-cut rather than emptied."""

    ok, content, _ = _run("supercalifragilistic", max_length=6)

    assert ok is True
    assert content == "superc"


def test_slugify_rejects_empty_text() -> None:
    """Whitespace-only input is rejected as empty."""

    ok, content, _ = _run("   ")

    assert ok is False
    assert "empty" in content


def test_slugify_rejects_text_reducing_to_empty_slug() -> None:
    """Text containing no alphanumerics reduces to an empty slug and fails."""

    ok, content, _ = _run("!!! @#$ %^&")

    assert ok is False
    assert "empty slug" in content


def test_slugify_rejects_unusable_separator() -> None:
    """A separator that is not itself slug-safe is rejected."""

    ok, content, _ = _run("hello world", separator="//")

    assert ok is False
    assert "separator" in content


def test_slugify_rejects_non_positive_max_length() -> None:
    """A non-positive or non-integer max_length is rejected."""

    ok, content, _ = _run("hello world", max_length=0)

    assert ok is False
    assert "max_length" in content
