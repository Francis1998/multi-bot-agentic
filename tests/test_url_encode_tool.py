"""Tests for the URL percent-encode tool."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, quote_plus

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.url_encode import UrlEncodeTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the url_encode tool."""

    result = UrlEncodeTool().execute(ToolInvocation(tool_name="url_encode", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_url_encode_percent_encodes_with_default_safe_slash() -> None:
    """Spaces and reserved characters encode; slash stays safe by default."""

    ok, content, metadata = _run(text="GPT-5.5 / Claude Sonnet 4.6")

    assert ok is True
    assert content == quote("GPT-5.5 / Claude Sonnet 4.6", safe="/")
    assert metadata["safe"] == "/"
    assert metadata["plus"] is False
    assert metadata["input_chars"] == len("GPT-5.5 / Claude Sonnet 4.6")
    assert metadata["chars"] == len(content)


def test_url_encode_supports_custom_safe_and_plus_for_space() -> None:
    """Custom safe chars and plus=true use quote_plus semantics."""

    ok, content, metadata = _run(text="Gemini 3.x & Kimi K2", safe="", plus=True)

    assert ok is True
    assert content == quote_plus("Gemini 3.x & Kimi K2", safe="")
    assert metadata["safe"] == ""
    assert metadata["plus"] is True


def test_url_encode_accepts_sentinel_form() -> None:
    """The sentinel suffix supplies plus and optional safe= key=value options."""

    ok_bool, content_bool, metadata_bool = _run(text="a b<<<URL_ENCODE>>>true")
    ok_opts, content_opts, metadata_opts = _run(text="path/to<<<URL_ENCODE>>>safe=:plus=true")

    assert ok_bool is True
    assert content_bool == quote_plus("a b", safe="/")
    assert metadata_bool["plus"] is True
    assert ok_opts is True
    assert content_opts == quote_plus("path/to", safe="")
    assert metadata_opts["safe"] == ""
    assert metadata_opts["plus"] is True


def test_url_encode_rejects_empty_oversized_and_invalid_options() -> None:
    """Empty, oversized, and invalid option inputs fail structurally."""

    ok_empty, content_empty, _m1 = _run(text="")
    ok_big, content_big, metadata_big = _run(text="x" * 20_001)
    ok_flag, content_flag, _m3 = _run(text="value", plus="sometimes")
    ok_sentinel, content_sentinel, _m4 = _run(text="value<<<URL_ENCODE>>>true<<<URL_ENCODE>>>false")

    assert ok_empty is False and "empty" in content_empty
    assert ok_big is False and "max_chars" in content_big
    assert metadata_big["chars"] == 20_001
    assert ok_flag is False and "plus must be a boolean" in content_flag
    assert ok_sentinel is False and "more than one" in content_sentinel


def test_url_encode_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "url_encode" in tools
    assert tools["url_encode"].name == "url_encode"
    SafetyPolicy().validate_tool("url_encode")
    assert "url_encode" in SafetyPolicy().allowed_tools
