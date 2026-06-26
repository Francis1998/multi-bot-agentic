"""Tests for environment-backed application configuration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

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
