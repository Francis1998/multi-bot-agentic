"""Unit tests for DeterministicRunSeedGuard."""

from __future__ import annotations

from pathlib import Path

import pytest

from multi_bot_agentic.deterministic_run_seed import DeterministicRunSeedGuard


def test_pin_and_match() -> None:
    """Pinned seed matches on check."""

    guard = DeterministicRunSeedGuard()
    guard.pin("run-1", 42)
    status = guard.check("run-1", 42)
    assert status.matched is True
    assert status.allowed is True


def test_hard_mismatch_blocks() -> None:
    """Hard mode disallows mismatched seeds."""

    guard = DeterministicRunSeedGuard(mode="hard")
    guard.pin("run-1", 7)
    status = guard.check("run-1", 8)
    assert status.matched is False
    assert status.allowed is False


def test_advisory_mismatch_allows() -> None:
    """Advisory mode allows mismatched seeds."""

    guard = DeterministicRunSeedGuard(mode="advisory")
    guard.pin("run-1", 1)
    status = guard.check("run-1", 2)
    assert status.matched is False
    assert status.allowed is True


def test_unpinned_raises() -> None:
    """Checking an unpinned run raises ValueError."""

    with pytest.raises(ValueError, match="not pinned"):
        DeterministicRunSeedGuard().check("missing", 1)


def test_invalid_seed_type_raises() -> None:
    """Non-int seed raises ValueError."""

    with pytest.raises(ValueError, match="seed"):
        DeterministicRunSeedGuard().pin("run-1", True)  # type: ignore[arg-type]


def test_module_has_no_httpx_import() -> None:
    """Feature module must not import httpx."""

    source = Path(__file__).resolve().parents[1] / "src/multi_bot_agentic/deterministic_run_seed.py"
    assert "httpx" not in source.read_text(encoding="utf-8")
