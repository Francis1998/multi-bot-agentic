"""Tests for the hmac_sign tool."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from multi_bot_agentic.models import ToolInvocation
from multi_bot_agentic.runner import build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.hmac_sign import HmacSignTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the hmac_sign tool."""

    result = HmacSignTool().execute(ToolInvocation(tool_name="hmac_sign", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_hmac_sign_sha256_hex_default() -> None:
    """Default algorithm/output matches stdlib HMAC-SHA256 hex digest."""

    text = "hello"
    key = "secret"
    expected = hmac.new(key.encode(), text.encode(), hashlib.sha256).hexdigest()
    ok, content, metadata = _run(text=text, key=key)
    assert ok is True
    assert content == expected
    assert metadata["algorithm"] == "sha256"
    assert metadata["output"] == "hex"
    assert "secret" not in content
    assert "secret" not in str(metadata)


def test_hmac_sign_sha1_base64_and_sha512() -> None:
    """sha1/base64 and sha512/hex outputs are supported."""

    import base64

    text = "payload"
    key = "webhook-key"
    ok, content, metadata = _run(text=text, key=key, algorithm="sha1", output="base64")
    expected = base64.b64encode(hmac.new(key.encode(), text.encode(), hashlib.sha1).digest()).decode()
    assert ok is True
    assert content == expected
    assert metadata["algorithm"] == "sha1"
    assert metadata["output"] == "base64"

    ok2, content2, metadata2 = _run(text=text, key=key, algorithm="sha512")
    expected2 = hmac.new(key.encode(), text.encode(), hashlib.sha512).hexdigest()
    assert ok2 is True
    assert content2 == expected2
    assert metadata2["algorithm"] == "sha512"


def test_hmac_sign_rejects_invalid_and_never_logs_secret() -> None:
    """Empty/oversized inputs and bad options fail without leaking the key."""

    secret = "super-secret-value-do-not-leak"
    ok_empty, content_empty, meta_empty = _run(text="", key=secret)
    ok_key, content_key, meta_key = _run(text="x", key="")
    ok_algo, content_algo, meta_algo = _run(text="x", key=secret, algorithm="md5")
    ok_out, content_out, meta_out = _run(text="x", key=secret, output="binary")
    ok_long_key, content_long_key, meta_long_key = _run(text="x", key="k" * 1025)

    for ok, content, metadata in (
        (ok_empty, content_empty, meta_empty),
        (ok_key, content_key, meta_key),
        (ok_algo, content_algo, meta_algo),
        (ok_out, content_out, meta_out),
        (ok_long_key, content_long_key, meta_long_key),
    ):
        assert ok is False
        assert secret not in content
        assert secret not in str(metadata)

    assert "empty" in content_empty
    assert "key is empty" in content_key
    assert "unsupported algorithm" in content_algo
    assert "unsupported output" in content_out
    assert "key exceeds" in content_long_key


def test_hmac_sign_mentions_model_versions_as_examples() -> None:
    """Webhook signing docs target GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2."""

    ok, content, metadata = _run(text="GPT-5.5 / Claude Sonnet 4.6", key="kimi-k2")
    assert ok is True
    assert len(content) == 64
    assert metadata["chars"] == len("GPT-5.5 / Claude Sonnet 4.6")


def test_hmac_sign_is_registered_and_allowed(tmp_path: Path) -> None:
    """The tool is wired into the default registry and safety allowlist."""

    tools = build_default_tools(tmp_path)
    assert "hmac_sign" in tools
    assert tools["hmac_sign"].name == "hmac_sign"
    SafetyPolicy().validate_tool("hmac_sign")
    assert "hmac_sign" in SafetyPolicy().allowed_tools
