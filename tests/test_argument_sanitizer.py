"""Tests for ToolArgumentSanitizer."""

from __future__ import annotations

import pytest

from multi_bot_agentic.argument_sanitizer import ToolArgumentSanitizer


def test_non_dict_raises() -> None:
    """Non-dict input raises TypeError."""

    with pytest.raises(TypeError):
        ToolArgumentSanitizer().sanitize("not-a-dict")  # type: ignore[arg-type]


def test_redacts_api_key_and_password() -> None:
    """Keys containing api_key or password are redacted."""

    result = ToolArgumentSanitizer().sanitize({"api_key": "super-secret", "password": "hunter2", "query": "ok"})
    assert result.arguments["api_key"] == "[REDACTED]"
    assert result.arguments["password"] == "[REDACTED]"
    assert result.arguments["query"] == "ok"
    assert "api_key" in result.redacted_keys
    assert "password" in result.redacted_keys


def test_leaves_safe_keys() -> None:
    """Non-sensitive keys and values are unchanged."""

    args = {"query": "launch checklist", "limit": 3, "dry_run": True}
    result = ToolArgumentSanitizer().sanitize(args)
    assert result.arguments == args
    assert result.redaction_count == 0
    assert result.redacted_keys == ()
    assert result.arguments is not args


def test_nested_paths() -> None:
    """Nested dict/list paths are deep-copied and redacted with dotted paths."""

    original = {
        "auth": {"api_key": "k", "user": "ada"},
        "items": [{"password": "x"}, {"note": "safe"}],
    }
    result = ToolArgumentSanitizer().sanitize(original)
    auth = result.arguments["auth"]
    items = result.arguments["items"]
    assert isinstance(auth, dict)
    assert isinstance(items, list)
    assert auth["api_key"] == "[REDACTED]"
    assert auth["user"] == "ada"
    assert items[0]["password"] == "[REDACTED]"
    assert items[1]["note"] == "safe"
    assert "auth.api_key" in result.redacted_keys
    assert "items[0].password" in result.redacted_keys
    orig_auth = original["auth"]
    orig_items = original["items"]
    assert isinstance(orig_auth, dict)
    assert isinstance(orig_items, list)
    assert orig_auth["api_key"] == "k"
    assert orig_items[0]["password"] == "x"


def test_redaction_count() -> None:
    """redaction_count matches the number of redactions."""

    result = ToolArgumentSanitizer().sanitize(
        {
            "token": "abc",
            "meta": {"passwd": "p"},
            "header": "Bearer abcdEFGH1234567890xyz",
        }
    )
    assert result.redaction_count == 3
    assert len(result.redacted_keys) == 3


def test_value_pattern_bearer_and_sk() -> None:
    """String values matching Bearer or sk- patterns are redacted."""

    result = ToolArgumentSanitizer().sanitize(
        {
            "header": "Bearer abcdEFGH1234567890xyz",
            "payload": "sk-abcdefghijklmnopqrstuvwxyz12",
            "note": "no secrets here",
        }
    )
    assert result.arguments["header"] == "[REDACTED]"
    assert result.arguments["payload"] == "[REDACTED]"
    assert result.arguments["note"] == "no secrets here"
    assert "header" in result.redacted_keys
    assert "payload" in result.redacted_keys
