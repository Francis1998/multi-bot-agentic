"""Tests for the URL parsing tool."""

from __future__ import annotations

import json

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.tools.url_parse import UrlParseTool


def _run(text: str) -> tuple[bool, str, dict[str, object]]:
    """Execute the url_parse tool for a URL.

    Args:
        text: URL text to parse.

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = UrlParseTool().execute(ToolInvocation(tool_name="url_parse", arguments={"text": text}))
    return result.ok, result.content, result.metadata


def test_url_parse_splits_absolute_url_components() -> None:
    """An absolute URL is split into scheme, host, port, path, query, fragment."""

    ok, content, metadata = _run("https://api.example.com:8443/v1/items?limit=10&q=a#top")

    assert ok is True
    assert metadata["scheme"] == "https"
    assert metadata["hostname"] == "api.example.com"
    assert metadata["port"] == 8443
    assert metadata["path"] == "/v1/items"
    assert metadata["fragment"] == "top"
    assert metadata["query_params"] == {"limit": ["10"], "q": ["a"]}
    # ``content`` is canonical JSON carrying the same components.
    assert json.loads(content)["hostname"] == "api.example.com"


def test_url_parse_repeated_query_keys_are_grouped() -> None:
    """Repeated query keys are grouped into a list, matching ``parse_qs``."""

    ok, _content, metadata = _run("https://example.com/search?tag=a&tag=b&tag=c")

    assert ok is True
    assert metadata["query_params"] == {"tag": ["a", "b", "c"]}


def test_url_parse_keeps_present_but_blank_query_params() -> None:
    """Present-but-valueless query parameters must survive in ``query_params``.

    A flag-style parameter without a value (``?debug``) or an explicit empty
    value (``?ref=``) is still part of the query a caller may be inspecting for
    presence. ``parse_qs`` drops such keys by default, silently hiding them; the
    tool must keep them so ``debug`` and ``ref`` remain observable.
    """

    ok, _content, metadata = _run("https://example.com/p?debug&verbose=1&ref=")

    assert ok is True
    assert metadata["query_params"] == {"debug": [""], "verbose": ["1"], "ref": [""]}


def test_url_parse_defaults_port_to_none_when_absent() -> None:
    """A URL without an explicit port reports ``port`` as ``None``."""

    ok, _content, metadata = _run("http://example.com/path")

    assert ok is True
    assert metadata["port"] is None


def test_url_parse_rejects_relative_url() -> None:
    """A relative URL (no scheme or host) is a structured failure."""

    ok, content, _metadata = _run("/v1/items?limit=10")

    assert ok is False
    assert "not absolute" in content


def test_url_parse_rejects_invalid_port() -> None:
    """A non-numeric port is surfaced as a structured failure, not a crash."""

    ok, content, _metadata = _run("https://example.com:notaport/path")

    assert ok is False
    assert "invalid port" in content


def test_url_parse_rejects_empty_document() -> None:
    """An empty document is reported as a failure."""

    ok, content, _metadata = _run("   ")

    assert ok is False
    assert "empty" in content
