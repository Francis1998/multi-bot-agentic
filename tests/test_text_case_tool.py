"""Tests for the text case conversion tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.text_case import TextCaseTool


def _run(text: str, case: str | None = None) -> tuple[bool, str, dict[str, object]]:
    """Execute the text_case tool.

    Args:
        text: Input document, or combined payload when ``case`` is omitted and
            a sentinel is embedded.
        case: Optional case mode for programmatic invocation.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    arguments: dict[str, object] = {"text": text}
    if case is not None:
        arguments["case"] = case
    result = TextCaseTool().execute(ToolInvocation(tool_name="text_case", arguments=arguments))
    return result.ok, result.content, result.metadata


def test_text_case_lower_upper_title() -> None:
    """Basic lower/upper/title transforms work."""

    ok_lower, lower, meta_lower = _run("Hello WORLD", "lower")
    ok_upper, upper, meta_upper = _run("Hello WORLD", "upper")
    ok_title, title, meta_title = _run("hello world", "title")

    assert ok_lower is True and lower == "hello world" and meta_lower["case"] == "lower"
    assert ok_upper is True and upper == "HELLO WORLD" and meta_upper["case"] == "upper"
    assert ok_title is True and title == "Hello World" and meta_title["case"] == "title"


def test_text_case_snake_kebab_camel() -> None:
    """Word-boundary transforms produce snake, kebab, and camel output."""

    ok_snake, snake, _m1 = _run("Hello World!", "snake")
    ok_kebab, kebab, _m2 = _run("Hello World!", "kebab")
    ok_camel, camel, _m3 = _run("Hello World!", "camel")
    ok_from_camel, from_camel, _m4 = _run("XMLHttpRequest", "snake")

    assert ok_snake is True and snake == "hello_world"
    assert ok_kebab is True and kebab == "hello-world"
    assert ok_camel is True and camel == "helloWorld"
    assert ok_from_camel is True and from_camel == "xml_http_request"


def test_text_case_default_is_lower_and_sentinel_form_works() -> None:
    """Default case is lower; sentinel payload supplies an explicit case."""

    ok_default, default_content, metadata = _run("AbC")
    ok_sentinel, sentinel_content, sentinel_meta = _run("Hello World<<<TEXT_CASE>>>kebab")

    assert ok_default is True
    assert default_content == "abc"
    assert metadata["case"] == "lower"
    assert ok_sentinel is True
    assert sentinel_content == "hello-world"
    assert sentinel_meta["case"] == "kebab"


def test_text_case_rejects_empty_oversized_and_bad_case() -> None:
    """Empty, oversized, and unsupported case values fail structurally."""

    ok_empty, content_empty, _m1 = _run("", "lower")
    ok_big, content_big, metadata_big = _run("x" * 20_001, "lower")
    ok_mode, content_mode, metadata_mode = _run("hello", "spongebob")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    value = metadata_big["chars"]
    assert isinstance(value, int) and value > 20_000
    assert ok_mode is False
    assert "unsupported case" in content_mode
    assert metadata_mode["case"] == "spongebob"


def test_text_case_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "text_case" in tools
    assert tools["text_case"].name == "text_case"
    SafetyPolicy().validate_tool("text_case")
    assert "text_case" in SafetyPolicy().allowed_tools
