"""Topological plan-step dependency resolver for multi-bot plans.

Resolves an ordered execution list from step ids + dependency edges.
Distinct from ``BudgetedStepPlanner`` (token/cost caps) and
``SpeculativeToolPrefetch`` (next-tool ranking). Fills a gap vs AutoGen /
CrewAI / LangGraph DAG planners that bury dependency order in graph runtimes.
Works with GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. Never performs
network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanStep:
    """One plan step with upstream dependencies.

    Attributes:
        step_id: Unique step identifier.
        depends_on: Upstream step ids that must complete first.
    """

    step_id: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanOrderResult:
    """Result of a dependency resolve attempt.

    Attributes:
        order: Topological order when acyclic; empty on cycle/error.
        cyclic: True when a dependency cycle was detected.
        missing_deps: Declared dependency ids not present in the plan.
        ok: True when a full order was produced.
    """

    order: tuple[str, ...]
    cyclic: bool
    missing_deps: tuple[str, ...]
    ok: bool


class PlanStepDependencyResolver:
    """Resolve plan steps into a deterministic topological order."""

    def resolve(self, steps: list[PlanStep]) -> PlanOrderResult:
        """Return a stable topological order for ``steps``.

        Args:
            steps: Plan steps (unique ``step_id`` values required).

        Returns:
            PlanOrderResult. Empty input yields ``ok=True`` with empty order.

        Raises:
            ValueError: On duplicate step ids or empty step_id.
        """

        if not steps:
            return PlanOrderResult(order=(), cyclic=False, missing_deps=(), ok=True)

        ids: list[str] = []
        deps: dict[str, set[str]] = {}
        seen: set[str] = set()
        for step in steps:
            sid = step.step_id.strip()
            if not sid:
                raise ValueError("step_id must be non-empty")
            if sid in seen:
                raise ValueError(f"duplicate step_id: {sid}")
            seen.add(sid)
            ids.append(sid)
            deps[sid] = {d.strip() for d in step.depends_on if d.strip()}

        missing: list[str] = []
        for _sid, dep_set in deps.items():
            for dep in sorted(dep_set):
                if dep not in seen:
                    missing.append(dep)
        missing_t = tuple(sorted(set(missing)))
        if missing_t:
            return PlanOrderResult(order=(), cyclic=False, missing_deps=missing_t, ok=False)

        # Kahn's algorithm with stable tie-break by original declaration order.
        index = {sid: i for i, sid in enumerate(ids)}
        indeg = dict.fromkeys(ids, 0)
        children: dict[str, list[str]] = {sid: [] for sid in ids}
        for _sid, dep_set in deps.items():
            for dep in dep_set:
                children[dep].append(sid)
                indeg[sid] += 1
        ready = sorted([sid for sid, n in indeg.items() if n == 0], key=lambda s: index[s])
        order: list[str] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for child in sorted(children[node], key=lambda s: index[s]):
                indeg[child] -= 1
                if indeg[child] == 0:
                    ready.append(child)
                    ready.sort(key=lambda s: index[s])
        if len(order) != len(ids):
            return PlanOrderResult(order=(), cyclic=True, missing_deps=(), ok=False)
        return PlanOrderResult(order=tuple(order), cyclic=False, missing_deps=(), ok=True)
