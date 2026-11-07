"""Claude Code CLI adapter."""

from __future__ import annotations

import shlex
import subprocess

from multi_bot_agentic.llm.base import render_tool_catalog
from multi_bot_agentic.models import ModelOutput, ModelRequest

# Print mode (-p) is Claude Code's non-interactive mode: it reads the prompt from stdin,
# prints the reply, and exits. Plain ``claude`` would start an interactive session.
DEFAULT_CLAUDE_CODE_COMMAND = "claude -p"


class ClaudeCodeCLIAdapter:
    """Adapter that consumes output from a local Claude Code CLI command.

    The prompt is written to the command's stdin, so the command must run Claude Code
    non-interactively (print mode, ``-p``), e.g. ``claude -p --model claude-opus-5-5``.
    """

    provider_name = "claude_code"

    def __init__(self, command: str) -> None:
        """Initialize the adapter.

        Args:
            command: Shell-like command string, parsed with shlex and executed without a shell.
        """

        self.command = command

    def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
        """Run Claude Code and normalize stdout.

        Args:
            request: Normalized model request.
            timeout_seconds: Provider timeout budget.

        Returns:
            Normalized model output.
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
        if completed.returncode != 0:
            raise RuntimeError(f"Claude Code exited with {completed.returncode}: {completed.stderr.strip()}")
        return ModelOutput(
            provider=self.provider_name,
            text=completed.stdout.strip()[: request.max_output_chars],
            raw={"command": command[0], "returncode": completed.returncode},
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
        f"Goal: {request.goal}\n\nObservations:\n{observations}{render_tool_catalog(request.tools)}\n"
    )
