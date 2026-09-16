"""Tests for BotSkillTagRouter."""

from __future__ import annotations

import pytest

from multi_bot_agentic.bot_skill_router import BotSkillTagRouter


def test_route_picks_highest_overlap_winner() -> None:
    """Winner is the bot with the most overlapping skill tags."""

    router = BotSkillTagRouter()
    router.register("research", ["research", "search", "docs"])
    router.register("code", ["code", "python", "refactor"])
    result = router.route("please research docs for the API")
    assert result.winner_bot_id == "research"
    assert result.matches[0].score == 2
    assert result.matches[0].matched_tags == frozenset({"research", "docs"})


def test_route_ranks_multiple_matches() -> None:
    """Matches are ranked by score desc then bot_id asc."""

    router = BotSkillTagRouter()
    router.register("alpha", ["ops", "deploy"])
    router.register("beta", ["ops"])
    router.register("gamma", ["ops", "deploy", "k8s"])
    result = router.route("ops deploy k8s rollout")
    assert [m.bot_id for m in result.matches] == ["gamma", "alpha", "beta"]
    assert result.winner_bot_id == "gamma"
    assert result.matches[0].score == 3
    assert result.matches[1].score == 2
    assert result.matches[2].score == 1


def test_route_no_overlap_returns_empty() -> None:
    """No overlapping tags yields empty matches and null winner."""

    router = BotSkillTagRouter()
    router.register("code", ["python", "refactor"])
    result = router.route("schedule a meeting tomorrow")
    assert result.winner_bot_id is None
    assert result.matches == ()


def test_tie_breaks_by_bot_id() -> None:
    """Equal scores break ties by bot_id ascending."""

    router = BotSkillTagRouter()
    router.register("zeta", ["search"])
    router.register("alpha", ["search"])
    result = router.route("search the wiki")
    assert [m.bot_id for m in result.matches] == ["alpha", "zeta"]
    assert result.winner_bot_id == "alpha"


def test_unregister_and_reregister() -> None:
    """unregister removes a bot; register overwrites tags."""

    router = BotSkillTagRouter()
    router.register("bot", ["old"])
    assert router.unregister("bot") is True
    assert router.unregister("bot") is False
    router.register("bot", ["new", "skill"])
    result = router.route("new skill task")
    assert result.winner_bot_id == "bot"
    assert result.matches[0].score == 2


def test_registered_lists_sorted() -> None:
    """registered returns bots sorted by bot_id."""

    router = BotSkillTagRouter()
    router.register("b", ["x"])
    router.register("a", ["y"])
    regs = router.registered()
    assert [r.bot_id for r in regs] == ["a", "b"]


def test_rejects_empty_inputs() -> None:
    """Empty bot_id, tags, or task_text raise ValueError."""

    router = BotSkillTagRouter()
    with pytest.raises(ValueError, match="bot_id"):
        router.register("  ", ["a"])
    with pytest.raises(ValueError, match="skill_tags"):
        router.register("bot", [])
    with pytest.raises(ValueError, match="skill tags"):
        router.register("bot", ["  "])
    with pytest.raises(ValueError, match="task_text"):
        router.route(" ")
    with pytest.raises(ValueError, match="bot_id"):
        router.unregister("")


def test_tags_are_casefolded() -> None:
    """Skill tags and task tokens match case-insensitively."""

    router = BotSkillTagRouter()
    router.register("BotA", ["Research", "CSV"])
    result = router.route("Please RESEARCH the csv file")
    assert result.winner_bot_id == "BotA"
    assert result.matches[0].matched_tags == frozenset({"research", "csv"})
