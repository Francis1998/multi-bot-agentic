"""Typed multi-bot registry for scoped handoffs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotSpec:
    """Registered bot identity and tool scope.

    Attributes:
        bot_id: Stable bot identifier used in ``HANDOFF:bot_id:summary`` directives.
        name: Human-readable bot name.
        allowed_tools: Tools this bot may invoke.
        description: Optional role description for operators.
    """

    bot_id: str
    name: str
    allowed_tools: frozenset[str]
    description: str = ""

    def __post_init__(self) -> None:
        """Validate bot identifiers and tool scopes."""

        if not self.bot_id.strip():
            raise ValueError("bot_id must be non-empty")
        if not self.name.strip():
            raise ValueError("name must be non-empty")
        if not self.allowed_tools:
            raise ValueError("allowed_tools must be non-empty")
