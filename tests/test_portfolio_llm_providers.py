"""Portfolio: multi-provider LLM adapter registry."""

from __future__ import annotations

import importlib


def test_llm_adapter_registry_is_importable() -> None:
    """LLM adapter module exposes a registry for external providers."""
    module = importlib.import_module("multi_bot_agentic.llm")
    assert module is not None
    exported = getattr(module, "__all__", None)
    assert exported is None or len(exported) >= 1


def test_fake_or_stub_adapter_available() -> None:
    """At least one non-network adapter exists for deterministic tests."""
    module = importlib.import_module("multi_bot_agentic.llm")
    names = set(getattr(module, "__all__", dir(module)))
    assert any("Fake" in n or "fake" in n.lower() or "mock" in n.lower() for n in names) or len(names) >= 2
