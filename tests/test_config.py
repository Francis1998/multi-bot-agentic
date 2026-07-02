"""Tests for environment-backed application configuration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from multi_bot_agentic.config import AppConfig

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def test_app_config_reads_cancel_file_from_env(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Environment configuration wires cancellation-file safety controls."""

    cancel_file = tmp_path / "cancel"
    monkeypatch.setenv("MULTIBOT_CANCEL_FILE", str(cancel_file))

    config = AppConfig.from_env()

    assert config.safety.cancellation_file == cancel_file


def test_app_config_rejects_non_positive_max_steps() -> None:
    """An explicit non-positive ``max_steps`` must fail fast, not be discarded.

    The previous implementation used ``max_steps or <default>``. Because ``0``
    is falsy, ``--max-steps 0`` was silently replaced with the default (6),
    hiding an operator error. A resolved ``max_steps`` below 1 must raise.
    """

    with pytest.raises(ValueError, match="max_steps must be >= 1"):
        AppConfig.from_env(max_steps=0)


def test_app_config_respects_explicit_max_steps() -> None:
    """A valid explicit ``max_steps`` override is honored."""

    config = AppConfig.from_env(max_steps=3)

    assert config.safety.max_steps == 3
