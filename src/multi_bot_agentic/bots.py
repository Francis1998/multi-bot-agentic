"""Typed multi-bot registry for scoped handoffs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BOT_KEYS = frozenset({"name", "allowed_tools", "description"})


class BotRegistryError(ValueError):
    """Raised when a bot registry file is missing or malformed."""


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


def load_bot_registry(path: Path) -> dict[str, BotSpec]:
    """Load bots and their tool scopes from a JSON registry file.

    The file maps bot ids to specs::

        {"bots": {"writer": {"name": "Writer", "allowed_tools": ["echo"], "description": "..."}}}

    ``allowed_tools`` is required and non-empty; ``name`` defaults to the bot id. Unknown keys
    are rejected so a typo cannot silently drop a scope.

    Args:
        path: Registry file.

    Returns:
        Bots keyed by bot id, in file order.

    Raises:
        BotRegistryError: If the file cannot be read, is not JSON, or declares an invalid bot.
    """

    try:
        document: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise BotRegistryError(f"cannot read bot registry {path}: {error.strerror or error}") from error
    except ValueError as error:
        raise BotRegistryError(f"bot registry {path} is not valid JSON: {error}") from error
    bots = document.get("bots") if isinstance(document, dict) else None
    if not isinstance(bots, dict) or not bots:
        raise BotRegistryError(f'bot registry {path} must be an object with a non-empty "bots" object')
    registry: dict[str, BotSpec] = {}
    for bot_id, spec in bots.items():
        where = f"bot registry {path}: bot {bot_id!r}"
        if not isinstance(spec, dict):
            raise BotRegistryError(f"{where} must be an object")
        unknown = sorted(set(spec) - _BOT_KEYS)
        if unknown:
            raise BotRegistryError(f"{where} has unknown keys: {', '.join(unknown)}")
        tools = spec.get("allowed_tools")
        if not isinstance(tools, list) or not all(isinstance(tool, str) and tool.strip() for tool in tools):
            raise BotRegistryError(f"{where} needs allowed_tools: a list of tool names")
        name = spec.get("name", bot_id)
        description = spec.get("description", "")
        if not isinstance(name, str) or not isinstance(description, str):
            raise BotRegistryError(f"{where}: name and description must be strings")
        try:
            registry[bot_id] = BotSpec(
                bot_id=bot_id,
                name=name,
                allowed_tools=frozenset(tool.strip() for tool in tools),
                description=description,
            )
        except ValueError as error:
            raise BotRegistryError(f"{where}: {error}") from error
    return registry
