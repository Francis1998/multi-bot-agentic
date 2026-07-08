# Use Case: Replay timelines must not leak provider metadata as an action target

**Issue:** #010
**Repository:** multi-bot-agentic

## Problem

The `replay --format text` command renders each event as a compact timeline
row. For `action_result` events it tried to show the acting tool:

```python
target = event.payload.get("tool", event.payload.get("metadata", {}))
detail = f" kind={event.payload.get('kind')} target={target}"
```

Only tool action results carry a `tool` key. An `llm` action result has no
`tool`, so the lookup fell back to the whole `metadata` dictionary and rendered
model internals into the human-readable timeline:

```text
007 acting     action_result kind=llm target={'model': 'gpt-5.5'}
```

The `target=` field is meant to identify the acting tool, not to dump provider
metadata, so llm rows were noisy and misleading during an audit.

## How this agent solves it

`format_event_text` now surfaces the action `kind` for every action result and
only appends `target=<tool>` when a named `tool` is present:

```text
007 acting     action_result kind=llm
008 acting     action_result kind=tool target=checklist
```

The machine-readable `replay --format json` and `report` outputs are unchanged;
they already carried the full payload for programmatic consumers.

## Agentic design elements

| Component | Role |
|-----------|------|
| Event log | Remains the durable, complete audit record (JSON payload intact) |
| Replay (text) | Presents a clean per-step timeline for human review |
| Decision engine | Its `kind`/`target` semantics are reflected faithfully in the row |

## Try it

```bash
pytest tests/test_cli.py::test_format_event_text_omits_metadata_dump_for_llm_action_result -q
```
