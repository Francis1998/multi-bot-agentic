"""Tests for the deterministic template rendering tool."""

from __future__ import annotations

from pathlib import Path

from multi_bot_agentic.event_log import SQLiteEventLog
from multi_bot_agentic.models import EventType, ModelOutput, ModelRequest, RunState, ToolInvocation
from multi_bot_agentic.runner import AgentRunner, build_default_tools
from multi_bot_agentic.safety import SafetyPolicy
from multi_bot_agentic.tools.template_render import TemplateRenderTool


def _run(**arguments: object) -> tuple[bool, str, dict[str, object]]:
    """Execute the template_render tool with the given arguments.

    Args:
        **arguments: Tool arguments (``template`` + ``variables``, or sentinel ``text``).

    Returns:
        Tuple of ``(ok, content, metadata)`` from the tool result.
    """

    result = TemplateRenderTool().execute(ToolInvocation(tool_name="template_render", arguments=dict(arguments)))
    return result.ok, result.content, result.metadata


def test_template_render_substitutes_and_escapes_values() -> None:
    """Simple ``{var}`` placeholders render with HTML-escaped values."""

    ok, content, metadata = _run(
        template="<p>Hello {name}, status: {status}</p>",
        variables={"name": "Ada <admin>", "status": '"ready" & safe'},
    )

    assert ok is True
    assert content == "<p>Hello Ada &lt;admin&gt;, status: &quot;ready&quot; &amp; safe</p>"
    assert metadata["escaped"] is True
    assert metadata["placeholder_count"] == 2
    assert metadata["unique_placeholders"] == ["name", "status"]


def test_template_render_accepts_jinja_like_placeholders() -> None:
    """Jinja-like ``{{ var }}`` placeholders are supported without expression eval."""

    ok, content, _metadata = _run(
        template="Ticket {{ ticket_id }} assigned={{ assigned }} count={{ count }}",
        variables={"ticket_id": "ABC-42", "assigned": True, "count": 3},
    )

    assert ok is True
    assert content == "Ticket ABC-42 assigned=true count=3"


def test_template_render_accepts_sentinel_json_payload() -> None:
    """A single text payload can embed variables as JSON after the sentinel."""

    ok, content, metadata = _run(text='Hello {name}!<<<TEMPLATE_VARS>>>{"name":"Grace & Hopper"}')

    assert ok is True
    assert content == "Hello Grace &amp; Hopper!"
    assert metadata["chars"] == len(content)


def test_template_render_rejects_unknown_placeholders() -> None:
    """Missing variables are structured failures instead of partial renders."""

    ok, content, metadata = _run(template="Hello {name} from {city}", variables={"name": "Ada"})

    assert ok is False
    assert "missing variable: city" in content
    assert metadata["missing"] == "city"


def test_template_render_rejects_expression_syntax() -> None:
    """Attribute access or filters are rejected; placeholders are names only."""

    ok, content, _metadata = _run(template="Unsafe {{ user.__class__ }}", variables={"user": "Ada"})

    assert ok is False
    assert "unsupported brace syntax" in content


def test_template_render_rejects_nested_variable_values() -> None:
    """Only scalar JSON values may be substituted."""

    ok, content, _metadata = _run(template="Hello {user}", variables={"user": {"name": "Ada"}})

    assert ok is False
    assert "must be a string, number, boolean, or null" in content


def test_template_render_bounds_output_size() -> None:
    """Rendered output above the cap returns a structured failure."""

    ok, content, metadata = _run(template="{chunk}" * 11, variables={"chunk": "x" * 4_000})

    assert ok is False
    assert "rendered output exceeds max_chars" in content
    assert metadata["chars"] == 44_000


def test_template_render_is_registered_in_default_tools() -> None:
    """The template_render tool is wired into the default allowlisted registry."""

    tools = build_default_tools(root=Path.cwd())
    assert "template_render" in tools
    assert tools["template_render"].name == "template_render"
    assert "template_render" in SafetyPolicy().allowed_tools


def test_runner_executes_template_render_tool(tmp_path: Path) -> None:
    """A model-suggested template_render directive runs end-to-end through the runner."""

    class TemplateProvider:
        """Provider that requests template rendering, then finishes from the tool result."""

        provider_name = "fake"

        def complete(self, request: ModelRequest, timeout_seconds: float) -> ModelOutput:
            del timeout_seconds
            tool_results = [
                observation for observation in request.observations if observation.source == "tool:template_render"
            ]
            if not tool_results:
                return ModelOutput(
                    provider=self.provider_name,
                    text='TOOL:template_render:  Hello {name}!  <<<TEMPLATE_VARS>>>{"name":"Ada & Lovelace"}',
                    raw={"mode": "template-request"},
                )
            return ModelOutput(
                provider=self.provider_name,
                text=f"DONE: {tool_results[-1].content}",
                raw={"mode": "template-done"},
            )

    log = SQLiteEventLog(tmp_path / "runs.sqlite")
    try:
        runner = AgentRunner(
            provider=TemplateProvider(),
            event_log=log,
            tools=build_default_tools(root=tmp_path),
            safety_policy=SafetyPolicy(max_steps=4),
        )
        result = runner.run("Render the greeting", run_id="run-template-render")
        events = log.list_events("run-template-render")
    finally:
        log.close()

    assert result.state == RunState.SUCCEEDED
    assert result.answer == "Hello Ada &amp; Lovelace!"
    tool_events = [
        event
        for event in events
        if event.event_type == EventType.ACTION_RESULT.value and event.payload.get("tool") == "template_render"
    ]
    assert tool_events
    assert tool_events[0].payload["ok"] is True
    assert tool_events[0].payload["content"] == "  Hello Ada &amp; Lovelace!  "
