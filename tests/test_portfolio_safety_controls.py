"""Portfolio: safety controls module contract."""

from __future__ import annotations

import importlib


def test_safety_or_config_module_exists() -> None:
    """Repo exposes safety or configuration for bounded agent scope."""
    candidates = (
        "multi_bot_agentic.safety",
        "multi_bot_agentic.config",
        "safety",
    )
    loaded = False
    for name in candidates:
        try:
            importlib.import_module(name)
            loaded = True
            break
        except ModuleNotFoundError:
            continue
    assert loaded, "expected safety or config module"
