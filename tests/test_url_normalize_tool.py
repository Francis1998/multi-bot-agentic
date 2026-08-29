"""Tests for the url_normalize tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.url_normalize import UrlNormalizeTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the url_normalize tool."""

    result = UrlNormalizeTool().execute(ToolInvocation(tool_name="url_normalize", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_url_normalize_lowercases_and_drops_default_port() -> None:
    """Scheme/host are lowercased and default ports dropped."""

    ok, content, metadata = _run(url="HTTPS://Example.COM:443/Path/")
    assert ok is True
    assert content == "https://example.com/Path"
    assert metadata["scheme"] == "https"


def test_url_normalize_keeps_nondefault_port_and_query() -> None:
    """Non-default ports and query strings are preserved; fragments dropped."""

    ok, content, _metadata = _run(url="http://example.com:8080/a?x=1#frag")
    assert ok is True
    assert content == "http://example.com:8080/a?x=1"


def test_url_normalize_can_keep_trailing_slash() -> None:
    """strip_trailing_slash=false preserves a trailing slash."""

    ok, content, metadata = _run(
        url="https://example.com/docs/",
        strip_trailing_slash=False,
    )
    assert ok is True
    assert content == "https://example.com/docs/"
    assert metadata["strip_trailing_slash"] is False


def test_url_normalize_rejects_missing_scheme() -> None:
    """URLs without scheme/host fail."""

    ok, content, _metadata = _run(url="/relative/path")
    assert ok is False
    assert "scheme and host" in content


def test_url_normalize_rejects_empty() -> None:
    """Empty url fails."""

    ok, content, metadata = _run(url="   ")
    assert ok is False
    assert "non-empty" in content
    assert metadata["chars"] == 0


def test_url_normalize_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "url_normalize" in tools
    assert tools["url_normalize"].name == "url_normalize"
    SafetyPolicy().validate_tool("url_normalize")
    assert "url_normalize" in SafetyPolicy().allowed_tools
