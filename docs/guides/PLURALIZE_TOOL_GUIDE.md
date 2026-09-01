# pluralize Tool Guide

![pluralize demo](../../assets/demo/pluralize.gif)

Pluralize or singularize an English word before the next GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 turn.

## Why

Agent pipelines need deterministic English plurals for labels and counts. Models invent irregular forms. Inspired by text utilities in LangChain/crewAI toolkits that rarely ship a focused pluralize tool.

## Usage

```python
tool.execute(
    ToolInvocation(
        tool_name="pluralize",
        arguments={"text": "child", "mode": "pluralize"},
    )
)
```

## Bounds & Safety

- Max text 2000 chars; single word only
- Modes: `pluralize` (default) or `singularize`
- Common irregulars included
- Never executes code or makes network requests
