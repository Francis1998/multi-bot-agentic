"""Structured bot-to-bot handoff receipts for multi-bot audit trails.

Records from_bot / to_bot / summary / artifacts / timestamp without network I/O.
Distinct from the typed ``HANDOFF:bot_id:summary`` decision directive in the
runner — this is a durable receipt store for post-hoc audit. Fills a
CrewAI/AutoGen handoff-audit gap and suits GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 multi-bot loops.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class BotHandoffReceipt:
    """Immutable record of one bot-to-bot handoff.

    Attributes:
        receipt_id: Stable unique identifier for this receipt.
        from_bot: Source bot identifier.
        to_bot: Destination bot identifier.
        summary: Short human-readable handoff summary.
        artifacts: Opaque artifact map (copied at issue time).
        timestamp_iso: UTC ISO-8601 timestamp when the receipt was issued.
    """

    receipt_id: str
    from_bot: str
    to_bot: str
    summary: str
    artifacts: Mapping[str, Any]
    timestamp_iso: str


class BotHandoffReceiptStore:
    """In-memory store for bot handoff receipts.

    Caller-driven v1: issue receipts when swapping bots; list by bot for audit.
    Never performs network I/O.
    """

    def __init__(self) -> None:
        self._receipts: list[BotHandoffReceipt] = []

    def issue(
        self,
        *,
        from_bot: str,
        to_bot: str,
        summary: str,
        artifacts: Mapping[str, Any] | None = None,
        timestamp_iso: str | None = None,
    ) -> BotHandoffReceipt:
        """Create and store a handoff receipt.

        Args:
            from_bot: Source bot id (non-empty).
            to_bot: Destination bot id (non-empty).
            summary: Handoff summary (non-empty).
            artifacts: Optional artifact dict; stored as a shallow copy.
            timestamp_iso: Optional UTC ISO timestamp; defaults to now.

        Returns:
            Newly issued BotHandoffReceipt.

        Raises:
            ValueError: When required string fields are empty.
            TypeError: When artifacts is not a mapping.
        """

        if not from_bot.strip():
            raise ValueError("from_bot must be non-empty")
        if not to_bot.strip():
            raise ValueError("to_bot must be non-empty")
        if not summary.strip():
            raise ValueError("summary must be non-empty")
        if artifacts is None:
            art: dict[str, Any] = {}
        else:
            if not isinstance(artifacts, Mapping):
                raise TypeError("artifacts must be a mapping")
            art = dict(artifacts)
        ts = timestamp_iso or datetime.now(timezone.utc).isoformat()
        receipt = BotHandoffReceipt(
            receipt_id=str(uuid4()),
            from_bot=from_bot.strip(),
            to_bot=to_bot.strip(),
            summary=summary.strip(),
            artifacts=art,
            timestamp_iso=ts,
        )
        self._receipts.append(receipt)
        return receipt

    def list_for(self, bot_id: str) -> list[BotHandoffReceipt]:
        """Return receipts where ``bot_id`` is from_bot or to_bot (issue order).

        Args:
            bot_id: Bot identifier to match.

        Returns:
            List of matching receipts in insertion order.

        Raises:
            ValueError: When ``bot_id`` is empty.
        """

        if not bot_id.strip():
            raise ValueError("bot_id must be non-empty")
        key = bot_id.strip()
        return [r for r in self._receipts if r.from_bot == key or r.to_bot == key]
