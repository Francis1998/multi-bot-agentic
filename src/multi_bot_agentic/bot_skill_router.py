"""Bot skill-tag router for multi-bot task assignment.

Routes a task text to the best ``bot_id`` by overlapping skill tags with
tokenized task words. Distinct from ``StickyBotAffinityStore`` (session→bot
pins) and ``BotVoteConsensusAggregator`` (post-answer voting) — this is a
thin, stdlib-only skill-tag router for GPT-5.5 / Claude Sonnet 4.6 /
Gemini 3.x / Kimi K2 multi-bot crews. Fills a gap vs AutoGen/CrewAI/LangGraph/
Semantic Kernel, which often hand-wire agent selection or use sticky roles
without an explicit tag-overlap ranked router.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotSkillRegistration:
    """Immutable bot registration with skill tags.

    Attributes:
        bot_id: Bot identifier.
        skill_tags: Normalized lowercase skill tags.
    """

    bot_id: str
    skill_tags: frozenset[str]


@dataclass(frozen=True)
class BotSkillMatch:
    """One ranked routing match.

    Attributes:
        bot_id: Matched bot.
        score: Number of overlapping skill tags with the task.
        matched_tags: Tags that overlapped.
    """

    bot_id: str
    score: int
    matched_tags: frozenset[str]


@dataclass(frozen=True)
class BotSkillRouteResult:
    """Result of routing a task to registered bots.

    Attributes:
        task_text: Original task text.
        winner_bot_id: Top-scoring bot, or None when no overlap.
        matches: Ranked matches (score desc, then bot_id asc); zeros omitted.
    """

    task_text: str
    winner_bot_id: str | None
    matches: tuple[BotSkillMatch, ...]


class BotSkillTagRouter:
    """Route tasks to bots by skill-tag overlap ranking.

    Caller-driven v1: ``register`` bots with skill tags, ``route`` a task
    string to ranked matches / winner, ``unregister`` when a bot leaves.
    Never performs network I/O.
    """

    def __init__(self) -> None:
        self._bots: dict[str, frozenset[str]] = {}

    def register(self, bot_id: str, skill_tags: list[str] | tuple[str, ...] | set[str]) -> BotSkillRegistration:
        """Register or replace ``bot_id`` with ``skill_tags``.

        Args:
            bot_id: Bot identifier (non-empty).
            skill_tags: Non-empty iterable of non-empty skill tag strings.

        Returns:
            BotSkillRegistration with normalized tags.

        Raises:
            ValueError: When ``bot_id`` is empty, tags are empty, or any tag
                is empty after strip/casefold.
        """

        bid = self._require_id(bot_id, "bot_id")
        tags = self._normalize_tags(skill_tags)
        self._bots[bid] = tags
        return BotSkillRegistration(bot_id=bid, skill_tags=tags)

    def unregister(self, bot_id: str) -> bool:
        """Remove a prior registration for ``bot_id``.

        Args:
            bot_id: Bot identifier (non-empty).

        Returns:
            True when a registration was removed; False on miss.

        Raises:
            ValueError: When ``bot_id`` is empty.
        """

        bid = self._require_id(bot_id, "bot_id")
        return self._bots.pop(bid, None) is not None

    def registered(self) -> tuple[BotSkillRegistration, ...]:
        """Return all registrations sorted by ``bot_id``."""

        return tuple(BotSkillRegistration(bot_id=bid, skill_tags=tags) for bid, tags in sorted(self._bots.items()))

    def route(self, task_text: str) -> BotSkillRouteResult:
        """Rank bots by skill-tag overlap with tokenized ``task_text``.

        Tokens are whitespace-split, stripped, and casefolded. Overlap score
        is the size of the intersection between bot tags and task tokens.
        Matches with score 0 are omitted. Ties break by ``bot_id`` ascending.

        Args:
            task_text: Task description (non-empty).

        Returns:
            BotSkillRouteResult with ranked matches and optional winner.

        Raises:
            ValueError: When ``task_text`` is empty.
        """

        text = task_text.strip()
        if not text:
            raise ValueError("task_text must be non-empty")
        tokens = frozenset(part.casefold() for part in text.split() if part.strip())
        matches: list[BotSkillMatch] = []
        for bid, tags in self._bots.items():
            overlap = tags & tokens
            if not overlap:
                continue
            matches.append(BotSkillMatch(bot_id=bid, score=len(overlap), matched_tags=overlap))
        matches.sort(key=lambda m: (-m.score, m.bot_id))
        winner = matches[0].bot_id if matches else None
        return BotSkillRouteResult(
            task_text=text,
            winner_bot_id=winner,
            matches=tuple(matches),
        )

    @staticmethod
    def _normalize_tags(skill_tags: list[str] | tuple[str, ...] | set[str]) -> frozenset[str]:
        if not skill_tags:
            raise ValueError("skill_tags must be non-empty")
        normalized: set[str] = set()
        for tag in skill_tags:
            stripped = tag.strip().casefold()
            if not stripped:
                raise ValueError("skill tags must be non-empty")
            normalized.add(stripped)
        if not normalized:
            raise ValueError("skill_tags must be non-empty")
        return frozenset(normalized)

    @staticmethod
    def _require_id(value: str, label: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{label} must be non-empty")
        return stripped
