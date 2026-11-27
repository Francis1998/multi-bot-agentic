"""Claude Code CLI adapter."""

from __future__ import annotations

import json
import shlex
import subprocess
from typing import Any

from multi_bot_agentic.llm.base import BilledCallError, render_output_contract, render_tool_catalog
from multi_bot_agentic.models import ModelOutput, ModelRequest, Usage
from multi_bot_agentic.usage import parse_anthropic_usage

# Print mode (-p) is Claude Code's non-interactive mode: it reads the prompt from stdin,
# prints the reply, and exits. Plain ``claude`` would start an interactive session.
DEFAULT_CLAUDE_CODE_COMMAND = "claude -p"


class ClaudeCodeCLIAdapter:
    """Adapter that consumes output from a local Claude Code CLI command.

    The prompt is written to the command's stdin, so the command must run Claude Code
    non-interactively (print mode, ``-p``), e.g. ``claude -p --model claude-opus-5-5``. Add
    ``--output-format json`` to record the call's token usage and Claude Code's own cost estimate
    (``total_cost_usd``); plain-text output carries no usage.
    """

    provider_name = "claude_code"

    def __init__(self, command: str) -> None:
        """Initialize the adapter.

        Args:
            command: Shell-like command string, parsed with shlex and executed without a shell.
        """

        self.command = command

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        """Run Claude Code and normalize its reply (and, for JSON output, usage and cost).

        Args:
            request: Normalized model request.
            timeout_seconds: Provider timeout budget.

        Returns:
            Normalized model output.

        Raises:
            BilledCallError: If Claude Code failed (nonzero exit or an error result) but reported usage or cost.
            RuntimeError: If Claude Code timed out or failed without reporting usage.
        """

        command = shlex.split(self.command)
        if not command:
            raise ValueError("Claude Code command cannot be empty")
        try:
            completed = subprocess.run(
                command,
                input=_render_prompt(request),
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"Claude Code timed out after {timeout_seconds}s: {command[0]}") from error
        result = _json_result(completed.stdout)
        usage, model, cost = _accounting(result) if result is not None else (None, None, None)
        failure: str | None = None
        if completed.returncode != 0:
            failure = f"Claude Code exited with {completed.returncode}: {completed.stderr.strip()}"
        elif result is not None and result.get("is_error") is True:
            failure = f"Claude Code reported an error result: {result.get('subtype') or 'error'}"
        if failure is not None:
            # Error results still carry the usage and cost of what ran, so the call may be billed.
            if usage is not None or cost is not None:
                raise BilledCallError(failure, usage=usage, model=model, cost_usd=cost)
            raise RuntimeError(failure)
        raw: dict[str, Any] = {"command": command[0], "returncode": completed.returncode}
        if result is None:
            return ModelOutput(
                provider=self.provider_name,
                text=completed.stdout.strip()[: request.max_output_chars],
                raw=raw,
            )
        return ModelOutput(
            provider=self.provider_name,
            text=str(result.get("result", "")).strip()[: request.max_output_chars],
            raw=raw | {"output_format": "json"},
            usage=usage,
            model=model,
            cost_usd=cost,
        )


def _json_result(stdout: str) -> dict[str, Any] | None:
    """Return the result object Claude Code prints with ``--output-format json``, else ``None``."""

    text = stdout.strip()
    if not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("type") != "result":
        return None
    return payload


def _accounting(result: dict[str, Any]) -> tuple[Usage | None, str | None, float | None]:
    """Return the usage, the model (when exactly one ran), and the cost a JSON result reports."""

    models = result.get("modelUsage")
    model_names = sorted(name for name in models if isinstance(name, str)) if isinstance(models, dict) else []
    cost = result.get("total_cost_usd")
    return (
        _model_usage(models) or parse_anthropic_usage(result.get("usage")),
        model_names[0] if len(model_names) == 1 else None,
        float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None,
    )


def _model_usage(models: Any) -> Usage | None:
    """Sum the per-model ``modelUsage`` counts, which (unlike ``usage``) include subagents.

    Each entry reports ``inputTokens`` without cache reads and writes, so ``cacheReadInputTokens``
    and ``cacheCreationInputTokens`` are added to the input; cache reads are the cached tokens.
    """

    if not isinstance(models, dict) or not models:
        return None
    input_tokens = output_tokens = cached = 0
    for entry in models.values():
        counts = (
            {
                "input_tokens": entry.get("inputTokens"),
                "output_tokens": entry.get("outputTokens"),
                "cache_read_input_tokens": entry.get("cacheReadInputTokens"),
                "cache_creation_input_tokens": entry.get("cacheCreationInputTokens"),
            }
            if isinstance(entry, dict)
            else None
        )
        usage = parse_anthropic_usage(counts)
        if usage is None or usage.input_tokens is None or usage.output_tokens is None:
            return None
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens
        cached += usage.cached_input_tokens or 0
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached,
        total_tokens=input_tokens + output_tokens,
    )


def _render_prompt(request: ModelRequest) -> str:
    """Render stdin prompt for Claude Code.

    Args:
        request: Normalized model request.

    Returns:
        Prompt string.
    """

    observations = "\n".join(f"- {observation.source}: {observation.content}" for observation in request.observations)
    return (
        "Return concise text. Use TOOL:echo:<text> when a safe echo tool is useful. "
        "Use DONE:<answer> when finished.\n\n"
        f"Goal: {request.goal}\n\nObservations:\n{observations}{render_tool_catalog(request.tools)}"
        f"{render_output_contract(request.output_schema)}\n"
    )
