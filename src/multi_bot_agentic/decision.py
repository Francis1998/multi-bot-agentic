"""Deterministic decision engine for Observe -> Decide -> Act runs."""

from __future__ import annotations

from dataclasses import dataclass

from multi_bot_agentic.models import Decision, Observation, RationaleTrace
from multi_bot_agentic.safety import SafetyPolicy


@dataclass(frozen=True)
class DeterministicDecisionEngine:
    """Rule-based decision engine with rationale traces."""

    provider_name: str

    def decide(
        self,
        observations: tuple[Observation, ...],
        step: int,
        policy: SafetyPolicy,
    ) -> Decision:
        """Select the next action from observations and policy.

        Args:
            observations: Current observations.
            step: Zero-based loop step.
            policy: Safety policy.

        Returns:
            Deterministic decision with rationale trace.
        """

        if policy.is_cancelled():
            return Decision(
                action="cancel",
                target=None,
                payload={"reason": "cancellation file exists"},
                rationale=RationaleTrace(
                    rule_id="safety.cancel-file",
                    observations_used=(),
                    rejected_actions=("call_llm", "call_tool", "finish"),
                    explanation="Cancellation file exists before the next action.",
                ),
            )

        latest_observation = observations[-1]
        if step >= policy.max_steps - 1:
            return Decision(
                action="finish",
                target=None,
                payload={"answer": latest_observation.content.removeprefix("DONE:").strip()},
                rationale=RationaleTrace(
                    rule_id="model.done-or-budget",
                    observations_used=(latest_observation.observation_id,),
                    rejected_actions=("call_llm", "call_tool"),
                    explanation="The step budget is exhausted, so the run finishes with the latest observation.",
                ),
            )

        if latest_observation.source.startswith("tool:"):
            return Decision(
                action="call_llm",
                target=self.provider_name,
                payload={"reason": "tool result needs model synthesis"},
                rationale=RationaleTrace(
                    rule_id="tool.result-needs-synthesis",
                    observations_used=(latest_observation.observation_id,),
                    rejected_actions=("call_tool", "finish"),
                    explanation="The latest observation is a tool result, so the provider must consume it.",
                ),
            )

        latest_model_output = _latest_observation_by_prefix(observations, "llm:")
        if latest_model_output is None:
            return Decision(
                action="call_llm",
                target=self.provider_name,
                payload={"reason": "no model output observed yet"},
                rationale=RationaleTrace(
                    rule_id="observe.no-model-output",
                    observations_used=tuple(observation.observation_id for observation in observations),
                    rejected_actions=("call_tool", "finish"),
                    explanation="The run has a user goal but no provider output, so it must ask a model.",
                ),
            )

        if latest_model_output.content.startswith("TOOL:"):
            parsed_tool_request = _parse_tool_request(latest_model_output.content)
            if parsed_tool_request is None:
                return Decision(
                    action="call_llm",
                    target=self.provider_name,
                    payload={"reason": "malformed tool request"},
                    rationale=RationaleTrace(
                        rule_id="model.malformed-tool-request",
                        observations_used=(latest_model_output.observation_id,),
                        rejected_actions=("finish", "call_tool"),
                        explanation="The latest provider output requested a tool without a valid payload.",
                    ),
                )
            tool_name, text = parsed_tool_request
            if tool_name not in policy.allowed_tools:
                return Decision(
                    action="call_llm",
                    target=self.provider_name,
                    payload={"reason": f"requested tool is not allowlisted: {tool_name}"},
                    rationale=RationaleTrace(
                        rule_id="model.disallowed-tool-request",
                        observations_used=(latest_model_output.observation_id,),
                        rejected_actions=("finish", "call_tool"),
                        explanation=(
                            "The provider requested a tool outside the safety allowlist, "
                            "so the run asks for a corrected action instead of failing."
                        ),
                    ),
                )
            return Decision(
                action="call_tool",
                target=tool_name,
                payload={"text": text},
                rationale=RationaleTrace(
                    rule_id="model.requested-tool",
                    observations_used=(latest_model_output.observation_id,),
                    rejected_actions=("finish", "call_llm"),
                    explanation="The latest model output requested an allowlisted tool action.",
                ),
            )

        if latest_model_output.content.startswith("DONE:"):
            return Decision(
                action="finish",
                target=None,
                payload={"answer": latest_model_output.content.removeprefix("DONE:").strip()},
                rationale=RationaleTrace(
                    rule_id="model.done-or-budget",
                    observations_used=(latest_model_output.observation_id,),
                    rejected_actions=("call_llm", "call_tool"),
                    explanation="The model indicated completion or the step budget is exhausted.",
                ),
            )

        return Decision(
            action="call_llm",
            target=self.provider_name,
            payload={"reason": "need another provider turn"},
            rationale=RationaleTrace(
                rule_id="model.needs-followup",
                observations_used=(latest_model_output.observation_id,),
                rejected_actions=("finish", "call_tool"),
                explanation="The latest provider output is neither a tool request nor a final answer.",
            ),
        )


def _latest_observation_by_prefix(
    observations: tuple[Observation, ...],
    source_prefix: str,
) -> Observation | None:
    """Return the latest observation whose source has a prefix.

    Args:
        observations: Observations to scan.
        source_prefix: Source prefix.

    Returns:
        Latest matching observation or None.
    """

    for observation in reversed(observations):
        if observation.source.startswith(source_prefix):
            return observation
    return None


def _parse_tool_request(content: str) -> tuple[str, str] | None:
    """Parse a `TOOL:name:payload` model output.

    Args:
        content: Model output text.

    Returns:
        Tool name and payload text, or None when the directive is malformed.
    """

    parts = content.split(":", maxsplit=2)
    if len(parts) != 3:
        return None

    _, tool_name, text = parts
    tool_name = tool_name.strip()
    text = text.strip()
    if not tool_name or not text:
        return None
    return tool_name, text
