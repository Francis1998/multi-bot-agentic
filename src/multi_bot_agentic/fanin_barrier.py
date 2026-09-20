"""Fan-in barrier gate for multi-bot result aggregation.

Waits until N distinct bot results arrive for a barrier id before releasing.
Distinct from ``BotVoteConsensusAggregator`` (vote tally) and
``PlanStepDependencyResolver`` (DAG ordering). Fills a gap vs AutoGen /
CrewAI / LangGraph fan-in barriers that are often implicit. Works with
GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FanInBarrierStatus:
    """Status of a fan-in barrier.

    Attributes:
        barrier_id: Barrier identifier.
        required: Number of distinct bot arrivals required.
        arrived: Sorted bot ids that have arrived.
        count: Number of arrivals.
        released: True when count >= required.
        mode: ``advisory`` or ``hard``.
        allowed: True when released, or always in advisory when not released.
    """

    barrier_id: str
    required: int
    arrived: tuple[str, ...]
    count: int
    released: bool
    mode: str
    allowed: bool


class FanInBarrierGate:
    """Collect bot arrivals until a fan-in quorum is reached."""

    def __init__(self, *, required: int = 2, mode: str = "hard") -> None:
        """Create a fan-in barrier.

        Args:
            required: Distinct bot arrivals needed (must be >= 1).
            mode: ``hard`` blocks until released; ``advisory`` always allows.

        Raises:
            ValueError: On invalid required/mode.
        """

        if required < 1:
            raise ValueError("required must be >= 1")
        if mode not in {"advisory", "hard"}:
            raise ValueError("mode must be 'advisory' or 'hard'")
        self._required = int(required)
        self._mode = mode
        self._arrived: dict[str, set[str]] = {}

    @property
    def required(self) -> int:
        """Return required arrival count."""

        return self._required

    def arrive(self, barrier_id: str, bot_id: str) -> FanInBarrierStatus:
        """Record a bot arrival and return barrier status.

        Args:
            barrier_id: Non-empty barrier id.
            bot_id: Non-empty bot id.

        Returns:
            FanInBarrierStatus after this arrival.
        """

        bid = barrier_id.strip()
        bot = bot_id.strip()
        if not bid:
            raise ValueError("barrier_id must be non-empty")
        if not bot:
            raise ValueError("bot_id must be non-empty")
        holders = self._arrived.setdefault(bid, set())
        holders.add(bot)
        return self.status(bid)

    def status(self, barrier_id: str) -> FanInBarrierStatus:
        """Return current barrier status without mutating state."""

        bid = barrier_id.strip()
        if not bid:
            raise ValueError("barrier_id must be non-empty")
        arrived = tuple(sorted(self._arrived.get(bid, set())))
        count = len(arrived)
        released = count >= self._required
        allowed = bool(released or self._mode == "advisory")
        return FanInBarrierStatus(
            barrier_id=bid,
            required=self._required,
            arrived=arrived,
            count=count,
            released=released,
            mode=self._mode,
            allowed=allowed,
        )

    def reset(self, barrier_id: str) -> None:
        """Clear arrivals for ``barrier_id``."""

        bid = barrier_id.strip()
        if not bid:
            raise ValueError("barrier_id must be non-empty")
        self._arrived.pop(bid, None)
